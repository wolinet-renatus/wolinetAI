const { app, BrowserWindow, ipcMain, shell, dialog, protocol, net } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const os = require('node:os');
const { pathToFileURL } = require('node:url');

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
let nextId = 1;
const pendingRequests = new Map();
let stdoutBuffer = Buffer.alloc(0);

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

// Start openidea-server Rust backend
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

function startOpenIdeaServer() {
  const binaryPath = resolveServerBinary();
  console.log('[Wolinex Code] Starting native Rust server:', binaryPath);

  if (!fs.existsSync(binaryPath)) {
    console.warn('[Wolinex Code] openidea-server binary not found at:', binaryPath);
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

  serverProc.stdout.on('data', (chunk) => {
    stdoutBuffer = Buffer.concat([stdoutBuffer, chunk]);
    while (stdoutBuffer.length >= 4) {
      const msgLen = stdoutBuffer.readUInt32LE(0);
      if (stdoutBuffer.length < 4 + msgLen) break;
      const msgBuf = stdoutBuffer.subarray(4, 4 + msgLen);
      stdoutBuffer = stdoutBuffer.subarray(4 + msgLen);
      try {
        const msg = JSON.parse(msgBuf.toString('utf-8'));
        if (msg.id && pendingRequests.has(msg.id)) {
          const resolve = pendingRequests.get(msg.id);
          pendingRequests.delete(msg.id);
          resolve(msg);
        }
      } catch (e) {
        console.error('[Wolinex Code] JSON parse error:', e);
      }
    }
  });

  serverProc.stderr.on('data', (d) => {
    const s = d.toString('utf-8');
    if (!s.includes('TRACE')) console.log('[OpenIDEA Engine]', s.trim());
  });

  serverProc.on('exit', (code, sig) => {
    console.log(`[Wolinex Code] Engine exited: code=${code}, sig=${sig}`);
    serverProc = null;
  });
}

function sendRpc(method, params = {}) {
  return new Promise((resolve, reject) => {
    if (!serverProc || !serverProc.stdin) {
      return reject(new Error('OpenIDEA server is not running'));
    }
    const id = nextId++;
    const payload = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    const payloadBuf = Buffer.from(payload, 'utf-8');
    const headerBuf = Buffer.alloc(4);
    headerBuf.writeUInt32LE(payloadBuf.length, 0);

    pendingRequests.set(id, (res) => {
      if (res.error) reject(new Error(res.error.message || 'RPC Error'));
      else resolve(res.result);
    });

    serverProc.stdin.write(headerBuf);
    serverProc.stdin.write(payloadBuf);
  });
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

// IPC Handlers
ipcMain.handle('openidea:init', async () => {
  return { version: '0.1.32', protocol: 2, name: 'Wolinex Code Engine' };
});

ipcMain.handle('openidea:invoke', async (_event, cmd, args) => {
  return sendRpc(cmd, args);
});

ipcMain.handle('openidea:read-dir', async (_event, dirPath) => {
  return sendRpc('vfs/read_dir', { path: dirPath });
});

ipcMain.handle('openidea:doc-open', async (_event, filePath) => {
  return sendRpc('document/open', { path: filePath });
});

ipcMain.handle('openidea:doc-save', async (_event, filePath, content) => {
  return sendRpc('document/save', { path: filePath, content });
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
        // Fallback for single-page app routing
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

app.on('window-all-closed', () => {
  if (serverProc) {
    serverProc.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
