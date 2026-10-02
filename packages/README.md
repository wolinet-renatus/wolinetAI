# Wolinet AI Official Client SDKs

This directory contains official, strongly typed client SDKs for connecting applications to the **Wolinet AI Sovereign Gateway & Inference Cluster**.

All SDKs support:
- 🚀 **Gateway Model Discovery:** Use model IDs enabled for your LiteLLM gateway key.
- ⚡ **Real-Time Streaming:** Server-Sent Events (SSE) streaming for instant response rendering.
- 📊 **Usage Billing:** LiteLLM usage events can be sent to Lago for subscription billing.
- 📊 **Platform Telemetry:** Instant cluster node status, GPU metrics, and health inspection.

---

## Available Packages

| Package | Language | Path | Status |
| :--- | :--- | :--- | :--- |
| **[`wolinet`](wolinet-python/)** | Python 3.9+ | `packages/wolinet-python/` | ✅ Active (Sync + Async, Pydantic) |
| **[`@wolinet/sdk`](wolinet-sdk/)** | TypeScript / JS | `packages/wolinet-sdk/` | ✅ Active (Zero-dep, Node/Browser/Deno) |
| **[`wolinet-go`](wolinet-go/)** | Go (Golang) 1.21+ | `packages/wolinet-go/` | ✅ Active (Context-aware, SSE Stream) |

---

## SDK Code Generator (Scalar Architecture)

The client SDKs and code snippets are automatically generated from the live OpenAPI schema:

```bash
# Generate all SDKs (Python, TypeScript, Go)
make sdk

# Or run the generator directly
python3 scripts/generate_sdk.py --lang all

# Generate multi-language code snippets for an enabled model
python3 scripts/generate_sdk.py --snippets --model YOUR_ENABLED_MODEL_ID
```

---

## Live Gateway Snippets API

The gateway also provides a live endpoint to retrieve multi-language code snippets dynamically:

```bash
curl -s "http://localhost:4000/wolinet/sdk/snippets?model=YOUR_ENABLED_MODEL_ID" | jq .
```
