const { app, BrowserWindow, ipcMain, shell, dialog, protocol, net } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const os = require('node:os');
const { pathToFileURL } = require('node:url');

// Load parsed languages list
let languagesList = [];
try {
  languagesList = require('./languages.json');
} catch (e) {
  console.warn('Could not load languages.json:', e);
}

// Register app scheme as privileged before app is ready
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

let mainWindow = null;
let serverProc = null;
let rpcNextId = 1;
const pendingRequests = new Map();
let stdoutBuffer = Buffer.alloc(0);
let channelSeq = 0;
let nextEventSeq = 1;
let nextListenerId = 1;
const eventListeners = [];
let pendingLaunch = null;

// Shared config directory ~/.wolinex
const WOLINEX_DIR = path.join(os.homedir(), '.wolinex');
const ACTIVE_STATE_FILE = path.join(WOLINEX_DIR, 'active_state.json');

try {
  fs.mkdirSync(WOLINEX_DIR, { recursive: true });
} catch {}

function readActiveState() {
  try {
    if (fs.existsSync(ACTIVE_STATE_FILE)) {
      return JSON.parse(fs.readFileSync(ACTIVE_STATE_FILE, 'utf-8'));
    }
  } catch (e) {
    console.error('Failed to read active state:', e);
  }
  return {
    active_project: path.join(os.homedir(), 'Documents', 'wolinetai'),
    active_session: '',
    gateway_url: process.env.LITELLM_HOST || 'http://127.0.0.1:4000',
  };
}

function writeActiveState(updates) {
  try {
    const current = readActiveState();
    const merged = { ...current, ...updates, updated_at: new Date().toISOString() };
    fs.writeFileSync(ACTIVE_STATE_FILE, JSON.stringify(merged, null, 2), 'utf-8');
  } catch (e) {
    console.error('Failed to write active state:', e);
  }
}

function getRecentProjects() {
  const recentFile = path.join(os.homedir(), '.openidea', 'config', 'recent.json');
  try {
    if (fs.existsSync(recentFile)) {
      const data = JSON.parse(fs.readFileSync(recentFile, 'utf-8'));
      if (Array.isArray(data) && data.length > 0) return data;
    }
  } catch (e) {
    log('Failed to read recent projects:', e);
  }
  const defaultProject = path.join(os.homedir(), 'Documents', 'wolinetai');
  const defaults = [
    {
      path: defaultProject,
      name: 'wolinetai',
      openedAtMs: Date.now(),
      branch: 'main',
    },
  ];
  try {
    fs.mkdirSync(path.dirname(recentFile), { recursive: true });
    fs.writeFileSync(recentFile, JSON.stringify(defaults, null, 2), 'utf-8');
  } catch {}
  return defaults;
}

function addToRecent(projectPath, projectName) {
  const recentFile = path.join(os.homedir(), '.openidea', 'config', 'recent.json');
  try {
    let list = [];
    if (fs.existsSync(recentFile)) {
      list = JSON.parse(fs.readFileSync(recentFile, 'utf-8'));
    }
    list = list.filter((p) => p.path !== projectPath);
    list.unshift({
      path: projectPath,
      name: projectName || path.basename(projectPath),
      openedAtMs: Date.now(),
      branch: null,
    });
    fs.mkdirSync(path.dirname(recentFile), { recursive: true });
    fs.writeFileSync(recentFile, JSON.stringify(list.slice(0, 30), null, 2), 'utf-8');
  } catch (e) {
    log('Failed to save recent projects:', e);
  }
}

app.setName('WolinexCode');
app.setAppUserModelId('com.wolinet.wolinexcode');

const LOG_FILE = path.join(WOLINEX_DIR, 'wolinex_code.log');
function log(...args) {
  const line = `[${new Date().toISOString()}] ${args.join(' ')}\n`;
  try {
    fs.appendFileSync(LOG_FILE, line);
  } catch {}
  console.log(...args);
}

log('Starting WolinexCode main process...');

// Single instance lock
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  log('Another instance is already running. Quitting.');
  app.quit();
  process.exit(0);
}

