import type {
  CanonicalModelInfoDto,
  CustomProviderCreateRequest_unstable,
  CustomProviderReadResponse_unstable,
  ProviderSecretDto,
  ProviderInventoryEntryDto,
  RefreshProviderInventoryResponse_unstable,
  ProviderTemplateCatalogEntryDto,
  ProviderTemplateDto,
} from '@aaif/goose-acp-client';
import { methods } from '@agentclientprotocol/sdk';
import type {
  ProviderDetails,
  ThinkingEffort,
  UpdateCustomProviderRequest,
} from '../types/providers';
import { getAcpClient } from './acpConnection';
import { wolinexGateway } from '../services/wolinexGatewayService';

export type { CanonicalModelInfoDto, ProviderSecretDto };

const INVENTORY_REFRESH_POLL_INTERVAL_MS = 100;
const INVENTORY_REFRESH_TIMEOUT_MS = 30_000;

function throwIfAborted(signal?: globalThis.AbortSignal) {
  if (signal?.aborted) throw new DOMException('The operation was aborted', 'AbortError');
}

function waitForInventoryPoll(signal?: globalThis.AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      signal?.removeEventListener('abort', abort);
      resolve();
    }, INVENTORY_REFRESH_POLL_INTERVAL_MS);
    const abort = () => {
      window.clearTimeout(timeout);
      reject(new DOMException('The operation was aborted', 'AbortError'));
    };
    signal?.addEventListener('abort', abort, { once: true });
  });
}

export const SOVEREIGN_GATEWAY_MODELS = [
  { id: 'Wolinex Coder', name: 'Wolinex Coder', contextLimit: 32768, reasoning: true },
  { id: 'Wolinet Pro', name: 'Wolinet Pro', contextLimit: 32768, reasoning: false },
  { id: 'Wolinet Max', name: 'Wolinet Max', contextLimit: 1048576, reasoning: true },
  { id: 'Wolinet Turbo Draft', name: 'Wolinet Turbo Draft', contextLimit: 32768, reasoning: false },
  { id: 'Secure Pro', name: 'Secure Pro', contextLimit: 32768, reasoning: false },
];

export function getDefaultWolinexGatewayProvider(): ProviderDetails {
  const dynamicHost = wolinexGateway.getGatewayUrlSync();
  const dynamicKey = wolinexGateway.getApiKeySync();

  return {
    name: 'litellm',
    is_configured: true,
    is_available: true,
    is_refreshing: false,
    last_refresh_error: null,
    supports_refresh: true,
    visible_in_setup: true,
    deprecated: false,
    replacement: null,
    provider_type: 'Standard' as ProviderDetails['provider_type'],
    uses_acp: false,
    metadata: {
      name: 'litellm',
      display_name: 'Wolinex Sovereign AI Gateway',
      description:
        'Unified Sovereign AI Gateway providing zero-data-leakage model routing, enterprise authentication, and intelligent agent orchestration.',
      default_model: 'Wolinex Coder',
      model_doc_link: wolinexGateway.getWebUIUrlSync(),
      config_keys: [
        {
          name: 'LITELLM_HOST',
          required: true,
          secret: false,
          default: dynamicHost,
          oauth_flow: false,
          device_code_flow: false,
          primary: true,
        },
        {
          name: 'LITELLM_API_KEY',
          required: false,
          secret: true,
          default: dynamicKey || null,
          oauth_flow: false,
          device_code_flow: false,
          primary: true,
        },
      ],
      known_models: SOVEREIGN_GATEWAY_MODELS.map((m) => ({
        name: m.name,
        context_limit: m.contextLimit,
        reasoning: m.reasoning,
      })),
      setup_steps: [],
    },
  };
}

