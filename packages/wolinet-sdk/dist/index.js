/**
 * Wolinet AI TypeScript SDK
 * Auto-generated from Wolinet AI Sovereign OpenAPI Specification
 */
export class WolinetAI {
    baseUrl;
    apiKey;
    timeout;
    constructor(options = {}) {
        const rawUrl = options.baseUrl || (typeof process !== 'undefined' ? process.env?.WOLINET_BASE_URL : undefined) || 'http://localhost:4000';
        this.baseUrl = rawUrl.replace(/\/+$/, '');
        this.apiKey = options.apiKey || (typeof process !== 'undefined' ? process.env?.WOLINET_API_KEY : undefined) || 'sk-wolinet-local-dev';
        this.timeout = options.timeout ?? 60000;
    }
    async request(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'WolinetAI-TS-SDK/1.1.0',
            ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
            ...options.headers,
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
            return (await res.json());
        }
        finally {
            clearTimeout(timer);
        }
    }
    chat = {
        completions: {
            create: async (opts) => {
                return this.request('/v1/chat/completions', {
                    method: 'POST',
                    body: JSON.stringify({ ...opts, stream: false }),
                });
            },
            stream: async function* (opts) {
                const headers = {
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
                    if (done)
                        break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';
                    for (const line of lines) {
                        const trimmed = line.trim();
                        if (!trimmed || trimmed.startsWith(':'))
                            continue;
                        if (trimmed === 'data: [DONE]')
                            return;
                        if (trimmed.startsWith('data: ')) {
                            const dataStr = trimmed.slice(6).trim();
                            try {
                                const parsed = JSON.parse(dataStr);
                                yield parsed;
                            }
                            catch {
                                // Ignore parse errors on partial chunks
                            }
                        }
                    }
                }
            }.bind(this),
        },
    };
    embeddings = {
        create: async (opts) => {
            return this.request('/v1/embeddings', {
                method: 'POST',
                body: JSON.stringify(opts),
            });
        },
    };
    rerank = {
        create: async (opts) => {
            return this.request('/v1/rerank', {
                method: 'POST',
                body: JSON.stringify(opts),
            });
        },
    };
    models = {
        list: async () => {
            return this.request('/v1/models');
        },
    };
    payments = {
        tanzania: {
            topup: async (opts) => {
                return this.request('/v1/payments/tanzania/topup', {
                    method: 'POST',
                    body: JSON.stringify(opts),
                });
            },
            status: async (transactionId) => {
                return this.request(`/v1/payments/tanzania/status?id=${encodeURIComponent(transactionId)}`);
            },
        },
    };
    async status() {
        return this.request('/wolinet/status');
    }
    async getKey() {
        return this.request('/wolinet/key');
    }
}
export default WolinetAI;
