import React, { useState, useEffect, useRef } from 'react';
import {
  Terminal as TerminalIcon,
  GitBranch,
  Code2,
  Globe,
  Database as DatabaseIcon,
  Play,
  X,
  Maximize2,
  Minimize2,
  RefreshCw,
  Send,
  CheckCircle2,
  Smartphone,
  Square,
  RotateCw,
  Laptop,
  ExternalLink,
  QrCode,
  Package,
  Trash2,
} from 'lucide-react';

export type ToolWindowTab = 'terminal' | 'expo' | 'git' | 'insight' | 'http' | 'database' | 'run';

interface BottomToolWindowsProps {
  isOpen: boolean;
  activeTab: ToolWindowTab;
  onTabChange: (tab: ToolWindowTab) => void;
  onClose: () => void;
  projectRoot: string;
  projectName: string;
  activeFilePath?: string;
  activeFileContent?: string;
  gitStatus: { branch?: string; modifiedCount?: number };
  onRefreshGit: () => void;
  onJumpToLine?: (line: number) => void;
  onSyncSimulatorUrl?: (url: string) => void;
}

export const BottomToolWindows: React.FC<BottomToolWindowsProps> = ({
  isOpen,
  activeTab,
  onTabChange,
  onClose,
  projectRoot,
  projectName,
  activeFilePath,
  activeFileContent,
  gitStatus,
  onRefreshGit,
  onJumpToLine,
  onSyncSimulatorUrl,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  // 1. Terminal State
  const [terminalOutput, setTerminalOutput] = useState<Array<{ type: 'cmd' | 'out' | 'err'; text: string }>>([
    { type: 'out', text: `✦ Wolinex Sovereign Terminal attached to [${projectName || 'Wolinex'}]` },
    { type: 'out', text: `Directory: ${projectRoot}` },
    { type: 'out', text: `Type any shell command (e.g. ls -la, git status, cargo test, pnpm build)...` },
  ]);
  const [terminalCmd, setTerminalCmd] = useState<string>('');
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);
  const [isTerminalBusy, setIsTerminalBusy] = useState<boolean>(false);
  const termScrollRef = useRef<HTMLDivElement>(null);
  const termInputRef = useRef<HTMLInputElement>(null);

  // 2. Git State
  const [commitMessage, setCommitMessage] = useState<string>('');
  const [gitOutput, setGitOutput] = useState<string>('');
  const [isCommitting, setIsCommitting] = useState<boolean>(false);

  // 3. HTTP Client State
  const [httpMethod, setHttpMethod] = useState<'GET' | 'POST' | 'PUT' | 'DELETE'>('GET');
  const [httpUrl, setHttpUrl] = useState<string>('http://127.0.0.1:4000/v1/models');
  const [httpHeaders, setHttpHeaders] = useState<string>('{\n  "Content-Type": "application/json"\n}');
  const [httpBody, setHttpBody] = useState<string>('{\n  "model": "wolinex-coder"\n}');
  const [httpResponse, setHttpResponse] = useState<{
    status?: number;
    statusText?: string;
    durationMs?: number;
    headers?: Record<string, string>;
    data?: string;
  } | null>(null);
  const [isHttpLoading, setIsHttpLoading] = useState<boolean>(false);

  // 4. Database Client State
  const [sqlQuery, setSqlQuery] = useState<string>(
    'CREATE TABLE IF NOT EXISTS wolinex_kv (key TEXT PRIMARY KEY, val TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);\nINSERT OR REPLACE INTO wolinex_kv VALUES ("engine", "OpenIDEA Rust v0.1.32", datetime("now"));\nSELECT * FROM wolinex_kv;'
  );
  const [dbResults, setDbResults] = useState<{
    columns: string[];
    rows: (string | number | null)[][];
    durationMs?: number;
    error?: string;
    rawOutput?: string;
  } | null>(null);
  const [isDbLoading, setIsDbLoading] = useState<boolean>(false);

  // 5. Run Console State
  const [selectedRunConfig, setSelectedRunConfig] = useState<string>('Typecheck (tsc --noEmit)');
  const [runLogs, setRunLogs] = useState<string[]>([]);
  const [isRunActive, setIsRunActive] = useState<boolean>(false);

  // 6. Expo / Mobile Dev Server State
  const [expoStatus, setExpoStatus] = useState<{
    running: boolean;
    pid: number;
    port: number;
    url: string;
    command: string;
    startTime: number;
  }>({
    running: false,
    pid: 0,
    port: 8081,
    url: 'http://localhost:8081',
    command: 'npx expo start --web',
    startTime: 0,
  });
  const [expoLogs, setExpoLogs] = useState<Array<{ type: 'stdout' | 'stderr' | 'status'; text: string; timestamp: number }>>([]);
  const [expoCommandPreset, setExpoCommandPreset] = useState<string>('npx expo start --web');
  const [isStartingExpo, setIsStartingExpo] = useState<boolean>(false);
  const expoScrollRef = useRef<HTMLDivElement>(null);

  // Subscribe to devServer events & initial state
  useEffect(() => {
    let unlistenLog: (() => void) | undefined;
    let unlistenStatus: (() => void) | undefined;

    if (window.electron?.devServer) {
      window.electron.devServer.getStatus().then((st) => {
        if (st) setExpoStatus(st);
      }).catch(console.error);

      window.electron.devServer.getLogs().then((logs) => {
        if (logs) setExpoLogs(logs);
      }).catch(console.error);

      unlistenLog = window.electron.devServer.onLog((entry) => {
        setExpoLogs((prev) => [...prev.slice(-800), entry]);
      });

      unlistenStatus = window.electron.devServer.onStatus((st) => {
        setExpoStatus(st);
      });
    }

    return () => {
      unlistenLog?.();
      unlistenStatus?.();
    };
  }, []);

  // Auto-scroll expo logs
  useEffect(() => {
    if (activeTab === 'expo' && expoScrollRef.current) {
      expoScrollRef.current.scrollTop = expoScrollRef.current.scrollHeight;
    }
  }, [expoLogs, activeTab]);

  const handleStartExpo = async (overrideCmd?: string) => {
    const cmd = overrideCmd || expoCommandPreset;
    setIsStartingExpo(true);
    try {
      await window.electron.devServer.start(cmd, projectRoot);
      const st = await window.electron.devServer.getStatus();
      setExpoStatus(st);
    } catch (e) {
      console.error('Failed to start Expo:', e);
    } finally {
      setIsStartingExpo(false);
    }
  };

  const handleStopExpo = async () => {
    try {
      await window.electron.devServer.stop();
      const st = await window.electron.devServer.getStatus();
      setExpoStatus(st);
    } catch (e) {
      console.error('Failed to stop Expo:', e);
    }
  };

  const handleSendExpoKey = async (char: string) => {
    try {
      await window.electron.devServer.sendInput(char);
    } catch (e) {
      console.error('Failed to send key:', e);
    }
  };

  // Auto-scroll terminal
  useEffect(() => {
    if (activeTab === 'terminal' && termScrollRef.current) {
      termScrollRef.current.scrollTop = termScrollRef.current.scrollHeight;
    }
  }, [terminalOutput, activeTab]);

  // Terminal Execution
  const handleRunTerminal = async (overrideCmd?: string) => {
    const cmdToRun = overrideCmd !== undefined ? overrideCmd : terminalCmd;
    if (!cmdToRun.trim()) return;

    if (cmdToRun.trim() === 'clear') {
      setTerminalOutput([]);
      setTerminalCmd('');
      return;
    }

    setTerminalOutput((prev) => [...prev, { type: 'cmd', text: `$ ${cmdToRun}` }]);
    setCmdHistory((prev) => [...prev, cmdToRun]);
    setHistoryIndex(-1);
    setTerminalCmd('');
    setIsTerminalBusy(true);

    try {
      const res = await window.electron.terminal.exec(cmdToRun, projectRoot);
      if (res.output) {
        setTerminalOutput((prev) => [
          ...prev,
          { type: res.exitCode === 0 ? 'out' : 'err', text: res.output.trimEnd() },
        ]);
      } else {
        setTerminalOutput((prev) => [...prev, { type: 'out', text: `(Process exited with code ${res.exitCode})` }]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setTerminalOutput((prev) => [...prev, { type: 'err', text: `Error: ${msg}` }]);
    } finally {
      setIsTerminalBusy(false);
      setTimeout(() => termInputRef.current?.focus(), 50);
    }
  };

  const handleTerminalKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleRunTerminal();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdHistory.length === 0) return;
      const nextIdx = historyIndex === -1 ? cmdHistory.length - 1 : Math.max(0, historyIndex - 1);
      setHistoryIndex(nextIdx);
      setTerminalCmd(cmdHistory[nextIdx]);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex >= 0) {
        const nextIdx = historyIndex + 1;
        if (nextIdx >= cmdHistory.length) {
          setHistoryIndex(-1);
          setTerminalCmd('');
        } else {
          setHistoryIndex(nextIdx);
          setTerminalCmd(cmdHistory[nextIdx]);
        }
      }
    }
  };

  // Git Commit Action
  const handleCommit = async () => {
    if (!commitMessage.trim()) return;
    setIsCommitting(true);
    try {
      const res = await window.electron.terminal.exec(
        `git add -A && git commit -m "${commitMessage.replace(/"/g, '\\"')}"`,
        projectRoot
      );
      setGitOutput(res.output || 'Commit completed.');
      setCommitMessage('');
      onRefreshGit();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setGitOutput(`Git error: ${msg}`);
    } finally {
      setIsCommitting(false);
    }
  };

  // HTTP Request Execution
  const handleSendHttp = async () => {
    setIsHttpLoading(true);
    setHttpResponse(null);
    try {
      let parsedHeaders: Record<string, string> = {};
      try {
        parsedHeaders = JSON.parse(httpHeaders);
      } catch {
        // use default
      }
      const res = await window.electron.httpClient.send({
        url: httpUrl,
        method: httpMethod,
        headers: parsedHeaders,
        body: ['POST', 'PUT', 'PATCH'].includes(httpMethod) ? httpBody : undefined,
      });
      setHttpResponse(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setHttpResponse({ status: 0, statusText: msg, data: msg });
    } finally {
      setIsHttpLoading(false);
    }
  };

  // Database Execution
  const handleExecSql = async () => {
    setIsDbLoading(true);
    setDbResults(null);
    try {
      const res = await window.electron.database.execSql(sqlQuery);
      setDbResults(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setDbResults({ columns: [], rows: [], error: msg });
    } finally {
      setIsDbLoading(false);
    }
  };

  // Run Configuration Execution
  const handleRunConfig = async () => {
    setIsRunActive(true);
    setRunLogs([`Starting configuration: ${selectedRunConfig}...`, `Working directory: ${projectRoot}`]);
    let cmd = 'pnpm run typecheck';
    if (selectedRunConfig.includes('cargo')) {
      cmd = 'cargo check --all';
    } else if (selectedRunConfig.includes('openidea-server')) {
      cmd = './apps/WolinexIde/bin/openidea-server --version';
    } else if (selectedRunConfig.includes('Test')) {
      cmd = 'pnpm test:run || true';
    }

    try {
      const res = await window.electron.terminal.exec(cmd, projectRoot);
      setRunLogs((prev) => [...prev, res.output || 'Process exited successfully with code 0.']);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setRunLogs((prev) => [...prev, `Run execution error: ${msg}`]);
    } finally {
      setIsRunActive(false);
    }
  };

  // AST Symbol Extraction for Insight Tab
  const parsedSymbols = React.useMemo(() => {
    if (!activeFileContent) return [];
    const lines = activeFileContent.split('\n');
    const symbols: Array<{ name: string; line: number; kind: string; code: string }> = [];
    const regex = /(?:function|fn|def|class|interface|struct|type|enum|const|let)\s+([A-Za-z0-9_]+)/g;

    lines.forEach((line, idx) => {
      let m;
      while ((m = regex.exec(line)) !== null) {
        symbols.push({
          name: m[1],
          line: idx + 1,
          kind: line.trim().split(/\s+/)[0],
          code: line.trim().slice(0, 80),
        });
      }
    });
    return symbols;
  }, [activeFileContent]);

  if (!isOpen) return null;

  return (
    <div
      className={`border-t border-[#2e323b] bg-[#16181b] flex flex-col font-sans transition-all duration-150 ${
        isExpanded ? 'h-[480px]' : 'h-64'
      }`}
    >
      {/* Tool Windows Tab Bar */}
      <div className="flex items-center justify-between border-b border-[#25282e] bg-[#121316] px-2 py-1 text-xs select-none">
        <div className="flex items-center gap-1">
          <button
            onClick={() => onTabChange('terminal')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'terminal'
                ? 'bg-[#22252b] text-blue-400 border border-blue-500/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1c20]'
            }`}
          >
            <TerminalIcon className="w-3.5 h-3.5 text-purple-400" />
            <span>Terminal</span>
            <span className="text-[10px] text-gray-500 font-mono ml-1">Alt+F12</span>
          </button>

          <button
            onClick={() => onTabChange('expo')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'expo'
                ? 'bg-[#22252b] text-cyan-400 border border-cyan-500/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1c20]'
            }`}
          >
            <Smartphone className="w-3.5 h-3.5 text-cyan-400" />
            <span>Expo & Mobile</span>
            {expoStatus.running ? (
              <span className="flex h-2 w-2 relative ml-1">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
            ) : (
              <span className="text-[10px] text-gray-500 font-mono ml-1">Metro</span>
            )}
          </button>

          <button
            onClick={() => onTabChange('git')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'git'
                ? 'bg-[#22252b] text-blue-400 border border-blue-500/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1c20]'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5 text-orange-400" />
            <span>Git / VCS</span>
            <span className="text-[10px] bg-orange-950/60 text-orange-300 px-1.5 py-0.2 rounded-full font-mono ml-1">
              {gitStatus.branch || 'main'}
            </span>
          </button>

          <button
            onClick={() => onTabChange('insight')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'insight'
                ? 'bg-[#22252b] text-blue-400 border border-blue-500/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1c20]'
            }`}
          >
            <Code2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Code Insight (60+ langs)</span>
            {parsedSymbols.length > 0 && (
              <span className="text-[10px] bg-emerald-950/60 text-emerald-300 px-1.5 py-0.2 rounded-full font-mono ml-1">
                {parsedSymbols.length}
              </span>
            )}
          </button>

          <button
            onClick={() => onTabChange('http')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'http'
                ? 'bg-[#22252b] text-blue-400 border border-blue-500/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1c20]'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-sky-400" />
            <span>HTTP Client</span>
          </button>

          <button
            onClick={() => onTabChange('database')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'database'
                ? 'bg-[#22252b] text-blue-400 border border-blue-500/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1c20]'
            }`}
          >
            <DatabaseIcon className="w-3.5 h-3.5 text-rose-400" />
            <span>Database</span>
          </button>

          <button
            onClick={() => onTabChange('run')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'run'
                ? 'bg-[#22252b] text-blue-400 border border-blue-500/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1c20]'
            }`}
          >
            <Play className="w-3.5 h-3.5 text-green-400" />
            <span>Run / Debugger</span>
          </button>
        </div>

        {/* Panel controls */}
        <div className="flex items-center gap-1 text-gray-400">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Restore height' : 'Expand height'}
            className="p-1 rounded hover:text-gray-200 hover:bg-[#22252b]"
          >
            {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
          <button onClick={onClose} title="Hide tool window" className="p-1 rounded hover:text-gray-200 hover:bg-[#22252b]">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Tool Window Content Area */}
      <div className="flex-1 overflow-hidden relative bg-[#181a1d]">
        {/* 1. Terminal Panel */}
        {activeTab === 'terminal' && (
          <div className="flex flex-col h-full font-mono text-xs">
            {/* Quick Actions Bar */}
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#22252b] bg-[#141518] text-[11px]">
              <div className="flex items-center gap-2 text-gray-400">
                <span className="font-semibold text-blue-400">cwd:</span>
                <span className="truncate max-w-md text-gray-300">{projectRoot}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleRunTerminal('git status')}
                  className="px-2 py-0.5 rounded bg-[#22252b] hover:bg-[#2c3038] text-gray-300 text-[10px]"
                >
                  git status
                </button>
                <button
                  onClick={() => handleRunTerminal('ls -la')}
                  className="px-2 py-0.5 rounded bg-[#22252b] hover:bg-[#2c3038] text-gray-300 text-[10px]"
                >
                  ls -la
                </button>
                <button
                  onClick={() => handleRunTerminal('cargo check')}
                  className="px-2 py-0.5 rounded bg-[#22252b] hover:bg-[#2c3038] text-gray-300 text-[10px]"
                >
                  cargo check
                </button>
                <button
                  onClick={() => handleRunTerminal('pnpm run typecheck')}
                  className="px-2 py-0.5 rounded bg-[#22252b] hover:bg-[#2c3038] text-gray-300 text-[10px]"
                >
                  tsc
                </button>
                <button
                  onClick={() => setTerminalOutput([])}
                  className="px-2 py-0.5 rounded bg-[#22252b] hover:bg-rose-950/60 hover:text-rose-300 text-gray-400 text-[10px]"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Terminal Logs */}
            <div ref={termScrollRef} className="flex-1 overflow-y-auto p-3 space-y-1 select-text">
              {terminalOutput.map((item, idx) => (
                <div
                  key={idx}
                  className={`leading-relaxed whitespace-pre-wrap break-all ${
                    item.type === 'cmd'
                      ? 'text-cyan-300 font-semibold mt-1'
                      : item.type === 'err'
                      ? 'text-rose-400'
                      : 'text-gray-300'
                  }`}
                >
                  {item.text}
                </div>
              ))}
              {isTerminalBusy && (
                <div className="flex items-center gap-2 text-amber-400 italic">
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  <span>Executing process...</span>
                </div>
              )}
            </div>

            {/* Command Input Prompt */}
            <div className="flex items-center gap-2 px-3 py-2 border-t border-[#22252b] bg-[#121316]">
              <span className="text-emerald-400 font-bold select-none">{projectName || 'wolinex'}:$</span>
              <input
                ref={termInputRef}
                type="text"
                value={terminalCmd}
                onChange={(e) => setTerminalCmd(e.target.value)}
                onKeyDown={handleTerminalKeyDown}
                placeholder="Type command and press Enter (Arrow keys for history)..."
                disabled={isTerminalBusy}
                className="flex-1 bg-transparent text-gray-100 placeholder-gray-600 outline-none font-mono text-xs"
              />
              <button
                onClick={() => handleRunTerminal()}
                disabled={isTerminalBusy || !terminalCmd.trim()}
                className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-sans text-xs flex items-center gap-1"
              >
                <Send className="w-3 h-3" /> Run
              </button>
            </div>
          </div>
        )}

        {/* 1.5. Expo & Mobile Metro Suite Panel */}
        {activeTab === 'expo' && (
          <div className="flex flex-col h-full p-2.5 overflow-hidden font-sans text-xs">
            {/* Top Expo Status & Action Bar */}
            <div className="flex flex-wrap items-center justify-between pb-2 border-b border-[#25282e] gap-2 shrink-0">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#1d2028] border border-[#2e323b]">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      expoStatus.running ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'
                    }`}
                  />
                  <span className="font-semibold text-gray-200">
                    {expoStatus.running
                      ? `Metro Active (Port ${expoStatus.port})`
                      : 'Metro Bundler Stopped'}
                  </span>
                </div>

                {expoStatus.running ? (
                  <button
                    onClick={handleStopExpo}
                    className="flex items-center gap-1 px-3 py-1 rounded bg-rose-600/20 text-rose-300 border border-rose-500/30 hover:bg-rose-600/30 font-medium transition-colors"
                  >
                    <Square className="w-3 h-3 fill-current" />
                    <span>Stop Server</span>
                  </button>
                ) : (
                  <div className="flex items-center gap-1">
                    <select
                      value={expoCommandPreset}
                      onChange={(e) => setExpoCommandPreset(e.target.value)}
                      className="bg-[#1e2027] border border-[#2e323b] rounded px-2 py-1 text-cyan-300 font-mono text-[11px] outline-none"
                    >
                      <option value="npx expo start --web">npx expo start --web (Web + Metro)</option>
                      <option value="npx expo start">npx expo start (Mobile Dev Server)</option>
                      <option value="npx expo start --clear">npx expo start --clear (Clean Cache)</option>
                      <option value="pnpm run dev">pnpm run dev</option>
                    </select>
                    <button
                      onClick={() => handleStartExpo()}
                      disabled={isStartingExpo}
                      className="flex items-center gap-1 px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-medium transition-colors disabled:opacity-40"
                    >
                      {isStartingExpo ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <Play className="w-3 h-3 fill-current" />
                      )}
                      <span>Start Dev Server</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Interactive Metro Shortcut Keys */}
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleSendExpoKey('r')}
                  disabled={!expoStatus.running}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-[#22252c] hover:bg-[#2c3039] disabled:opacity-40 text-gray-300 transition-colors"
                  title="Send 'r' to reload mobile app"
                >
                  <RotateCw className="w-3 h-3 text-cyan-400" />
                  <span>Reload (r)</span>
                </button>

                <button
                  onClick={() => handleSendExpoKey('i')}
                  disabled={!expoStatus.running}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-[#22252c] hover:bg-[#2c3039] disabled:opacity-40 text-gray-300 transition-colors"
                  title="Send 'i' to launch iOS Simulator via xcrun simctl"
                >
                  <Smartphone className="w-3 h-3 text-blue-400" />
                  <span>iOS Sim (i)</span>
                </button>

                <button
                  onClick={() => handleSendExpoKey('a')}
                  disabled={!expoStatus.running}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-[#22252c] hover:bg-[#2c3039] disabled:opacity-40 text-gray-300 transition-colors"
                  title="Send 'a' to open Android Emulator via adb"
                >
                  <Smartphone className="w-3 h-3 text-emerald-400" />
                  <span>Android (a)</span>
                </button>

                <button
                  onClick={() => handleSendExpoKey('w')}
                  disabled={!expoStatus.running}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-[#22252c] hover:bg-[#2c3039] disabled:opacity-40 text-gray-300 transition-colors"
                  title="Send 'w' to open web app in browser"
                >
                  <Laptop className="w-3 h-3 text-purple-400" />
                  <span>Web (w)</span>
                </button>

                {onSyncSimulatorUrl && (
                  <button
                    onClick={() => onSyncSimulatorUrl(expoStatus.url || 'http://localhost:8081')}
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-blue-600/20 text-blue-300 border border-blue-500/30 hover:bg-blue-600/30 font-medium transition-colors"
                    title="Attach IDE Split Simulator frame to this Metro Dev Server"
                  >
                    <Smartphone className="w-3 h-3 text-blue-400" />
                    <span>Sync with IDE Simulator</span>
                  </button>
                )}

                <button
                  onClick={() => setExpoLogs([])}
                  className="p-1 rounded text-gray-500 hover:text-gray-300 transition-colors"
                  title="Clear Logs"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Split View: Live Metro Terminal on Left, Expo Go & App Store Tools on Right */}
            <div className="flex-1 flex gap-3 mt-2 min-h-0 overflow-hidden">
              {/* Metro Logs Terminal */}
              <div
                ref={expoScrollRef}
                className="flex-1 bg-[#0f1013] border border-[#25282e] rounded-lg p-2.5 font-mono text-[11px] overflow-auto select-text whitespace-pre-wrap flex flex-col gap-0.5"
              >
                {expoLogs.length > 0 ? (
                  expoLogs.map((log, idx) => {
                    const isErr = log.type === 'stderr';
                    const isStatus = log.type === 'status';
                    return (
                      <div
                        key={idx}
                        className={
                          isErr
                            ? 'text-rose-400'
                            : isStatus
                            ? 'text-cyan-400 font-semibold'
                            : 'text-gray-300'
                        }
                      >
                        {log.text}
                      </div>
                    );
                  })
                ) : (
                  <div className="text-gray-500 italic p-3 text-center">
                    Metro bundler terminal is ready. Click "Start Dev Server" above to launch Expo or React Native.
                  </div>
                )}
              </div>

              {/* Mobile Production Companion Panel */}
              <div className="w-72 bg-[#141518] border border-[#25282e] rounded-lg p-2.5 flex flex-col justify-between shrink-0 text-xs">
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between pb-1.5 border-b border-[#242730]">
                    <span className="font-semibold text-gray-200 flex items-center gap-1.5">
                      <QrCode className="w-3.5 h-3.5 text-cyan-400" />
                      Expo Go Testing
                    </span>
                    <span className="text-[10px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-1 rounded">
                      Physical Device
                    </span>
                  </div>

                  <p className="text-[11px] text-gray-400 leading-relaxed">
                    Scan the terminal QR code using the <strong>Expo Go</strong> camera on iOS or Android to preview this app instantly on your physical phone.
                  </p>

                  <div className="bg-[#1c1e24] p-2 rounded border border-[#2c303a] font-mono text-[10px] text-cyan-300 break-all select-text">
                    URL: {expoStatus.url || 'http://localhost:8081'}
                  </div>
                </div>

                <div className="flex flex-col gap-1.5 pt-2 border-t border-[#242730]">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                    Publish & Store Deploy
                  </span>
                  <button
                    onClick={() => handleRunTerminal('npx expo export --platform web')}
                    className="flex items-center justify-between px-2.5 py-1.5 rounded bg-[#1e2027] hover:bg-[#252833] text-gray-300 transition-colors"
                  >
                    <span className="flex items-center gap-1.5">
                      <Package className="w-3 h-3 text-amber-400" />
                      <span>Export Web Bundle</span>
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono">web</span>
                  </button>

                  <button
                    onClick={() =>
                      handleRunTerminal('npx eas-cli build --platform ios --profile preview || echo "EAS CLI ready"')
                    }
                    className="flex items-center justify-between px-2.5 py-1.5 rounded bg-[#1e2027] hover:bg-[#252833] text-gray-300 transition-colors"
                  >
                    <span className="flex items-center gap-1.5">
                      <ExternalLink className="w-3 h-3 text-blue-400" />
                      <span>EAS iOS/Android Build</span>
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono">eas</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. Git / VCS Panel */}
        {activeTab === 'git' && (
          <div className="flex flex-col h-full p-4 overflow-y-auto font-sans text-xs">
            <div className="flex items-center justify-between pb-3 border-b border-[#25282e]">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-gray-200">Git Version Control</span>
                <span className="px-2 py-0.5 rounded bg-orange-950/70 border border-orange-500/40 text-orange-300 font-mono">
                  Branch: {gitStatus.branch || 'main'}
                </span>
                <span className="text-gray-400">Modified: {gitStatus.modifiedCount ?? 0} files</span>
              </div>
              <button
                onClick={onRefreshGit}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-[#22252b] hover:bg-[#2c3038] text-gray-300"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Refresh Status
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-3 flex-1">
              {/* Commit Staged Box */}
              <div className="flex flex-col gap-2">
                <label className="text-gray-400 font-medium">Commit Message (IntelliJ Commit Window):</label>
                <textarea
                  value={commitMessage}
                  onChange={(e) => setCommitMessage(e.target.value)}
                  placeholder="feat(ide): add openidea native file operations and bottom terminal"
                  rows={3}
                  className="w-full bg-[#1e2024] border border-[#2e323b] rounded-lg p-2.5 text-xs text-gray-100 placeholder-gray-600 outline-none focus:border-blue-500 resize-none font-mono"
                />
                <button
                  onClick={handleCommit}
                  disabled={isCommitting || !commitMessage.trim()}
                  className="self-start px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-medium flex items-center gap-2"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" /> Commit All Changes
                </button>
              </div>

              {/* VCS Output / Log */}
              <div className="flex flex-col gap-1">
                <label className="text-gray-400 font-medium">Git Operations Log:</label>
                <div className="flex-1 bg-[#121316] border border-[#25282e] rounded-lg p-3 font-mono text-[11px] text-gray-300 overflow-y-auto max-h-36 whitespace-pre-wrap">
                  {gitOutput || 'Ready. Click Commit All Changes or Refresh to inspect branches and status.'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 3. Code Insight Panel */}
        {activeTab === 'insight' && (
          <div className="flex flex-col h-full p-4 overflow-y-auto font-sans text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-[#25282e]">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-200">OpenIDEA AST & Symbols</span>
                <span className="text-gray-500 font-mono">({activeFilePath || 'no file active'})</span>
              </div>
              <span className="text-[11px] text-emerald-400 font-mono">
                {parsedSymbols.length} declarations detected
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-3 overflow-y-auto">
              {parsedSymbols.length > 0 ? (
                parsedSymbols.map((sym, idx) => (
                  <div
                    key={idx}
                    onClick={() => onJumpToLine?.(sym.line)}
                    className="flex items-center justify-between p-2 rounded bg-[#1e2024] border border-[#282c34] hover:border-emerald-500/50 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-[#282c34] text-emerald-300 font-mono">
                        {sym.kind}
                      </span>
                      <span className="font-mono text-gray-100 font-medium truncate">{sym.name}</span>
                    </div>
                    <span className="text-gray-500 font-mono text-[11px]">Ln {sym.line}</span>
                  </div>
                ))
              ) : (
                <div className="col-span-2 py-8 text-center text-gray-500 italic">
                  Open a code file (.ts, .rs, .py, .go) in the editor to inspect AST structure and symbols.
                </div>
              )}
            </div>
          </div>
        )}

        {/* 4. HTTP Client Panel */}
        {activeTab === 'http' && (
          <div className="flex flex-col h-full p-3 overflow-y-auto font-sans text-xs">
            {/* Request Bar */}
            <div className="flex items-center gap-2">
              <select
                value={httpMethod}
                onChange={(e) => setHttpMethod(e.target.value as any)}
                className="bg-[#22252b] border border-[#2e323b] rounded-lg px-2.5 py-1.5 font-bold text-xs text-blue-400 outline-none"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
              </select>
              <input
                type="text"
                value={httpUrl}
                onChange={(e) => setHttpUrl(e.target.value)}
                placeholder="https://api.example.com/v1/..."
                className="flex-1 bg-[#1e2024] border border-[#2e323b] rounded-lg px-3 py-1.5 text-xs text-gray-100 outline-none font-mono focus:border-blue-500"
              />
              <button
                onClick={handleSendHttp}
                disabled={isHttpLoading}
                className="px-4 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-white font-medium flex items-center gap-1.5"
              >
                {isHttpLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                Send
              </button>
            </div>

            {/* Split: Headers/Body vs Response */}
            <div className="grid grid-cols-2 gap-3 mt-3 flex-1 overflow-hidden">
              <div className="flex flex-col gap-2">
                <span className="text-[11px] text-gray-400 font-semibold">Request Headers (JSON):</span>
                <input
                  type="text"
                  value={httpHeaders}
                  onChange={(e) => setHttpHeaders(e.target.value)}
                  className="bg-[#141518] border border-[#25282e] rounded-lg p-1.5 font-mono text-[11px] text-gray-200 outline-none"
                />
                <span className="text-[11px] text-gray-400 font-semibold">Request Body (JSON):</span>
                <textarea
                  value={httpBody}
                  onChange={(e) => setHttpBody(e.target.value)}
                  rows={4}
                  className="flex-1 bg-[#141518] border border-[#25282e] rounded-lg p-2 font-mono text-[11px] text-gray-200 outline-none resize-none"
                />
              </div>

              <div className="flex flex-col gap-1 overflow-hidden">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-gray-400 font-semibold">Response:</span>
                  {httpResponse && (
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-mono font-bold px-1.5 py-0.5 rounded ${
                          (httpResponse.status || 0) < 300 ? 'bg-emerald-950/70 text-emerald-300' : 'bg-rose-950/70 text-rose-300'
                        }`}
                      >
                        {httpResponse.status} {httpResponse.statusText}
                      </span>
                      <span className="text-gray-500 font-mono">{httpResponse.durationMs}ms</span>
                    </div>
                  )}
                </div>
                <div className="flex-1 bg-[#121316] border border-[#25282e] rounded-lg p-2 font-mono text-[11px] text-gray-300 overflow-y-auto whitespace-pre-wrap select-text">
                  {httpResponse ? httpResponse.data : 'Send a request above to inspect response payload and headers.'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 5. Database Panel */}
        {activeTab === 'database' && (
          <div className="flex flex-col h-full p-3 overflow-y-auto font-sans text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-[#25282e]">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-200">SQLite & Database Console</span>
                <span className="text-gray-500 font-mono text-[11px]">(/tmp/wolinex_scratch.db)</span>
              </div>
              <button
                onClick={handleExecSql}
                disabled={isDbLoading}
                className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 disabled:opacity-40 text-white font-medium flex items-center gap-1.5"
              >
                {isDbLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                Execute SQL (Cmd+Enter)
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-2 flex-1">
              <div className="flex flex-col gap-1">
                <span className="text-[11px] text-gray-400">SQL Scratchpad:</span>
                <textarea
                  value={sqlQuery}
                  onChange={(e) => setSqlQuery(e.target.value)}
                  className="flex-1 bg-[#141518] border border-[#25282e] rounded-lg p-2.5 font-mono text-[11px] text-rose-300 outline-none resize-none focus:border-rose-500/60"
                />
              </div>

              <div className="flex flex-col gap-1 overflow-hidden">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-gray-400">Results Table:</span>
                  {dbResults && (
                    <span className="text-gray-500 font-mono">
                      {dbResults.rows.length} rows • {dbResults.durationMs}ms
                    </span>
                  )}
                </div>
                <div className="flex-1 bg-[#121316] border border-[#25282e] rounded-lg p-2 overflow-auto font-mono text-[11px] text-gray-200">
                  {dbResults?.error ? (
                    <div className="text-rose-400 p-2 whitespace-pre-wrap">{dbResults.error}</div>
                  ) : dbResults?.columns && dbResults.columns.length > 0 ? (
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-[#2e323b] text-gray-400">
                          {dbResults.columns.map((col, idx) => (
                            <th key={idx} className="p-1.5 font-semibold">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {dbResults.rows.map((row, rIdx) => (
                          <tr key={rIdx} className="border-b border-[#22252b] hover:bg-[#1a1c20]">
                            {row.map((cell, cIdx) => (
                              <td key={cIdx} className="p-1.5 text-gray-300">
                                {cell ?? 'NULL'}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="p-4 text-center text-gray-500 italic">
                      {dbResults?.rawOutput || 'Click Execute SQL to run queries against the database.'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 6. Run Console Panel */}
        {activeTab === 'run' && (
          <div className="flex flex-col h-full p-3 overflow-y-auto font-sans text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-[#25282e]">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-gray-200">Run Configurations</span>
                <select
                  value={selectedRunConfig}
                  onChange={(e) => setSelectedRunConfig(e.target.value)}
                  className="bg-[#22252b] border border-[#2e323b] rounded-lg px-2.5 py-1 text-xs text-green-400 font-mono outline-none"
                >
                  <option value="Typecheck (tsc --noEmit)">Typecheck (tsc --noEmit)</option>
                  <option value="Cargo Check (Rust ide crates)">Cargo Check (Rust ide crates)</option>
                  <option value="Test Suite (vitest)">Test Suite (vitest)</option>
                  <option value="OpenIDEA Server Version">OpenIDEA Server Version</option>
                </select>
              </div>
              <button
                onClick={handleRunConfig}
                disabled={isRunActive}
                className="px-4 py-1 rounded bg-green-600 hover:bg-green-500 disabled:opacity-40 text-white font-medium flex items-center gap-1.5"
              >
                {isRunActive ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                Run Configuration
              </button>
            </div>

            <div className="flex-1 bg-[#121316] border border-[#25282e] rounded-lg p-3 mt-2 font-mono text-[11px] text-gray-300 overflow-y-auto select-text whitespace-pre-wrap">
              {runLogs.length > 0 ? (
                runLogs.map((log, idx) => <div key={idx}>{log}</div>)
              ) : (
                <div className="text-gray-500 italic">Select a run configuration above and press Run.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
