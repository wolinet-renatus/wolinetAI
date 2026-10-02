/**
 * Wolinet AI TypeScript SDK
 * Auto-generated from Wolinet AI Sovereign OpenAPI Specification
 */

declare const process: { env?: Record<string, string | undefined> } | undefined;

import type {
  ChatCompletionOptions,
  ChatCompletionResponse,
  ChatCompletionChunk,
  EmbeddingOptions,
  EmbeddingResponse,
  RerankOptions,
  RerankResponse,
  WolinetStatusResponse,
  WolinetKeyResponse,
} from './types.ts';

export type * from './types.ts';

export interface WolinetClientOptions {
  baseUrl?: string;
  apiKey?: string;
  timeout?: number;
}

export class WolinetAI {
  public readonly baseUrl: string;
  public readonly apiKey: string;
  public readonly timeout: number;

  constructor(options: WolinetClientOptions = {}) {
    const rawUrl = options.baseUrl || (typeof process !== 'undefined' ? process.env?.WOLINET_BASE_URL : undefined) || 'http://localhost:4000';
    this.baseUrl = rawUrl.replace(/\/+$/, '');
    this.apiKey = options.apiKey || (typeof process !== 'undefined' ? process.env?.WOLINET_API_KEY : undefined) || 'sk-wolinet-local-dev';
    this.timeout = options.timeout ?? 60000;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'User-Agent': 'WolinetAI-TS-SDK/1.1.0',
      ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
      ...(options.headers as Record<string, string>),
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (!res.ok) {
        const errorText = await res.text().catch(() => '');
        throw new Error(`Wolinet API error [${res.status}]: ${errorText || res.statusText}`);
      }

      return (await res.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  public readonly chat = {
    completions: {
      create: async (opts: ChatCompletionOptions): Promise<ChatCompletionResponse> => {
        return this.request<ChatCompletionResponse>('/v1/chat/completions', {
          method: 'POST',
          body: JSON.stringify({ ...opts, stream: false }),
        });
      },

      stream: async function* (
        this: WolinetAI,
        opts: ChatCompletionOptions
      ): AsyncIterable<ChatCompletionChunk> {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          'User-Agent': 'WolinetAI-TS-SDK/1.1.0',
          ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
        };

        const res = await fetch(`${this.baseUrl}/v1/chat/completions`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ ...opts, stream: true }),
        });

        if (!res.ok) {
          const errText = await res.text().catch(() => '');
          throw new Error(`Wolinet Stream error [${res.status}]: ${errText}`);
        }

        if (!res.body) {
          throw new Error('Response body is null, cannot stream');
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith(':')) continue;
            if (trimmed === 'data: [DONE]') return;

            if (trimmed.startsWith('data: ')) {
              const dataStr = trimmed.slice(6).trim();
              try {
                const parsed = JSON.parse(dataStr) as ChatCompletionChunk;
                yield parsed;
              } catch {
                // Ignore parse errors on partial chunks
              }
            }
          }
        }
      }.bind(this),
    },
  };

  public readonly embeddings = {
    create: async (opts: EmbeddingOptions): Promise<EmbeddingResponse> => {
      return this.request<EmbeddingResponse>('/v1/embeddings', {
        method: 'POST',
        body: JSON.stringify(opts),
      });
    },
  };

  public readonly rerank = {
    create: async (opts: RerankOptions): Promise<RerankResponse> => {
      return this.request<RerankResponse>('/v1/rerank', {
        method: 'POST',
        body: JSON.stringify(opts),
      });
    },
  };

  public readonly models = {
    list: async (): Promise<{ data: Array<{ id: string; object: string; created: number; owned_by: string }> }> => {
      return this.request('/v1/models');
    },
  };

  public async status(): Promise<WolinetStatusResponse> {
    return this.request<WolinetStatusResponse>('/wolinet/status');
  }

  public async getKey(): Promise<WolinetKeyResponse> {
    return this.request<WolinetKeyResponse>('/wolinet/key');
  }
}

export default WolinetAI;
