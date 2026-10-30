import test from 'node:test';
import assert from 'node:assert/strict';
import { WolinetAI } from '../dist/index.js';

test('WolinetAI Client Initialization Defaults', () => {
  const client = new WolinetAI({
    baseUrl: 'https://api.wolinet.com',
    apiKey: 'sk-test-token',
    timeout: 12000,
  });

  assert.equal(client.baseUrl, 'https://api.wolinet.com');
  assert.equal(client.apiKey, 'sk-test-token');
  assert.equal(client.timeout, 12000);
  assert.ok(typeof client.chat.completions.create === 'function');
  assert.ok(typeof client.chat.completions.stream === 'function');
  assert.ok(typeof client.embeddings.create === 'function');
  assert.ok(typeof client.status === 'function');
});

test('WolinetAI Client Environment Variable Fallbacks', () => {
  const prevUrl = process.env.WOLINET_BASE_URL;
  const prevKey = process.env.WOLINET_API_KEY;

  try {
    process.env.WOLINET_BASE_URL = 'https://custom-env.wolinet.com';
    process.env.WOLINET_API_KEY = 'sk-env-custom-key';

    const client = new WolinetAI();
    assert.equal(client.baseUrl, 'https://custom-env.wolinet.com');
    assert.equal(client.apiKey, 'sk-env-custom-key');
  } finally {
    process.env.WOLINET_BASE_URL = prevUrl;
    process.env.WOLINET_API_KEY = prevKey;
  }
});

