'use client';

import { FC, useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  Rocket,
  Square,
  FileCode,
  Cpu,
  TrendingDown,
  Clock,
  Database,
  Layers,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import request from '@/lib/request';
import { cn } from '@/lib/utils';

export interface CheckpointInfo {
  checkpoint_id: string;
  model_name: string;
  model_family: string;
  base_checkpoint: string;
  target_device: string;
  training_samples: number;
  initial_loss: number;
  final_loss: number;
  loss_reduction_pct: number;
  training_time_seconds: number;
  timestamp: string;
  lora_parameters: {
    r: number;
    lora_alpha: number;
    lora_dropout: number;
    target_modules: string[];
  };
  status: string;
  dir_path: string;
  readme?: string;
  is_running?: boolean;
  running_model_uid?: string;
}

interface CheckpointMarketSectionProps {
  onModelLaunched?: () => void;
}

export const CheckpointMarketSection: FC<CheckpointMarketSectionProps> = ({
  onModelLaunched,
}) => {
  const [checkpoints, setCheckpoints] = useState<CheckpointInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [selectedManifest, setSelectedManifest] = useState<CheckpointInfo | null>(null);

  const fetchCheckpoints = useCallback(async () => {
    setLoading(true);
    try {
      const res = (await request.get('/v1/storage/checkpoints')) as { checkpoints?: CheckpointInfo[] };
      if (Array.isArray(res?.checkpoints)) {
        setCheckpoints(res.checkpoints);
      }
    } catch (err) {
      console.error('Failed to fetch checkpoints:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCheckpoints();
  }, [fetchCheckpoints]);

  const handleLaunch = async (ckpt: CheckpointInfo) => {
    setActionLoading(ckpt.checkpoint_id);
    try {
      await request.post('/v1/storage/checkpoints/launch', {
        checkpoint_id: ckpt.checkpoint_id,
        model_uid: ckpt.checkpoint_id,
      });
      await fetchCheckpoints();
      onModelLaunched?.();
    } catch (err) {
      console.error('Failed to launch checkpoint:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async (ckpt: CheckpointInfo) => {
    setActionLoading(ckpt.checkpoint_id);
    try {
      await request.post('/v1/storage/models/stop', {
        model_name: ckpt.checkpoint_id,
        model_uid: ckpt.running_model_uid,
      });
      await fetchCheckpoints();
      onModelLaunched?.();
    } catch (err) {
      console.error('Failed to stop checkpoint:', err);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Sparkles className="size-5 text-primary" />
              <h2 className="text-lg font-bold tracking-tight text-foreground">
                Self-Trained Model Market & Fine-Tune Checkpoints
              </h2>
              <Badge variant="outline" className="border-primary/40 text-primary">
                Sovereign Checkpoints
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground max-w-2xl">
              Locally synthesized and fine-tuned checkpoints from <span className="font-mono text-foreground">inference/models/checkpoints/</span>.
              Ready for immediate 1-click deployment with zero external dependencies.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchCheckpoints}
            disabled={loading}
            className="shrink-0"
          >
            <RefreshCw className={cn('size-3.5 mr-1.5', loading && 'animate-spin')} />
            Refresh Checkpoints
          </Button>
        </div>
      </div>

      {/* Grid */}
      {loading && !checkpoints.length ? (
        <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="mr-2 size-4 animate-spin text-primary" />
          Scanning checkpoints repository...
        </div>
      ) : !checkpoints.length ? (
        <div className="rounded-lg border border-dashed border-border/80 p-8 text-center text-sm text-muted-foreground">
          No trained checkpoints found in <span className="font-mono">inference/models/checkpoints/</span>. Run self-training pipelines to produce checkpoints.
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {checkpoints.map((ckpt) => {
            const isActing = actionLoading === ckpt.checkpoint_id;
            return (
              <div
                key={ckpt.checkpoint_id}
                className="group relative flex flex-col justify-between rounded-xl border border-border/80 bg-card p-5 transition-all duration-200 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5"
              >
                <div className="space-y-3.5">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-foreground group-hover:text-primary transition-colors">
                        {ckpt.model_name}
                      </h3>
                      <p className="font-mono text-xs text-muted-foreground">
                        {ckpt.checkpoint_id}
                      </p>
                    </div>
                    {ckpt.is_running ? (
                      <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 gap-1">
                        <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Running
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">
                        {ckpt.status === 'ready_for_deployment'
                          ? 'Ready to Deploy'
                          : ckpt.status}
                      </Badge>
                    )}
                  </div>

                  {/* Architecture & Base Checkpoint */}
                  <div className="flex flex-wrap gap-1.5 text-xs">
                    <span className="rounded-md border border-border/60 bg-muted/40 px-2 py-0.5 text-muted-foreground">
                      Base: {ckpt.base_checkpoint}
                    </span>
                    <span className="rounded-md border border-border/60 bg-muted/40 px-2 py-0.5 text-muted-foreground">
                      Arch: {ckpt.model_family}
                    </span>
                  </div>

                  {/* Training Performance Stats */}
                  <div className="grid grid-cols-2 gap-2 rounded-lg border border-border/50 bg-muted/20 p-2.5 text-xs">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <TrendingDown className="size-3 text-emerald-500" />
                        <span>Loss Reduction:</span>
                      </div>
                      <p className="font-semibold text-emerald-600 dark:text-emerald-400">
                        {ckpt.loss_reduction_pct.toFixed(1)}% ({ckpt.initial_loss.toFixed(2)} → {ckpt.final_loss.toFixed(2)})
                      </p>
                    </div>

                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Clock className="size-3 text-primary" />
                        <span>Training Time:</span>
                      </div>
                      <p className="font-semibold text-foreground">
                        {ckpt.training_time_seconds.toFixed(2)}s
                      </p>
                    </div>

                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Database className="size-3 text-amber-500" />
                        <span>Samples:</span>
                      </div>
                      <p className="font-semibold text-foreground">
                        {ckpt.training_samples} pairs
                      </p>
                    </div>

                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Cpu className="size-3 text-blue-500" />
                        <span>Hardware:</span>
                      </div>
                      <p className="font-semibold text-foreground uppercase">
                        {ckpt.target_device}
                      </p>
                    </div>
                  </div>

                  {/* LoRA Parameters */}
                  {ckpt.lora_parameters && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Layers className="size-3.5 text-primary" />
                      <span>
                        LoRA Rank <span className="font-mono text-foreground font-medium">r={ckpt.lora_parameters.r}</span>,
                        Alpha <span className="font-mono text-foreground font-medium">α={ckpt.lora_parameters.lora_alpha}</span>
                      </span>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="mt-5 flex items-center justify-between gap-2 pt-3 border-t border-border/60">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedManifest(ckpt)}
                    className="h-8 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <FileCode className="size-3.5 mr-1" />
                    Manifest
                  </Button>

                  <div className="flex items-center gap-2">
                    {ckpt.is_running ? (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleStop(ckpt)}
                        disabled={isActing}
                        className="h-8 text-xs"
                      >
                        <Square className="size-3 mr-1 fill-current" />
                        {isActing ? 'Stopping...' : 'Stop'}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => handleLaunch(ckpt)}
                        disabled={isActing}
                        className="h-8 text-xs"
                      >
                        <Rocket className="size-3 mr-1" />
                        {isActing ? 'Launching...' : '1-Click Launch'}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Manifest Dialog */}
      <Dialog open={Boolean(selectedManifest)} onOpenChange={(open) => !open && setSelectedManifest(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileCode className="size-5 text-primary" />
              <span>Checkpoint Manifest: {selectedManifest?.model_name}</span>
            </DialogTitle>
            <DialogDescription className="font-mono text-xs">
              {selectedManifest?.dir_path}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            {selectedManifest?.readme && (
              <div className="rounded-lg border border-border/80 bg-muted/20 p-3 space-y-1">
                <span className="font-semibold text-foreground">README Provenance:</span>
                <p className="whitespace-pre-wrap text-muted-foreground font-mono leading-relaxed">
                  {selectedManifest.readme}
                </p>
              </div>
            )}

            <div className="space-y-1">
              <span className="font-semibold text-foreground">Hyperparameter & Training Details:</span>
              <pre className="rounded-lg border border-border/80 bg-card p-3 font-mono overflow-x-auto text-muted-foreground">
                {JSON.stringify(selectedManifest, null, 2)}
              </pre>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
