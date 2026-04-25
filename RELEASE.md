# AuraBackTest — Build & Release

Instalador Windows (.exe) + auto-update via GitHub Releases.

## 1. Primeiro setup (uma vez)

- **Ícone do app:** coloque um `icon.ico` (256×256) em `electron/build/icon.ico`.
  Sem ele o builder usa o ícone padrão do Electron.
- **Repo no GitHub:** confirme em `electron/package.json` → `build.publish` que
  `owner` e `repo` batem com o seu repositório (hoje: `thiagobelopasa/AuraBackTest`).
- O repo precisa ser **público** (ou os amigos precisariam de token pra update).

## 2. Build local (teste sem publicar)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-local.ps1
```

Gera `release/AuraBackTest-Setup-0.3.0.exe`. Instale e teste antes de publicar.

## 3. Publicar uma nova versão (amigos recebem update automático)

1. **Suba a versão** em `electron/package.json` (ex: `0.3.0` → `0.3.1`).
2. Commit + push.
3. Crie uma tag:
   ```bash
   git tag v0.3.1
   git push origin v0.3.1
   ```
4. O GitHub Actions (`.github/workflows/release.yml`) constrói e publica como
   **Release rascunho** automaticamente.
5. Abra a release em `github.com/thiagobelopasa/AuraBackTest/releases`,
   revise, e clique em **Publish release**.
6. A partir desse momento, qualquer amigo com o app instalado vê o aviso
   "Nova versão disponível" ao abrir e pode atualizar em 1 clique.

## 4. Como distribuir pros amigos (primeira vez)

Mande o link do `.exe` da release no GitHub:
```
https://github.com/thiagobelopasa/AuraBackTest/releases/latest
```

Na primeira execução o Windows SmartScreen alerta que o app "não é reconhecido"
(porque não tem code signing). Os amigos clicam em:
**Mais informações → Executar mesmo assim**. Só precisam fazer isso uma vez.

## 5. Trial

Hard stop em **30/05/2026**. Depois disso o app abre um diálogo
"Período de avaliação encerrado" e fecha. Para estender, edite
`TRIAL_END_ISO` em `electron/main.js` e faça uma nova release.

## 6. Onde ficam os dados dos usuários

No diretório do usuário (não some ao atualizar):
- Windows: `%APPDATA%\AuraBackTest\aurabacktest.db`
- Logs: `%APPDATA%\AuraBackTest\logs\main.log`

## 7. Troubleshooting

- **Backend não sobe no app empacotado:** veja `%APPDATA%\AuraBackTest\logs\main.log`.
  Falha comum: PyInstaller não coletou um submódulo — adicione em `hiddenimports`
  do spec.
- **Update não aparece:** a release precisa estar **publicada** (não rascunho) e
  o `latest.yml` deve estar anexado à release (o electron-builder faz isso
  sozinho via `npm run release`).
