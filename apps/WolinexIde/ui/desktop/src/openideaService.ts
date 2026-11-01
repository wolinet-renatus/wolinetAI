import { spawn, type ChildProcess } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs/promises';
import fsSync from 'node:fs';

export interface ServerInfo {
  version: string;
  protocol: number;
  os: string;
  arch: string;
  home: string;
}

export interface ProjectInfo {
  name: string;
  root: string;
  isGit: boolean;
  trusted: boolean;
  settings: Record<string, unknown>;
}

export class OpenIdeaService {
  private static instance: OpenIdeaService | null = null;
  private proc: ChildProcess | null = null;
  private nextId = 1;
  private pendingRequests = new Map<number, (res: { result?: unknown; error?: { code: number; message: string } }) => void>();
  private stdoutBuffer = Buffer.alloc(0);
  private currentProject: ProjectInfo | null = null;
  private serverInfo: ServerInfo | null = null;
  private isStarting = false;

  public static getInstance(): OpenIdeaService {
    if (!OpenIdeaService.instance) {
      OpenIdeaService.instance = new OpenIdeaService();
    }
    return OpenIdeaService.instance;
  }

  private resolveBinaryPath(): string {
    const candidates = [
      path.join(process.cwd(), 'bin', 'openidea-server'),
      path.join(process.cwd(), 'src', 'bin', 'openidea-server'),
      path.join(process.cwd(), 'apps', 'WolinexIde', 'bin', 'openidea-server'),
      path.join(os.homedir(), 'Documents', 'wolinetai', 'apps', 'WolinexIde', 'bin', 'openidea-server'),
      path.join(os.homedir(), 'Documents', 'wolinetai', 'apps', 'WolinexIde', 'ui', 'desktop', 'src', 'bin', 'openidea-server'),
      path.join(__dirname, 'bin', 'openidea-server'),
      path.join(__dirname, '..', 'bin', 'openidea-server'),
    ];
    for (const c of candidates) {
      if (fsSync.existsSync(c)) {
        return c;
      }
    }
    return candidates[3];
  }

  public async start(): Promise<ServerInfo> {
    if (this.serverInfo && this.proc && !this.proc.killed) {
      return this.serverInfo;
    }
    if (this.isStarting) {
      while (this.isStarting) {
        await new Promise((r) => setTimeout(r, 100));
      }
      if (this.serverInfo) return this.serverInfo;
    }

    this.isStarting = true;
    const binaryPath = this.resolveBinaryPath();
    const serverHome = path.join(os.homedir(), '.openidea');
    await fs.mkdir(path.join(serverHome, 'config'), { recursive: true });
    await fs.mkdir(path.join(serverHome, 'data'), { recursive: true });

    return new Promise((resolve, reject) => {
      try {
        this.proc = spawn(binaryPath, ['--stdio'], {
          stdio: ['pipe', 'pipe', 'pipe'],
          env: {
            ...process.env,
            OPENIDEA_SERVER_HOME: serverHome,
          },
        });

        this.proc.stderr?.on('data', (chunk: Buffer) => {
          console.warn('[OpenIdeaService stderr]', chunk.toString().trim());
        });

        this.proc.stdout?.on('data', (chunk: Buffer) => {
          this.handleStdout(chunk);
        });

        this.proc.on('error', (err) => {
          console.error('[OpenIdeaService] Process error:', err);
          this.isStarting = false;
          reject(err);
        });

        this.proc.on('exit', (code) => {
          console.log(`[OpenIdeaService] Exited with code ${code}`);
          this.proc = null;
          this.serverInfo = null;
          this.isStarting = false;
        });

        // Handshake
        this.request('initialize', { version: 2 })
          .then((res) => {
            this.serverInfo = res.result as ServerInfo;
            this.isStarting = false;
            console.log('✓ [OpenIdeaService] Initialized:', this.serverInfo);
            resolve(this.serverInfo);
          })
          .catch((err) => {
            this.isStarting = false;
            reject(err);
          });
      } catch (err) {
        this.isStarting = false;
        reject(err);
      }
    });
  }

