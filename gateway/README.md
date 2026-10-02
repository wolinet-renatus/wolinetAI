# Wolinet AI Gateway (LiteLLM Layer)

The AI Gateway provides a unified, production-grade reverse proxy layer sitting between your client applications (agentic IDE, web dashboard, autonomous agents) and the underlying model providers (Local Xinference engine + Cloud APIs).

## Key Responsibilities
1. **Single Unified Endpoint**: All clients connect to `http://localhost:4000/v1` (or `https://api.wolinet.tech/v1`) using standard OpenAI SDKs or HTTP requests.
2. **Hybrid Routing (80/20 Rule)**:
   - Running Xinference chat models are discovered from Mitambo and synchronized to LiteLLM. The public `Wolinet Coder` model routes to the selected active local model; additional active local models appear by their live IDs.
   - Complex reasoning queries, large architectural planning, or media requests are routed to Cloud APIs (DeepSeek-R1, Claude 3.5 Sonnet, GPT-4o, Kling Video).
3. **Resilience & Fallbacks**: If the local engine is temporarily saturated or offline, requests automatically fall back to cloud providers (e.g. `deepseek-v3` or `gpt-4o-mini`).
4. **Budget Guardrails & Cost Tracking**: LiteLLM tracks per-key and per-user token usage and enforces monthly spend caps.

## Files
- `config.yaml`: Model definitions, routing targets, fallback lists, and proxy settings.
- `run_gateway.sh`: Startup script for running the LiteLLM proxy server on port 4000.

## Starting the Gateway
From repository root:
```bash
make gateway
# or directly:
./gateway/run_gateway.sh
```

## Adding a New Model Route
To add a new model, edit `gateway/config.yaml`:
```yaml
model_list:
  - model_name: my-new-model
    litellm_params:
      model: openai/my-new-model
      api_base: http://127.0.0.1:9997/v1
      api_key: "none"
```
Or for cloud providers:
```yaml
  - model_name: claude-3-7-sonnet
    litellm_params:
      model: anthropic/claude-3-7-sonnet-20250219
      api_key: os.environ/ANTHROPIC_API_KEY
```
