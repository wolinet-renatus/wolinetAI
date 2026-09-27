/**
 * Wolinet AI TypeScript SDK — Type Definitions
 * Auto-generated from Wolinet AI Sovereign OpenAPI Specification
 */

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  name?: string;
}

export interface ChatCompletionOptions {
  model: 'wolinex-coder' | 'deepseek-coder-1.3b' | 'wolinex-omni' | (string & {});
  messages: ChatMessage[];
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  stream?: boolean;
  stop?: string | string[];
  presence_penalty?: number;
  frequency_penalty?: number;
}

export interface ChatCompletionChoice {
  index: number;
  message: ChatMessage;
  finish_reason: string | null;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  timings?: {
    prompt_per_second?: number;
    predicted_per_second?: number;
    prompt_ms?: number;
    predicted_ms?: number;
  };
}

export interface ChatCompletionChunkChoice {
  index: number;
  delta: {
    role?: string;
    content?: string;
  };
  finish_reason: string | null;
}

export interface ChatCompletionChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChunkChoice[];
}

export interface EmbeddingOptions {
  model: 'bge-small-en-v1.5' | (string & {});
  input: string | string[];
  encoding_format?: 'float' | 'base64';
}

export interface EmbeddingData {
  index: number;
  object: 'embedding';
  embedding: number[];
}

export interface EmbeddingResponse {
  object: 'list';
  data: EmbeddingData[];
  model: string;
  usage: {
    prompt_tokens: number;
    total_tokens: number;
  };
}

export interface RerankOptions {
  model: 'bge-reranker-v2-m3' | (string & {});
  query: string;
  documents: string[];
  top_n?: number;
  return_documents?: boolean;
}

export interface RerankResult {
  index: number;
  relevance_score: number;
  document?: string;
}

export interface RerankResponse {
  id: string;
  results: RerankResult[];
  model: string;
  usage: {
    total_tokens: number;
  };
}

export interface TanzaniaPaymentRequest {
  provider: 'mpesa' | 'tigopesa' | 'airtel' | 'halopesa';
  phone_number: string;
  amount_tzs: number;
  account_reference?: string;
}

export interface TanzaniaPaymentResponse {
  transaction_id: string;
  status: 'PENDING' | 'SUCCESS' | 'FAILED';
  amount_tzs: number;
  message: string;
  provider: string;
}

export interface WolinetStatusResponse {
  brand: {
    name: string;
    gateway: string;
    inference: string;
    docs: string;
    openapi: string;
  };
  active_key?: string;
  default_key?: string;
  gateway: {
    status: string;
    db: string;
    total_spend: number;
  };
  inference: {
    status: string;
    model_count: number;
    models: Array<{
      id: string;
      type: string;
      engine: string;
      quantization?: string;
      size_b?: number | string | null;
      context_length?: number | null;
      description?: string;
    }>;
    nodes: Array<{
      role: string;
      address: string;
      gpus: number;
    }>;
  };
  timestamp: string;
}

export interface WolinetKeyResponse {
  key: string;
  key_alias: string;
  status: string;
  models: string[];
  gateway_url: string;
  auth_header: string;
  curl_example: string;
}
