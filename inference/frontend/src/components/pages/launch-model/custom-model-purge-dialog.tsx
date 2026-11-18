'use client';

import { FC, useState } from 'react';
import { Trash2, AlertTriangle, HardDrive } from 'lucide-react';
import { Button } from '@/components/ui/button';
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

interface CustomModelPurgeDialogProps {
  model: CatalogModel;
  modelType: RequestModelType;
  onSuccess: () => void;
}

export const CustomModelPurgeDialog: FC<CustomModelPurgeDialogProps> = ({
  model,
  modelType,
  onSuccess,
}) => {
  const [open, setOpen] = useState(false);
  const [purgeDisk, setPurgeDisk] = useState(false);
  const [loading, setLoading] = useState(false);

  // Find associated local weight path if available
  const rawSpecs = Array.isArray(model.model_specs) ? model.model_specs : [];
  const spec = rawSpecs[0] as Record<string, unknown> | undefined;
  const uri = (spec?.model_uri as string) || '';
  const filename = (spec?.model_file_name_template as string) || '';
  const weightPath = uri && filename ? `${uri}/${filename}` : uri || filename;

  const handleDelete = async () => {
    setLoading(true);
    try {
      if (purgeDisk) {
        await request.delete('/v1/storage/models/purge', {
          data: {
            model_name: model.model_name,
            model_type: modelType,
            purge_disk_files: true,
            file_path: weightPath,
          },
        });
      } else {
        await request.delete(`/v1/model_registrations/${modelType}/${model.model_name}`);
      }
      setOpen(false);
      onSuccess();
    } catch (err) {
      console.error('Delete model failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label="Delete model"
          className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 className="size-4" />
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="size-5" />
            <DialogTitle>Delete Custom Model</DialogTitle>
          </div>
          <DialogDescription className="pt-2 text-left">
            Are you sure you want to remove <span className="font-semibold text-foreground">{model.model_name}</span> from the sovereign model registry?
          </DialogDescription>
        </DialogHeader>

        <div className="my-3 space-y-3 rounded-lg border border-border/60 bg-muted/30 p-3.5 text-sm">
          <div className="flex items-start gap-2.5">
            <HardDrive className="mt-0.5 size-4 text-primary shrink-0" />
            <div className="flex-1 space-y-1">
              <p className="font-medium text-foreground">Local Weight Management</p>
              {weightPath ? (
                <p className="font-mono text-xs text-muted-foreground break-all">{weightPath}</p>
              ) : (
                <p className="text-xs text-muted-foreground">Standard registry manifest</p>
              )}
            </div>
          </div>

          <label className="flex items-center gap-2.5 pt-2 border-t border-border/40 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={purgeDisk}
              onChange={(e) => setPurgeDisk(e.target.checked)}
              className="size-4 rounded border-border text-primary accent-primary"
            />
            <span className="text-xs font-medium text-foreground">
              Also permanently purge model weight file from disk to reclaim space
            </span>
          </label>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={loading}>
            Cancel
          </Button>
          <Button variant="destructive" size="sm" onClick={handleDelete} disabled={loading}>
            {loading ? 'Deleting...' : purgeDisk ? 'Delete & Purge Disk' : 'Unregister Model'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
