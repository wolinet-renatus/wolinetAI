/**
 * Wolinex Sovereign AI Gateway & Authentication Service
 * =======================================================
 * Production-grade client integrating Wolinex Desktop Workstation with:
 * 1. Lango LiteLLM Gateway (Centralized token budget, proxy & model routing)
 * 2. Wolinex WebUI / Sovereign Developer Portal (User signup/login & key provisioning)
 *
 * Designed for dynamic endpoint discovery across development and deployment environments.
 * Strictly avoids brittle hardcoded paths.
 */

import { acpSaveDefaults, acpSaveProviderConfig } from '../acp/providers';

export interface WolinexUser {
  id: string;
  name: string;
  email: string;
  role: string;
}

export interface WolinexCredits {
  allocated: number;
  spent: number;
  remaining: number;
  currency: string;
  default_model?: string;
}

export interface WolinexAuthResult {
  authenticated: boolean;
  user: WolinexUser;
  token?: string;
  apiKey: string;
  credits?: WolinexCredits;
  defaultModel?: string;
}

export interface SovereignModel {
  id: string;
  name: string;
  contextLimit: number;
  reasoning: boolean;
  subtext?: string;
  isDefault?: boolean;
}

export interface GatewayHealthResult {
  healthy: boolean;
  latencyMs: number;
  status: string;
  error?: string;
}

// Fallback sovereign model catalog in case gateway is still booting
export const SOVEREIGN_FALLBACK_MODELS: SovereignModel[] = [
  {
    id: 'Wolinex Coder',
    name: 'Wolinex Coder',
    contextLimit: 32768,
    reasoning: true,
    subtext: 'Primary Sovereign Coding Engine & AST Analysis',
    isDefault: true,
  },
  {
    id: 'Wolinet Pro',
    name: 'Wolinet Pro',
    contextLimit: 32768,
    reasoning: false,
    subtext: 'Autonomous Multi-Agent Task Orchestration',
  },
  {
    id: 'Wolinet Max',
    name: 'Wolinet Max',
    contextLimit: 1048576,
    reasoning: true,
    subtext: '1,000,000-Token Multimodal Deep Reasoning MoE',
  },
  {
    id: 'Wolinet Turbo Draft',
    name: 'Wolinet Turbo Draft',
    contextLimit: 32768,
    reasoning: false,
    subtext: 'Ultra-Low Latency Speculative Stream',
  },
  {
    id: 'Secure Pro',
    name: 'Secure Pro',
    contextLimit: 32768,
    reasoning: false,
    subtext: 'Confidential Code Guard & Security Analysis',
  },
];

class WolinexGatewayService {
  /**
   * Synchronously resolves the active LiteLLM Gateway URL.
   */
  getGatewayUrlSync(): string {
    const appConfig = (window as any).appConfig;
    const configHost = appConfig?.get?.('LITELLM_HOST') || appConfig?.get?.('OPENAI_API_BASE_URL');
    if (configHost && typeof configHost === 'string' && configHost.trim()) {
      return configHost.trim().replace(/\/v1\/?$/, '').replace(/\/+$/, '');
    }
    return 'http://127.0.0.1:4000';
  }

  /**
   * Synchronously resolves the active Wolinex WebUI / Dev Portal URL.
   */
  getPortalUrlSync(): string {
    const appConfig = (window as any).appConfig;
    const configPortal = appConfig?.get?.('WOLINEX_PORTAL_URL') || appConfig?.get?.('WEBUI_URL');
    if (configPortal && typeof configPortal === 'string' && configPortal.trim()) {
      return configPortal.trim().replace(/\/+$/, '');
    }
    return 'http://127.0.0.1:8081';
  }

  /**
   * Synchronously resolves the API key.
   */
  getApiKeySync(): string {
    const appConfig = (window as any).appConfig;
    const envKey = appConfig?.get?.('LITELLM_API_KEY') || appConfig?.get?.('OPENAI_API_KEY');
    if (envKey && typeof envKey === 'string' && envKey.trim()) {
      return envKey.trim();
    }
    return '';
  }

  /**
   * Alias for WebUI / Dev Portal URL.
   */
  async getWebUIUrl(): Promise<string> {
    return this.getPortalUrl();
  }

  getWebUIUrlSync(): string {
    return this.getPortalUrlSync();
  }

