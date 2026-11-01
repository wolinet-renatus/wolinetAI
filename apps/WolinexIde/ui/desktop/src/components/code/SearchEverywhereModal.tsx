import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Search,
  FileCode,
  Terminal,
  Zap,
  GitBranch,
  Layers,
  Database,
  Globe,
  Play,
  X,
  Code,
  Smartphone,
} from 'lucide-react';

export type SearchTab = 'all' | 'files' | 'actions' | 'symbols' | 'git';

export interface SearchResultItem {
  id: string;
  title: string;
  subtitle: string;
  kind: 'file' | 'action' | 'symbol' | 'git';
  icon: React.ReactNode;
  action: () => void;
}

interface SearchEverywhereModalProps {
  isOpen: boolean;
  onClose: () => void;
  files: Array<{ name: string; path: string; kind: 'dir' | 'file' }>;
  activeFileContent?: string;
  activeFileName?: string;
  onOpenFile: (path: string) => void;
  onTriggerAction: (actionId: string) => void;
}

export const SearchEverywhereModal: React.FC<SearchEverywhereModalProps> = ({
  isOpen,
  onClose,
  files,
  activeFileContent,
  activeFileName,
  onOpenFile,
  onTriggerAction,
}) => {
  const [activeTab, setActiveTab] = useState<SearchTab>('all');
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Extract symbols from currently active file (functions, classes, interfaces, structs)
  const symbols = useMemo(() => {
    if (!activeFileContent) return [];
    const lines = activeFileContent.split('\n');
    const detected: Array<{ name: string; line: number; kind: string }> = [];

    const symbolRegex =
      /(?:function|fn|def|class|interface|struct|type|enum|const|let)\s+([A-Za-z0-9_]+)/g;

    lines.forEach((line, idx) => {
      let match;
      while ((match = symbolRegex.exec(line)) !== null) {
        detected.push({
          name: match[1],
          line: idx + 1,
          kind: line.trim().split(/\s+/)[0],
        });
      }
    });
    return detected;
  }, [activeFileContent]);

  // Built-in actions
  const ideActions = useMemo(
    () => [
      {
        id: 'new_file',
        title: 'New File',
        subtitle: 'Create a new file in workspace',
        icon: <FileCode className="w-4 h-4 text-emerald-400" />,
      },
      {
        id: 'new_folder',
        title: 'New Folder',
        subtitle: 'Create a new directory in workspace',
        icon: <Layers className="w-4 h-4 text-blue-400" />,
      },
      {
        id: 'save_doc',
        title: 'Save Active Document',
        subtitle: 'Cmd+S / Ctrl+S',
        icon: <Zap className="w-4 h-4 text-amber-400" />,
      },
      {
        id: 'toggle_terminal',
        title: 'Toggle Terminal Tool Window',
        subtitle: 'Alt+F12 / Ctrl+` (default open to project root)',
        icon: <Terminal className="w-4 h-4 text-purple-400" />,
      },
      {
        id: 'toggle_git',
        title: 'Toggle Git / VCS Tool Window',
        subtitle: 'Alt+9 - Review staged diffs & commit',
        icon: <GitBranch className="w-4 h-4 text-orange-400" />,
      },
      {
        id: 'toggle_http',
        title: 'HTTP Client Tool Window',
        subtitle: 'IntelliJ .http scratchpad & API runner',
        icon: <Globe className="w-4 h-4 text-sky-400" />,
      },
      {
        id: 'toggle_db',
        title: 'Database Tool Window',
        subtitle: 'IntelliJ SQLite & Database scratchpad runner',
        icon: <Database className="w-4 h-4 text-rose-400" />,
      },
      {
        id: 'toggle_preview',
        title: 'Toggle Live Mobile Simulator',
        subtitle: 'Side-by-side iPhone 16 Pro, iPad & Web preview',
        icon: <Smartphone className="w-4 h-4 text-cyan-400" />,
      },
      {
        id: 'send_to_wolinex',
        title: 'Send Selection to Wolinex Agent',
        subtitle: 'Cmd+Shift+G - Attach file context chips',
        icon: <Zap className="w-4 h-4 text-cyan-400" />,
      },
      {
        id: 'run_configs',
        title: 'Run Configurations',
        subtitle: 'Execute pnpm typecheck or cargo test',
        icon: <Play className="w-4 h-4 text-green-400" />,
      },
    ],
    []
  );

  // Filtered Results
  const results = useMemo<SearchResultItem[]>(() => {
    const q = query.toLowerCase().trim();
    const items: SearchResultItem[] = [];

    // 1. Files
    if (activeTab === 'all' || activeTab === 'files') {
      files
        .filter((f) => f.kind === 'file')
        .forEach((f) => {
          if (!q || f.name.toLowerCase().includes(q) || f.path.toLowerCase().includes(q)) {
            items.push({
              id: `file-${f.path}`,
              title: f.name,
              subtitle: f.path,
              kind: 'file',
              icon: <FileCode className="w-4 h-4 text-blue-400 flex-shrink-0" />,
              action: () => {
                onOpenFile(f.path);
                onClose();
              },
            });
          }
        });
    }

    // 2. Actions
    if (activeTab === 'all' || activeTab === 'actions') {
      ideActions.forEach((act) => {
        if (!q || act.title.toLowerCase().includes(q) || act.subtitle.toLowerCase().includes(q)) {
          items.push({
            id: `action-${act.id}`,
            title: act.title,
            subtitle: act.subtitle,
            kind: 'action',
            icon: act.icon,
            action: () => {
              onTriggerAction(act.id);
              onClose();
            },
          });
        }
      });
    }

    // 3. Symbols
    if (activeTab === 'all' || activeTab === 'symbols') {
      symbols.forEach((sym) => {
        if (!q || sym.name.toLowerCase().includes(q)) {
          items.push({
            id: `sym-${sym.name}-${sym.line}`,
            title: sym.name,
            subtitle: `${activeFileName || 'current file'} : line ${sym.line} (${sym.kind})`,
            kind: 'symbol',
            icon: <Code className="w-4 h-4 text-amber-400 flex-shrink-0" />,
            action: () => {
              onTriggerAction(`jump_line_${sym.line}`);
              onClose();
            },
          });
        }
      });
    }

    // 4. Git
    if (activeTab === 'all' || activeTab === 'git') {
      ['main', 'origin/main', 'HEAD', 'commit: staged changes'].forEach((branch) => {
        if (!q || branch.toLowerCase().includes(q)) {
          items.push({
            id: `git-${branch}`,
            title: branch,
            subtitle: 'Git VCS reference',
            kind: 'git',
            icon: <GitBranch className="w-4 h-4 text-orange-400 flex-shrink-0" />,
            action: () => {
              onTriggerAction('toggle_git');
              onClose();
            },
          });
        }
      });
    }

    return items.slice(0, 50);
  }, [
    activeTab,
    query,
    files,
    ideActions,
    symbols,
    activeFileName,
    onOpenFile,
    onTriggerAction,
    onClose,
  ]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (results[selectedIndex]) {
        results[selectedIndex].action();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const tabs: SearchTab[] = ['all', 'files', 'actions', 'symbols', 'git'];
      const nextIdx = (tabs.indexOf(activeTab) + 1) % tabs.length;
      setActiveTab(tabs[nextIdx]);
      setSelectedIndex(0);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-2xl bg-[#1e2024] border border-[#383c44] rounded-xl shadow-2xl overflow-hidden flex flex-col font-sans"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar & Tabs */}
        <div className="flex items-center justify-between border-b border-[#2c3038] px-4 pt-3 pb-2 bg-[#181a1d]">
          <div className="flex items-center gap-1 text-xs">
            {(['all', 'files', 'actions', 'symbols', 'git'] as SearchTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => {
                  setActiveTab(tab);
                  setSelectedIndex(0);
                }}
                className={`px-3 py-1 rounded-md font-medium capitalize transition-colors ${
                  activeTab === tab
                    ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-[#25282e]'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 text-[11px] text-gray-500">
            <span>Tab to cycle</span>
            <span>•</span>
            <span>Double ⇧ / Esc</span>
            <button onClick={onClose} className="hover:text-gray-300 ml-2">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[#2c3038] bg-[#1a1c20]">
          <Search className="w-5 h-5 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder={`Search everywhere in OpenIDEA (${activeTab})...`}
            className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500 outline-none"
          />
          {query && (
            <button onClick={() => setQuery('')} className="text-xs text-gray-500 hover:text-gray-300">
              Clear
            </button>
          )}
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto divide-y divide-[#25282e] p-1">
          {results.length > 0 ? (
            results.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => item.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                    isSelected ? 'bg-blue-600/25 border border-blue-500/40' : 'hover:bg-[#25282e]/60'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {item.icon}
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-medium text-gray-100 truncate">{item.title}</span>
                      <span className="text-[11px] text-gray-400 truncate font-mono">{item.subtitle}</span>
                    </div>
                  </div>
                  <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider ml-2">
                    {item.kind}
                  </span>
                </div>
              );
            })
          ) : (
            <div className="py-8 text-center text-xs text-gray-500">
              No matches found for "{query}". Try a different term or tab.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-[#2c3038] bg-[#16181b] flex items-center justify-between text-[11px] text-gray-500">
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>Esc Close</span>
          </div>
          <span className="text-blue-400 font-mono">OpenIDEA Rust Core v0.1.32</span>
        </div>
      </div>
    </div>
  );
};