function providerEntryToDetails(entry: ProviderInventoryEntryDto): ProviderDetails {
  const isLiteLLM = entry.providerId === 'litellm';
  return {
    name: entry.providerId,
    is_configured: isLiteLLM ? true : entry.configured,
    is_available: isLiteLLM ? true : entry.available,
    is_refreshing: entry.refreshing,
    last_refresh_error: entry.lastRefreshError ?? null,
    supports_refresh: entry.supportsRefresh,
    visible_in_setup: isLiteLLM ? true : entry.visibleInSetup,
    deprecated: entry.deprecated,
    replacement: entry.replacement ?? null,
    provider_type: entry.providerType as ProviderDetails['provider_type'],
    uses_acp: entry.acp ?? false,
    metadata: {
      name: entry.providerId,
      display_name: isLiteLLM ? 'Wolinex Sovereign AI Gateway' : entry.providerName,
      description: isLiteLLM
        ? 'Unified Sovereign AI Gateway providing zero-data-leakage model routing, enterprise authentication, and intelligent agent orchestration.'
        : entry.description,
      default_model: isLiteLLM ? 'Wolinex Coder' : entry.defaultModel,
      model_doc_link: '',
      config_keys: entry.configKeys.map((key) => ({
        name: key.name,
        required: key.required,
        secret: key.secret,
        default: key.default ?? null,
        oauth_flow: key.oauthFlow ?? false,
        device_code_flow: key.deviceCodeFlow ?? false,
        primary: key.primary ?? false,
      })),
      known_models:
        isLiteLLM && entry.models.length === 0
          ? SOVEREIGN_GATEWAY_MODELS.map((m) => ({
              name: m.name,
              context_limit: m.contextLimit,
              reasoning: m.reasoning,
            }))
          : entry.models.map((model) => ({
              name: model.id,
              context_limit: model.contextLimit ?? undefined,
              reasoning: model.reasoning ?? undefined,
            })),
      setup_steps: entry.setupSteps,
    },
  };
}

function updateRequestToCreate(
  request: UpdateCustomProviderRequest
): CustomProviderCreateRequest_unstable {
  return {
    engine: request.engine,
    displayName: request.display_name,
    apiUrl: request.api_url,
    apiKey: request.api_key || null,
    models: request.models,
    supportsStreaming: request.supports_streaming ?? null,
    headers: request.headers ?? undefined,
    requiresAuth: request.requires_auth,
    catalogProviderId: request.catalog_provider_id ?? null,
    basePath: request.base_path ?? null,
    toolshim: request.toolshim,
    preservesThinking: request.preserves_thinking ?? null,
  };
}

export async function acpListProviderDetails(): Promise<ProviderDetails[]> {
  try {
    const client = await getAcpClient();
    const { entries } = await client.goose.providersList_unstable({});
    const details = entries.map(providerEntryToDetails);
    // Strictly filter out all cloud and third-party direct providers
    // Only allow Wolinex Lango Gateway (litellm) and custom endpoints routed to it
    const filtered = details.filter(
      (p) =>
        p.name === 'litellm' ||
        (p.provider_type === 'Custom' && !['openai', 'anthropic', 'google', 'groq', 'ollama', 'databricks', 'snowflake', 'xai', 'minimax'].includes(p.name))
    );
    if (filtered.length === 0) {
      filtered.push(getDefaultWolinexGatewayProvider());
    }
    return filtered;
  } catch (error) {
    console.warn('Using default Wolinex Gateway provider:', error);
    return [getDefaultWolinexGatewayProvider()];
  }
}

export async function acpListSetupProviderDetails(): Promise<ProviderDetails[]> {
  const providers = await acpListProviderDetails();
  return providers.filter((provider) => provider.visible_in_setup);
}

export async function acpListSettingsProviderDetails(): Promise<ProviderDetails[]> {
  const providers = await acpListProviderDetails();
  return providers.filter((provider) => provider.visible_in_setup || provider.is_configured);
}

export async function acpGetProviderDetails(providerId: string): Promise<ProviderDetails> {
  if (providerId === 'litellm') {
    try {
      const client = await getAcpClient();
      const { entries } = await client.goose.providersList_unstable({ providerIds: [providerId] });
      const entry = entries.find((candidate) => candidate.providerId === providerId);
      if (entry) return providerEntryToDetails(entry);
    } catch {
      // fallback
    }
    return getDefaultWolinexGatewayProvider();
  }
  const client = await getAcpClient();
  const { entries } = await client.goose.providersList_unstable({ providerIds: [providerId] });
  const entry = entries.find((candidate) => candidate.providerId === providerId);
  if (!entry) throw new Error(`Unknown provider: ${providerId}`);
  return providerEntryToDetails(entry);
}

