'use client';

import { FC, useState, useEffect, useCallback, useRef } from 'react';
import {
  HardDrive,
  Upload,
  Download,
  Trash2,
  RefreshCw,
  Rocket,
  AlertTriangle,
  FolderOpen,
  Loader2,
  FileBox,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import request from '@/lib/request';
import { cn } from '@/lib/utils';

export interface StorageModelFile {
  filename: string;
  rel_path: string;
  abs_path: string;
  size_bytes: number;
  size_human: string;
  category: string;
  format: string;
  modified_at: string;
  is_registered: boolean;
  registered_model_name?: string;
  registered_model_type?: string;
  is_running: boolean;
  running_model_uid?: string;
}

interface StorageDriveManagerProps {
  onRefreshRegistrations?: () => void;
}

export const StorageDriveManager: FC<StorageDriveManagerProps> = ({
  onRefreshRegistrations,
}) => {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<StorageModelFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [totalDiskHuman, setTotalDiskHuman] = useState('0 B');
  const [modelsRoot, setModelsRoot] = useState('');

  // Upload state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadCategory, setUploadCategory] = useState('llm');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Download state
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState('');
  const [downloadCategory, setDownloadCategory] = useState('llm');
  const [downloadFilename, setDownloadFilename] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState('');

  // Delete state
  const [fileToDelete, setFileToDelete] = useState<StorageModelFile | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchStorageFiles = useCallback(async () => {
    setLoading(true);
    try {
      const res = (await request.get('/v1/storage/models')) as {
        files?: StorageModelFile[];
        total_disk_human?: string;
        models_root?: string;
      };
      if (Array.isArray(res?.files)) {
        setFiles(res.files);
        setTotalDiskHuman(res.total_disk_human || '0 B');
        setModelsRoot(res.models_root || '');
      }
    } catch (err) {
      console.error('Failed to fetch storage files:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStorageFiles();
  }, [fetchStorageFiles]);

  const handleUploadSubmit = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('category', uploadCategory);
      formData.append('filename', selectedFile.name);

      await request.post('/v1/storage/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setUploadOpen(false);
      setSelectedFile(null);
      await fetchStorageFiles();
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadSubmit = async () => {
    if (!downloadUrl) return;
    setDownloading(true);
    setDownloadMsg('Downloading model weights from URL to sovereign disk storage...');
    try {
      await request.post('/v1/storage/download', {
        url: downloadUrl,
        category: downloadCategory,
        filename: downloadFilename || undefined,
      });

      setDownloadOpen(false);
      setDownloadUrl('');
      setDownloadFilename('');
      setDownloadMsg('');
      await fetchStorageFiles();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Network error';
      console.error('Download failed:', err);
      setDownloadMsg(`Download failed: ${errorMsg}`);
    } finally {
      setDownloading(false);
    }
  };

  const handleDeleteFile = async () => {
    if (!fileToDelete) return;
    setDeleting(true);
    try {
      await request.delete('/v1/storage/models/purge', {
        data: {
          file_path: fileToDelete.abs_path,
          model_name: fileToDelete.registered_model_name,
          purge_disk_files: true,
        },
      });
      setFileToDelete(null);
      await fetchStorageFiles();
      onRefreshRegistrations?.();
    } catch (err) {
      console.error('Failed to purge file:', err);
    } finally {
      setDeleting(false);
    }
  };

  const handleQuickRegister = (file: StorageModelFile) => {
    // Pre-fill session storage for register-model
    const modelName = file.filename.replace(/\.[^/.]+$/, '').toLowerCase();
    const defaultData = {
      model_name: modelName,
      model_ability: ['chat', 'tools', 'reasoning'],
      model_family: 'qwen2',
      model_description: `Sovereign model loaded from ${file.filename} (${file.size_human})`,
      context_length: 131072,
      model_specs: [
        {
          model_format: file.format,
          model_size_in_billions: '1_5',
          quantization: 'IQ4_XS',
          model_uri: file.rel_path.substring(0, file.rel_path.lastIndexOf('/')),
          model_file_name_template: file.filename,
        },
      ],
    };

    sessionStorage.setItem('customJsonData', JSON.stringify(defaultData));
    router.push(`/register-model/LLM/${modelName}`);
  };

  const categoryOptions = [
    { label: 'LLM Weights (inference/models/llm)', value: 'llm' },
    { label: 'DFlash Speculative Defense (inference/models/dflash)', value: 'dflash' },
    { label: 'Fine-tune Checkpoints (inference/models/checkpoints)', value: 'checkpoints' },
  ];

  return (
    <div className="space-y-6">
      {/* Storage Overview Header */}
      <div className="rounded-xl border border-border/80 bg-card p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <HardDrive className="size-5 text-primary" />
              <h2 className="text-lg font-bold text-foreground">Local Storage & Model Drive Manager</h2>
              <Badge variant="outline" className="border-border">
                {files.length} Weight Files
              </Badge>
              <Badge variant="secondary" className="font-semibold text-primary">
                {totalDiskHuman} Used
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground font-mono truncate max-w-2xl">
              Root: {modelsRoot || 'inference/models/'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDownloadOpen(true)}
              className="text-xs"
            >
              <Download className="size-3.5 mr-1.5" />
              Download from URL
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => setUploadOpen(true)}
              className="text-xs"
            >
              <Upload className="size-3.5 mr-1.5" />
              Upload Weights
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchStorageFiles}
              disabled={loading}
              className="size-9 p-0"
              title="Refresh Storage"
            >
              <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
            </Button>
          </div>
        </div>
      </div>

      {/* Files Table / Grid */}
      {loading && !files.length ? (
        <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="mr-2 size-4 animate-spin text-primary" />
          Scanning local drive storage...
        </div>
      ) : !files.length ? (
        <div className="rounded-lg border border-dashed border-border/80 p-8 text-center text-sm text-muted-foreground">
          No model weights detected in local storage. Upload weights or download from URL to get started.
        </div>
      ) : (
        <div className="rounded-xl border border-border/80 bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border/80 bg-muted/40 font-medium text-muted-foreground">
                <tr>
                  <th className="py-3 px-4">Model Weight File</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Size</th>
                  <th className="py-3 px-4">Format</th>
                  <th className="py-3 px-4">Registry & Run Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {files.map((file) => (
                  <tr
                    key={file.abs_path}
                    className="hover:bg-muted/20 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <FileBox className="size-4 text-primary shrink-0" />
                        <div>
                          <p className="font-semibold text-foreground">{file.filename}</p>
                          <p className="font-mono text-[10px] text-muted-foreground truncate max-w-sm">
                            {file.rel_path}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 uppercase font-mono text-muted-foreground">
                      {file.category}
                    </td>
                    <td className="py-3 px-4 font-semibold text-foreground">
                      {file.size_human}
                    </td>
                    <td className="py-3 px-4 uppercase text-muted-foreground">
                      {file.format}
                    </td>
                    <td className="py-3 px-4">
                      {file.is_running ? (
                        <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 gap-1">
                          <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          Running ({file.running_model_uid})
                        </Badge>
                      ) : file.is_registered ? (
                        <Badge variant="outline" className="border-primary/40 text-primary">
                          Registered: {file.registered_model_name}
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-muted-foreground">
                          Unregistered
                        </Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {!file.is_registered && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleQuickRegister(file)}
                            className="h-7 text-xs"
                          >
                            <Rocket className="size-3 mr-1" />
                            Register
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setFileToDelete(file)}
                          className="h-7 px-2 text-muted-foreground hover:text-destructive"
                          title="Purge weight file from disk to reclaim space"
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Upload Dialog */}
      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-2 text-primary">
              <Upload className="size-5" />
              <DialogTitle>Upload Model Weights</DialogTitle>
            </div>
            <DialogDescription>
              Upload GGUF or Safetensors model weights directly to sovereign local storage.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-sm">
            <div className="space-y-1">
              <span className="text-xs font-medium text-foreground">Target Directory:</span>
              <Select
                value={uploadCategory}
                onChange={(val) => setUploadCategory(val || 'llm')}
                options={categoryOptions}
                className="w-full"
              />
            </div>

            <div
              onClick={() => fileInputRef.current?.click()}
              className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border/80 p-6 text-center cursor-pointer hover:border-primary/60 transition-colors bg-muted/20"
            >
              <FolderOpen className="size-8 text-primary/80 mb-2" />
              {selectedFile ? (
                <div>
                  <p className="font-semibold text-foreground">{selectedFile.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-xs font-medium text-foreground">Click or drop model weight here</p>
                  <p className="text-[11px] text-muted-foreground">Supports .gguf, .bin, .safetensors</p>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".gguf,.bin,.safetensors,.pt"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setUploadOpen(false)} disabled={uploading}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleUploadSubmit} disabled={!selectedFile || uploading}>
              {uploading ? 'Uploading...' : 'Start Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Download Dialog */}
      <Dialog open={downloadOpen} onOpenChange={setDownloadOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-2 text-primary">
              <Download className="size-5" />
              <DialogTitle>Download Model from URL</DialogTitle>
            </div>
            <DialogDescription>
              Fetch model weights from Hugging Face, ModelScope, or direct HTTP/HTTPS links.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-sm">
            <div className="space-y-1">
              <span className="text-xs font-medium text-foreground">Download URL:</span>
              <Input
                value={downloadUrl}
                onChange={(e) => setDownloadUrl(e.target.value)}
                placeholder="https://huggingface.co/.../model.gguf"
                className="h-9 text-xs font-mono"
              />
            </div>

            <div className="space-y-1">
              <span className="text-xs font-medium text-foreground">Destination Folder:</span>
              <Select
                value={downloadCategory}
                onChange={(val) => setDownloadCategory(val || 'llm')}
                options={categoryOptions}
                className="w-full"
              />
            </div>

            <div className="space-y-1">
              <span className="text-xs font-medium text-foreground">Custom Filename (Optional):</span>
              <Input
                value={downloadFilename}
                onChange={(e) => setDownloadFilename(e.target.value)}
                placeholder="Leave blank to infer from URL"
                className="h-9 text-xs font-mono"
              />
            </div>

            {downloadMsg && (
              <p className="text-xs text-primary animate-pulse">{downloadMsg}</p>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setDownloadOpen(false)} disabled={downloading}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleDownloadSubmit} disabled={!downloadUrl || downloading}>
              {downloading ? 'Downloading...' : 'Start Download'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Purge File Dialog */}
      <Dialog open={Boolean(fileToDelete)} onOpenChange={(open) => !open && setFileToDelete(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="size-5" />
              <DialogTitle>Purge Model File from Disk</DialogTitle>
            </div>
            <DialogDescription className="pt-2 text-left">
              Permanently delete <span className="font-semibold text-foreground">{fileToDelete?.filename}</span> from the local file system to reclaim <span className="font-semibold text-foreground">{fileToDelete?.size_human}</span> of disk space?
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-lg border border-border/80 bg-muted/20 p-3 text-xs font-mono text-muted-foreground break-all">
            {fileToDelete?.abs_path}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setFileToDelete(null)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="destructive" size="sm" onClick={handleDeleteFile} disabled={deleting}>
              {deleting ? 'Purging...' : 'Permanently Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
