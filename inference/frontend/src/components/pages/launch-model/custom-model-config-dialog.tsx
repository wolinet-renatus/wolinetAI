'use client';

import { FC, useState, useEffect } from 'react';
import { Settings2, Save, HardDrive, Sparkles, Layers, Sliders } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import request from '@/lib/request';
import type { CatalogModel, RequestModelType } from './types';

interface CustomModelConfigDialogProps {
  model: CatalogModel;
  modelType: RequestModelType;
  onSuccess: () => void;
}

interface StorageFile {
  filename: string;
  rel_path: string;
  size_human: string;
  category: string;
}

export const CustomModelConfigDialog: FC<CustomModelConfigDialogProps> = ({
  model,
  modelType,
  onSuccess,
}) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [storageFiles, setStorageFiles] = useState<StorageFile[]>([]);

  // Parse existing spec
  const rawSpecs = Array.isArray(model.model_specs) ? model.model_specs : [];
  const initialSpec = (rawSpecs[0] as Record<string, unknown>) || {};
  const [weightUri, setWeightUri] = useState<string>(
    (initialSpec.model_uri as string) || 'inference/models/llm'
  );
  const [weightFileName, setWeightFileName] = useState<string>(
    (initialSpec.model_file_name_template as string) || ''
  );
  const modelRecord = model as unknown as Record<string, unknown>;
  const [contextLength, setContextLength] = useState<number>(
    (typeof modelRecord.context_length === 'number' ? modelRecord.context_length : 131072)
  );
  const [quantization, setQuantization] = useState<string>(
    (initialSpec.quantization as string) || 'IQ4_XS'
  );
  const [reasoningStart, setReasoningStart] = useState<string>(
    (typeof modelRecord.reasoning_start_tag === 'string' ? modelRecord.reasoning_start_tag : '<think>')
  );
  const [reasoningEnd, setReasoningEnd] = useState<string>(
    (typeof modelRecord.reasoning_end_tag === 'string' ? modelRecord.reasoning_end_tag : '</think>')
  );
  const [description, setDescription] = useState<string>(
    model.model_description || ''
  );
  const [chatTemplate, setChatTemplate] = useState<string>(
    (typeof modelRecord.chat_template === 'string' ? modelRecord.chat_template : '')
  );

  useEffect(() => {
    if (open) {
      // Fetch local storage files for dropdown selection
      request
        .get('/v1/storage/models')
        .then((res: unknown) => {
          const data = res as { files?: StorageFile[] };
          if (Array.isArray(data?.files)) {
            setStorageFiles(data.files);
          }
        })
        .catch(() => {});
    }
  }, [open]);

  const handleSelectWeight = (filename: string) => {
    const file = storageFiles.find((f) => f.filename === filename);
    if (file) {
      setWeightFileName(file.filename);
      const parentDir = file.rel_path.substring(0, file.rel_path.lastIndexOf('/'));
      setWeightUri(parentDir || `inference/models/${file.category}`);
    } else {
      setWeightFileName(filename);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      // Build updated spec
      const updatedModel: Record<string, unknown> = {
        ...(model as unknown as Record<string, unknown>),
        model_description: description,
        context_length: Number(contextLength),
        reasoning_start_tag: reasoningStart,
        reasoning_end_tag: reasoningEnd,
        chat_template: chatTemplate,
        model_specs: [
          {
            ...initialSpec,
            model_uri: weightUri,
            model_file_name_template: weightFileName,
            quantization: quantization,
          },
        ],
      };

      await request.post('/v1/storage/models/update', {
        model_name: model.model_name,
        model_type: modelType,
        spec: updatedModel,
      });

      setOpen(false);
      onSuccess();
    } catch (err) {
      console.error('Update model config failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const storageOptions = storageFiles.map((f) => ({
    label: `${f.filename} (${f.size_human} - ${f.category})`,
    value: f.filename,
  }));

  const quantOptions = [
    { label: 'IQ4_XS (Ultra-efficient 4-bit imatrix)', value: 'IQ4_XS' },
    { label: 'Q4_K_M (Standard 4-bit Medium)', value: 'Q4_K_M' },
    { label: 'Q8_0 (High Precision 8-bit)', value: 'Q8_0' },
    { label: 'FP16 (Half Precision 16-bit)', value: 'FP16' },
  ];

  const contextOptions = [
    { label: '131,072 Tokens (Native Flagship 131k)', value: '131072' },
    { label: '65,536 Tokens (64k Extended)', value: '65536' },
    { label: '32,768 Tokens (32k Standard)', value: '32768' },
    { label: '8,192 Tokens (8k Fast)', value: '8192' },
    { label: '262,144 Tokens (262k Long-Horizon)', value: '262144' },
  ];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label="Configure & upgrade model"
          className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
        >
          <Settings2 className="size-4" />
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2 text-primary">
            <Sliders className="size-5" />
            <DialogTitle>Configure & Upgrade Model: {model.model_name}</DialogTitle>
          </div>
          <DialogDescription>
            Update sovereign weights, quantization, context horizons, and reasoning templates without manual JSON edits.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 text-sm">
          {/* Weight Selection */}
          <div className="space-y-2 rounded-lg border border-border/80 bg-muted/20 p-3.5">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <HardDrive className="size-4 text-primary" />
              <span>Model Weight & Local Storage</span>
            </div>
            {storageOptions.length > 0 && (
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Select from Local Storage Models:</span>
                <Select
                  value={weightFileName}
                  onChange={(val) => handleSelectWeight(val ?? '')}
                  options={storageOptions}
                  placeholder="Choose local model weight..."
                  allowClear
                  className="w-full"
                />
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Weight Directory / URI:</span>
                <Input
                  value={weightUri}
                  onChange={(e) => setWeightUri(e.target.value)}
                  placeholder="e.g. inference/models/llm"
                  className="h-9 font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Weight File Template:</span>
                <Input
                  value={weightFileName}
                  onChange={(e) => setWeightFileName(e.target.value)}
                  placeholder="e.g. wolinet-brain-r1-1.5b.gguf"
                  className="h-9 font-mono text-xs"
                />
              </div>
            </div>
          </div>

          {/* Engine Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-xs text-foreground">
                <Layers className="size-3.5 text-primary" />
                <span>Context Horizon:</span>
              </div>
              <Select
                value={String(contextLength)}
                onChange={(val) => setContextLength(Number(val || 131072))}
                options={contextOptions}
                className="w-full"
              />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-xs text-foreground">
                <Layers className="size-3.5 text-primary" />
                <span>Quantization Format:</span>
              </div>
              <Select
                value={quantization}
                onChange={(val) => setQuantization(val || 'IQ4_XS')}
                options={quantOptions}
                className="w-full"
              />
            </div>
          </div>

          {/* Reasoning Tags */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-xs text-foreground">
                <Sparkles className="size-3.5 text-primary" />
                <span>Reasoning Start Tag:</span>
              </div>
              <Input
                value={reasoningStart}
                onChange={(e) => setReasoningStart(e.target.value)}
                className="h-9 font-mono text-xs"
              />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-xs text-foreground">
                <Sparkles className="size-3.5 text-primary" />
                <span>Reasoning End Tag:</span>
              </div>
              <Input
                value={reasoningEnd}
                onChange={(e) => setReasoningEnd(e.target.value)}
                className="h-9 font-mono text-xs"
              />
            </div>
          </div>

          {/* Description */}
          <div className="space-y-1">
            <span className="text-xs font-medium text-foreground">Description & Capabilities:</span>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Model description and architectural role..."
              className="h-9 text-xs"
            />
          </div>

          {/* Chat Template */}
          <div className="space-y-1">
            <span className="text-xs font-medium text-foreground">Jinja2 Chat Template / System Prompt:</span>
            <Textarea
              value={chatTemplate}
              onChange={(e) => setChatTemplate(e.target.value)}
              placeholder="{%- if messages ... %}"
              className="min-h-24 font-mono text-xs leading-relaxed"
            />
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={loading}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave} disabled={loading}>
            <Save className="size-4 mr-1.5" />
            {loading ? 'Saving...' : 'Save & Hot-Upgrade'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