async function waitForProviderInventoryRefresh(
  client: Awaited<ReturnType<typeof getAcpClient>>,
  providerId: string,
  refresh: RefreshProviderInventoryResponse_unstable,
  signal?: globalThis.AbortSignal
): Promise<ProviderDetails> {
  const shouldWait =
    refresh.started.includes(providerId) ||
    refresh.skipped?.some(
      (skip) => skip.providerId === providerId && skip.reason === 'already_refreshing'
    );

  let entry: ProviderInventoryEntryDto | undefined;
  const attempts = shouldWait
    ? INVENTORY_REFRESH_TIMEOUT_MS / INVENTORY_REFRESH_POLL_INTERVAL_MS
    : 1;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    throwIfAborted(signal);
    const response = await client.goose.providersList_unstable({ providerIds: [providerId] });
    throwIfAborted(signal);
    entry = response.entries.find((candidate) => candidate.providerId === providerId);
    if (!entry) throw new Error(`Unknown provider: ${providerId}`);
    if (!entry.refreshing) return providerEntryToDetails(entry);
    await waitForInventoryPoll(signal);
  }

  if (!entry) throw new Error(`Unknown provider: ${providerId}`);
  throw new Error(`Timed out while checking ${entry.providerName}`);
}

export async function acpRefreshProviderDetails(
  providerId: string,
  signal?: globalThis.AbortSignal
): Promise<{
  provider: ProviderDetails;
  connectionChecked: boolean;
  readinessError: string | null;
}> {
  const client = await getAcpClient();
  throwIfAborted(signal);
  let { entries } = await client.goose.providersList_unstable({ providerIds: [providerId] });
  throwIfAborted(signal);
  let entry = entries.find((candidate) => candidate.providerId === providerId);
  if (!entry) throw new Error(`Unknown provider: ${providerId}`);

  if (!entry.available) {
    return {
      provider: providerEntryToDetails(entry),
      connectionChecked: false,
      readinessError: null,
    };
  }

  const readiness = await client.goose.providersReadinessCheck_unstable({ providerId });
  throwIfAborted(signal);
  if (!readiness.ready) {
    return {
      provider: providerEntryToDetails(entry),
      connectionChecked: true,
      readinessError: readiness.error ?? 'Provider is not ready',
    };
  }

  if (entry.supportsRefresh) {
    const refresh = await client.goose.providersInventoryRefresh_unstable({
      providerIds: [providerId],
    });
    const provider = await waitForProviderInventoryRefresh(client, providerId, refresh, signal);
    return { provider, connectionChecked: true, readinessError: null };
  }

  return {
    provider: providerEntryToDetails(entry),
    connectionChecked: true,
    readinessError: null,
  };
}

export async function acpListProviderModels(providerId: string) {
  const safeProvider =
    !providerId || ['openai', 'openaib', 'anthropic', 'google', 'groq'].includes(providerId)
      ? 'litellm'
      : providerId;

  if (safeProvider === 'litellm') {
    // 1. Fetch live sovereign models directly from LiteLLM / Lango gateway
    try {
      const host = await wolinexGateway.getGatewayUrl();
      const apiKey = await wolinexGateway.getApiKey();
      const headers: Record<string, string> = {};
      if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;

      const res = await fetch(`${host}/v1/models`, { headers });
      if (res.ok) {
        const json = await res.json();
        if (Array.isArray(json?.data) && json.data.length > 0) {
          const validModels = json.data
            .filter((m: { id?: string; model_name?: string; mode?: string }) => {
              const id = m.id || m.model_name || '';
              if (m.mode && (m.mode === 'embedding' || m.mode === 'audio_transcription')) return false;
              if (id.startsWith('text-embedding') || id.startsWith('whisper') || id.startsWith('dall-e')) return false;
              if (/deepseek/i.test(id) || /gpt-/i.test(id) || /gemini-/i.test(id) || /claude-/i.test(id)) return false;
              return true;
            })
            .map((m: { id?: string; model_name?: string; max_input_tokens?: number }) => ({
              id: m.id || m.model_name || '',
              name: m.id || m.model_name || '',
              contextLimit: m.max_input_tokens ?? 32768,
              reasoning: Boolean(m.max_input_tokens && m.max_input_tokens > 32768),
            }));

          if (validModels.length > 0) return validModels;
        }
      }
    } catch {
      // Continue to ACP discovery
    }

    // 2. Fall back to ACP client discovery
    try {
      const client = await getAcpClient();
      const { entries } = await client.goose.providersList_unstable({ providerIds: [safeProvider] });
      const models = entries.find((e) => e.providerId === safeProvider)?.models;
      if (models && models.length > 0) {
        const clean = models.filter((m) => !/deepseek/i.test(m.id) && !/gpt-/i.test(m.id));
        if (clean.length > 0) return clean;
      }
    } catch {
      // fallback
    }
    return SOVEREIGN_GATEWAY_MODELS.map((m) => ({
      id: m.id,
      name: m.name,
      contextLimit: m.contextLimit,
      reasoning: m.reasoning,
    }));
  }
  const client = await getAcpClient();
  const { entries } = await client.goose.providersList_unstable({ providerIds: [safeProvider] });
  return entries.find((e) => e.providerId === safeProvider)?.models ?? [];
}

