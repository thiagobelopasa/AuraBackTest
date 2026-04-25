"""Suite de robustez — bateria de testes que fundos quant usam pra validar edge.

Inclui:
    - Monte Carlo: shuffle, bootstrap IID, block bootstrap (preserva autocorr)
    - Skip / Noise (já existiam, re-rodados aqui agregados)
    - Deflated Sharpe Ratio / Probabilistic Sharpe Ratio (Bailey & López de Prado)
    - Minimum Track Record Length (MinTRL)
    - Regime Analysis (performance por ano calendário + por quartil de volatilidade)
    - Scorecard verde/amarelo/vermelho a partir de thresholds

Não inclui (pendente):
    - PBO via CSCV (exige matriz de performance por sub-período × candidato)
    - Capacity / slippage curve (exige modelo de market impact)
    - Hold-out lock (processo, não teste)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

# Importação lazy para evitar circular import (stat_tests usa numpy puro)
try:
    from services import stat_tests as _stat_tests
    _HAS_STAT_TESTS = True
except ImportError:
    _HAS_STAT_TESTS = False


# --------------------------------------------------------------- utilitários
def _trade_profits(trades: list[dict[str, Any]]) -> np.ndarray:
    return np.array([float(t["profit"]) for t in trades], dtype=np.float64)


def _trade_returns(trades: list[dict[str, Any]], initial: float) -> np.ndarray:
    """Retornos por trade em % do equity anterior."""
    profits = _trade_profits(trades)
    equity = initial + np.concatenate([[0.0], np.cumsum(profits)[:-1]])
    return profits / np.where(equity > 0, equity, initial)


def _max_dd_pct(profits: np.ndarray, initial: float) -> float:
    values = initial + np.cumsum(profits)
    peaks = np.maximum.accumulate(np.concatenate([[initial], values]))
    trough = np.concatenate([[initial], values])
    dd = (peaks - trough) / np.where(peaks > 0, peaks, 1.0)
    return float(np.max(dd)) * 100


# --------------------------------------------------------------- Monte Carlo
def _simulate(profits: np.ndarray, initial: float, runs: int, mode: str,
              rng: np.random.Generator, block_size: int = 5,
              skip_pct: float = 0.1, noise_pct: float = 0.1,
              ) -> tuple[np.ndarray, np.ndarray]:
    n = profits.size
    net = np.empty(runs)
    dd = np.empty(runs)
    for i in range(runs):
        if mode == "shuffle":
            seq = rng.permutation(profits)
        elif mode == "bootstrap":
            seq = profits[rng.integers(0, n, size=n)]
        elif mode == "block_bootstrap":
            nb = max(1, n // block_size)
            starts = rng.integers(0, max(1, n - block_size + 1), size=nb)
            seq = np.concatenate([profits[s:s + block_size] for s in starts])[:n]
        elif mode == "skip":
            mask = rng.random(n) >= skip_pct
            seq = profits[mask] if mask.any() else profits
        elif mode == "noise":
            seq = profits * (1.0 + rng.uniform(-noise_pct, noise_pct, size=n))
        else:
            raise ValueError(mode)
        values = initial + np.cumsum(seq)
        net[i] = values[-1] - initial
        peaks = np.maximum.accumulate(np.concatenate([[initial], values]))
        trough = np.concatenate([[initial], values])
        ddseq = (peaks - trough) / np.where(peaks > 0, peaks, 1.0)
        dd[i] = float(np.max(ddseq)) * 100
    return net, dd


def mc_summary(profits: np.ndarray, initial: float, mode: str, runs: int,
               rng: np.random.Generator, **kwargs) -> dict[str, float]:
    net, dd = _simulate(profits, initial, runs, mode, rng, **kwargs)
    return {
        "mode": mode,
        "runs": runs,
        "net_p5": float(np.percentile(net, 5)),
        "net_p50": float(np.percentile(net, 50)),
        "net_p95": float(np.percentile(net, 95)),
        "dd_p5": float(np.percentile(dd, 5)),
        "dd_p50": float(np.percentile(dd, 50)),
        "dd_p95": float(np.percentile(dd, 95)),
        "prob_profitable": float(np.mean(net > 0)),
    }


# --------------------------------------------------------- Probabilistic SR
def _sharpe_from_returns(returns: np.ndarray) -> float:
    if returns.size < 2:
        return 0.0
    std = returns.std(ddof=1)
    return float(returns.mean() / std) if std > 0 else 0.0


def _skew_kurt(returns: np.ndarray) -> tuple[float, float]:
    """Skewness e kurtosis (excess) amostral."""
    if returns.size < 4:
        return 0.0, 0.0
    r = returns - returns.mean()
    s = returns.std(ddof=1)
    if s <= 0:
        return 0.0, 0.0
    skew = float(np.mean((r / s) ** 3))
    kurt = float(np.mean((r / s) ** 4) - 3.0)
    return skew, kurt


def _std_normal_ppf(p: float) -> float:
    """Inversa da CDF normal padrão (Acklam's approximation)."""
    # Abramowitz & Stegun 26.2.23 — rápido e suficiente para nossos thresholds
    p = min(max(p, 1e-10), 1 - 1e-10)
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def _std_normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probabilistic_sharpe(sr: float, n: int, skew: float, kurt: float,
                         sr_threshold: float = 0.0) -> float:
    """PSR = Prob(SR_verdadeiro > sr_threshold) dado SR observado + skew/kurt.

    Fórmula Bailey & López de Prado (2012).
    """
    if n < 2:
        return 0.0
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt / 4.0) * sr * sr))
    z = (sr - sr_threshold) * math.sqrt(n - 1) / denom
    return _std_normal_cdf(z)


