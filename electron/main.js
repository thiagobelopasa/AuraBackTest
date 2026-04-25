const { app, BrowserWindow, dialog, globalShortcut, ipcMain, shell, Menu } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const http = require('http')
const log = require('electron-log')
const { autoUpdater } = require('electron-updater')

// -----------------------------------------------------------------------------
// Config
// -----------------------------------------------------------------------------
const TRIAL_END_ISO = '2026-05-30T23:59:59-03:00'
const BACKEND_PORT = 8765
const BACKEND_HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/health`
const BACKEND_START_TIMEOUT_MS = 30_000

log.transports.file.level = 'info'
log.info('AuraBackTest booting', { version: app.getVersion() })
autoUpdater.logger = log

let mainWindow = null
let backendProcess = null

// -----------------------------------------------------------------------------
// Trial check
// -----------------------------------------------------------------------------
function isExpired() {
  const now = new Date()
  const end = new Date(TRIAL_END_ISO)
  return now.getTime() > end.getTime()
}

function showExpiredDialog() {
  dialog.showMessageBoxSync({
    type: 'warning',
    title: 'AuraBackTest — período de avaliação encerrado',
    message: 'Período de avaliação encerrado.',
    detail:
      `Este período de uso gratuito terminou em ${new Date(TRIAL_END_ISO).toLocaleDateString('pt-BR')}.\n\n` +
      'Para continuar usando, entre em contato com o autor:\n' +
      'thiago.belo.pasa@gmail.com',
    buttons: ['Fechar'],
  })
}

// -----------------------------------------------------------------------------
// Backend lifecycle
// -----------------------------------------------------------------------------
function resolveBackendExe() {
  // Produção: backend empacotado em resources/backend
  const prodExe = path.join(process.resourcesPath, 'backend', 'AuraBackTestServer.exe')
  if (fs.existsSync(prodExe)) return { type: 'exe', path: prodExe }

  // Dev: roda main.py via python local
  const devMain = path.join(__dirname, '..', 'backend', 'main.py')
  if (fs.existsSync(devMain)) return { type: 'python', path: devMain }

  return null
}

function waitForBackend(timeoutMs) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(BACKEND_HEALTH_URL, (res) => {
        res.resume()
        if (res.statusCode === 200) return resolve()
        retry()
      })
      req.on('error', retry)
      req.setTimeout(1500, () => { req.destroy(); retry() })
    }
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error('Backend demorou demais para responder'))
      }
      setTimeout(tick, 400)
    }
    tick()
  })
}

function startBackend() {
  const target = resolveBackendExe()
  if (!target) {
    throw new Error('Backend não encontrado. Reinstale o AuraBackTest.')
  }

  let cmd, args, opts
  const userData = app.getPath('userData')
  const env = {
    ...process.env,
    AURABACKTEST_DATA_DIR: userData,
    AURABACKTEST_PORT: String(BACKEND_PORT),
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  }

  if (target.type === 'exe') {
    cmd = target.path
    args = ['--host', '127.0.0.1', '--port', String(BACKEND_PORT)]
    opts = { cwd: path.dirname(target.path), env, windowsHide: true }
  } else {
    cmd = 'python'
    args = ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)]
    opts = { cwd: path.dirname(target.path), env, windowsHide: true, shell: true }
  }

  log.info('Spawning backend', { cmd, args })
  backendProcess = spawn(cmd, args, opts)
  backendProcess.stdout?.on('data', d => log.info('[backend]', d.toString().trim()))
  backendProcess.stderr?.on('data', d => log.warn('[backend]', d.toString().trim()))
  backendProcess.on('exit', (code, signal) => {
    log.warn('Backend exited', { code, signal })
    backendProcess = null
  })
}

function stopBackend() {
  if (!backendProcess) return
  try {
    if (process.platform === 'win32') {
      // Graceful kill da árvore de processos no Windows
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t'], { windowsHide: true })
    } else {
      backendProcess.kill('SIGTERM')
    }
  } catch (e) {
    log.error('Erro ao encerrar backend', e)
  }
  backendProcess = null
}

// -----------------------------------------------------------------------------
// Window
// -----------------------------------------------------------------------------
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: '#0d1117',
    autoHideMenuBar: true,
    show: false,
    icon: path.join(__dirname, 'build', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  Menu.setApplicationMenu(null)

  const frontendIndex = path.join(process.resourcesPath, 'frontend', 'index.html')
  const devIndex = path.join(__dirname, '..', 'frontend', 'dist', 'index.html')
  const indexPath = fs.existsSync(frontendIndex) ? frontendIndex : devIndex

  mainWindow.loadFile(indexPath).catch(err => {
    log.error('Falha ao carregar frontend', err)
    dialog.showErrorBox('Erro', `Não foi possível carregar o frontend: ${err.message}`)
  })

  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.on('closed', () => { mainWindow = null })

  // Links externos abrem no browser, não numa janela nova do Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url)
    return { action: 'deny' }
  })
}

function showLoadingDialog(message) {
  const win = new BrowserWindow({
    width: 420, height: 220,
    frame: false, resizable: false, movable: true, alwaysOnTop: true,
    backgroundColor: '#0d1117',
    webPreferences: { contextIsolation: true },
  })
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    body{margin:0;font-family:system-ui;background:#0d1117;color:#e6edf3;
      display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh}
    h1{font-size:18px;margin:0 0 8px;font-weight:600}
    .muted{color:#8b949e;font-size:12px}
    .spin{width:36px;height:36px;border:3px solid #30363d;border-top-color:#3fb950;
      border-radius:50%;animation:s 1s linear infinite;margin-bottom:14px}
    @keyframes s{to{transform:rotate(360deg)}}
  </style></head><body>
    <div class="spin"></div>
    <h1>AuraBackTest</h1>
    <div class="muted">${message}</div>
  </body></html>`
  win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html))
  return win
}

