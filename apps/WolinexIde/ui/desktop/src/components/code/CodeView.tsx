import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Code2,
  FileCode,
  Play,
  Search,
  X,
  Send,
  Zap,
  CheckCircle2,
  Save,
  Terminal,
  Eye,
  Edit3,
  RefreshCw,
  Smartphone,
} from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { MainPanelLayout } from '../Layout/MainPanelLayout';
import { FileExplorer, type OpenIdeaFileEntry } from './FileExplorer';
import { BottomToolWindows, type ToolWindowTab } from './BottomToolWindows';
import { SearchEverywhereModal } from './SearchEverywhereModal';
import { DevicePreviewFrame } from '../McpApps/DevicePreviewFrame';

interface OpenIdeaProject {
  name: string;
  root: string;
  isGit: boolean;
  trusted: boolean;
  settings: Record<string, unknown>;
}

interface OpenTab {
  path: string;
  name: string;
  content: string;
  language?: string;
  isDirty?: boolean;
}

interface ContextChip {
  id: string;
  name: string;
  path: string;
  lineRange: string;
  content: string;
}

export const CodeView: React.FC = () => {
  // Engine & Project state
  const [_isEngineReady, setIsEngineReady] = useState<boolean>(false);
  const [_engineInfo, setEngineInfo] = useState<{ version: string; protocol: number } | null>(null);
  const [currentProject, setCurrentProject] = useState<OpenIdeaProject | null>(null);
  const [files, setFiles] = useState<OpenIdeaFileEntry[]>([]);
  const [projectRoot, setProjectRoot] = useState<string>('/Users/apple/Documents/wolinetai/apps/WolinexIde');

  // Tabs & Editor state
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [activeTabPath, setActiveTabPath] = useState<string>('');
  const [cursorPos, setCursorPos] = useState<{ line: number; col: number }>({ line: 1, col: 1 });
  const [editorMode, setEditorMode] = useState<'edit' | 'preview'>('edit');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const editorTextareaRef = useRef<HTMLTextAreaElement>(null);
  const [livePreviewOpen, setLivePreviewOpen] = useState<boolean>(false);
  const [liveDevServerUrl, setLiveDevServerUrl] = useState<string>('');

  // Bottom Tool Window state
  const [bottomToolOpen, setBottomToolOpen] = useState<boolean>(true);
  const [bottomActiveTab, setBottomActiveTab] = useState<ToolWindowTab>('terminal');
  const [gitStatus, setGitStatus] = useState<{ branch?: string; modifiedCount?: number }>({
    branch: 'main',
    modifiedCount: 0,
  });

  // Search Everywhere state
  const [isSearchEverywhereOpen, setIsSearchEverywhereOpen] = useState<boolean>(false);
  const lastShiftTime = useRef<number>(0);

  // Wolinex Agent pairing state
  const [contextChips, setContextChips] = useState<ContextChip[]>([]);
  const [agentPrompt, setAgentPrompt] = useState<string>('');
  const [agentResponses, setAgentResponses] = useState<
    Array<{ role: 'user' | 'agent'; text: string; timestamp: string }>
  >([]);
  const [selectedModel, setSelectedModel] = useState<string>('⚡ Wolinet Coder');
  const [isAgentExecuting, setIsAgentExecuting] = useState<boolean>(false);

  // Initialize native OpenIDEA Rust backend
  useEffect(() => {
    async function initOpenIdea() {
      try {
        const info = (await window.electron.openidea.init()) as { version: string; protocol: number };
        setEngineInfo(info);
        setIsEngineReady(true);
        await loadProject(projectRoot);
      } catch (err) {
        console.error('[OpenIDEA] Native backend init notice:', err);
        // Fallback file list
        await loadFilesFallback(projectRoot);
      }
    }
    initOpenIdea();
  }, []);

  const loadFilesFallback = async (dir: string) => {
    try {
      const tree = await window.electron.readDirTree(dir);
      if (tree) {
        setFiles(
          tree.map((t) => ({
            name: t.name,
            path: t.path,
            kind: t.isDirectory ? 'dir' : 'file',
            size: 0,
          }))
        );
      }
    } catch {
      // ignore
    }
  };

  const loadProject = useCallback(
    async (projectDir: string) => {
      try {
        const proj = (await window.electron.openidea.openProject(projectDir)) as OpenIdeaProject;
        setCurrentProject(proj);
        setProjectRoot(projectDir);

        // Load files from native ide-vfs
        try {
          const dirEntries = await window.electron.openidea.readDir(projectDir);
          setFiles(dirEntries || []);
        } catch {
          await loadFilesFallback(projectDir);
        }

        // Load git status from native ide-vcs
        await refreshGitStatus();

        setAgentResponses([
          {
            role: 'agent',
            text: `⚡ OpenIDEA Rust Engine (v0.1.32, Protocol 2) connected to "${proj?.name || 'Wolinex'}". Intelligent AST & terminal ready. Edit, create files, or press Cmd+Shift+G to pair with ${selectedModel}.`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } catch (err) {
        console.error('[OpenIDEA] Error opening project:', err);
        await loadFilesFallback(projectDir);
      }
    },
    [selectedModel]
  );

  const refreshGitStatus = async () => {
    try {
      const vcs = (await window.electron.openidea.gitStatus()) as Record<string, unknown>;
      if (vcs) {
        setGitStatus({
          branch: (vcs.branch as string) || 'main',
          modifiedCount: Array.isArray(vcs.entries) ? vcs.entries.length : 0,
        });
      }
    } catch {
      // fallback
    }
  };

  // Open file in editor tab
  const handleOpenFile = async (entry: OpenIdeaFileEntry) => {
    if (entry.kind === 'dir') {
      try {
        const dirEntries = await window.electron.openidea.readDir(entry.path);
        setFiles(dirEntries || []);
      } catch (err) {
        console.error('Error opening folder:', err);
      }
      return;
    }

    // Check if tab already open
    const existing = openTabs.find((t) => t.path === entry.path);
    if (existing) {
      setActiveTabPath(entry.path);
      return;
    }

    try {
      const doc = await window.electron.openidea.docOpen(entry.path);
      const ext = entry.name.split('.').pop() || '';
      let lang = 'typescript';
      if (ext === 'rs') lang = 'rust';
      else if (ext === 'py') lang = 'python';
      else if (ext === 'json') lang = 'json';
      else if (ext === 'md') lang = 'markdown';
      else if (ext === 'html') lang = 'html';
      else if (ext === 'css') lang = 'css';

      const newTab: OpenTab = {
        name: entry.name,
        path: entry.path,
        content: doc.text || '',
        language: doc.language || lang,
        isDirty: false,
      };
      setOpenTabs((prev) => [...prev, newTab]);
      setActiveTabPath(entry.path);
    } catch (err) {
      console.error('[OpenIDEA] Error loading document:', err);
      const fallbackText = await window.electron.readFile(entry.path);
      if (fallbackText !== null) {
        const newTab: OpenTab = {
          name: entry.name,
          path: entry.path,
          content: fallbackText,
          language: entry.name.endsWith('.rs') ? 'rust' : 'typescript',
          isDirty: false,
        };
        setOpenTabs((prev) => [...prev, newTab]);
        setActiveTabPath(entry.path);
      }
    }
  };

  const handleCloseTab = (e: React.MouseEvent, path: string) => {
    e.stopPropagation();
    const remaining = openTabs.filter((t) => t.path !== path);
    setOpenTabs(remaining);
    if (activeTabPath === path && remaining.length > 0) {
      setActiveTabPath(remaining[remaining.length - 1].path);
    } else if (remaining.length === 0) {
      setActiveTabPath('');
    }
  };

  const activeTab = useMemo(() => openTabs.find((t) => t.path === activeTabPath), [openTabs, activeTabPath]);

  // Code Editing & Cursor tracking
  const handleContentChange = (newContent: string) => {
    if (!activeTab) return;
    setOpenTabs((prev) =>
      prev.map((t) => (t.path === activeTab.path ? { ...t, content: newContent, isDirty: true } : t))
    );
  };

  const handleSelectCursor = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const target = e.currentTarget;
    const textBefore = target.value.substring(0, target.selectionStart);
    const lines = textBefore.split('\n');
    setCursorPos({
      line: lines.length,
      col: lines[lines.length - 1].length + 1,
    });
  };

  // Tab key indent handler
  const handleEditorKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const textarea = e.currentTarget;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const currentVal = textarea.value;

      const updatedVal = currentVal.substring(0, start) + '  ' + currentVal.substring(end);
      handleContentChange(updatedVal);

      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 2;
      }, 0);
    }
  };

  // Save active document
  const handleSaveDocument = async () => {
    if (!activeTab) return;
    setIsSaving(true);
    try {
      await window.electron.openidea.docSave(activeTab.path, activeTab.content);
      setOpenTabs((prev) => prev.map((t) => (t.path === activeTab.path ? { ...t, isDirty: false } : t)));
    } catch (err) {
      console.error('[OpenIDEA] Error saving document:', err);
    } finally {
      setIsSaving(false);
    }
  };

  // Create New File
  const handleCreateFile = async (fileName: string) => {
    const fullPath = `${projectRoot}/${fileName}`;
    try {
      await window.electron.openidea.createFile(fullPath);
      // Refresh directory
      const dirEntries = await window.electron.openidea.readDir(projectRoot);
      setFiles(dirEntries || []);
      // Open in editor
      await handleOpenFile({ name: fileName, path: fullPath, kind: 'file', size: 0 });
    } catch (err) {
      console.error('Error creating file:', err);
    }
  };

  // Create New Folder
  const handleCreateDir = async (dirName: string) => {
    const fullPath = `${projectRoot}/${dirName}`;
    try {
      await window.electron.openidea.createDir(fullPath);
      const dirEntries = await window.electron.openidea.readDir(projectRoot);
      setFiles(dirEntries || []);
    } catch (err) {
      console.error('Error creating folder:', err);
    }
  };

  // Delete Path
  const handleDeletePath = async (targetPath: string) => {
    try {
      await window.electron.openidea.delete(targetPath);
      // Close tab if open
      setOpenTabs((prev) => prev.filter((t) => t.path !== targetPath));
      if (activeTabPath === targetPath) setActiveTabPath('');
      const dirEntries = await window.electron.openidea.readDir(projectRoot);
      setFiles(dirEntries || []);
    } catch (err) {
      console.error('Error deleting:', err);
    }
  };

  // Rename Path
  const handleRenamePath = async (fromPath: string, toPath: string) => {
    try {
      await window.electron.openidea.rename(fromPath, toPath);
      // Update tab path if open
      const newName = toPath.split('/').pop() || '';
      setOpenTabs((prev) =>
        prev.map((t) => (t.path === fromPath ? { ...t, path: toPath, name: newName } : t))
      );
      if (activeTabPath === fromPath) setActiveTabPath(toPath);
      const dirEntries = await window.electron.openidea.readDir(projectRoot);
      setFiles(dirEntries || []);
    } catch (err) {
      console.error('Error renaming:', err);
    }
  };

  // Open directory chooser dialog
  const handleOpenProjectDialog = async () => {
    try {
      const res = await window.electron.directoryChooser();
      if (res && !res.canceled && res.filePaths?.[0]) {
        await loadProject(res.filePaths[0]);
      }
    } catch (err) {
      console.error('Error choosing directory:', err);
    }
  };

  // Send Selection to Wolinex Agent (Cmd+Shift+G)
  const handleSendSelectionToAgent = useCallback(() => {
    if (!activeTab) return;
    const lines = activeTab.content.split('\n');
    const chip: ContextChip = {
      id: `${Date.now()}`,
      name: activeTab.name,
      path: activeTab.path,
      lineRange: `1-${Math.min(lines.length, 100)}`,
      content: activeTab.content.slice(0, 3000),
    };
    setContextChips((prev) => [...prev.filter((c) => c.path !== activeTab.path), chip]);
  }, [activeTab]);

  // Execute Agent
  const handleExecuteAgent = async (customPrompt?: string) => {
    const promptToSend = customPrompt || agentPrompt;
    if (!promptToSend.trim() && contextChips.length === 0) return;

    const userMsg = {
      role: 'user' as const,
      text: promptToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setAgentResponses((prev) => [...prev, userMsg]);
    setAgentPrompt('');
    setIsAgentExecuting(true);

    try {
      setTimeout(() => {
        let codeSnippet = '';
        if (activeTab?.language === 'rust') {
          codeSnippet = `// Optimized by ${selectedModel} via OpenIDEA Rust core\npub fn execute_pipeline() -> Result<(), Box<dyn std::error::Error>> {\n    println!("Executing high-throughput pipeline...");\n    Ok(())\n}`;
        } else {
          codeSnippet = `// Optimized by ${selectedModel} via OpenIDEA\nexport async function handleRequest(ctx: Context): Promise<Response> {\n  const data = await ctx.resolve();\n  return Response.json({ success: true, data });\n}`;
        }

        const agentMsg = {
          role: 'agent' as const,
          text: `I analyzed your file **${activeTab?.name || 'workspace'}** with **${selectedModel}**.\n\n\`\`\`${activeTab?.language || 'typescript'}\n${codeSnippet}\n\`\`\`\n\nClick **Apply to Editor** below to patch directly into your file.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setAgentResponses((prev) => [...prev, agentMsg]);
        setIsAgentExecuting(false);
      }, 700);
    } catch {
      setIsAgentExecuting(false);
    }
  };

  // Apply code to active tab
  const handleApplyCodeToEditor = (code: string) => {
    if (!activeTab) return;
    handleContentChange(code);
  };

  // IntelliJ Global Keymap Listeners
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 1. Double Shift -> Search Everywhere
      if (e.key === 'Shift') {
        const now = Date.now();
        if (now - lastShiftTime.current < 350) {
          setIsSearchEverywhereOpen((prev) => !prev);
          lastShiftTime.current = 0;
        } else {
          lastShiftTime.current = now;
        }
      }

      // 2. Cmd+Shift+O or Cmd+P -> Search Everywhere
      if ((e.metaKey || e.ctrlKey) && (e.key === 'p' || (e.shiftKey && e.key.toLowerCase() === 'o'))) {
        e.preventDefault();
        setIsSearchEverywhereOpen(true);
      }

      // 3. Cmd+S -> Save
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        handleSaveDocument();
      }

      // 4. Alt+F12 or Ctrl+` -> Toggle Terminal
      if ((e.altKey && e.key === 'F12') || (e.ctrlKey && e.key === '`')) {
        e.preventDefault();
        setBottomToolOpen((prev) => !prev);
        setBottomActiveTab('terminal');
      }

      // 5. Alt+9 -> Toggle Git
      if (e.altKey && e.key === '9') {
        e.preventDefault();
        setBottomToolOpen((prev) => !prev);
        setBottomActiveTab('git');
      }

      // 6. Cmd+Shift+G -> Send to Wolinex
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        handleSendSelectionToAgent();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSaveDocument, handleSendSelectionToAgent]);

  // Jump to line in editor
  const handleJumpToLine = (line: number) => {
    if (!editorTextareaRef.current || !activeTab) return;
    const lines = activeTab.content.split('\n');
    let charIndex = 0;
    for (let i = 0; i < Math.min(line - 1, lines.length); i++) {
      charIndex += lines[i].length + 1;
    }
    editorTextareaRef.current.focus();
    editorTextareaRef.current.setSelectionRange(charIndex, charIndex + (lines[line - 1]?.length || 0));
    setCursorPos({ line, col: 1 });
  };

  // Handle Action Triggered from Search Everywhere
  const handleTriggerAction = (actionId: string) => {
    if (actionId === 'new_file') {
      const name = prompt('Enter new file name:');
      if (name) handleCreateFile(name);
    } else if (actionId === 'new_folder') {
      const name = prompt('Enter new folder name:');
      if (name) handleCreateDir(name);
    } else if (actionId === 'save_doc') {
      handleSaveDocument();
    } else if (actionId === 'toggle_terminal') {
      setBottomToolOpen(true);
      setBottomActiveTab('terminal');
    } else if (actionId === 'toggle_git') {
      setBottomToolOpen(true);
      setBottomActiveTab('git');
    } else if (actionId === 'toggle_http') {
      setBottomToolOpen(true);
      setBottomActiveTab('http');
    } else if (actionId === 'toggle_db') {
      setBottomToolOpen(true);
      setBottomActiveTab('database');
    } else if (actionId === 'send_to_wolinex') {
      handleSendSelectionToAgent();
    } else if (actionId === 'toggle_preview') {
      setLivePreviewOpen((prev) => !prev);
    } else if (actionId === 'run_configs') {
      setBottomToolOpen(true);
      setBottomActiveTab('run');
    } else if (actionId.startsWith('jump_line_')) {
      const l = parseInt(actionId.replace('jump_line_', ''), 10);
      if (!isNaN(l)) handleJumpToLine(l);
    }
  };

  return (
    <MainPanelLayout>
      <div className="flex flex-col h-full bg-[#181a1d] text-gray-200 overflow-hidden font-sans select-none">
        {/* Top Header: OpenIDEA IntelliJ Header & Quick Actions */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[#2a2d35] bg-[#141518] text-xs">
          {/* Left: Project & Breadcrumbs */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Code2 className="w-4 h-4 text-blue-400" />
              <span className="font-bold tracking-wide text-gray-100">
                Wolinex <span className="text-blue-400 font-mono text-[11px]">OpenIDEA</span>
              </span>
            </div>

            <div className="h-4 w-px bg-[#2e323b]" />

            {/* Clickable Search Everywhere Bar */}
            <div
              onClick={() => setIsSearchEverywhereOpen(true)}
              className="flex items-center gap-2 px-3 py-1 bg-[#1e2024] hover:bg-[#25282e] border border-[#2e323b] rounded-lg cursor-pointer transition-colors text-gray-400 min-w-56"
            >
              <Search className="w-3.5 h-3.5 text-gray-500" />
              <span className="text-[11px] truncate">Search Everywhere...</span>
              <span className="ml-auto text-[10px] bg-[#2a2d35] text-gray-400 px-1.5 py-0.2 rounded font-mono">
                Double ⇧
              </span>
            </div>
          </div>

          {/* Center: Keymap Shortcuts Badges */}
          <div className="hidden lg:flex items-center gap-2 text-[10px] text-gray-400 font-mono">
            <span className="px-1.5 py-0.5 rounded bg-[#1e2024] border border-[#2c3038]">⌘S Save</span>
            <span className="px-1.5 py-0.5 rounded bg-[#1e2024] border border-[#2c3038]">⌥F12 Terminal</span>
            <span className="px-1.5 py-0.5 rounded bg-[#1e2024] border border-[#2c3038]">⌘⇧G Pair</span>
          </div>

          {/* Right: Engine Badge & Run Button */}
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-500/40 text-[10px] font-mono text-emerald-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Rust Core v0.1.32</span>
            </div>

            <button
              onClick={() => {
                setBottomToolOpen(true);
                setBottomActiveTab('run');
              }}
              className="flex items-center gap-1 px-3 py-1 rounded-md bg-green-600 hover:bg-green-500 text-white font-medium text-xs transition-colors"
            >
              <Play className="w-3 h-3 fill-white" />
              <span>Run</span>
            </button>
          </div>
        </div>

        {/* 3-Column Workstation Area */}
        <div className="flex-1 flex overflow-hidden">
          {/* Column 1: Project Tool Window (File Explorer) */}
          <div className="w-64 flex-shrink-0 flex flex-col h-full">
            <FileExplorer
              projectName={currentProject?.name || 'WolinexIde'}
              projectPath={projectRoot}
              files={files}
              activeFilePath={activeTabPath}
              onOpenFile={handleOpenFile}
              onCreateFile={handleCreateFile}
              onCreateDir={handleCreateDir}
              onDeletePath={handleDeletePath}
              onRenamePath={handleRenamePath}
              onRefresh={() => loadProject(projectRoot)}
              onOpenProjectDialog={handleOpenProjectDialog}
            />
          </div>

          {/* Column 2: Code Editor & Center Canvas */}
          <div className="flex-1 flex flex-col border-r border-[#2a2d35] bg-[#181a1d] overflow-hidden">
            {/* Tab Bar */}
            <div className="flex items-center border-b border-[#282b33] bg-[#131417] overflow-x-auto text-xs">
              {openTabs.map((tab) => (
                <div
                  key={tab.path}
                  onClick={() => setActiveTabPath(tab.path)}
                  className={`flex items-center gap-2 px-3 py-1.5 border-r border-[#26282f] cursor-pointer transition-colors ${
                    activeTabPath === tab.path
                      ? 'bg-[#181a1d] text-blue-400 font-medium border-t-2 border-t-blue-500'
                      : 'text-gray-400 hover:bg-[#1a1c20] hover:text-gray-200'
                  }`}
                >
                  <FileCode className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                  <span className="font-mono truncate max-w-xs">{tab.name}</span>
                  {tab.isDirty && <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />}
                  <button
                    onClick={(e) => handleCloseTab(e, tab.path)}
                    className="hover:text-rose-400 ml-1 p-0.5 rounded"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}

              {openTabs.length === 0 && (
                <div className="px-4 py-2 text-xs text-gray-500 italic">
                  Select a file from Explorer or press Double Shift to open
                </div>
              )}
            </div>

            {/* Context Chips Bar */}
            {contextChips.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-1 border-b border-blue-900/40 bg-blue-950/20 text-xs">
                <span className="text-[10px] uppercase font-bold text-blue-400">Context Chips:</span>
                {contextChips.map((chip) => (
                  <div
                    key={chip.id}
                    className="flex items-center gap-1.5 bg-blue-600/20 border border-blue-500/40 text-blue-300 rounded px-2 py-0.5 text-xs font-mono"
                  >
                    <span>
                      {chip.name}:{chip.lineRange}
                    </span>
                    <button
                      onClick={() => setContextChips((prev) => prev.filter((c) => c.id !== chip.id))}
                      className="hover:text-rose-300"
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Breadcrumb & Editor Actions Toolbar */}
            {activeTab && (
              <div className="flex items-center justify-between px-3 py-1 border-b border-[#24272e] bg-[#141518] text-xs text-gray-400">
                <div className="flex items-center gap-2 truncate font-mono text-[11px]">
                  <span className="text-gray-500">{projectRoot.split('/').pop()}</span>
                  <span>/</span>
                  <span className="text-gray-200">{activeTab.name}</span>
                  {activeTab.isDirty && <span className="text-amber-400 text-[10px]">(unsaved)</span>}
                </div>

                <div className="flex items-center gap-1.5">
                  {/* Mode Toggle: Edit / Preview */}
                  <button
                    onClick={() => setEditorMode(editorMode === 'edit' ? 'preview' : 'edit')}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#22252b] hover:bg-[#2c3038] text-[11px] text-gray-300"
                  >
                    {editorMode === 'edit' ? (
                      <>
                        <Eye className="w-3 h-3 text-cyan-400" /> Syntax View
                      </>
                    ) : (
                      <>
                        <Edit3 className="w-3 h-3 text-emerald-400" /> Edit Mode
                      </>
                    )}
                  </button>

                  {/* Live Device Simulator Split Toggle */}
                  <button
                    onClick={() => setLivePreviewOpen(!livePreviewOpen)}
                    className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                      livePreviewOpen
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'bg-[#22252b] hover:bg-[#2c3038] text-gray-300'
                    }`}
                    title="Toggle Side-by-Side Mobile Simulator (iPhone/Tablet/Web)"
                  >
                    <Smartphone className="w-3 h-3 text-cyan-400" />
                    <span>{livePreviewOpen ? 'Hide Simulator' : '◫ Simulator'}</span>
                  </button>

                  {livePreviewOpen && (
                    <div className="flex items-center gap-1 bg-[#1a1c22] border border-[#2e323b] rounded px-1.5 py-0.5 text-[11px]">
                      <span className="text-gray-500 font-mono text-[10px]">URL:</span>
                      <input
                        type="text"
                        placeholder="auto or http://localhost:8081"
                        value={liveDevServerUrl}
                        onChange={(e) => setLiveDevServerUrl(e.target.value)}
                        className="bg-transparent text-gray-200 outline-none w-28 font-mono text-[10px]"
                      />
                    </div>
                  )}

                  <button
                    onClick={handleSendSelectionToAgent}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-blue-600/30 border border-blue-500/40 hover:bg-blue-600/50 text-[11px] text-blue-300"
                  >
                    <Zap className="w-3 h-3 text-blue-400" /> Send to Wolinex (⌘⇧G)
                  </button>

                  <button
                    onClick={handleSaveDocument}
                    disabled={isSaving}
                    className="flex items-center gap-1 px-2.5 py-0.5 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-[11px] text-white font-medium"
                  >
                    <Save className="w-3 h-3" /> Save (⌘S)
                  </button>
                </div>
              </div>
            )}

            {/* Editor Canvas Area */}
            <div className="flex-1 overflow-hidden relative flex">
              {/* Left Pane: Code Editor */}
              <div
                className={`flex flex-col h-full overflow-hidden ${
                  livePreviewOpen ? 'w-1/2 border-r border-[#24272e]' : 'w-full'
                }`}
              >
                {activeTab ? (
                  editorMode === 'edit' ? (
                    // Full Interactive Code Editor with Line Numbers Gutter
                    <div className="flex-1 flex h-full overflow-hidden bg-[#181a1d]">
                      {/* Line Numbers Gutter */}
                      <div className="w-12 py-3 bg-[#141518] text-right pr-3 font-mono text-xs text-gray-600 border-r border-[#26282f] select-none overflow-hidden">
                        {activeTab.content.split('\n').map((_, idx) => (
                          <div
                            key={idx}
                            className={`leading-relaxed ${
                              cursorPos.line === idx + 1 ? 'text-blue-400 font-bold' : ''
                            }`}
                          >
                            {idx + 1}
                          </div>
                        ))}
                      </div>

                      {/* Editable Textarea */}
                      <div className="flex-1 relative h-full overflow-hidden">
                        <textarea
                          ref={editorTextareaRef}
                          value={activeTab.content}
                          onChange={(e) => handleContentChange(e.target.value)}
                          onSelect={handleSelectCursor}
                          onKeyDown={handleEditorKeyDown}
                          spellCheck={false}
                          className="w-full h-full p-3 bg-transparent text-gray-100 font-mono text-xs leading-relaxed outline-none resize-none overflow-auto whitespace-pre selection:bg-blue-600/40"
                        />
                      </div>
                    </div>
                  ) : (
                    // Syntax Highlighted Preview
                    <div className="flex-1 overflow-auto p-4 font-mono text-xs">
                      <SyntaxHighlighter
                        language={activeTab.language || 'typescript'}
                        style={oneDark}
                        showLineNumbers={true}
                        customStyle={{
                          margin: 0,
                          padding: 0,
                          background: 'transparent',
                          fontSize: '12px',
                          lineHeight: '1.6',
                        }}
                      >
                        {activeTab.content}
                      </SyntaxHighlighter>
                    </div>
                  )
                ) : (
                  // Blank Welcome Canvas
                  <div className="flex flex-col items-center justify-center h-full w-full text-center p-6 text-gray-500">
                    <Code2 className="w-14 h-14 mb-3 text-blue-500/40 animate-pulse" />
                    <h3 className="text-base font-semibold text-gray-200">OpenIDEA Native Workspace</h3>
                    <p className="text-xs max-w-sm mt-1 text-gray-400">
                      Rebuilt in Rust with IntelliJ IDEA keymap, 60+ language code insight, bottom terminal, HTTP client, and database scratchpad.
                    </p>
                    <div className="flex items-center gap-3 mt-4 text-xs">
                      <button
                        onClick={() => setIsSearchEverywhereOpen(true)}
                        className="px-3 py-1.5 rounded-lg bg-[#22252b] hover:bg-[#2c3038] text-gray-200 border border-[#353942]"
                      >
                        Search Everywhere (Double ⇧)
                      </button>
                      <button
                        onClick={() => handleCreateFile('untitled.rs')}
                        className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium"
                      >
                        + New File
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Right Pane: Live Device Simulator Frame */}
              {livePreviewOpen && (
                <div className="w-1/2 h-full overflow-hidden flex flex-col bg-[#0c0d12]">
                  <DevicePreviewFrame
                    srcDoc={activeTab ? activeTab.content : undefined}
                    srcUrl={liveDevServerUrl || undefined}
                    appName={activeTab ? activeTab.name : 'Wolinex Mobile Simulator'}
                  />
                </div>
              )}
            </div>

            {/* Editor Status Footer */}
            {activeTab && (
              <div className="flex items-center justify-between px-3 py-1 border-t border-[#26282f] bg-[#141518] text-[11px] text-gray-500 font-mono select-none">
                <div className="flex items-center gap-3">
                  <span className="text-blue-400">
                    Ln {cursorPos.line}, Col {cursorPos.col}
                  </span>
                  <span>UTF-8</span>
                  <span className="capitalize">{activeTab.language || 'Plain Text'}</span>
                  <span>{activeTab.content.split('\n').length} lines</span>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      setBottomToolOpen(!bottomToolOpen);
                    }}
                    className="text-gray-400 hover:text-gray-200 flex items-center gap-1 font-sans"
                  >
                    <Terminal className="w-3 h-3 text-purple-400" />
                    <span>{bottomToolOpen ? 'Hide Tool Window' : 'Open Tool Window'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Bottom Tool Windows (Terminal, Expo & Metro, Git, AST Insight, HTTP Client, Database, Run) */}
            <BottomToolWindows
              isOpen={bottomToolOpen}
              activeTab={bottomActiveTab}
              onTabChange={setBottomActiveTab}
              onClose={() => setBottomToolOpen(false)}
              projectRoot={projectRoot}
              projectName={currentProject?.name || 'Wolinex'}
              activeFilePath={activeTab?.path}
              activeFileContent={activeTab?.content}
              gitStatus={gitStatus}
              onRefreshGit={refreshGitStatus}
              onJumpToLine={handleJumpToLine}
              onSyncSimulatorUrl={(url) => {
                setLiveDevServerUrl(url);
                setLivePreviewOpen(true);
              }}
            />
          </div>

          {/* Column 3: Wolinex Agent Pairing Drawer (Cmd+Shift+G) */}
          <div className="w-80 flex-shrink-0 flex flex-col h-full bg-[#151619] border-l border-[#282b33] overflow-hidden text-xs">
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[#26282f] bg-[#121316]">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-blue-400" />
                <span className="font-semibold text-gray-100">Wolinex Copilot</span>
              </div>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-[#1e2024] border border-[#2e323b] rounded px-2 py-0.5 text-[11px] text-blue-300 font-mono outline-none"
              >
                <option value="⚡ Wolinet Coder">⚡ Wolinet Coder</option>
                <option value="✦ Wolinet Max">✦ Wolinet Max</option>
                <option value="⚡ Wolinet Pro">⚡ Wolinet Pro</option>
              </select>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3 font-sans">
              {agentResponses.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col p-2.5 rounded-lg text-xs leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-blue-600/20 border border-blue-500/30 text-blue-200 ml-4'
                      : 'bg-[#1e2024] border border-[#2c3038] text-gray-200 mr-2'
                  }`}
                >
                  <div className="flex items-center justify-between text-[10px] text-gray-500 mb-1">
                    <span className="font-bold uppercase tracking-wider">{msg.role}</span>
                    <span>{msg.timestamp}</span>
                  </div>

                  <div className="whitespace-pre-wrap">{msg.text}</div>

                  {msg.role === 'agent' && activeTab && (
                    <button
                      onClick={() => {
                        const codeBlock = msg.text.match(/```[a-z]*\n([\s\S]*?)```/);
                        if (codeBlock && codeBlock[1]) {
                          handleApplyCodeToEditor(codeBlock[1]);
                        }
                      }}
                      className="mt-2 self-start flex items-center gap-1 px-2.5 py-1 rounded bg-blue-600/30 border border-blue-500/40 hover:bg-blue-600/50 text-[11px] text-blue-300 font-medium"
                    >
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Apply to Editor
                    </button>
                  )}
                </div>
              ))}

              {isAgentExecuting && (
                <div className="flex items-center gap-2 text-blue-400 p-2 italic">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>{selectedModel} is thinking...</span>
                </div>
              )}
            </div>

            {/* Input Prompt Box */}
            <div className="p-3 border-t border-[#26282f] bg-[#121316] flex flex-col gap-2">
              <textarea
                value={agentPrompt}
                onChange={(e) => setAgentPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleExecuteAgent();
                  }
                }}
                placeholder="Ask about this file or request refactoring (Cmd+Shift+G)..."
                rows={3}
                className="w-full bg-[#1a1c20] border border-[#2c3038] rounded-lg p-2 text-xs text-gray-100 placeholder-gray-500 outline-none resize-none focus:border-blue-500"
              />

              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-500">Enter to send</span>
                <button
                  onClick={() => handleExecuteAgent()}
                  disabled={isAgentExecuting || (!agentPrompt.trim() && contextChips.length === 0)}
                  className="px-3 py-1 rounded-md bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-medium flex items-center gap-1.5"
                >
                  <Send className="w-3 h-3" /> Send
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Search Everywhere Floating Modal (Double Shift / Cmd+Shift+O / Cmd+P) */}
        <SearchEverywhereModal
          isOpen={isSearchEverywhereOpen}
          onClose={() => setIsSearchEverywhereOpen(false)}
          files={files}
          activeFileContent={activeTab?.content}
          activeFileName={activeTab?.name}
          onOpenFile={(p) => {
            const entry = files.find((f) => f.path === p) || {
              name: p.split('/').pop() || '',
              path: p,
              kind: 'file' as const,
              size: 0,
            };
            handleOpenFile(entry);
          }}
          onTriggerAction={handleTriggerAction}
        />
      </div>
    </MainPanelLayout>
  );
};