def deflated_sharpe(sr: float, n: int, skew: float, kurt: float,
                    n_trials: int, var_sr_trials: float) -> dict[str, float]:
    """DSR = PSR contra o threshold do "melhor Sharpe sob hipótese nula".

    n_trials: quantos candidatos você testou (ex: 3663).
    var_sr_trials: variância dos Sharpes entre os candidatos testados.
    """
    if n_trials < 2 or var_sr_trials <= 0:
        return {"dsr": 0.0, "sr_threshold": 0.0, "psr_0": probabilistic_sharpe(sr, n, skew, kurt)}
    gamma = 0.5772156649  # Euler-Mascheroni
    z1 = _std_normal_ppf(1 - 1.0 / n_trials)
    z2 = _std_normal_ppf(1 - 1.0 / (n_trials * math.e))
    sr_threshold = math.sqrt(var_sr_trials) * ((1 - gamma) * z1 + gamma * z2)
    dsr = probabilistic_sharpe(sr, n, skew, kurt, sr_threshold=sr_threshold)
    return {
        "dsr": dsr,
        "sr_threshold": sr_threshold,
        "psr_0": probabilistic_sharpe(sr, n, skew, kurt),
    }


def minimum_track_record_length(sr: float, skew: float, kurt: float,
                                sr_target: float = 0.0,
                                confidence: float = 0.95) -> float:
    """MinTRL em número de trades. Quantos trades reais você precisa pra ter
    `confidence` de que SR_verdadeiro > sr_target."""
    if sr <= sr_target:
        return float("inf")
    z = _std_normal_ppf(confidence)
    num = 1 - skew * sr + (kurt / 4.0) * sr * sr
    return 1 + num * (z / (sr - sr_target)) ** 2


# --------------------------------------------------------- Regime analysis
def regime_by_year(trades: list[dict[str, Any]], initial: float) -> list[dict[str, Any]]:
    """Performance agrupada por ano calendário (campo time_out)."""
    by_year: dict[int, list[dict[str, Any]]] = {}
    for t in trades:
        tm = t.get("time_out") or t.get("time_in")
        if isinstance(tm, str):
            try:
                tm = datetime.fromisoformat(tm)
            except ValueError:
                continue
        if not isinstance(tm, datetime):
            continue
        by_year.setdefault(tm.year, []).append(t)

    out = []
    for year in sorted(by_year):
        tr = by_year[year]
        profits = _trade_profits(tr)
        returns = _trade_returns(tr, initial)
        sharpe = _sharpe_from_returns(returns) * math.sqrt(252)  # anualizado (aprox)
        out.append({
            "year": year,
            "trades": len(tr),
            "net_profit": float(profits.sum()),
            "win_rate": float(np.mean(profits > 0)),
            "max_dd_pct": _max_dd_pct(profits, initial),
            "sharpe_annual": sharpe,
        })
    return out


# --------------------------------------------------------- Scorecard
@dataclass
class SuiteResult:
    mc: dict[str, dict[str, float]]                # por modo
    psr_0: float
    dsr: dict[str, float]
    mintrl: float
    sharpe: float
    skew: float
    kurt: float
    n_trades: int
    regime_by_year: list[dict[str, Any]]
    scorecard: list[dict[str, Any]] = field(default_factory=list)
    overall: str = "yellow"