  private handleStdout(chunk: Buffer) {
    this.stdoutBuffer = Buffer.concat([this.stdoutBuffer, chunk]);
    for (;;) {
      const sep = this.stdoutBuffer.indexOf('\r\n\r\n');
      if (sep < 0) return;
      const headerStr = this.stdoutBuffer.subarray(0, sep).toString();
      const match = /Content-Length:\s*(\d+)/i.exec(headerStr);
      if (!match) {
        this.stdoutBuffer = this.stdoutBuffer.subarray(sep + 4);
        continue;
      }
      const len = Number(match[1]);
      if (this.stdoutBuffer.length < sep + 4 + len) return;
      const bodyBytes = this.stdoutBuffer.subarray(sep + 4, sep + 4 + len);
      this.stdoutBuffer = this.stdoutBuffer.subarray(sep + 4 + len);

      try {
        const msg = JSON.parse(bodyBytes.toString());
        if (msg.id != null && this.pendingRequests.has(msg.id)) {
          const handler = this.pendingRequests.get(msg.id);
          this.pendingRequests.delete(msg.id);
          handler?.(msg);
        }
      } catch (e) {
        console.error('[OpenIdeaService] JSON parse error:', e);
      }
    }
  }

  private request(method: string, params: Record<string, unknown>): Promise<{ result?: unknown; error?: { code: number; message: string } }> {
    if (!this.proc || this.proc.killed || !this.proc.stdin) {
      return Promise.reject(new Error('OpenIdeaService process is not running'));
    }
    const id = this.nextId++;
    const payload = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    const header = `Content-Length: ${Buffer.byteLength(payload)}\r\n\r\n`;

    return new Promise((resolve) => {
      this.pendingRequests.set(id, resolve);
      this.proc?.stdin?.write(`${header}${payload}`);
    });
  }

  public async invoke<T = unknown>(cmd: string, args: Record<string, unknown> = {}, window = 'main'): Promise<T> {
    await this.start();
    const res = await this.request('invoke', { window, cmd, args });
    if (res.error) {
      throw new Error(`[OpenIDEA ${cmd}] ${res.error.message} (code: ${res.error.code})`);
    }
    return res.result as T;
  }

  public async openProject(projectPath: string, window = 'main'): Promise<ProjectInfo> {
    const res = await this.invoke<ProjectInfo>('open_project', { path: projectPath }, window);
    this.currentProject = res;
    return res;
  }

  public async getCurrentProject(): Promise<ProjectInfo | null> {
    if (this.currentProject) return this.currentProject;
    return await this.invoke<ProjectInfo | null>('project_current', {});
  }

  public async listFiles(dirPath: string): Promise<Array<{ name: string; path: string; kind: 'dir' | 'file'; size: number }>> {
    return await this.invoke('fs_read_dir', { path: dirPath });
  }

  public async openDocument(filePath: string): Promise<{ text: string; mtimeMs: number; language: string }> {
    try {
      return await this.invoke('doc_open', { path: filePath });
    } catch {
      const text = await fs.readFile(filePath, 'utf-8');
      const stat = await fs.stat(filePath);
      return {
        text,
        mtimeMs: stat.mtimeMs,
        language: path.extname(filePath).replace('.', '') || 'text',
      };
    }
  }

  public async saveDocument(filePath: string, content?: string): Promise<boolean> {
    if (content !== undefined) {
      await fs.writeFile(filePath, content, 'utf-8');
    }
    try {
      await this.invoke('doc_save', { path: filePath });
    } catch {
      // Direct write already completed
    }
    return true;
  }

  public async createFile(filePath: string): Promise<boolean> {
    try {
      await this.invoke('fs_create_file', { path: filePath });
      return true;
    } catch {
      await fs.writeFile(filePath, '', 'utf-8');
      return true;
    }
  }

  public async createDir(dirPath: string): Promise<boolean> {
    try {
      await this.invoke('fs_create_dir', { path: dirPath });
      return true;
    } catch {
      await fs.mkdir(dirPath, { recursive: true });
      return true;
    }
  }

  public async deletePath(targetPath: string): Promise<boolean> {
    try {
      await this.invoke('fs_delete', { path: targetPath });
      return true;
    } catch {
      await fs.rm(targetPath, { recursive: true, force: true });
      return true;
    }
  }

  public async renamePath(fromPath: string, toPath: string): Promise<boolean> {
    try {
      await this.invoke('fs_rename', { from: fromPath, to: toPath });
      return true;
    } catch {
      await fs.rename(fromPath, toPath);
      return true;
    }
  }

  public async getGitStatus(): Promise<Record<string, unknown>> {
    try {
      return await this.invoke('vcs_status', {});
    } catch {
      return { branch: 'main', entries: [] };
    }
  }

  public stop() {
    if (this.proc && !this.proc.killed) {
      this.proc.kill();
      this.proc = null;
      this.serverInfo = null;
    }
  }
}

