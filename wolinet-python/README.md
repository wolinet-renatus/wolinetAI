# Wolinet AI Python SDK

Official Python client for the **Wolinet AI Sovereign Gateway & Inference Cluster**.

## Installation

```bash
pip install -e packages/wolinet-python
```

## Quickstart

```python
from wolinet import WolinetAI

client = WolinetAI(base_url="http://localhost:4000", api_key="sk-wolinet-local-dev")

# 1. Unary Chat Completion
res = client.chat.create(
    model="wolinex-coder",
    messages=[{"role": "user", "content": "Write a Python decorator for logging execution time."}],
)
print(res.choices[0].message.content)

# 2. Real-time Streaming
for chunk in client.chat.create(
    model="wolinex-coder",
    messages=[{"role": "user", "content": "Explain vector databases in 2 sentences"}],
    stream=True,
):
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
print()

# 3. Dense Vector Embeddings
emb = client.embeddings.create(model="bge-small-en-v1.5", input="Wolinet AI sovereign cloud")
print("Vector length:", len(emb.data[0].embedding))

# 4. Check Cluster Status
status = client.status()
print("Gateway status:", status["gateway"]["status"])
```
