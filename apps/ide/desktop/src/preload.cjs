const { contextBridge, ipcRenderer } = require('electron');

let callbackIdCounter = 1;
const callbackMap = new Map();

ipcRenderer.on('tauri:callback', (_event, { id, data }) => {
  const entry = callbackMap.get(id);
  if (entry) {
    try {
      entry.callback(data);
    } catch (e) {
      console.error('[Tauri Callback Error]', e);
    }
    if (entry.once) {
      callbackMap.delete(id);
    }
  }
});

const tauriInternals = {
  invoke: async (cmd, args = {}, options = {}) => {
    const res = await ipcRenderer.invoke('openidea:invoke', cmd, args, options);
    if (res && res.__isTauriError) {
      return Promise.reject(res.error);
    }
    return res;
  },
  transformCallback: (callback, once = false) => {
    const id = callbackIdCounter++;
    callbackMap.set(id, { callback, once });
    return id;
  },
  unregisterCallback: (id) => {
    callbackMap.delete(id);
  },
  metadata: {
    currentWindow: { label: 'main' },
    currentWebview: { label: 'main' },
  },
  plugins: {
    path: {
      sep: '/',
      delimiter: ':',
    },
  },
};

const tauriEventPluginInternals = {
  unregisterListener: (event, eventId) => {
    ipcRenderer.invoke('openidea:invoke', 'plugin:event|unlisten', { event, eventId });
  },
};

try {
  contextBridge.exposeInMainWorld('__TAURI_INTERNALS__', tauriInternals);
  contextBridge.exposeInMainWorld('__TAURI_EVENT_PLUGIN_INTERNALS__', tauriEventPluginInternals);
} catch (e) {
  console.error('[Preload] Failed to expose Tauri internals:', e);
}

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

contextBridge.exposeInMainWorld('__TAURI__', {
  core: {
    invoke: async (cmd, args, options) => {
      const res = await ipcRenderer.invoke('openidea:invoke', cmd, args, options);
      if (res && res.__isTauriError) {
        return Promise.reject(res.error);
      }
      return res;
    },
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
