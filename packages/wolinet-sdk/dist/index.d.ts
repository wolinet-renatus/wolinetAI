/**
 * Wolinet AI TypeScript SDK
 * Auto-generated from Wolinet AI Sovereign OpenAPI Specification
 */
import type { ChatCompletionOptions, ChatCompletionResponse, ChatCompletionChunk, EmbeddingOptions, EmbeddingResponse, RerankOptions, RerankResponse, TanzaniaPaymentRequest, TanzaniaPaymentResponse, WolinetStatusResponse, WolinetKeyResponse } from './types.ts';
export type * from './types.ts';
export interface WolinetClientOptions {
    baseUrl?: string;
    apiKey?: string;
    timeout?: number;
}
export declare class WolinetAI {
    readonly baseUrl: string;
    readonly apiKey: string;
    readonly timeout: number;
    constructor(options?: WolinetClientOptions);
    private request;
    readonly chat: {
        completions: {
            create: (opts: ChatCompletionOptions) => Promise<ChatCompletionResponse>;
            stream: (opts: ChatCompletionOptions) => AsyncIterable<ChatCompletionChunk>;
        };
    };
    readonly embeddings: {
        create: (opts: EmbeddingOptions) => Promise<EmbeddingResponse>;
    };
    readonly rerank: {
        create: (opts: RerankOptions) => Promise<RerankResponse>;
    };
    readonly models: {
        list: () => Promise<{
            data: Array<{
                id: string;
                object: string;
                created: number;
                owned_by: string;
            }>;
        }>;
    };
    readonly payments: {
        tanzania: {
            topup: (opts: TanzaniaPaymentRequest) => Promise<TanzaniaPaymentResponse>;
            status: (transactionId: string) => Promise<TanzaniaPaymentResponse>;
        };
    };
    status(): Promise<WolinetStatusResponse>;
    getKey(): Promise<WolinetKeyResponse>;
}
export default WolinetAI;
//# sourceMappingURL=index.d.ts.map