def _check(name: str, passed: bool, value: str, note: str,
           suggestion: str = "") -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail",
            "value": value, "note": note,
            "suggestion": "" if passed else suggestion}


def run_suite(
    trades: list[dict[str, Any]],
    initial: float = 10_000.0,
    runs: int = 2000,
    seed: int | None = 42,
    block_size: int = 5,
    skip_pct: float = 0.2,
    noise_pct: float = 0.25,
    n_trials: int = 1,
    var_sr_trials: float = 0.0,
) -> dict[str, Any]:
    if not trades:
        return {"error": "sem trades"}

    profits = _trade_profits(trades)
    returns = _trade_returns(trades, initial)
    rng = np.random.default_rng(seed)

    mc = {
        m: mc_summary(profits, initial, m, runs, rng,
                      block_size=block_size, skip_pct=skip_pct, noise_pct=noise_pct)
        for m in ("shuffle", "bootstrap", "block_bootstrap", "skip", "noise")
    }

    sr_per_trade = _sharpe_from_returns(returns)
    skew, kurt = _skew_kurt(returns)
    psr0 = probabilistic_sharpe(sr_per_trade, len(returns), skew, kurt, 0.0)
    dsr = deflated_sharpe(sr_per_trade, len(returns), skew, kurt, n_trials, var_sr_trials)
    mintrl = minimum_track_record_length(sr_per_trade, skew, kurt, 0.0, 0.95)
    regimes = regime_by_year(trades, initial)

    # DD original
    orig_dd = _max_dd_pct(profits, initial)
    orig_net = float(profits.sum())

    # Scorecard
    cards = []
    cards.append(_check(
        "Probabilistic Sharpe > 95%",
        psr0 >= 0.95, f"{psr0*100:.1f}%",
        "Prob. que o Sharpe verdadeiro > 0 considerando skew/kurt.",
        "PSR baixo = Sharpe observado pode ser ruído. Opções: "
        "(1) rodar em período maior (mais trades → menos incerteza); "
        "(2) se skew é negativa, ajustar SL/TP para gerar skew positiva; "
        "(3) se kurtosis é alta (fat tails), reduzir position size; "
        "(4) edge provavelmente pequeno: apertar filtros de entrada para elevar t-stat.",
    ))
    cards.append(_check(
        "Deflated Sharpe > 95% (multi-testing)",
        dsr["dsr"] >= 0.95, f"{dsr['dsr']*100:.1f}%",
        f"Corrige Sharpe para N={n_trials} trials testados. Threshold SR={dsr['sr_threshold']:.3f}.",
        f"Você testou N={n_trials} candidatos e o Sharpe do melhor não sobrevive à correção multi-teste. "
        f"Threshold SR ajustado = {dsr['sr_threshold']:.3f}. Opções: "
        "(1) reduzir o espaço de busca da otimização (menos parâmetros, ranges menores); "
        "(2) validar em hold-out / walk-forward antes de aceitar o 'top 1'; "
        "(3) não escolher o single best — pegar o top-N e analisar estabilidade entre eles; "
        "(4) aceitar que o edge é overfit e reformular a estratégia.",
    ))
    cards.append(_check(
        "MinTRL ≤ 500 trades",
        mintrl <= 500, f"{mintrl:.0f} trades" if not math.isinf(mintrl) else "∞",
        "Trades reais necessários p/ 95% de confiança de edge.",
        f"São necessários {mintrl:.0f} trades para ter 95% de confiança. Opções: "
        "(1) rodar em histórico maior; "
        "(2) reduzir timeframe (M15→M5) para gerar mais trades (cuidado com custos); "
        "(3) operar múltiplos ativos descorrelacionados para compor amostra; "
        "(4) elevar Sharpe per-trade (apertar filtros) reduz MinTRL drasticamente.",
    ))
    cards.append(_check(
        "Shuffle: prob lucro ≥ 90%",
        mc["shuffle"]["prob_profitable"] >= 0.9,
        f"{mc['shuffle']['prob_profitable']*100:.1f}%",
        "Estratégia não depende de ordem específica.",
        "Lucro depende de ordem específica dos trades — pode ser um grande trade inicial "
        "ou streak favorável que nunca repete. Opções: "
        "(1) verificar outlier dependency (se poucos trades dominam, distribuir ou cortar); "
        "(2) rodar em sample maior; "
        "(3) se é regime-dependente, adicionar filtro de regime.",
    ))
    cards.append(_check(
        "Block bootstrap DD P95 < 1.5× DD histórico",
        mc["block_bootstrap"]["dd_p95"] < 1.5 * orig_dd,
        f"{mc['block_bootstrap']['dd_p95']:.2f}% vs {orig_dd:.2f}%",
        "Preserva autocorrelação de streaks.",
        f"DD P95 do block bootstrap ({mc['block_bootstrap']['dd_p95']:.1f}%) muito maior que o "
        f"histórico ({orig_dd:.1f}%). Streaks de losses podem ser piores em live. Opções: "
        "(1) dimensionar capital para aguentar o DD P95, não o histórico (regra fundamental); "
        "(2) aplicar equity control (parar após N losses consecutivos); "
        "(3) reduzir position size; "
        "(4) adicionar filtro anti-streak (ex: pausar após X losses no dia).",
    ))
    cards.append(_check(
        f"Sobrevive a remoção de {int(skip_pct*100)}% dos trades",
        mc["skip"]["prob_profitable"] >= 0.9,
        f"{mc['skip']['prob_profitable']*100:.1f}% lucrativos",
        "Edge não depende de punhado de trades específicos.",
        "Sem 10-20% dos trades, a estratégia quebra. Sinais ruins passam "
        "e dependem de trades específicos para compensar. Opções: "
        "(1) endurecer filtro de entrada — reduz trades ruins; "
        "(2) analisar MAE/MFE dos losses e encurtar stop para cortar perdas precoces; "
        "(3) trailing stop em winners para capturar mais; "
        "(4) validar se a remoção corresponde a slippage real (conexão caindo = perde trades).",
    ))
    cards.append(_check(
        f"Robusto a slippage ±{int(noise_pct*100)}%",
        mc["noise"]["prob_profitable"] >= 0.9,
        f"{mc['noise']['prob_profitable']*100:.1f}% lucrativos",
        "Edge maior que custo de execução.",
        f"Slippage de ±{int(noise_pct*100)}% no profit mata o sistema. Isso é grande. Opções: "
        "(1) operar ativos mais líquidos (menor spread); "
        "(2) evitar horários de baixa liquidez (use Análise Temporal para identificar); "
        "(3) usar ordens limit em vez de market quando possível; "
        "(4) aumentar TP para que slippage seja pequeno relativamente; "
        "(5) margem insuficiente: reformular o edge.",
    ))
    if regimes:
        positive_years = sum(1 for r in regimes if r["net_profit"] > 0)
        losing_years = [r["year"] for r in regimes if r["net_profit"] <= 0]
        cards.append(_check(
            "Lucrativo em todos os anos testados",
            positive_years == len(regimes),
            f"{positive_years}/{len(regimes)} anos",
            "Não depende de regime específico.",
            f"Anos negativos: {losing_years}. Regime-dependência. Opções: "
            "(1) identificar o que mudou naqueles anos (volatilidade, tendência, spread) "
            "e adicionar filtro; "
            "(2) combinar com outra estratégia que funcione no regime contrário "
            "(hedge portfolio); "
            "(3) aceitar que vai ter anos ruins e dimensionar capital para isso; "
            "(4) equity control: sair do mercado após DD% no ano.",
        ))

    # Testes estatísticos adicionais (Simons-style)
    if _HAS_STAT_TESTS:
        sv = _stat_tests.run_stat_validation(trades, initial)
        for sc in sv.get("scorecard", []):
            cards.append(sc)

    passes = sum(1 for c in cards if c["status"] == "pass")
    total = len(cards)
    if passes == total:
        overall = "green"
    elif passes >= total - 2:
        overall = "yellow"
    else:
        overall = "red"

    return {
        "n_trades": len(trades),
        "sharpe_per_trade": sr_per_trade,
        "sharpe_annualized": sr_per_trade * math.sqrt(252),
        "skew": skew,
        "kurt": kurt,
        "net_profit": orig_net,
        "max_dd_pct": orig_dd,
        "mc": mc,
        "psr_0": psr0,
        "dsr": dsr,
        "mintrl": mintrl if not math.isinf(mintrl) else None,
        "regime_by_year": regimes,
        "scorecard": cards,
        "overall": overall,
        "passes": passes,
        "total": total,
    }