export async function acpListProviderCatalogEntries(
  _format?: string
): Promise<ProviderTemplateCatalogEntryDto[]> {
  // Cloud providers catalog stripped per user instructions
  return [];
}

export async function acpGetProviderTemplate(providerId: string): Promise<ProviderTemplateDto> {
  const client = await getAcpClient();
  const { template } = await client.goose.providersCatalogTemplate_unstable({ providerId });
  return template;
}

export async function acpGetCustomProvider(
  providerId: string
): Promise<CustomProviderReadResponse_unstable> {
  const client = await getAcpClient();
  return client.goose.providersCustomRead_unstable({ providerId });
}

export async function acpCreateCustomProviderFromRequest(
  request: UpdateCustomProviderRequest
): Promise<{ provider_name: string }> {
  const client = await getAcpClient();
  const response = await client.goose.providersCustomCreate_unstable(
    updateRequestToCreate(request)
  );
  return { provider_name: response.providerId };
}

export async function acpUpdateCustomProviderFromRequest(
  providerId: string,
  request: UpdateCustomProviderRequest
): Promise<void> {
  const client = await getAcpClient();
  await client.goose.providersCustomUpdate_unstable({
    providerId,
    ...updateRequestToCreate(request),
  });
}

export async function acpDeleteCustomProvider(providerId: string): Promise<void> {
  const client = await getAcpClient();
  await client.goose.providersCustomDelete_unstable({ providerId });
}

export async function acpReadProviderConfig(providerId: string) {
  const client = await getAcpClient();
  const { fields } = await client.goose.providersConfigRead_unstable({ providerId });
  return fields;
}

export async function acpDeleteProviderConfig(providerId: string): Promise<void> {
  const client = await getAcpClient();
  await client.goose.providersConfigDelete_unstable({ providerId });
}

export async function acpSaveProviderConfig(
  providerId: string,
  fields: { key: string; value: string }[]
): Promise<void> {
  const client = await getAcpClient();
  await client.goose.providersConfigSave_unstable({ providerId, fields });
}

export async function acpEnableProvider(
  providerId: string,
  signal?: globalThis.AbortSignal
): Promise<ProviderDetails> {
  const client = await getAcpClient();
  throwIfAborted(signal);
  const { refresh } = await client.goose.providersConfigSave_unstable({
    providerId,
    fields: [],
  });
  throwIfAborted(signal);
  return waitForProviderInventoryRefresh(client, providerId, refresh, signal);
}

export async function acpAuthenticateProvider(providerId: string): Promise<void> {
  const client = await getAcpClient();
  await client.goose.providersConfigAuthenticate_unstable({ providerId });
}

export async function acpListProviderSecrets(): Promise<ProviderSecretDto[]> {
  const client = await getAcpClient();
  const { secrets } = await client.goose.providersSecretsList_unstable({});
  return secrets;
}

export async function acpDeleteProviderSecret(id: string): Promise<void> {
  const client = await getAcpClient();
  await client.goose.providersSecretsDelete_unstable({ id });
}

export async function acpGetCanonicalModelInfo(
  provider: string,
  model: string
): Promise<CanonicalModelInfoDto | null> {
  const client = await getAcpClient();
  const { modelInfo } = await client.goose.providersCanonicalModelInfo_unstable({
    provider,
    model,
  });
  return modelInfo ?? null;
}

