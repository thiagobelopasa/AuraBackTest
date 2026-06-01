const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('aura', {
  getInfo: () => ipcRenderer.invoke('app:get-info'),
  openLogs: () => ipcRenderer.invoke('app:open-logs'),
  openExternal: (url) => ipcRenderer.invoke('app:open-external', url),
  checkUpdates: () => ipcRenderer.invoke('app:check-updates'),
  applyUpdate: () => ipcRenderer.invoke('app:apply-update'),
  backendHealth: () => ipcRenderer.invoke('app:backend-health'),
  restartBackend: () => ipcRenderer.invoke('app:restart-backend'),
  onUpdateStatus: (cb) => {
    const handler = (_e, payload) => cb(payload)
    ipcRenderer.on('update-status', handler)
    return () => ipcRenderer.removeListener('update-status', handler)
  },
  license: {
    status: () => ipcRenderer.invoke('license:status'),
    activate: (key) => ipcRenderer.invoke('license:activate', key),
    deactivate: () => ipcRenderer.invoke('license:deactivate'),
    info: () => ipcRenderer.invoke('license:info'),
  },
})
