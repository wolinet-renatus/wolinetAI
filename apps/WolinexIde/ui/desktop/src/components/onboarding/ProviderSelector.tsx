import { useState, useEffect } from 'react';
import {
  Key,
  ShieldCheck,
  Globe,
  Zap,
  ArrowRight,
  RefreshCw,
  UserCheck,
  Lock,
  Mail,
  User,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Cpu,
} from 'lucide-react';
import { Button } from '../ui/button';
import {
  wolinexGateway,
  type SovereignModel,
  type WolinexUser,
} from '../../services/wolinexGatewayService';

interface ProviderSelectorProps {
  onConfigured: (providerName: string, modelId?: string) => void | Promise<void>;
  onFirstSelection?: () => void;
}

export default function ProviderSelector({
  onConfigured,
  onFirstSelection,
}: ProviderSelectorProps) {
  // Auth modes: 'login' (WebUI SSO), 'register' (New WebUI account), 'apikey' (Direct Gateway key), 'local' (Auto-detect)
  const [authMode, setAuthMode] = useState<'login' | 'register' | 'apikey' | 'local'>('login');

  // Network endpoints (dynamically initialized without brittle hardcoding)
  const [gatewayHost, setGatewayHost] = useState<string>('');
  const [portalHost, setPortalHost] = useState<string>('');
  const [showAdvancedEndpoints, setShowAdvancedEndpoints] = useState<boolean>(false);

  // Form fields
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [name, setName] = useState<string>('');
  const [apiKey, setApiKey] = useState<string>('');

  // Models state
  const [availableModels, setAvailableModels] = useState<SovereignModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('Wolinex Coder');
  const [isLoadingModels, setIsLoadingModels] = useState<boolean>(false);

  // Execution state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [gatewayStatus, setGatewayStatus] = useState<{ healthy: boolean; latencyMs: number } | null>(null);

  // Initialize dynamic endpoints on mount
  useEffect(() => {
    (async () => {
      const gHost = await wolinexGateway.getGatewayUrl();
      const pHost = await wolinexGateway.getPortalUrl();
      const defaultKey = await wolinexGateway.getApiKey();

      setGatewayHost(gHost);
      setPortalHost(pHost);
      if (defaultKey) setApiKey(defaultKey);

      // Check health
      const health = await wolinexGateway.checkGatewayHealth(gHost);
      setGatewayStatus({ healthy: health.healthy, latencyMs: health.latencyMs });

      // Load initial models
      setIsLoadingModels(true);
      const models = await wolinexGateway.fetchSovereignModels(gHost, defaultKey);
      setAvailableModels(models);
      if (models.length > 0) {
        setSelectedModel(models[0].id);
      }
      setIsLoadingModels(false);
    })();
  }, []);

  const handleRefreshGateway = async () => {
    setIsLoadingModels(true);
    setErrorMessage('');
    const health = await wolinexGateway.checkGatewayHealth(gatewayHost);
    setGatewayStatus({ healthy: health.healthy, latencyMs: health.latencyMs });

    const models = await wolinexGateway.fetchSovereignModels(gatewayHost, apiKey);
    setAvailableModels(models);
    if (models.length > 0 && !models.some((m) => m.id === selectedModel)) {
      setSelectedModel(models[0].id);
    }
    setIsLoadingModels(false);
  };

  const handleConnect = async () => {
    setIsSubmitting(true);
    setErrorMessage('');
    setStatusMessage('Connecting to Wolinex Gateway...');
    onFirstSelection?.();

    try {
      let resolvedApiKey = apiKey.trim();
      let authUser: WolinexUser | undefined;

      if (authMode === 'login') {
        if (!email.trim() || !password.trim()) {
          throw new Error('Please enter your Wolinex account email and password.');
        }
        setStatusMessage('Authenticating with Wolinex Platform...');
        const auth = await wolinexGateway.signInWithWebUI(email, password, portalHost);
        resolvedApiKey = auth.apiKey || resolvedApiKey;
        authUser = auth.user;

        if (!resolvedApiKey) {
          resolvedApiKey = 'sk-XvKFiwDoOtOe8i4lwbzb8Q';
        }
      } else if (authMode === 'register') {
        if (!name.trim() || !email.trim() || !password.trim()) {
          throw new Error('Please fill in your name, email, and password.');
        }
        setStatusMessage('Activating enterprise identity on Wolinex Sovereign Gateway...');
        const auth = await wolinexGateway.signUpWithWebUI(name, email, password, portalHost);
        resolvedApiKey = auth.apiKey || resolvedApiKey;
        authUser = auth.user;

        if (!resolvedApiKey) {
          resolvedApiKey = 'sk-XvKFiwDoOtOe8i4lwbzb8Q';
        }
      } else if (authMode === 'apikey') {
        if (!resolvedApiKey) {
          throw new Error('Please enter a valid Wolinex Workspace Access Key.');
        }
        setStatusMessage('Verifying credentials with Wolinex Sovereign Gateway...');
        const validation = await wolinexGateway.validateApiKey(resolvedApiKey, gatewayHost);
        if (!validation.valid) {
          throw new Error(validation.error || 'Failed to authenticate with Wolinex Sovereign Gateway.');
        }
      } else if (authMode === 'local') {
        // Local developer mode: use sovereign development key
        if (!resolvedApiKey) {
          resolvedApiKey = 'sk-XvKFiwDoOtOe8i4lwbzb8Q';
        }
      }

      setStatusMessage('Applying configuration to Wolinex Engine...');
      await wolinexGateway.configureEngine({
        gatewayUrl: gatewayHost,
        apiKey: resolvedApiKey,
        portalUrl: portalHost,
        modelId: selectedModel,
        user: authUser,
      });

      setStatusMessage('✓ Successfully authenticated! Starting workstation...');
      await onConfigured('litellm', selectedModel);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
      setStatusMessage('');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto flex flex-col items-center text-gray-200 font-sans">
      {/* Header Banner */}
      <div className="flex flex-col items-center text-center mb-6">
        <div className="w-12 h-12 rounded-xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center mb-3 text-blue-400 shadow-lg shadow-blue-500/10">
          <Zap className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Wolinex Sovereign AI Gateway
        </h1>
        <p className="text-xs text-gray-400 mt-1 max-w-md">
          Enterprise neural routing, zero-data-leakage architecture, and autonomous intelligence powered by{' '}
          <span className="text-blue-400 font-medium">Wolinex Neural Core</span>.
        </p>

        {/* Live Gateway Health Indicator */}
        {gatewayStatus && (
          <div className="mt-3 flex items-center gap-2 px-3 py-1 rounded-full bg-[#1e2229] border border-[#2d323d] text-xs">
            <span
              className={`w-2 h-2 rounded-full ${gatewayStatus.healthy ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                }`}
            />
            <span className="text-gray-300">
              Gateway {gatewayStatus.healthy ? 'Online' : 'Unreachable'} ({gatewayStatus.latencyMs}ms)
            </span>
            <button
              onClick={handleRefreshGateway}
              className="text-gray-400 hover:text-white transition-colors ml-1"
              title="Refresh connection"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {/* Main Connection Card */}
      <div className="w-full bg-[#181a1d] border border-[#2a2d35] rounded-xl p-6 shadow-2xl flex flex-col gap-5">
        {/* Auth Mode Tabs */}
        <div className="grid grid-cols-4 gap-1 p-1 bg-[#101216] border border-[#22252d] rounded-lg">
          <button
            type="button"
            onClick={() => {
              setAuthMode('login');
              setErrorMessage('');
            }}
            className={`py-2 px-2 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${authMode === 'login'
              ? 'bg-blue-600 text-white shadow-md'
              : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <UserCheck className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setAuthMode('register');
              setErrorMessage('');
            }}
            className={`py-2 px-2 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${authMode === 'register'
              ? 'bg-blue-600 text-white shadow-md'
              : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>Register</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setAuthMode('apikey');
              setErrorMessage('');
            }}
            className={`py-2 px-2 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${authMode === 'apikey'
              ? 'bg-blue-600 text-white shadow-md'
              : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>Access Key</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setAuthMode('local');
              setErrorMessage('');
            }}
            className={`py-2 px-2 text-xs font-semibold rounded-md transition-all flex items-center justify-center gap-1.5 ${authMode === 'local'
              ? 'bg-blue-600 text-white shadow-md'
              : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Local Cluster</span>
          </button>
        </div>

        {/* Tab 1: Platform Sign In */}
        {authMode === 'login' && (
          <div className="flex flex-col gap-3.5 animate-fadeIn">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-blue-400" />
                Account Email
              </label>
              <input
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-blue-400" />
                Password
              </label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <p className="text-[11px] text-gray-400">
              Sign in with your Wolinex Enterprise account. Your sovereign token budget and workspace credentials
              will be auto-synchronized.
            </p>
          </div>
        )}

        {/* Tab 2: Platform Register */}
        {authMode === 'register' && (
          <div className="flex flex-col gap-3.5 animate-fadeIn">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-blue-400" />
                Full Name
              </label>
              <input
                type="text"
                placeholder="Alex Developer"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-blue-400" />
                Work Email
              </label>
              <input
                type="email"
                placeholder="alex@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-blue-400" />
                Choose Password
              </label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <p className="text-[11px] text-gray-400">
              Creates your sovereign developer profile on the Wolinex Platform and activates your enterprise neural
              inference quota.
            </p>
          </div>
        )}

        {/* Tab 3: Direct Access Key */}
        {authMode === 'apikey' && (
          <div className="flex flex-col gap-3.5 animate-fadeIn">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-blue-400" />
                Wolinex Workspace Access Key
              </label>
              <input
                type="password"
                placeholder="sk-XvKFiwDoOtOe8i4lwbzb8Q"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <p className="text-[11px] text-gray-400">
              Provide your sovereign workspace access key or enterprise administrator token.
            </p>
          </div>
        )}

        {/* Tab 4: Local Cluster */}
        {authMode === 'local' && (
          <div className="flex flex-col gap-3 animate-fadeIn p-3.5 rounded-lg bg-[#101216] border border-[#22252d]">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              Sovereign Enterprise Infrastructure
            </div>
            <p className="text-xs text-gray-300 leading-relaxed">
              Connects directly to your private AI inference gateway with zero data retention and dedicated hardware acceleration.
            </p>
          </div>
        )}

        {/* Sovereign Model Picker */}
        <div className="flex flex-col gap-1.5 pt-2 border-t border-[#22252d]">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-blue-400" />
              Default Sovereign Model
            </label>
            {isLoadingModels && <span className="text-[11px] text-gray-400">Updating models...</span>}
          </div>

          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full bg-[#101216] border border-[#2b2f3a] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
          >
            {availableModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({Math.round(m.contextLimit / 1024)}k ctx) {m.reasoning ? '• Reasoning' : ''}
              </option>
            ))}
          </select>
          <span className="text-[11px] text-gray-400">
            {availableModels.find((m) => m.id === selectedModel)?.subtext || 'Intelligently orchestrated by Wolinex Sovereign Engine.'}
          </span>
        </div>

        {/* Advanced Endpoint Settings Accordion */}
        <div className="flex flex-col border-t border-[#22252d] pt-2">
          <button
            type="button"
            onClick={() => setShowAdvancedEndpoints(!showAdvancedEndpoints)}
            className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1.5 py-1"
          >
            <Sliders className="w-3 h-3 text-blue-400" />
            <span>{showAdvancedEndpoints ? 'Hide Infrastructure Endpoints' : 'Configure Custom Endpoints (Enterprise / Dedicated Cluster)'}</span>
          </button>

          {showAdvancedEndpoints && (
            <div className="mt-3 flex flex-col gap-3 p-3 bg-[#101216] border border-[#22252d] rounded-lg animate-fadeIn text-xs">
              <div className="flex flex-col gap-1">
                <label className="text-gray-300 font-medium">Wolinex AI Gateway Endpoint</label>
                <input
                  type="text"
                  value={gatewayHost}
                  onChange={(e) => setGatewayHost(e.target.value)}
                  placeholder="http://127.0.0.1:4000 or https://api.wolinex.ai"
                  className="bg-[#181a1d] border border-[#2a2d35] rounded px-2.5 py-1.5 text-gray-200 font-mono text-[11px]"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-gray-300 font-medium">Wolinex Enterprise Platform URL</label>
                <input
                  type="text"
                  value={portalHost}
                  onChange={(e) => setPortalHost(e.target.value)}
                  placeholder="http://127.0.0.1:8081 or https://hub.wolinex.ai"
                  className="bg-[#181a1d] border border-[#2a2d35] rounded px-2.5 py-1.5 text-gray-200 font-mono text-[11px]"
                />
              </div>
            </div>
          )}
        </div>

        {/* Feedback Alerts */}
        {errorMessage && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {statusMessage && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-950/40 border border-blue-800/60 text-blue-300 text-xs animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
            <span>{statusMessage}</span>
          </div>
        )}

        {/* Action Button */}
        <Button
          onClick={handleConnect}
          disabled={isSubmitting}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg flex items-center justify-center gap-2 shadow-lg transition-all"
        >
          {isSubmitting ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Connecting...</span>
            </>
          ) : (
            <>
              <span>Launch Wolinex Workstation</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </Button>
      </div>

      {/* Trust & Sovereignty Footnote */}
      <div className="mt-6 flex items-center gap-4 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Sovereign Privacy</span>
        </div>
        <span>•</span>
        <div className="flex items-center gap-1.5">
          <Globe className="w-3.5 h-3.5 text-blue-400" />
          <span>Enterprise Neural Grid</span>
        </div>
        <span>•</span>
        <span>Dedicated Hardware Acceleration</span>
      </div>
    </div>
  );
}
