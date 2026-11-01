import { useState, useEffect } from 'react';
import {
  Cpu,
  CheckCircle2,
  Zap,
  Layers,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../ui/button';
import {
  wolinexGateway,
  type SovereignModel,
} from '../../services/wolinexGatewayService';

interface LocalModelPickerProps {
  onConfigured: (providerName: string, modelId: string) => void | Promise<void>;
}

export default function LocalModelPicker({ onConfigured }: LocalModelPickerProps) {
  const [models, setModels] = useState<SovereignModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>('Wolinex Coder');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [gatewayUrl, setGatewayUrl] = useState<string>('http://127.0.0.1:4000');
  const [gatewayStatus, setGatewayStatus] = useState<{ healthy: boolean; latencyMs: number } | null>(null);
  const [isApplying, setIsApplying] = useState<boolean>(false);

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      const url = await wolinexGateway.getGatewayUrl();
      setGatewayUrl(url);

      const health = await wolinexGateway.checkGatewayHealth(url);
      setGatewayStatus({ healthy: health.healthy, latencyMs: health.latencyMs });

      const fetchedModels = await wolinexGateway.fetchSovereignModels(url);
      setModels(fetchedModels);
      if (fetchedModels.length > 0) {
        setSelectedModelId(fetchedModels[0].id);
      }
      setIsLoading(false);
    })();
  }, []);

  const handleSelectAndApply = async (modelId: string) => {
    setIsApplying(true);
    setSelectedModelId(modelId);
    try {
      const apiKey = await wolinexGateway.getApiKey();
      await wolinexGateway.configureEngine({
        gatewayUrl,
        apiKey: apiKey || 'sk-XvKFiwDoOtOe8i4lwbzb8Q',
        modelId,
      });
      await onConfigured('litellm', modelId);
    } catch (e) {
      console.error('Failed to configure local model:', e);
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto flex flex-col gap-6 text-gray-200">
      {/* Header */}
      <div className="flex flex-col gap-1 text-center items-center">
        <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 mb-2">
          <Cpu className="w-5 h-5" />
        </div>
        <h2 className="text-xl font-bold text-white tracking-tight">Sovereign Inference Models</h2>
        <p className="text-xs text-gray-400 max-w-md">
          High-performance sovereign models running on your infrastructure with zero external telemetry and zero data leakage.
        </p>

        {gatewayStatus && (
          <div className="mt-2 inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-[#181a1d] border border-[#2a2d35] text-[11px] text-gray-300">
            <span
              className={`w-2 h-2 rounded-full ${gatewayStatus.healthy ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
            />
            <span>Wolinex Sovereign Gateway ({gatewayStatus.latencyMs}ms latency)</span>
          </div>
        )}
      </div>

      {/* Model Cards Grid */}
      <div className="grid grid-cols-1 gap-3">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center p-12 text-gray-500 gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
            <span className="text-xs">Connecting to Wolinex Sovereign Grid...</span>
          </div>
        ) : (
          models.map((model) => {
            const isSelected = selectedModelId === model.id;
            return (
              <div
                key={model.id}
                onClick={() => setSelectedModelId(model.id)}
                className={`flex items-start justify-between p-4 rounded-xl border transition-all cursor-pointer ${isSelected
                  ? 'bg-blue-950/20 border-blue-500/70 shadow-lg shadow-blue-500/5'
                  : 'bg-[#181a1d] border-[#262933] hover:border-[#373b49]'
                  }`}
              >
                <div className="flex items-start gap-3.5">
                  <div
                    className={`mt-0.5 p-2 rounded-lg ${isSelected
                      ? 'bg-blue-600 text-white'
                      : 'bg-[#22252e] text-gray-400'
                      }`}
                  >
                    {model.reasoning ? <Layers className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
                  </div>

                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">{model.name}</span>
                      {model.isDefault && (
                        <span className="text-[10px] bg-blue-600/30 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/40 font-medium">
                          Primary
                        </span>
                      )}
                      {model.reasoning && (
                        <span className="text-[10px] bg-purple-600/30 text-purple-300 px-2 py-0.5 rounded-full border border-purple-500/40 font-medium">
                          Reasoning
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">{model.subtext}</span>

                    <div className="flex items-center gap-3 mt-1 text-[11px] text-gray-500">
                      <span>Context: {Math.round(model.contextLimit / 1024)}k tokens</span>
                      <span>•</span>
                      <span>Enterprise Sovereign Grid</span>
                      <span>•</span>
                      <span className="text-emerald-400">0.00 USD / token</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center self-center pl-2">
                  <div
                    className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all ${isSelected
                      ? 'border-blue-500 bg-blue-600 text-white'
                      : 'border-[#373b49] bg-transparent'
                      }`}
                  >
                    {isSelected && <CheckCircle2 className="w-3.5 h-3.5" />}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-[#262933]">
        <span className="text-xs text-gray-500">
          Selected: <strong className="text-gray-300">{selectedModelId}</strong>
        </span>

        <Button
          onClick={() => handleSelectAndApply(selectedModelId)}
          disabled={isApplying || isLoading}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-5 py-2 rounded-lg flex items-center gap-2 shadow-md transition-all"
        >
          {isApplying ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Configuring...</span>
            </>
          ) : (
            <>
              <span>Activate Model</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
