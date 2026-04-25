"""Validações estatísticas inspiradas em práticas de fundos sistemáticos (Renaissance/López de Prado).

Cada função retorna um dict padronizado com:
  - os valores calculados
  - `pass` / `fail` baseado em thresholds referenciados
  - nota explicativa
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats as sp


# ---------------------------------------------------------------- utilidades
def _returns_from_profits(profits: np.ndarray, initial: float = 10_000.0) -> np.ndarray:
    eq = initial + np.concatenate([[0.0], np.cumsum(profits)[:-1]])
    return profits / np.where(eq > 0, eq, initial)


# ---------------------------------------------------------------- t-test
def t_test_returns(returns: np.ndarray) -> dict[str, Any]:
    """t-test unilateral: média dos retornos é significativamente > 0?

    Simons/Renaissance: threshold interno estimado em t ≥ 2.5.
    Referência: Zuckerman (2019) + Bailey & López de Prado (2012).
    """
    n = len(returns)
    THRESHOLD = 2.5
    if n < 5:
        return {"t_stat": 0.0, "p_value": 1.0, "passed": False, "n": n, "threshold": THRESHOLD}
    result = sp.ttest_1samp(returns, popmean=0.0, alternative="greater")
    t_stat = float(result.statistic)
    p_value = float(result.pvalue)
    return {
        "t_stat": t_stat,
        "p_value": p_value,
        "passed": t_stat >= THRESHOLD and p_value < 0.05,
        "n": n,
        "threshold": THRESHOLD,
    }


# ---------------------------------------------------------------- Ljung-Box
def ljung_box(returns: np.ndarray, lags: int = 10) -> dict[str, Any]:
    """Ljung-Box: autocorrelação nos retornos?

    H0: retornos são não-correlacionados (o que é desejável — sem padrão
    serial explorado pelo modelo que possa desaparecer fora da amostra).
    p > 0.05 → sem autocorrelação → PASS.
    """
    n = len(returns)
    if n < lags + 5:
        return {"statistic": 0.0, "p_value": 1.0, "passed": True, "lags": lags, "acf_1": 0.0}
    r = returns - returns.mean()
    var = float(np.var(r, ddof=1))
    if var < 1e-12:
        return {"statistic": 0.0, "p_value": 1.0, "passed": True, "lags": lags, "acf_1": 0.0}

    # autocorrelações amostral para k = 0..lags
    acf = np.array([
        float(np.mean(r[k:] * r[:-k]) / var) if k > 0 else 1.0
        for k in range(lags + 1)
    ])

    # Q-statistic (Ljung-Box 1978)
    q = float(n * (n + 2) * sum(acf[k] ** 2 / (n - k) for k in range(1, lags + 1)))
    p_value = float(1 - sp.chi2.cdf(q, df=lags))

    return {
        "statistic": q,
        "p_value": p_value,
        "passed": p_value >= 0.05,   # True = não há autocorr = PASS
        "lags": lags,
        "acf_1": float(acf[1]),      # autocorr de lag-1 (mais informativa)
    }


# ---------------------------------------------------------------- Runs test
def runs_test(profits: np.ndarray) -> dict[str, Any]:
    """Wald-Wolfowitz: a sequência wins/losses é aleatória?

    Poucas runs = wins clusterizados em regime específico.
    Muitas runs = mean-reverting excessivo.
    p > 0.05 → sequência compatível com independência → PASS.
    """
    n = len(profits)
    if n < 10:
        return {"z_stat": 0.0, "p_value": 1.0, "passed": True, "runs": 0, "n_wins": 0}

    signs = (profits > 0).astype(int)
    n1 = int(signs.sum())   # wins
    n2 = n - n1              # losses + breakevens
    if n1 == 0 or n2 == 0:
        return {"z_stat": 0.0, "p_value": 1.0, "passed": True, "runs": n1 or n2, "n_wins": n1}

    runs = 1 + int(np.sum(np.diff(signs) != 0))
    exp = 2.0 * n1 * n2 / n + 1.0
    var = max(1e-12, 2.0 * n1 * n2 * (2.0 * n1 * n2 - n) / (n ** 2 * (n - 1)))
    z = (runs - exp) / math.sqrt(var)
    p = float(2.0 * (1.0 - sp.norm.cdf(abs(z))))

    return {
        "z_stat": z,
        "p_value": p,
        "passed": p >= 0.05,
        "runs": runs,
        "expected_runs": exp,
        "n_wins": n1,
        "n_losses": n2,
    }


# ---------------------------------------------------------------- Outlier dependency
def outlier_dependency(profits: np.ndarray, top_pct: float = 0.05) -> dict[str, Any]:
    """Remove os top_pct% melhores trades: ainda é lucrativo?

    Princípio Simons: estratégia robusta não depende de poucos trades outliers.
    Referência: Zuckerman (2019) — Simons descartava sistemas frágeis.
    """
    n = len(profits)
    if n < 10:
        return {"passed": True, "removed": 0, "net_original": float(profits.sum()),
                "net_without_top": float(profits.sum()), "pct_from_outliers": 0.0}

    k = max(1, int(n * top_pct))
    top_idx = np.argpartition(profits, -k)[-k:]
    mask = np.ones(n, dtype=bool)
    mask[top_idx] = False
    net_orig = float(profits.sum())
    net_without = float(profits[mask].sum())

    return {
        "passed": net_without > 0,
        "removed": k,
        "remove_pct": top_pct,
        "net_original": net_orig,
        "net_without_top": net_without,
        "pct_from_outliers": (net_orig - net_without) / abs(net_orig) if net_orig else 0.0,
    }


# ---------------------------------------------------------------- Tail ratio
def tail_ratio(returns: np.ndarray) -> dict[str, Any]:
    """P95 / |P5|: as caudas positivas são maiores que as negativas?

    > 1.0 = assimetria favorável (bom).
    Fundos sistemáticos buscam estratégias com retornos assimétricos à direita.
    """
    if len(returns) < 20:
        return {"tail_ratio": 1.0, "p5": 0.0, "p95": 0.0, "passed": True}
    p5 = float(np.percentile(returns, 5))
    p95 = float(np.percentile(returns, 95))
    ratio = abs(p95) / abs(p5) if abs(p5) > 1e-12 else (1.0 if p95 >= 0 else 0.0)
    return {"tail_ratio": ratio, "p5": p5, "p95": p95, "passed": ratio >= 1.0}


# ---------------------------------------------------------------- Jarque-Bera
def jarque_bera(returns: np.ndarray) -> dict[str, Any]:
    """JB: distribuição dos retornos se afasta da normal?

    Skewness > 0 = cauda direita longa (favorável para longs).
    Kurtosis > 0 = caudas gordas = risco de perda extrema subestimado.
    PASS se skewness > 0 (não rejeitamos normalidade por si só; queremos skew positivo).
    """
    n = len(returns)
    if n < 8:
        return {"statistic": 0.0, "p_value": 1.0, "skewness": 0.0,
                "excess_kurtosis": 0.0, "passed": True}
    jb_stat, p = sp.jarque_bera(returns)
    skew = float(sp.skew(returns))
    kurt = float(sp.kurtosis(returns, fisher=True))   # excess kurtosis
    return {
        "statistic": float(jb_stat),
        "p_value": float(p),
        "skewness": skew,
        "excess_kurtosis": kurt,
        "positive_skew": skew > 0,
        "fat_tails": kurt > 1.0,
        "passed": skew > 0,   # assimetria positiva é o que importa
    }


# ---------------------------------------------------------------- Variance Ratio (Lo-MacKinlay 1988)
def variance_ratio(returns: np.ndarray, q: int = 2) -> dict[str, Any]:
    """VR(q) test: retornos seguem random walk?

    VR ≈ 1 = retornos independentes (desejável em retornos de ESTRATÉGIA).
    VR << 1 = mean-reverting (suspeito: pode ser overfit ao passado).
    VR >> 1 = persistente (regime-dependente, pode explodir fora da amostra).
    p > 0.05 = não rejeita random walk = PASS.
    """
    n = len(returns)
    if n < 4 * q:
        return {"vr": 1.0, "z_stat": 0.0, "p_value": 1.0, "passed": True, "q": q}

    mu = float(returns.mean())
    var_1 = float(np.var(returns, ddof=1))
    if var_1 < 1e-14:
        return {"vr": 1.0, "z_stat": 0.0, "p_value": 1.0, "passed": True, "q": q}

    # Agregados de q períodos (com overlap para ganhar potência estatística)
    rolling = np.convolve(returns, np.ones(q), mode="valid")
    var_q = float(np.var(rolling, ddof=1)) / q

    vr = var_q / var_1
    # Lo-MacKinlay homoskedastic asymptotic variance of (VR-1)
    var_vr = 2.0 * (2 * q - 1) * (q - 1) / (3 * q * n)
    z = (vr - 1.0) / math.sqrt(max(var_vr, 1e-14))
    p_value = float(2.0 * (1.0 - sp.norm.cdf(abs(z))))
    return {
        "vr": float(vr),
        "z_stat": float(z),
        "p_value": p_value,
        "passed": p_value >= 0.05,
        "q": q,
    }


# ---------------------------------------------------------------- Hurst (R/S analysis)
def hurst_exponent(returns: np.ndarray) -> dict[str, Any]:
    """Hurst via Rescaled Range Analysis (Mandelbrot).

    H ≈ 0.5 = retornos independentes (desejável).
    H > 0.55 = persistência (wins clusterizados → regime-dependente).
    H < 0.45 = anti-persistência / mean-reverting (possível overfit).
    """
    n = len(returns)
    if n < 50:
        return {"hurst": 0.5, "passed": True, "n": n, "interpretation": "amostra pequena"}

    y = returns - returns.mean()
    candidates = [8, 16, 32, 64, 128, 256, 512]
    lags = [L for L in candidates if L < n // 2]
    if len(lags) < 3:
        return {"hurst": 0.5, "passed": True, "n": n, "interpretation": "amostra pequena"}

    rs_values = []
    for L in lags:
        n_blocks = n // L
        ratios = []
        for i in range(n_blocks):
            block = y[i * L:(i + 1) * L]
            cs = np.cumsum(block - block.mean())
            r = float(cs.max() - cs.min())
            s = float(np.std(block, ddof=1))
            if s > 1e-14:
                ratios.append(r / s)
        if ratios:
            rs_values.append(np.mean(ratios))

    if len(rs_values) < 3:
        return {"hurst": 0.5, "passed": True, "n": n, "interpretation": "dados insuficientes"}

    H, _ = np.polyfit(np.log(lags[:len(rs_values)]), np.log(rs_values), 1)
    H = float(H)
    if 0.45 <= H <= 0.55:
        interp = "independente"
    elif H > 0.55:
        interp = "persistente (clustering)"
    else:
        interp = "mean-reverting"
    return {
        "hurst": H,
        "passed": 0.45 <= H <= 0.55,
        "interpretation": interp,
        "n": n,
    }


# ---------------------------------------------------------------- Edge stability (ANOVA)
def edge_stability(returns: np.ndarray, k_chunks: int = 4) -> dict[str, Any]:
    """Split em K chunks e testa igualdade de médias via one-way ANOVA.

    p > 0.05 = médias iguais = edge NÃO decai = PASS.
    Se p < 0.05, a estratégia tem performance heterogênea no tempo.
    """
    n = len(returns)
    if n < 4 * k_chunks:
        return {"f_stat": 0.0, "p_value": 1.0, "passed": True,
                "chunk_means": [], "chunk_sharpes": [], "k_chunks": k_chunks}

    chunk_size = n // k_chunks
    chunks = [returns[i * chunk_size:(i + 1) * chunk_size] for i in range(k_chunks)]
    f_stat, p_value = sp.f_oneway(*chunks)

    means = [float(c.mean()) for c in chunks]
    sharpes = [float(c.mean() / c.std(ddof=1)) if c.std(ddof=1) > 0 else 0.0 for c in chunks]
    return {
        "f_stat": float(f_stat),
        "p_value": float(p_value),
        "chunk_means": means,
        "chunk_sharpes": sharpes,
        "passed": p_value >= 0.05,
        "k_chunks": k_chunks,
    }


# ---------------------------------------------------------------- Sharpe CI (bootstrap)
def sharpe_bootstrap_ci(returns: np.ndarray, runs: int = 2000,
                       seed: int | None = 42, confidence: float = 0.95) -> dict[str, Any]:
    """Bootstrap Sharpe per-trade: qual a confiança de que é > 0?

    CI 95%; se o lower bound > 0 → Sharpe é positivo com 95% de confiança → PASS.
    """
    n = len(returns)
    if n < 30:
        return {"sharpe": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "passed": False, "n": n}

    rng = np.random.default_rng(seed)
    sharpes = np.empty(runs)
    for i in range(runs):
        sample = returns[rng.integers(0, n, size=n)]
        s = float(sample.std(ddof=1))
        sharpes[i] = float(sample.mean() / s) if s > 1e-14 else 0.0

    sr = float(returns.mean() / returns.std(ddof=1)) if returns.std(ddof=1) > 1e-14 else 0.0
    alpha = (1.0 - confidence) / 2.0
    ci_low = float(np.percentile(sharpes, alpha * 100))
    ci_high = float(np.percentile(sharpes, (1.0 - alpha) * 100))
    return {
        "sharpe": sr,
        "ci_lower": ci_low,
        "ci_upper": ci_high,
        "passed": ci_low > 0.0,
        "runs": runs,
        "confidence": confidence,
    }


# ---------------------------------------------------------------- Max consec. losses
def max_consecutive_losses(profits: np.ndarray) -> dict[str, Any]:
    """Max losing streak observada vs esperada dado win_rate.

    Expected max streak ≈ log(n * p) / log(1/(1-p)) em n trades.
    PASS se ratio (observado/esperado) ≤ 2.0.
    """
    n = len(profits)
    if n < 20:
        return {"max_streak": 0, "expected_max": 0.0, "ratio": 1.0, "passed": True}

    wins = profits > 0
    p = float(wins.mean())
    if p <= 0 or p >= 1:
        return {"max_streak": 0, "expected_max": 0.0, "ratio": 1.0, "passed": True}

    streak = max_streak = 0
    for w in wins.astype(int):
        if w == 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    expected = math.log(max(n * p, 1.1)) / math.log(1.0 / (1.0 - p))
    ratio = max_streak / expected if expected > 0 else 1.0
    return {
        "max_streak": int(max_streak),
        "expected_max": float(expected),
        "ratio": float(ratio),
        "win_rate": p,
        "passed": ratio <= 2.0,
    }


# ---------------------------------------------------------------- Profit concentration (Gini)
def profit_gini(profits: np.ndarray) -> dict[str, Any]:
    """Gini da distribuição de lucros absolutos — concentração em poucos trades.

    G = 0 → lucros uniformemente distribuídos.
    G ≈ 1 → um trade domina tudo.
    PASS se G < 0.65 (threshold prático para fundos sistemáticos).
    """
    abs_p = np.abs(profits[profits != 0])
    n = abs_p.size
    if n < 5:
        return {"gini": 0.0, "passed": True, "n": n}
    sorted_p = np.sort(abs_p)
    idx = np.arange(1, n + 1)
    total = float(sorted_p.sum())
    if total < 1e-14:
        return {"gini": 0.0, "passed": True, "n": n}
    gini = float(2.0 * np.sum(idx * sorted_p) / (n * total) - (n + 1) / n)
    return {"gini": gini, "passed": gini < 0.65, "n": n}


# ---------------------------------------------------------------- t-stat Renaissance-grade
def t_test_renaissance_grade(returns: np.ndarray) -> dict[str, Any]:
    """Threshold rigoroso: t ≥ 3.0 e p < 0.001.

    Diferente do check quant-grade (t ≥ 2.5). Fontes públicas sugerem que
    Renaissance aplica um corte bem acima de 2.5.
    """
    n = len(returns)
    THRESHOLD = 3.0
    if n < 5:
        return {"t_stat": 0.0, "p_value": 1.0, "passed": False, "n": n, "threshold": THRESHOLD}
    result = sp.ttest_1samp(returns, popmean=0.0, alternative="greater")
    return {
        "t_stat": float(result.statistic),
        "p_value": float(result.pvalue),
        "passed": result.statistic >= THRESHOLD and result.pvalue < 0.001,
        "n": n,
        "threshold": THRESHOLD,
    }


# ---------------------------------------------------------------- Suite completa
def run_stat_validation(
    trades: list[dict[str, Any]],
    initial: float = 10_000.0,
) -> dict[str, Any]:
    """Bateria completa de testes estatísticos — retorna resultados + scorecard."""
    if not trades:
        return {}
    profits = np.array([float(t["profit"]) for t in trades], dtype=np.float64)
    returns = _returns_from_profits(profits, initial)

    t = t_test_returns(returns)
    lb = ljung_box(returns)
    rt = runs_test(profits)
    od = outlier_dependency(profits)
    tr = tail_ratio(returns)
    jb = jarque_bera(returns)

    def _card(name: str, result: dict, value_fmt: str, note: str,
              suggestion: str = "") -> dict[str, Any]:
        passed = result["passed"]
        return {
            "name": name,
            "status": "pass" if passed else "fail",
            "value": value_fmt,
            "note": note,
            "suggestion": "" if passed else suggestion,
        }

    scorecard = [
        _card(
            "t-stat retornos ≥ 2.5",
            t,
            f"t={t['t_stat']:.2f} · p={t['p_value']:.3f}",
            "Significância estatística do edge. Renaissance estimado ≥ 2.5.",
            "Edge fraco ou amostra pequena. Opções: (1) aumentar nº de trades (testar em período maior); "
            "(2) adicionar filtro de qualidade (ex: só operar com ATR > X, só em tendência clara) — "
            "reduz trades mas aumenta t-stat; (3) combinar com outro sinal para entradas de maior convicção; "
            "(4) se já tem muitos trades e t continua baixo, o edge provavelmente não é real.",
        ),
        _card(
            "Sem autocorrelação (Ljung-Box)",
            lb,
            f"Q={lb['statistic']:.2f} · p={lb['p_value']:.3f} · acf₁={lb['acf_1']:.3f}",
            "p > 0.05 = retornos independentes. Autocorr. sugere look-ahead bias.",
            f"ACF lag-1 = {lb['acf_1']:.3f}. Autocorrelação positiva alta indica: "
            "(1) possível look-ahead bias (indicador usa dado futuro — revisar cálculo de SMA/regressão); "
            "(2) trades muito próximos no tempo compartilhando regime — aumentar cooldown entre trades; "
            "(3) se for negativa, trades estão compensando um ao outro (over-trading). "
            "Solução prática: adicionar cooldown mínimo ou reduzir frequência.",
        ),
        _card(
            "Sequência aleatória (Runs test)",
            rt,
            f"z={rt['z_stat']:.2f} · p={rt['p_value']:.3f} · {rt['runs']} runs",
            "p > 0.05 = wins/losses não clusterizados. Clustering = regime-dependente.",
            "Wins/losses estão clusterizados (ganha-ganha-ganha / perde-perde-perde). "
            "Estratégia é regime-dependente. Opções: (1) identificar o regime via filtro (ADX, "
            "volatilidade, horário, dia da semana) e só operar no regime favorável; "
            "(2) usar equity control (parar após N perdas consecutivas, reiniciar após X dias); "
            "(3) segmentar análise: rodar backtest separado por regime.",
        ),
        _card(
            "Lucrativo sem top 5% trades",
            od,
            f"Sem top {od['removed']} trades: {od['net_without_top']:.2f} ({od['pct_from_outliers']*100:.0f}% vem de outliers)",
            "Robustez a ausência de trades excepcionais.",
            f"{od['pct_from_outliers']*100:.0f}% do lucro vem dos top {od['removed']} trades — frágil. "
            "Opções: (1) aumentar TP/trailing para capturar mais desses outliers (eles são o edge); "
            "(2) reduzir tamanho da posição em setups normais e aumentar nos outliers via volatility sizing; "
            "(3) verificar se os outliers não são gaps/slippage inviáveis em live; "
            "(4) rodar mais tempo — amostra pequena inflama dependência.",
        ),
        _card(
            "Tail ratio ≥ 1 (cauda direita ≥ esquerda)",
            tr,
            f"TR={tr['tail_ratio']:.2f} · P95={tr['p95']:.4f} · P5={tr['p5']:.4f}",
            "Caudas positivas maiores que negativas = assimetria favorável.",
            "Perdas extremas são maiores que ganhos extremos (risco assimétrico). Opções: "
            "(1) apertar stop loss — corta cauda esquerda; "
            "(2) usar trailing stop para esticar winners — alonga cauda direita; "
            "(3) aumentar TP:SL ratio (ex: 2:1 → 3:1); "
            "(4) filtrar entradas de baixa qualidade que produzem perdas grandes.",
        ),
        _card(
            "Assimetria positiva (Jarque-Bera)",
            jb,
            f"skew={jb['skewness']:.3f} · kurt={jb['excess_kurtosis']:.3f}",
            "Skewness > 0 = distribuição assimétrica à direita (desejável).",
            f"Skewness = {jb['skewness']:.2f} (negativa). Mais perdas grandes do que ganhos grandes. "
            "Característico de estratégias vende-volatilidade (short gamma). Opções: "
            "(1) apertar stop; (2) alongar take-profit; (3) cortar trades de pior payoff ratio; "
            f"(4) kurtosis excess = {jb['excess_kurtosis']:.1f} — se > 3, fat tails; "
            "considerar position sizing por vol (ex: Kelly fracionado).",
        ),
    ]

    passes = sum(1 for c in scorecard if c["status"] == "pass")
    return {
        "t_test": t,
        "ljung_box": lb,
        "runs_test": rt,
        "outlier_dependency": od,
        "tail_ratio": tr,
        "jarque_bera": jb,
        "scorecard": scorecard,
        "passes": passes,
        "total": len(scorecard),
        "overall": "green" if passes == len(scorecard) else "yellow" if passes >= len(scorecard) - 2 else "red",
        "n_trades": len(trades),
    }
