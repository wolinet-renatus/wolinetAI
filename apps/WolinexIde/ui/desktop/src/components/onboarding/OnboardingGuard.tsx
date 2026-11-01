import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useConfig } from '../ConfigContext';
import { useModelAndProvider } from '../ModelAndProviderContext';
import { acpListProviderDetails, acpReadDefaults, acpSaveDefaults } from '../../acp/providers';
import { Button } from '../ui/button';
import { RefreshCw, AlertCircle } from 'lucide-react';
import ProviderSelector from './ProviderSelector';
import OnboardingSuccess from './OnboardingSuccess';
import {
  trackOnboardingStarted,
  trackOnboardingCompleted,
  trackOnboardingProviderSelected,
  trackTelemetryPreference,
  setTelemetryEnabled as setAnalyticsTelemetryEnabled,
} from '../../utils/analytics';

const TELEMETRY_CONFIG_KEY = 'GOOSE_TELEMETRY_ENABLED';

interface OnboardingGuardProps {
  children: React.ReactNode;
}

export default function OnboardingGuard({ children }: OnboardingGuardProps) {
  const navigate = useNavigate();
  const { upsert } = useConfig();
  const { getFallbackModelAndProvider, refreshCurrentModelAndProvider } = useModelAndProvider();

  const [isCheckingProvider, setIsCheckingProvider] = useState(true);
  const [hasProvider, setHasProvider] = useState(false);
  const [checkProviderError, setCheckProviderError] = useState(false);
  const [hasSelection, setHasSelection] = useState(false);
  const [configuredProvider, setConfiguredProvider] = useState<string | null>(null);
  const [configuredProviderDisplayName, setConfiguredProviderDisplayName] = useState<string | null>(
    null
  );
  const [configuredModel, setConfiguredModel] = useState<string | null>(null);
  const hasTrackedOnboardingStart = useRef(false);

  const checkProvider = async (retries = 3, delay = 1000) => {
    setIsCheckingProvider(true);
    setCheckProviderError(false);

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const { providerId, modelId } = await acpReadDefaults();

        // If litellm is already the active provider and has a model, proceed immediately
        if (
          providerId === 'litellm' &&
          modelId &&
          !modelId.includes('Deepseeker') &&
          !modelId.includes('deepseek')
        ) {
          setHasProvider(true);
          setIsCheckingProvider(false);
          return;
        }

        // Try auto-resolving fallback litellm provider with dynamic model from LiteLLM
        const fallback = await getFallbackModelAndProvider();
        if (fallback.provider === 'litellm' && fallback.model?.trim()) {
          await acpSaveDefaults(fallback.provider, fallback.model);
          await refreshCurrentModelAndProvider();
          setHasProvider(true);
          setIsCheckingProvider(false);
          return;
        }

        setHasProvider(false);
        setIsCheckingProvider(false);
        return;
      } catch (error) {
        console.error(`Error verifying Wolinex provider (attempt ${attempt + 1}/${retries + 1}):`, error);
        if (attempt < retries) {
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      }
    }

    setCheckProviderError(true);
    setIsCheckingProvider(false);
  };

  useEffect(() => {
    checkProvider();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isCheckingProvider && !hasProvider && !checkProviderError && !hasTrackedOnboardingStart.current) {
      trackOnboardingStarted();
      hasTrackedOnboardingStart.current = true;
    }
  }, [isCheckingProvider, hasProvider, checkProviderError]);

  const handleConfigured = async (providerName: string, modelId?: string) => {
    trackOnboardingProviderSelected({ provider: providerName });
    const providers = await acpListProviderDetails();
    const matchedProvider = providers.find((p) => p.name === providerName);
    const resolvedModel = modelId ?? matchedProvider?.metadata.default_model ?? 'Wolinex Coder';

    await acpSaveDefaults(providerName, resolvedModel);
    setConfiguredModel(resolvedModel);
    await refreshCurrentModelAndProvider();
    setConfiguredProvider(providerName);
    setConfiguredProviderDisplayName('Wolinex Sovereign AI Gateway');
  };

  const finishOnboarding = async (telemetryEnabled: boolean) => {
    try {
      await upsert(TELEMETRY_CONFIG_KEY, telemetryEnabled, false);
    } catch (error) {
      console.error('Failed to save telemetry preference:', error);
    }
    trackTelemetryPreference(telemetryEnabled, 'onboarding');
    if (configuredProvider) {
      trackOnboardingCompleted(configuredProvider, configuredModel ?? undefined);
    }
    if (!telemetryEnabled) {
      setAnalyticsTelemetryEnabled(false);
    }
    navigate('/', { replace: true });
    setHasProvider(true);
  };

  if (isCheckingProvider) {
    return (
      <div className="h-screen w-full bg-[#101216] flex flex-col items-center justify-center text-gray-400 gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
        <span className="text-xs font-mono">Initializing Wolinex Sovereign Workstation...</span>
      </div>
    );
  }

  if (checkProviderError) {
    return (
      <div className="h-screen w-full bg-[#101216] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-[#181a1d] border border-[#2a2d35] rounded-xl p-6 text-center text-gray-200">
          <div className="w-12 h-12 rounded-xl bg-red-600/20 border border-red-500/40 flex items-center justify-center mx-auto mb-4 text-red-400">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h1 className="text-lg font-bold text-white mb-2">Unable to Connect to Wolinex Engine</h1>
          <p className="text-xs text-gray-400 mb-5">
            The ACP backend service or local Lango Gateway may still be initializing.
          </p>
          <Button
            onClick={() => checkProvider()}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold py-2 rounded-lg"
          >
            Retry Connection
          </Button>
        </div>
      </div>
    );
  }

  if (hasProvider) {
    return <>{children}</>;
  }

  if (configuredProviderDisplayName) {
    return (
      <OnboardingSuccess providerName={configuredProviderDisplayName} onFinish={finishOnboarding} />
    );
  }

  return (
    <div className="h-screen w-full bg-[#101216] overflow-hidden">
      <div className="h-full overflow-y-auto">
        <div
          className={`flex flex-col items-center p-4 pb-8 transition-all duration-500 ease-in-out ${
            hasSelection ? 'pt-8' : 'pt-[10vh]'
          }`}
        >
          <div className="max-w-2xl w-full mx-auto">
            <ProviderSelector
              onConfigured={handleConfigured}
              onFirstSelection={() => setHasSelection(true)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
