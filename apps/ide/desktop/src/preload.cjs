const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  openidea: {
    init: () => ipcRenderer.invoke('openidea:init'),
    invoke: (cmd, args) => ipcRenderer.invoke('openidea:invoke', cmd, args),
    readDir: (dirPath) => ipcRenderer.invoke('openidea:read-dir', dirPath),
    docOpen: (filePath) => ipcRenderer.invoke('openidea:doc-open', filePath),
    docSave: (filePath, content) => ipcRenderer.invoke('openidea:doc-save', filePath, content),
    getState: () => ipcRenderer.invoke('openidea:get-state'),
    setState: (updates) => ipcRenderer.invoke('openidea:set-state', updates),
    openWorkstation: (project, session) => ipcRenderer.invoke('openidea:open-workstation', project, session),
    onOpenProject: (callback) => {
      ipcRenderer.on('wolinex:open-project', (_event, data) => callback(data));
    },
  },
});

// Also expose Tauri-compatible bridge for OpenIDEA core
contextBridge.exposeInMainWorld('__TAURI__', {
  core: {
    invoke: (cmd, args) => ipcRenderer.invoke('openidea:invoke', cmd, args),
  },
  event: {
    listen: (event, handler) => {
      const listener = (_e, payload) => handler({ event, payload });
      ipcRenderer.on(event, listener);
      return () => ipcRenderer.removeListener(event, listener);
    },
    emit: (event, payload) => ipcRenderer.send(event, payload),
  },
});