// -----------------------------------------------------------------------------
// Auto-update
// -----------------------------------------------------------------------------
function setupAutoUpdater() {
  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = true

  autoUpdater.on('update-available', (info) => {
    log.info('Update disponível', info?.version)
    mainWindow?.webContents.send('update-status', { state: 'available', version: info?.version })
  })
  autoUpdater.on('update-not-available', () => {
    mainWindow?.webContents.send('update-status', { state: 'none' })
  })
  autoUpdater.on('download-progress', (p) => {
    mainWindow?.webContents.send('update-status', {
      state: 'downloading', percent: p.percent, bps: p.bytesPerSecond,
    })
  })
  autoUpdater.on('update-downloaded', (info) => {
    log.info('Update baixada', info?.version)
    // Notifica a UI; usuário decide quando aplicar via botão no banner.
    mainWindow?.webContents.send('update-status', { state: 'downloaded', version: info?.version })
  })
  autoUpdater.on('error', (err) => {
    log.warn('Auto-updater error', err?.stack || err?.message || String(err))
    mainWindow?.webContents.send('update-status', {
      state: 'error',
      error: err?.message || String(err),
    })
  })

  // Check inicial + periódico (a cada 30 min) caso estivesse offline no boot.
  const tryCheck = () => autoUpdater.checkForUpdates().catch(err =>
    log.warn('checkForUpdates failed', err?.message || err)
  )
  tryCheck()
  setInterval(tryCheck, 30 * 60 * 1000)
}

// -----------------------------------------------------------------------------
// IPC
// -----------------------------------------------------------------------------
ipcMain.handle('app:get-info', () => ({
  version: app.getVersion(),
  trialEndIso: TRIAL_END_ISO,
  backendUrl: `http://127.0.0.1:${BACKEND_PORT}`,
}))

ipcMain.handle('app:open-logs', () => {
  shell.showItemInFolder(log.transports.file.getFile().path)
})

ipcMain.handle('app:check-updates', async () => {
  try {
    const r = await autoUpdater.checkForUpdates()
    return { ok: true, version: r?.updateInfo?.version }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('app:apply-update', () => {
  try {
    stopBackend()
    // isSilent=true: installer roda em silêncio (NSIS /S); isForceRunAfter=true: reabre o app
    autoUpdater.quitAndInstall(true, true)
    return { ok: true }
  } catch (e) {
    log.error('apply-update failed', e)
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('app:backend-health', () => new Promise((resolve) => {
  const req = http.get(BACKEND_HEALTH_URL, (res) => {
    res.resume()
    resolve({ ok: res.statusCode === 200, status: res.statusCode, pid: backendProcess?.pid || null })
  })
  req.on('error', (err) => resolve({ ok: false, error: err.message, pid: backendProcess?.pid || null }))
  req.setTimeout(2000, () => { req.destroy(); resolve({ ok: false, error: 'timeout', pid: backendProcess?.pid || null }) })
}))

ipcMain.handle('app:restart-backend', async () => {
  try {
    stopBackend()
    // breve pausa pra liberar a porta antes de re-spawnar
    await new Promise(r => setTimeout(r, 500))
    startBackend()
    await waitForBackend(BACKEND_START_TIMEOUT_MS)
    return { ok: true }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

// -----------------------------------------------------------------------------
// App lifecycle
// -----------------------------------------------------------------------------
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })

  app.whenReady().then(async () => {
    if (isExpired()) {
      showExpiredDialog()
      app.quit()
      return
    }

    const loader = showLoadingDialog('Iniciando serviços…')
    try {
      startBackend()
      await waitForBackend(BACKEND_START_TIMEOUT_MS)
    } catch (e) {
      log.error('Falha ao subir backend', e)
      loader.close()
      dialog.showErrorBox('Erro ao iniciar', e.message)
      app.quit()
      return
    }
    loader.close()

    createWindow()
    if (app.isPackaged) setupAutoUpdater()

    // Atalhos de diagnóstico: DevTools + abrir logs
    globalShortcut.register('Control+Shift+I', () => {
      mainWindow?.webContents.toggleDevTools()
    })
    globalShortcut.register('F12', () => {
      mainWindow?.webContents.toggleDevTools()
    })
    globalShortcut.register('Control+Shift+L', () => {
      shell.showItemInFolder(log.transports.file.getFile().path)
    })
  })

  app.on('window-all-closed', () => {
    stopBackend()
    if (process.platform !== 'darwin') app.quit()
  })

  app.on('before-quit', stopBackend)
  app.on('will-quit', () => {
    globalShortcut.unregisterAll()
    stopBackend()
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
}
