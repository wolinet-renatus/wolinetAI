import React, { useState } from 'react';
import {
  FolderOpen,
  Folder,
  FileCode,
  File,
  RefreshCw,
  Search,
  Trash2,
  Edit2,
  Check,
  X,
  FilePlus,
  FolderPlus,
} from 'lucide-react';

export interface OpenIdeaFileEntry {
  name: string;
  path: string;
  kind: 'dir' | 'file';
  size: number;
}

interface FileExplorerProps {
  projectName: string;
  projectPath: string;
  files: OpenIdeaFileEntry[];
  activeFilePath: string;
  onOpenFile: (entry: OpenIdeaFileEntry) => void;
  onCreateFile: (fileName: string) => Promise<void>;
  onCreateDir: (dirName: string) => Promise<void>;
  onDeletePath: (path: string) => Promise<void>;
  onRenamePath: (fromPath: string, toPath: string) => Promise<void>;
  onRefresh: () => void;
  onOpenProjectDialog: () => void;
}

export const FileExplorer: React.FC<FileExplorerProps> = ({
  projectName,
  projectPath,
  files,
  activeFilePath,
  onOpenFile,
  onCreateFile,
  onCreateDir,
  onDeletePath,
  onRenamePath,
  onRefresh,
  onOpenProjectDialog,
}) => {
  const [searchFilter, setSearchFilter] = useState('');
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [isCreatingDir, setIsCreatingDir] = useState(false);
  const [newItemName, setNewItemName] = useState('');
  const [editingPath, setEditingPath] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');

  // Helper for file type icons & colors
  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'rs':
        return <FileCode className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />;
      case 'ts':
      case 'tsx':
        return <FileCode className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />;
      case 'js':
      case 'jsx':
        return <FileCode className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0" />;
      case 'py':
        return <FileCode className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />;
      case 'json':
      case 'yaml':
      case 'toml':
        return <FileCode className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />;
      case 'md':
        return <File className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />;
      case 'css':
      case 'scss':
        return <FileCode className="w-3.5 h-3.5 text-pink-400 flex-shrink-0" />;
      case 'html':
        return <FileCode className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />;
      default:
        return <File className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />;
    }
  };

  const handleCreateSubmit = async () => {
    if (!newItemName.trim()) {
      setIsCreatingFile(false);
      setIsCreatingDir(false);
      return;
    }

    if (isCreatingFile) {
      await onCreateFile(newItemName.trim());
      setIsCreatingFile(false);
    } else if (isCreatingDir) {
      await onCreateDir(newItemName.trim());
      setIsCreatingDir(false);
    }
    setNewItemName('');
  };

  const handleRenameSubmit = async (entry: OpenIdeaFileEntry) => {
    if (!editingName.trim() || editingName === entry.name) {
      setEditingPath(null);
      return;
    }
    const parentDir = entry.path.substring(0, entry.path.lastIndexOf('/'));
    const newPath = `${parentDir}/${editingName.trim()}`;
    await onRenamePath(entry.path, newPath);
    setEditingPath(null);
  };

  const filteredFiles = files.filter((f) => {
    if (!searchFilter.trim()) return true;
    return f.name.toLowerCase().includes(searchFilter.toLowerCase().trim());
  });

  return (
    <div className="flex flex-col h-full bg-[#181a1d] text-xs font-sans select-none border-r border-[#2a2d35]">
      {/* Project Title Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#26282f] bg-[#141518]">
        <div className="flex items-center gap-2 min-w-0" title={projectPath}>
          <FolderOpen className="w-4 h-4 text-amber-400 flex-shrink-0" />
          <span className="font-semibold text-gray-100 truncate">{projectName || 'Project'}</span>
        </div>

        {/* Toolbar Actions */}
        <div className="flex items-center gap-1 text-gray-400">
          <button
            onClick={() => {
              setIsCreatingFile(true);
              setIsCreatingDir(false);
              setNewItemName('');
            }}
            title="New File"
            className="p-1 rounded hover:text-emerald-400 hover:bg-[#22252b] transition-colors"
          >
            <FilePlus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => {
              setIsCreatingDir(true);
              setIsCreatingFile(false);
              setNewItemName('');
            }}
            title="New Folder"
            className="p-1 rounded hover:text-blue-400 hover:bg-[#22252b] transition-colors"
          >
            <FolderPlus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onRefresh}
            title="Refresh Explorer"
            className="p-1 rounded hover:text-gray-200 hover:bg-[#22252b] transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onOpenProjectDialog}
            title="Open Other Directory..."
            className="p-1 rounded hover:text-amber-400 hover:bg-[#22252b] transition-colors"
          >
            <FolderOpen className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Search Filter Input */}
      <div className="px-3 py-2 border-b border-[#26282f] bg-[#16181b]">
        <div className="flex items-center gap-2 bg-[#1e2024] border border-[#2a2d35] rounded-md px-2 py-1">
          <Search className="w-3 h-3 text-gray-400 flex-shrink-0" />
          <input
            type="text"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Filter files..."
            className="w-full bg-transparent text-[11px] text-gray-200 placeholder-gray-500 outline-none"
          />
          {searchFilter && (
            <button onClick={() => setSearchFilter('')} className="hover:text-gray-300">
              <X className="w-3 h-3 text-gray-400" />
            </button>
          )}
        </div>
      </div>

      {/* New Item Inline Input */}
      {(isCreatingFile || isCreatingDir) && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-950/30 border-b border-blue-500/30 text-xs">
          {isCreatingFile ? (
            <FileCode className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
          ) : (
            <Folder className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
          )}
          <input
            type="text"
            autoFocus
            value={newItemName}
            onChange={(e) => setNewItemName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCreateSubmit();
              if (e.key === 'Escape') {
                setIsCreatingFile(false);
                setIsCreatingDir(false);
              }
            }}
            placeholder={isCreatingFile ? 'filename.ts' : 'folder_name'}
            className="flex-1 bg-transparent text-gray-100 placeholder-gray-500 outline-none font-mono text-xs border-b border-blue-400"
          />
          <button onClick={handleCreateSubmit} className="text-emerald-400 hover:text-emerald-300">
            <Check className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => {
              setIsCreatingFile(false);
              setIsCreatingDir(false);
            }}
            className="text-gray-400 hover:text-gray-200"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* File Tree List */}
      <div className="flex-1 overflow-y-auto divide-y divide-[#1e2024]/50 py-1">
        {filteredFiles.map((entry) => {
          const isActive = activeFilePath === entry.path;
          const isEditing = editingPath === entry.path;

          return (
            <div
              key={entry.path}
              className={`group flex items-center justify-between px-3 py-1.5 cursor-pointer transition-colors ${
                isActive
                  ? 'bg-blue-600/20 text-blue-300 font-medium'
                  : 'text-gray-300 hover:bg-[#22252b] hover:text-gray-100'
              }`}
              onClick={() => onOpenFile(entry)}
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {entry.kind === 'dir' ? (
                  <Folder className="w-3.5 h-3.5 text-amber-400/90 flex-shrink-0" />
                ) : (
                  getFileIcon(entry.name)
                )}

                {isEditing ? (
                  <input
                    type="text"
                    autoFocus
                    value={editingName}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setEditingName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleRenameSubmit(entry);
                      if (e.key === 'Escape') setEditingPath(null);
                    }}
                    className="flex-1 bg-transparent text-white border-b border-blue-400 outline-none font-mono text-xs"
                  />
                ) : (
                  <span className="truncate font-mono text-[11px]">{entry.name}</span>
                )}
              </div>

              {/* Action Buttons on Hover */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2">
                {isEditing ? (
                  <>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRenameSubmit(entry);
                      }}
                      className="p-1 hover:text-emerald-400"
                    >
                      <Check className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingPath(null);
                      }}
                      className="p-1 hover:text-gray-400"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingPath(entry.path);
                        setEditingName(entry.name);
                      }}
                      title="Rename"
                      className="p-1 hover:text-blue-400"
                    >
                      <Edit2 className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Delete ${entry.name}?`)) {
                          onDeletePath(entry.path);
                        }
                      }}
                      title="Delete"
                      className="p-1 hover:text-rose-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}

        {filteredFiles.length === 0 && (
          <div className="p-4 text-center text-gray-500 italic text-[11px]">
            {searchFilter ? 'No files match filter' : 'No files in directory'}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="px-3 py-1.5 border-t border-[#26282f] bg-[#141518] flex items-center justify-between text-[10px] text-gray-500">
        <span>{files.length} items</span>
        <span className="font-mono text-emerald-400">ide-vfs indexed</span>
      </div>
    </div>
  );
};