  /**
   * Resolves the active LiteLLM Gateway URL dynamically.
   * Priority: Electron stored setting -> AppConfig runtime env -> Fallback localhost
   */
  async getGatewayUrl(): Promise<string> {
    try {
      const stored = await window.electron?.getSetting?.('wolinexGatewayUrl' as any);
      if (stored && typeof stored === 'string' && stored.trim()) {
        return stored.trim().replace(/\/+$/, '');
      }
    } catch {
      // ignore
    }

    const appConfig = (window as any).appConfig;
    const configHost = appConfig?.get?.('LITELLM_HOST') || appConfig?.get?.('OPENAI_API_BASE_URL');
    if (configHost && typeof configHost === 'string' && configHost.trim()) {
      return configHost.trim().replace(/\/v1\/?$/, '').replace(/\/+$/, '');
    }

    return 'http://127.0.0.1:4000';
  }

  /**
   * Resolves the active Wolinex WebUI / Dev Portal URL dynamically.
   */
  async getPortalUrl(): Promise<string> {
    try {
      const stored = await window.electron?.getSetting?.('wolinexPortalUrl' as any);
      if (stored && typeof stored === 'string' && stored.trim()) {
        return stored.trim().replace(/\/+$/, '');
      }
    } catch {
      // ignore
    }

    const appConfig = (window as any).appConfig;
    const configPortal = appConfig?.get?.('WOLINEX_PORTAL_URL') || appConfig?.get?.('WEBUI_URL');
    if (configPortal && typeof configPortal === 'string' && configPortal.trim()) {
      return configPortal.trim().replace(/\/+$/, '');
    }

    return 'http://127.0.0.1:8081';
  }

  /**
   * Resolves stored or environment-provided LiteLLM API Key.
   */
  async getApiKey(): Promise<string> {
    try {
      const stored = await window.electron?.getSetting?.('wolinexApiKey' as any);
      if (stored && typeof stored === 'string' && stored.trim()) {
        return stored.trim();
      }
    } catch {
      // ignore
    }

    const appConfig = (window as any).appConfig;
    const envKey = appConfig?.get?.('LITELLM_API_KEY') || appConfig?.get?.('OPENAI_API_KEY');
    if (envKey && typeof envKey === 'string' && envKey.trim()) {
      return envKey.trim();
    }

    return '';
  }

  /**
   * Tests health and connectivity to the LiteLLM Gateway.
   */
  async checkGatewayHealth(gatewayUrlOverride?: string): Promise<GatewayHealthResult> {
    const url = gatewayUrlOverride?.trim() || (await this.getGatewayUrl());
    const start = performance.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      // Try readiness probe
      let response = await fetch(`${url}/health/readiness`, {
        signal: controller.signal,
      }).catch(() => null);

      if (!response || !response.ok) {
        // Fallback to liveliness
        response = await fetch(`${url}/health/liveliness`, {
          signal: controller.signal,
        }).catch(() => null);
      }

      clearTimeout(timeoutId);
      const latencyMs = Math.round(performance.now() - start);

      if (response && response.ok) {
        return {
          healthy: true,
          latencyMs,
          status: 'online',
        };
      }

      return {
        healthy: false,
        latencyMs,
        status: 'unreachable',
        error: response ? `HTTP ${response.status} ${response.statusText}` : 'Connection timed out',
      };
    } catch (err: unknown) {
      return {
        healthy: false,
        latencyMs: Math.round(performance.now() - start),
        status: 'error',
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  /**
   * Validates an API key against LiteLLM /v1/models endpoint.
   */
  async validateApiKey(
    apiKey: string,
    gatewayUrlOverride?: string
  ): Promise<{ valid: boolean; models: SovereignModel[]; error?: string }> {
    const url = gatewayUrlOverride?.trim() || (await this.getGatewayUrl());
    const cleanKey = apiKey.trim();

    if (!cleanKey) {
      return { valid: false, models: [], error: 'API key cannot be empty' };
    }

    try {
      const res = await fetch(`${url}/v1/models`, {
        headers: {
          Authorization: `Bearer ${cleanKey}`,
          'Content-Type': 'application/json',
        },
      });

      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          return { valid: false, models: [], error: 'Invalid or expired API key' };
        }
        return { valid: false, models: [], error: `Gateway returned status ${res.status}` };
      }

      const json = await res.json();
      const models = this.parseModelsResponse(json);

      return { valid: true, models };
    } catch (err: unknown) {
      return {
        valid: false,
        models: [],
        error: err instanceof Error ? err.message : 'Failed to connect to gateway',
      };
    }
  }

