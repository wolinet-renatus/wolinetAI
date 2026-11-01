import { useState, useEffect } from 'react';
import {
  Globe,
  Key,
  Cpu,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  Zap,
} from 'lucide-react';
import { Button } from '../ui/button';
import {
  wolinexGateway,
  type SovereignModel,
} from '../../services/wolinexGatewayService';

interface ProviderConfigFormProps {
  providerName?: string;
  onConfigured: (providerName: string, modelId?: string) => void | Promise<void>;
  onCancel?: () => void;
}

export default function ProviderConfigForm({
  onConfigured,
  onCancel,
}: ProviderConfigFormProps) {
  const [gatewayUrl, setGatewayUrl] = useState<string>('');
  const [apiKey, setApiKey] = useState<string>('');
  const [models, setModels] = useState<SovereignModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('Wolinex Coder');

  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    (async () => {
      const gUrl = await wolinexGateway.getGatewayUrl();
      const existingKey = await wolinexGateway.getApiKey();
      setGatewayUrl(gUrl);
      if (existingKey) setApiKey(existingKey);

      const m = await wolinexGateway.fetchSovereignModels(gUrl, existingKey);
      setModels(m);
      if (m.length > 0) setSelectedModel(m[0].id);
    })();
  }, []);

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const health = await wolinexGateway.checkGatewayHealth(gatewayUrl);
      if (!health.healthy) {
        throw new Error(health.error || `Unable to reach gateway at ${gatewayUrl}`);
      }

      if (apiKey.trim()) {
        const val = await wolinexGateway.validateApiKey(apiKey.trim(), gatewayUrl);
        if (!val.valid) {
          throw new Error(val.error || 'API key validation failed');
        }
        if (val.models.length > 0) {
          setModels(val.models);
        }
      }

      setTestResult({
        success: true,
        message: `Connection verified! Gateway responded in ${health.latencyMs}ms.`,
      });
    } catch (err: unknown) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await wolinexGateway.configureEngine({
        gatewayUrl,
        apiKey: apiKey.trim() || 'sk-XvKFiwDoOtOe8i4lwbzb8Q',
        modelId: selectedModel,
      });
      await onConfigured('litellm', selectedModel);
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to save configuration',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="w-full max-w-lg mx-auto bg-[#181a1d] border border-[#2a2d35] rounded-xl p-6 shadow-2xl flex flex-col gap-5 text-gray-200">
      <div className="flex items-center gap-3 pb-3 border-b border-[#262933]">
        <div className="w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
          <Zap className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">Wolinex Sovereign AI Gateway Setup</h2>
          <p className="text-xs text-gray-400">
            Configure your enterprise AI inference endpoint and secure access credentials.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {/* Gateway URL */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5 text-blue-400" />
            Wolinex Gateway Endpoint URL
          </label>
          <input
            type="text"
            value={gatewayUrl}
            onChange={(e) => setGatewayUrl(e.target.value)}
            placeholder="http://127.0.0.1:4000 or https://api.wolinex.ai"
            className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* API Key */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-blue-400" />
              Workspace Access Token / API Key
            </label>
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={isTesting}
              className="text-[11px] text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              {isTesting ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
              <span>Test Connection</span>
            </button>
          </div>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-... (or enterprise access token)"
            className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Model Selector */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-blue-400" />
            Active Sovereign Model
          </label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500"
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({Math.round(m.contextLimit / 1024)}k) {m.reasoning ? '• Reasoning' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Test Result Feedback */}
        {testResult && (
          <div
            className={`flex items-start gap-2 p-3 rounded-lg text-xs ${
              testResult.success
                ? 'bg-emerald-950/30 border border-emerald-800/50 text-emerald-300'
                : 'bg-red-950/30 border border-red-800/50 text-red-300'
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            )}
            <span>{testResult.message}</span>
          </div>
        )}
      </div>

      {/* Buttons */}
      <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#262933]">
        {onCancel && (
          <Button
            variant="ghost"
            onClick={onCancel}
            disabled={isSaving}
            className="text-gray-400 hover:text-white text-xs px-4"
          >
            Cancel
          </Button>
        )}
        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium px-5 py-2 rounded-lg flex items-center gap-1.5 shadow-md"
        >
          {isSaving ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <span>Save & Launch</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
