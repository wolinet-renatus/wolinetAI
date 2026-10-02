# @wolinet/sdk

Official TypeScript & JavaScript client for the **Wolinet AI Sovereign Gateway & Inference Cluster**.

- 🚀 **Gateway Model Discovery:** Use any model enabled in the LiteLLM catalog.
- ⚡ **Streaming Support:** Async generator SSE streaming for instant code and text token rendering.
- 🌐 **Zero External Dependencies:** Built on native `fetch` and `ReadableStream`.

## Installation

```bash
npm install @wolinet/sdk
```

## Quickstart

```typescript
import { WolinetAI } from '@wolinet/sdk';

const client = new WolinetAI({
  baseUrl: 'http://localhost:4000',
  apiKey: 'sk-wolinet-local-dev',
});

// 1. Unary Chat Completion
const completion = await client.chat.completions.create({
  model: 'your-enabled-model-id',
  messages: [{ role: 'user', content: 'Write a quicksort in TypeScript' }],
});
console.log(completion.choices[0].message.content);

// 2. Real-time Streaming
for await (const chunk of client.chat.completions.stream({
  model: 'your-enabled-model-id',
  messages: [{ role: 'user', content: 'Count from 1 to 5' }],
})) {
  process.stdout.write(chunk.choices[0]?.delta?.content || '');
}

// 3. Dense Vector Embeddings
const embeddings = await client.embeddings.create({
  model: 'bge-small-en-v1.5',
  input: 'Wolinet AI Sovereign Infrastructure',
});
console.log('Embedding dimension:', embeddings.data[0].embedding.length);

// 4. Cluster Telemetry
const status = await client.status();
console.log('Active inference models:', status.inference.model_count);
```