export async function acpReadDefaults(): Promise<{
  providerId: string | null;
  modelId: string | null;
}> {
  try {
    const client = await getAcpClient();
    const response = await client.goose.defaultsRead_unstable({});
    let providerId = response.providerId ?? null;
    let modelId = response.modelId ?? null;

    if (!providerId || ['openai', 'openaib', 'anthropic', 'google', 'groq'].includes(providerId)) {
      providerId = 'litellm';
    }
    if (!modelId || modelId.startsWith('gpt-') || /deepseek/i.test(modelId)) {
      modelId = 'Wolinex Coder';
    }
    return {
      providerId,
      modelId,
    };
  } catch {
    return {
      providerId: 'litellm',
      modelId: 'Wolinex Coder',
    };
  }
}

export async function acpSaveDefaults(providerId: string, modelId: string | null): Promise<void> {
  const safeProvider = (!providerId || ['openai', 'openaib', 'anthropic', 'google', 'groq'].includes(providerId))
    ? 'litellm'
    : providerId;
  const safeModel = (!modelId || modelId.startsWith('gpt-') || /deepseek/i.test(modelId))
    ? 'Wolinex Coder'
    : modelId;

  const client = await getAcpClient();
  await client.goose.defaultsSave_unstable({ providerId: safeProvider, modelId: safeModel });
}

export async function acpClearDefaults(): Promise<void> {
  const client = await getAcpClient();
  await client.goose.defaultsClear_unstable({});
}

export async function acpReadThinkingEffort(): Promise<ThinkingEffort | null> {
  const client = await getAcpClient();
  const response = await client.goose.preferencesRead_unstable({ keys: ['gooseThinkingEffort'] });
  const value = response.values.find((v) => v.key === 'gooseThinkingEffort')?.value;
  return typeof value === 'string' ? (value as ThinkingEffort) : null;
}

export async function acpSaveThinkingEffort(effort: ThinkingEffort): Promise<void> {
  const client = await getAcpClient();
  await client.goose.preferencesSave_unstable({
    values: [{ key: 'gooseThinkingEffort', value: effort }],
  });
}

export type AppliedSessionProviderModel = {
  providerId?: string;
  modelId?: string;
};

function extractAppliedSessionProviderModel(configOptions: unknown): AppliedSessionProviderModel {
  if (!Array.isArray(configOptions)) {
    return {};
  }

  const applied: AppliedSessionProviderModel = {};

  for (const option of configOptions) {
    if (!option || typeof option !== 'object') {
      continue;
    }

    const id = 'id' in option ? option.id : undefined;
    if (id !== 'provider' && id !== 'model') {
      continue;
    }

    const currentValue = selectCurrentValue(option);
    if (typeof currentValue !== 'string') {
      continue;
    }

    if (id === 'provider') {
      applied.providerId = currentValue;
    } else {
      applied.modelId = currentValue;
    }
  }

  return applied;
}

function selectCurrentValue(kind: unknown): unknown {
  if (!kind || typeof kind !== 'object') {
    return undefined;
  }

  if ('type' in kind && kind.type === 'select' && 'currentValue' in kind) {
    return kind.currentValue;
  }

  return undefined;
}

/**
 * Switch the provider (and model) for an active session via ACP config options.
 *
 * Changing the provider on the server resets the session's model, so the model
 * is applied as a follow-up step when supplied.
 */
export async function acpSetSessionProviderModel(
  sessionId: string,
  providerId: string,
  modelId?: string | null,
  thinkingEffort?: ThinkingEffort | null
): Promise<AppliedSessionProviderModel> {
  const safeProvider =
    !providerId || ['openai', 'openaib', 'anthropic', 'google', 'groq'].includes(providerId)
      ? 'litellm'
      : providerId;
  const safeModel =
    !modelId || modelId.startsWith('gpt-') || /deepseek/i.test(modelId)
      ? 'Wolinex Coder'
      : modelId;

  const client = await getAcpClient();
  let response = await client.connection.agent.request(methods.agent.session.setConfigOption, {
    sessionId,
    configId: 'provider',
    value: safeProvider,
  });
  if (safeModel) {
    response = await client.connection.agent.request(methods.agent.session.setConfigOption, {
      sessionId,
      configId: 'model',
      value: safeModel,
    });
  }
  if (thinkingEffort != null) {
    response = await client.connection.agent.request(methods.agent.session.setConfigOption, {
      sessionId,
      configId: 'thinking_effort',
      value: thinkingEffort,
    });
  }

  return extractAppliedSessionProviderModel(response.configOptions);
}