// Register deep linking
if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient('wolinex-code', process.execPath, [path.resolve(process.argv[1])]);
  }
} else {
  app.setAsDefaultProtocolClient('wolinex-code');
}

function handleDeepLink(url) {
  if (!url || !url.startsWith('wolinex-code://')) return;
  try {
    const parsed = new URL(url);
    const project = parsed.searchParams.get('project');
    const session = parsed.searchParams.get('session');
    if (project) {
      writeActiveState({ active_project: project, active_session: session || '' });
      if (mainWindow) {
        mainWindow.webContents.send('wolinex:open-project', { project, session });
      }
    }
  } catch (e) {
    console.error('Error handling deep link:', e);
  }
}

app.on('second-instance', (_event, commandLine) => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
  const url = commandLine.find((arg) => arg.startsWith('wolinex-code://'));
  if (url) handleDeepLink(url);
});

app.on('open-url', (_event, url) => {
  handleDeepLink(url);
});

// Resolve openidea-server binary
function resolveServerBinary() {
  const candidates = [
    path.join(__dirname, '..', 'bin', 'openidea-server'),
    path.join(__dirname, '..', '..', 'bin', 'openidea-server'),
    path.join(process.resourcesPath || '', 'bin', 'openidea-server'),
    path.join(os.homedir(), 'Documents', 'wolinetai', 'apps', 'ide', 'bin', 'openidea-server'),
    path.join(os.homedir(), 'Documents', 'wolinetai', 'apps', 'WolinexIde', 'ui', 'desktop', 'src', 'bin', 'openidea-server'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return candidates[0];
}

function sendRpc(method, params = {}) {
  return new Promise((resolve, reject) => {
    if (!serverProc || !serverProc.stdin) {
      return reject({ kind: 'unavailable', message: 'OpenIDEA server is not running' });
    }
    const id = rpcNextId++;
    const payload = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    const header = `Content-Length: ${Buffer.byteLength(payload, 'utf-8')}\r\n\r\n`;

    pendingRequests.set(id, { resolve, reject });

    serverProc.stdin.write(header + payload);
  });
}

function handleServerMessage(msg) {
  // 1. Response to a request
  if (msg.id != null && pendingRequests.has(msg.id)) {
    const { resolve, reject } = pendingRequests.get(msg.id);
    pendingRequests.delete(msg.id);
    if (msg.error) {
      let kind = 'internal';
      let message = msg.error.message || 'RPC Error';
      if (msg.error.data && typeof msg.error.data === 'object' && msg.error.data.kind) {
        kind = msg.error.data.kind;
        message = msg.error.data.message || message;
      } else if (msg.error.message) {
        try {
          const parsed = JSON.parse(msg.error.message);
          if (parsed && parsed.kind) {
            kind = parsed.kind;
            message = parsed.message || message;
          }
        } catch {
          if (msg.error.message.includes('already exists')) kind = 'alreadyExists';
          else if (msg.error.message.includes('not found') || msg.error.message.includes('No such file')) kind = 'notFound';
        }
      }
      reject({ kind, message });
    } else {
      resolve(msg.result);
    }
    return;
  }

  // 2. Notification from server
  if (msg.method === 'event') {
    const eventPayload = msg.params?.event;
    if (eventPayload && mainWindow) {
      for (const l of eventListeners) {
        if (l.event === 'ide://event' || l.event === '*') {
          mainWindow.webContents.send('tauri:callback', {
            id: l.handler,
            data: { event: 'ide://event', id: nextEventSeq++, payload: eventPayload },
          });
        }
      }
    }
  } else if (msg.method === 'channel') {
    const channelId = msg.params?.id;
    const channelData = msg.params?.data;
    if (channelId != null && mainWindow) {
      mainWindow.webContents.send('tauri:callback', {
        id: channelId,
        data: { message: channelData, index: channelSeq++ },
      });
    }
  }
}

function processServerStdout(chunk) {
  stdoutBuffer = Buffer.concat([stdoutBuffer, chunk]);
  while (true) {
    const headerEnd = stdoutBuffer.indexOf('\r\n\r\n');
    if (headerEnd === -1) break;
    const headerStr = stdoutBuffer.subarray(0, headerEnd).toString('utf-8');
    const m = headerStr.match(/Content-Length:\s*(\d+)/i);
    if (!m) {
      log('Unrecognized server header:', headerStr);
      stdoutBuffer = stdoutBuffer.subarray(headerEnd + 4);
      continue;
    }
    const len = parseInt(m[1], 10);
    const bodyStart = headerEnd + 4;
    if (stdoutBuffer.length < bodyStart + len) break;
    const bodyStr = stdoutBuffer.subarray(bodyStart, bodyStart + len).toString('utf-8');
    stdoutBuffer = stdoutBuffer.subarray(bodyStart + len);
    try {
      const msg = JSON.parse(bodyStr);
      handleServerMessage(msg);
    } catch (e) {
      log('Failed to parse server JSON-RPC message:', e, bodyStr);
    }
  }
}

function startOpenIdeaServer() {
  const binaryPath = resolveServerBinary();
  log('Starting native Rust server:', binaryPath);

  if (!fs.existsSync(binaryPath)) {
    log('openidea-server binary not found at:', binaryPath);
    return;
  }

  serverProc = spawn(binaryPath, ['--stdio'], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: {
      ...process.env,
      RUST_BACKTRACE: '1',
      RUST_LOG: 'info',
    },
  });

  serverProc.stdout.on('data', processServerStdout);

  serverProc.stderr.on('data', (d) => {
    const s = d.toString('utf-8');
    if (!s.includes('TRACE')) log('[Rust Server Stderr]', s.trim());
  });

  serverProc.on('exit', (code, sig) => {
    log(`[Rust Server] Process exited: code=${code}, sig=${sig}`);
    serverProc = null;
  });

  sendRpc('initialize', { version: '0.1.32' })
    .then((info) => {
      log('[Rust Server] Initialized successfully:', JSON.stringify(info));
    })
    .catch((err) => {
      log('[Rust Server] Initialize failed:', err);
    });
}

function normalizeArgs(obj) {
  if (obj === null || obj === undefined) return obj;
  if (typeof obj === 'string') {
    if (obj.startsWith('__CHANNEL__:')) {
      const id = parseInt(obj.slice(12), 10);
      return { $channel: id };
    }
    return obj;
  }
  if (Array.isArray(obj)) {
    return obj.map(normalizeArgs);
  }
  if (typeof obj === 'object') {
    if (typeof obj.$channel === 'number') {
      return { $channel: obj.$channel };
    }
    if (typeof obj.id === 'number' && (obj.hasOwnProperty('onmessage') || Object.keys(obj).length <= 3)) {
      return { $channel: obj.id };
    }
    const result = {};
    for (const [k, v] of Object.entries(obj)) {
      if (
        v &&
        typeof v === 'object' &&
        (typeof v.$channel === 'number' ||
          (typeof v.id === 'number' &&
            (v.hasOwnProperty('onmessage') ||
              k.startsWith('on') ||
              k.includes('Channel') ||
              k.toLowerCase().includes('output') ||
              k.toLowerCase().includes('event'))))
      ) {
        result[k] = { $channel: v.$channel ?? v.id };
      } else {
        result[k] = normalizeArgs(v);
      }
    }
    return result;
  }
  return obj;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'Wolinex Code — Sovereign Rust IDE',
    backgroundColor: '#181a1d',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  mainWindow.webContents.on('console-message', (_e, level, message) => {
    log(`[IDE UI Level ${level}]: ${message}`);
  });

  const candidateIndices = [
    path.join(__dirname, '..', 'dist', 'index.html'),
    path.join(__dirname, 'dist', 'index.html'),
    path.join(__dirname, '..', '..', 'dist', 'index.html'),
  ];
  const distIndex = candidateIndices.find((p) => fs.existsSync(p));
  if (distIndex) {
    log('Loading Workbench UI from app://localhost/index.html via dist:', path.dirname(distIndex));
    mainWindow.loadURL('app://localhost/index.html');
  } else {
    log('Loading dev server at http://localhost:5174');
    mainWindow.loadURL('http://localhost:5174');
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Tauri & OpenIDEA IPC Bridge
ipcMain.handle('openidea:invoke', async (_event, cmd, args = {}, options = {}) => {
  try {
    // 1. Path plugin
    if (cmd === 'plugin:path|resolve_directory') {
      switch (args.directory) {
        case 11: return os.homedir(); // Home
        case 6: return path.join(os.homedir(), 'Desktop'); // Desktop
        case 7: return path.join(os.homedir(), 'Documents'); // Document
        case 8: return path.join(os.homedir(), 'Downloads'); // Download
        case 20: return os.tmpdir(); // Temp
        case 21: return path.join(os.homedir(), '.openidea', 'config'); // AppConfig
        case 22:
        case 23: return path.join(os.homedir(), '.openidea', 'data'); // AppData / AppLocalData
        case 24: return path.join(os.homedir(), '.openidea', 'cache'); // AppCache
        case 25: return path.join(os.homedir(), '.wolinex'); // AppLog
        default: return os.homedir();
      }
    }
    if (cmd === 'plugin:path|join') {
      return path.join(...(args.paths || []));
    }
    if (cmd === 'plugin:path|resolve') {
      return path.resolve(...(args.paths || []));
    }
    if (cmd === 'plugin:path|normalize') {
      return path.normalize(args.path || '');
    }
    if (cmd === 'plugin:path|dirname') {
      return path.dirname(args.path || '');
    }
    if (cmd === 'plugin:path|extname') {
      return path.extname(args.path || '');
    }
    if (cmd === 'plugin:path|basename') {
      return path.basename(args.path || '', args.ext || undefined);
    }
    if (cmd === 'plugin:path|is_absolute') {
      return path.isAbsolute(args.path || '');
    }

    // 2. Dialog plugin
    if (cmd === 'plugin:dialog|open') {
      const opts = args.options || {};
      const properties = [];
      if (opts.directory) properties.push('openDirectory');
      else properties.push('openFile');
      if (opts.multiple) properties.push('multiSelections');
      const res = await dialog.showOpenDialog(mainWindow, {
        title: opts.title || 'Open',
        defaultPath: opts.defaultPath || os.homedir(),
        filters: opts.filters || [],
        properties,
      });
      if (res.canceled || !res.filePaths.length) return null;
      return opts.multiple ? res.filePaths : res.filePaths[0];
    }
    if (cmd === 'plugin:dialog|save') {
      const opts = args.options || {};
      const res = await dialog.showSaveDialog(mainWindow, {
        title: opts.title || 'Save',
        defaultPath: opts.defaultPath || os.homedir(),
        filters: opts.filters || [],
      });
      if (res.canceled) return null;
      return res.filePath;
    }
    if (cmd === 'plugin:dialog|message') {
      const res = await dialog.showMessageBox(mainWindow, {
        title: args.title || 'Wolinex Code',
        message: args.message || '',
        type: args.kind === 'error' ? 'error' : args.kind === 'warning' ? 'warning' : 'info',
        buttons: ['OK'],
      });
      return res.response === 0;
    }

    // 3. Opener plugin
    if (cmd === 'plugin:opener|open_url') {
      if (args.url) await shell.openExternal(args.url);
      return null;
    }
    if (cmd === 'plugin:opener|open_path') {
      if (args.path) await shell.openPath(args.path);
      return null;
    }
    if (cmd === 'plugin:opener|reveal_item_in_dir') {
      if (args.path) shell.showItemInFolder(args.path);
      return null;
    }

    // 4. Window & Webview plugins
    if (cmd === 'plugin:window|get_all_windows') return ['main'];
    if (cmd === 'plugin:window|set_title') {
      if (mainWindow && args.title) mainWindow.setTitle(args.title);
      return null;
    }
    if (cmd === 'plugin:window|set_background_color') {
      if (mainWindow && args.color) {
        try { mainWindow.setBackgroundColor(args.color); } catch {}
      }
      return null;
    }
    if (cmd === 'plugin:window|is_maximized') return mainWindow?.isMaximized() || false;
    if (cmd === 'plugin:window|is_minimized') return mainWindow?.isMinimized() || false;
    if (cmd === 'plugin:window|is_fullscreen') return mainWindow?.isFullScreen() || false;
    if (cmd === 'plugin:window|maximize') { mainWindow?.maximize(); return null; }
    if (cmd === 'plugin:window|unmaximize') { mainWindow?.unmaximize(); return null; }
    if (cmd === 'plugin:window|minimize') { mainWindow?.minimize(); return null; }
    if (cmd === 'plugin:window|close') { mainWindow?.close(); return null; }
    if (cmd === 'plugin:window|show') { mainWindow?.show(); return null; }
    if (cmd === 'plugin:window|hide') { mainWindow?.hide(); return null; }
    if (cmd === 'plugin:window|set_focus') { mainWindow?.focus(); return null; }
    if (cmd === 'plugin:window|is_focused') return mainWindow?.isFocused() || true;
    if (cmd === 'plugin:window|scale_factor') return 1;
    if (cmd === 'plugin:window|inner_size' || cmd === 'plugin:window|outer_size') {
      const [w, h] = mainWindow?.getSize() || [1440, 900];
      return { width: w, height: h };
    }
    if (cmd.startsWith('plugin:window|') || cmd.startsWith('plugin:webview|')) {
      return null;
    }

    // 5. Event plugin
    if (cmd === 'plugin:event|listen') {
      const listenerId = nextListenerId++;
      eventListeners.push({
        id: listenerId,
        event: args.event,
        handler: args.handler,
        target: args.target,
      });
      return listenerId;
    }
    if (cmd === 'plugin:event|unlisten') {
      const idx = eventListeners.findIndex((l) => l.event === args.event && l.id === args.eventId);
      if (idx !== -1) eventListeners.splice(idx, 1);
      return null;
    }
    if (cmd === 'plugin:event|emit' || cmd === 'plugin:event|emit_to') {
      for (const l of eventListeners) {
        if (l.event === args.event) {
          mainWindow?.webContents.send('tauri:callback', {
            id: l.handler,
            data: { event: args.event, id: nextEventSeq++, payload: args.payload },
          });
        }
      }
      return null;
    }

    // 6. App info & Core commands
    if (cmd === 'app_info') {
      return {
        version: '0.1.32',
        platform: 'macos',
        configDir: path.join(os.homedir(), '.openidea', 'config'),
      };
    }
    if (cmd === 'app_build_info') {
      return {
        version: '0.1.32',
        build: 'release',
        profile: 'release',
        os: 'macos',
        arch: 'x86_64',
        tauri: '2.0.0',
        updates: false,
      };
    }
    if (cmd === 'app_log_location') {
      return {
        dir: path.join(os.homedir(), '.wolinex'),
        file: path.join(os.homedir(), '.wolinex', 'wolinex_code.log'),
      };
    }
    if (cmd === 'log_frontend') {
      log(`[UI Frontend ${args.level || 'info'}]: ${args.message || ''}`);
      return null;
    }

    if (cmd === 'recent_projects') {
      return getRecentProjects();
    }

    if (cmd === 'remove_recent_project') {
      if (args.path) {
        const recentFile = path.join(os.homedir(), '.openidea', 'config', 'recent.json');
        try {
          if (fs.existsSync(recentFile)) {
            let list = JSON.parse(fs.readFileSync(recentFile, 'utf-8'));
            list = list.filter((p) => p.path !== args.path);
            fs.writeFileSync(recentFile, JSON.stringify(list, null, 2), 'utf-8');
          }
        } catch {}
      }
      return null;
    }

    if (cmd === 'languages') {
      return languagesList;
    }

    if (cmd === 'project_trust_status') {
      return {
        root: args.path || '',
        trusted: true,
        decided: true,
      };
    }
    if (cmd === 'project_trust_list') {
      return { locations: [], projects: [], restricted: [] };
    }
    if (cmd === 'project_trust_set') {
      try {
        const trustFile = path.join(os.homedir(), '.openidea', 'data', 'project-trust.json');
        let trustData = { projects: [], locations: [], restricted: [] };
        if (fs.existsSync(trustFile)) trustData = JSON.parse(fs.readFileSync(trustFile, 'utf-8'));
        if (args.path && !trustData.projects.includes(args.path)) trustData.projects.push(args.path);
        fs.mkdirSync(path.dirname(trustFile), { recursive: true });
        fs.writeFileSync(trustFile, JSON.stringify(trustData, null, 2), 'utf-8');
      } catch {}
      return null;
    }
    if (cmd === 'project_trust_remove_location') {
      return null;
    }

    if (cmd === 'window_take_launch') {
      const state = readActiveState();
      const launch = pendingLaunch || (state.active_project ? { project: state.active_project, files: [] } : null);
      pendingLaunch = null;
      return launch;
    }

    if (cmd === 'window_open_project') {
      let targetPath = args.path;
      if (targetPath) {
        if (!path.isAbsolute(targetPath)) {
          const candidates = [
            path.resolve(os.homedir(), 'Desktop', targetPath),
            path.resolve(os.homedir(), 'Documents', targetPath),
            path.resolve(os.homedir(), targetPath),
            path.resolve(process.cwd(), targetPath),
          ];
          const found = candidates.find((c) => fs.existsSync(c));
          targetPath = found || path.resolve(targetPath);
        }
        if (!fs.existsSync(targetPath)) {
          return {
            __isTauriError: true,
            error: {
              kind: 'notFound',
              message: `cannot open ${targetPath}: No such file or directory`,
            },
          };
        }
      }
      return { kind: 'current' };
    }
    if (cmd === 'window_open_files') {
      return args.files || [];
    }
    if (cmd === 'window_open_projects') {
      return [];
    }
    if (cmd === 'clipboard_file_list') {
      return [];
    }
    if (cmd === 'menu_refresh' || cmd === 'gh_availability') {
      return null;
    }
    if (cmd === 'window_open_file_in_new_window' || cmd === 'window_open_settings' || cmd === 'window_open_remote' || cmd === 'window_new' || cmd === 'window_cycle') {
      return null;
    }
    if (cmd === 'window_toggle_fullscreen') {
      if (mainWindow) mainWindow.setFullScreen(!mainWindow.isFullScreen());
      return null;
    }
    if (cmd === 'window_set_titlebar_height' || cmd === 'window_close_context') {
      return null;
    }
    if (cmd === 'window_group_current') {
      return [{ label: 'main', title: mainWindow?.getTitle() || 'Wolinex Code', active: true }];
    }
    if (cmd.startsWith('window_group_')) {
      return null;
    }
    if (cmd.startsWith('workspace_')) {
      return null;
    }

    // Menus
    if (cmd === 'menu_model') return [];
    if (cmd === 'menu_configure' || cmd === 'menu_set_disabled') return null;

    // Plugins
    if (cmd === 'plugin_list') return { plugins: [], activeTheme: null };
    if (cmd === 'plugin_subscribe') return null;
    if (cmd === 'plugin_catalog') return [];
    if (cmd === 'plugin_set_enabled' || cmd === 'plugin_install_dir' || cmd === 'plugin_uninstall' || cmd === 'plugin_set_active_file') {
      return null;
    }

    // Web
    if (cmd === 'web_browsers') return [];
    if (cmd === 'web_url') return `http://localhost:5174/${args.path || ''}`;
    if (cmd === 'web_open') {
      if (args.url) shell.openExternal(args.url);
      return null;
    }

    // Settings
    if (cmd === 'settings_get_global') {
      try {
        return await sendRpc('invoke', { window: 'main', cmd: 'settings_get', args: {} });
      } catch {
        return {};
      }
    }

    // 7. Open Project
    if (cmd === 'open_project') {
      let targetPath = args.path;
      if (!targetPath) {
        return {
          __isTauriError: true,
          error: { kind: 'invalid', message: 'Project path is required' },
        };
      }
      if (!path.isAbsolute(targetPath)) {
        const candidates = [
          path.resolve(os.homedir(), 'Desktop', targetPath),
          path.resolve(os.homedir(), 'Documents', targetPath),
          path.resolve(os.homedir(), targetPath),
          path.resolve(process.cwd(), targetPath),
        ];
        const found = candidates.find((c) => fs.existsSync(c));
        targetPath = found || path.resolve(targetPath);
      }
      log('[Open Project Request]', targetPath);
      if (!fs.existsSync(targetPath)) {
        log('[Open Project Error] Directory not found:', targetPath);
        return {
          __isTauriError: true,
          error: {
            kind: 'notFound',
            message: `cannot open ${targetPath}: No such file or directory`,
          },
        };
      }
      try {
        const trustFile = path.join(os.homedir(), '.openidea', 'data', 'project-trust.json');
        let trustData = { projects: [], locations: [], restricted: [] };
        if (fs.existsSync(trustFile)) trustData = JSON.parse(fs.readFileSync(trustFile, 'utf-8'));
        if (!trustData.locations.includes(os.homedir())) trustData.locations.push(os.homedir());
        if (!trustData.projects.includes(targetPath)) trustData.projects.push(targetPath);
        fs.mkdirSync(path.dirname(trustFile), { recursive: true });
        fs.writeFileSync(trustFile, JSON.stringify(trustData, null, 2), 'utf-8');
      } catch (e) {
        log('Failed to save project trust:', e);
      }
      const res = await sendRpc('invoke', {
        window: 'main',
        cmd: 'open_project',
        args: { path: targetPath },
      });
      addToRecent(targetPath, res?.name || path.basename(targetPath));
      writeActiveState({ active_project: targetPath });
      if (mainWindow) {
        mainWindow.setTitle(`${res?.name || path.basename(targetPath)} — Wolinex Code`);
      }
      return res;
    }

    // 8. Forward all other commands to openidea-server
    const norm = normalizeArgs(args);
    return await sendRpc('invoke', { window: 'main', cmd, args: norm });
  } catch (err) {
    const kind = (err && err.kind) ? err.kind : 'internal';
    let message = (err && err.message) ? err.message : (typeof err === 'string' ? err : JSON.stringify(err));
    log(`[RPC Error Handled] cmd=${cmd}:`, message);
    return {
      __isTauriError: true,
      error: {
        kind,
        message,
      },
    };
  }
});

// Legacy / Helper IPC Handlers
ipcMain.handle('openidea:init', async () => {
  return { version: '0.1.32', protocol: 2, name: 'Wolinex Code Engine' };
});

ipcMain.handle('openidea:read-dir', async (_event, dirPath) => {
  return sendRpc('invoke', { window: 'main', cmd: 'fs_read_dir', args: { path: dirPath } });
});

ipcMain.handle('openidea:doc-open', async (_event, filePath) => {
  return sendRpc('invoke', { window: 'main', cmd: 'doc_open', args: { path: filePath } });
});

ipcMain.handle('openidea:doc-save', async (_event, filePath, content) => {
  return sendRpc('invoke', { window: 'main', cmd: 'doc_save', args: { doc: filePath, content } });
});

ipcMain.handle('openidea:get-state', async () => {
  return readActiveState();
});

ipcMain.handle('openidea:set-state', async (_event, updates) => {
  writeActiveState(updates);
  return true;
});

ipcMain.handle('openidea:open-workstation', async (_event, projectPath, sessionId) => {
  const url = `wolinex://open?project=${encodeURIComponent(projectPath || '')}&session=${sessionId || ''}`;
  shell.openExternal(url);
  return true;
});

app.whenReady().then(() => {
  const candidateIndices = [
    path.join(__dirname, '..', 'dist', 'index.html'),
    path.join(__dirname, 'dist', 'index.html'),
    path.join(__dirname, '..', '..', 'dist', 'index.html'),
  ];
  const distIndex = candidateIndices.find((p) => fs.existsSync(p));
  const distDir = distIndex ? path.dirname(distIndex) : null;

  if (distDir) {
    protocol.handle('app', (request) => {
      try {
        const parsedUrl = new URL(request.url);
        let pathname = decodeURIComponent(parsedUrl.pathname);
        if (pathname.startsWith('/')) pathname = pathname.slice(1);
        if (!pathname || pathname === 'index.html') {
          return net.fetch(pathToFileURL(distIndex).toString());
        }
        const candidate = path.join(distDir, pathname);
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
          return net.fetch(pathToFileURL(candidate).toString());
        }
        return net.fetch(pathToFileURL(distIndex).toString());
      } catch (err) {
        log('Protocol handler error for url:', request.url, err);
        return new Response('Not Found', { status: 404 });
      }
    });
  }

  startOpenIdeaServer();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});