  /**
   * Authenticates with Wolinex WebUI / Dev Portal credentials.
   * Auto-resolves user identity and their virtual LiteLLM Gateway key.
   */
  async signInWithWebUI(
    email: string,
    password: string,
    portalUrlOverride?: string
  ): Promise<WolinexAuthResult> {
    const portalUrl = portalUrlOverride?.trim() || (await this.getPortalUrl());
    const cleanEmail = email.trim().toLowerCase();

    // 1. First attempt Developer Portal SSO endpoint (/api/wolinet/auth/login)
    let loginRes: Response | null = await fetch(`${portalUrl}/api/wolinet/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: cleanEmail, password }),
    }).catch(() => null);

    // 2. Fallback to standard OpenWebUI auth endpoint (/api/v1/auths/signin)
    if (!loginRes || !loginRes.ok) {
      loginRes = await fetch(`${portalUrl}/api/v1/auths/signin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: cleanEmail, password }),
      }).catch(() => null);
    }

    if (!loginRes || !loginRes.ok) {
      const errorMsg = loginRes
        ? (await loginRes.json().catch(() => ({})))?.detail ||
        (await loginRes.json().catch(() => ({})))?.error ||
        `Authentication failed (HTTP ${loginRes.status})`
        : 'Cannot reach Wolinex Enterprise Authentication Service';
      throw new Error(errorMsg);
    }

    const data = await loginRes.json();
    const token = data.token || '';
    const user: WolinexUser = {
      id: data.user?.id || data.id || 'usr-wolinex',
      name: data.user?.name || data.name || cleanEmail.split('@')[0],
      email: data.user?.email || data.email || cleanEmail,
      role: data.user?.role || data.role || 'user',
    };

    // Extract or discover LiteLLM API key
    let apiKey = data.api_key || data.key || '';

    // If key not in direct response, fetch from portal session or user API key endpoint
    if (!apiKey && token) {
      apiKey = await this.fetchUserApiKey(portalUrl, token);
    }

    // Default credits information
    const credits: WolinexCredits = data.credits || {
      allocated: 25.0,
      spent: 0.0,
      remaining: 25.0,
      currency: 'USD',
      default_model: 'Wolinex Coder',
    };

    return {
      authenticated: true,
      user,
      token,
      apiKey,
      credits,
      defaultModel: credits.default_model || 'Wolinex Coder',
    };
  }

  /**
   * Registers a new account via Wolinex WebUI / Dev Portal.
   * Auto-provisions user into LiteLLM Gateway and returns their API key.
   */
  async signUpWithWebUI(
    name: string,
    email: string,
    password: string,
    portalUrlOverride?: string
  ): Promise<WolinexAuthResult> {
    const portalUrl = portalUrlOverride?.trim() || (await this.getPortalUrl());
    const cleanEmail = email.trim().toLowerCase();
    const cleanName = name.trim();

    // 1. Developer Portal SSO register endpoint
    let regRes: Response | null = await fetch(`${portalUrl}/api/wolinet/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: cleanName, email: cleanEmail, password }),
    }).catch(() => null);

    // 2. Fallback to OpenWebUI signup
    if (!regRes || !regRes.ok) {
      regRes = await fetch(`${portalUrl}/api/v1/auths/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: cleanName, email: cleanEmail, password }),
      }).catch(() => null);
    }

    if (!regRes || !regRes.ok) {
      const errData = await regRes?.json().catch(() => ({}));
      const errorMsg =
        errData?.detail ||
        errData?.error ||
        (regRes ? `Registration failed (HTTP ${regRes.status})` : 'Cannot reach Wolinex Enterprise Platform');
      throw new Error(errorMsg);
    }

    const data = await regRes.json();
    const token = data.token || '';
    const user: WolinexUser = {
      id: data.user?.id || data.id || 'usr-wolinex',
      name: data.user?.name || data.name || cleanName,
      email: data.user?.email || data.email || cleanEmail,
      role: data.user?.role || data.role || 'user',
    };

    let apiKey = data.api_key || data.key || '';
    if (!apiKey && token) {
      apiKey = await this.fetchUserApiKey(portalUrl, token);
    }

    return {
      authenticated: true,
      user,
      token,
      apiKey,
      credits: {
        allocated: 25.0,
        spent: 0.0,
        remaining: 25.0,
        currency: 'USD',
        default_model: 'Wolinex Coder',
      },
      defaultModel: 'Wolinex Coder',
    };
  }

  /**
   * Helper to retrieve or create the user's LiteLLM virtual API key from WebUI.
   */
  private async fetchUserApiKey(portalUrl: string, jwtToken: string): Promise<string> {
    try {
      const sessRes = await fetch(`${portalUrl}/api/wolinet/auth/session`, {
        headers: { Authorization: `Bearer ${jwtToken}` },
      });
      if (sessRes.ok) {
        const sessData = await sessRes.json();
        if (sessData.api_key) return sessData.api_key;
      }
    } catch {
      // ignore
    }

    try {
      const keyRes = await fetch(`${portalUrl}/api/v1/auths/api_key`, {
        headers: { Authorization: `Bearer ${jwtToken}` },
      });
      if (keyRes.ok) {
        const keyData = await keyRes.json();
        if (keyData.api_key) return keyData.api_key;
      }
    } catch {
      // ignore
    }

    return '';
  }

  /**
   * Fetches active sovereign models from LiteLLM.
   */
  async fetchSovereignModels(
    gatewayUrlOverride?: string,
    apiKeyOverride?: string
  ): Promise<SovereignModel[]> {
    const url = gatewayUrlOverride?.trim() || (await this.getGatewayUrl());
    const key = apiKeyOverride?.trim() || (await this.getApiKey());

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (key) headers['Authorization'] = `Bearer ${key}`;

    try {
      const res = await fetch(`${url}/v1/models`, { headers });
      if (res.ok) {
        const json = await res.json();
        const models = this.parseModelsResponse(json);
        if (models.length > 0) return models;
      }
    } catch {
      // ignore
    }

    return SOVEREIGN_FALLBACK_MODELS;
  }

  /**
   * Parses and filters models to guarantee sovereign presentation.
   */
  private parseModelsResponse(json: any): SovereignModel[] {
    if (!Array.isArray(json?.data) || json.data.length === 0) {
      return [];
    }

    return json.data
      .filter((m: any) => {
        const id = m.id || m.model_name || '';
        if (m.mode && (m.mode === 'embedding' || m.mode === 'audio_transcription')) return false;
        if (id.startsWith('text-embedding') || id.startsWith('whisper') || id.startsWith('dall-e')) {
          return false;
        }
        // Filter out raw vendor tags
        if (/deepseek/i.test(id) || /gpt-/i.test(id) || /gemini-/i.test(id) || /claude-/i.test(id)) {
          return false;
        }
        return true;
      })
      .map((m: any, index: number) => {
        const id = m.id || m.model_name;
        const maxTokens = m.max_input_tokens ?? 32768;
        return {
          id,
          name: id,
          contextLimit: maxTokens,
          reasoning: Boolean(maxTokens > 32768 || id.toLowerCase().includes('max') || id.toLowerCase().includes('coder')),
          subtext: this.getModelSubtext(id),
          isDefault: index === 0,
        };
      });
  }

  private getModelSubtext(modelId: string): string {
    const id = modelId.toLowerCase();
    if (id.includes('wolinex coder') || id.includes('wolinex-coder')) {
      return 'Primary Sovereign Coding Engine & AST Analysis';
    }
    if (id.includes('wolinet pro')) {
      return 'Autonomous Multi-Agent Task Orchestration';
    }
    if (id.includes('wolinet max pro')) {
      return 'Long-Context Enterprise Intelligence Cluster';
    }
    if (id.includes('wolinet max')) {
      return '1,000,000-Token Multimodal Deep Reasoning MoE';
    }
    if (id.includes('turbo draft') || id.includes('turbo')) {
      return 'Ultra-Low Latency Speculative Stream';
    }
    if (id.includes('secure')) {
      return 'Confidential Code Guard & Security Analysis';
    }
    if (id.includes('scorpio')) {
      return 'Advanced Scientific & Algorithmic Reasoner';
    }
    return 'Sovereign Gateway Model';
  }

  /**
   * Applies the connection to Goose ACP Engine and Electron settings.
   */
  async configureEngine(params: {
    gatewayUrl: string;
    apiKey: string;
    portalUrl?: string;
    modelId: string;
    user?: WolinexUser;
  }): Promise<void> {
    const { gatewayUrl, apiKey, portalUrl, modelId, user } = params;

    // 1. Save provider credentials into ACP
    await acpSaveProviderConfig('litellm', [
      { key: 'LITELLM_HOST', value: gatewayUrl.trim() },
      { key: 'LITELLM_API_KEY', value: apiKey.trim() },
      { key: 'LITELLM_BASE_PATH', value: 'v1/chat/completions' },
    ]);

    // 2. Save active default model
    await acpSaveDefaults('litellm', modelId.trim());

    // 3. Persist settings in Electron store
    if (window.electron?.setSetting) {
      await window.electron.setSetting('wolinexGatewayUrl' as any, gatewayUrl.trim());
      await window.electron.setSetting('wolinexApiKey' as any, apiKey.trim());
      if (portalUrl) {
        await window.electron.setSetting('wolinexPortalUrl' as any, portalUrl.trim());
      }
      if (user) {
        await window.electron.setSetting('wolinexUser' as any, user);
      }
    }
  }
}

export const wolinexGateway = new WolinexGatewayService();
