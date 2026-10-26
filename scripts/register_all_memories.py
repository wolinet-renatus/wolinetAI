import asyncio
import httpx

API_URL = "http://127.0.0.1:4000/v1/memory"
AUTH_HEADER = {"Authorization": "Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q", "Content-Type": "application/json"}

MEMORIES = [
    {
        "key": "wolinet:stack:sovereign_core",
        "value": "Wolinet Sovereign AI Stack: LiteLLM v1.106.4 Enterprise Air-gapped Gateway, PostgreSQL 16 persistence (databases: litellm, webui, litellm_memory), Podman container orchestration, zero-CVE posture, and native streaming.",
        "metadata": {
            "tier": "core_infrastructure",
            "release": "v1.106.4",
            "runtime": "podman",
            "database": "postgresql-16"
        }
    },
    {
        "key": "wolinet:models:catalog",
        "value": "Configured sovereign branded models: 'Wolinet Pro' (High-reasoning general LLM), 'Wolinet Max' (Deep analytical flagship), 'Wolinet Coder' (Optimized software development & code synthesis). All routed through LiteLLM with fallback resilience.",
        "metadata": {
            "tier": "model_gateway",
            "models": ["Wolinet Pro", "Wolinet Max", "Wolinet Coder"],
            "router": "litellm_proxy"
        }
    },
    {
        "key": "wolinet:memory:cross_session_continuity",
        "value": "ai-memory v3.2.5 active LaunchAgent daemon on 0.0.0.0:49374 (PID managed by launchd: com.github.akitaonrails.ai-memory). Features LanceDB vector indexing, durable wiki pages, session observations, workstream handoffs, and canonical AGENTS.md / GEMINI.md routing.",
        "metadata": {
            "tier": "developer_memory",
            "engine": "ai-memory",
            "version": "3.2.5",
            "port": 49374,
            "status": "healthy"
        }
    },
    {
        "key": "wolinet:memory:team_workstreams",
        "value": "litellm-memory daemon active on 0.0.0.0:8000. Provides sovereign classification via Wolinet Pro (TypeSafe Jev fallback), PostgreSQL team workstream persistence, daily summaries, chronological feeds, and MCP tool access for Claude Code and Cursor.",
        "metadata": {
            "tier": "team_workstreams",
            "service": "litellm-memory",
            "port": 8000,
            "database": "litellm_memory",
            "classifier": "sovereign:Wolinet Pro"
        }
    },
    {
        "key": "wolinet:storage:curvine_cache",
        "value": "Curvine CNCF Sandbox high-throughput distributed memory, object storage, and LanceDB cache. Container image docker.io/curvine/curvine:latest with host CLI wrapper at bin/cv (curvine-cli 0.2.2). Accelerates vector and dataset retrieval.",
        "metadata": {
            "tier": "distributed_cache",
            "cncf_project": "curvine",
            "cli": "bin/cv",
            "version": "0.2.2"
        }
    },
    {
        "key": "wolinet:skills:registry_summary",
        "value": "339 specialized skills registered in LiteLLM marketplace: 20 Gateway Admin skills, 311 ECC engineering skills, 6 AI-memory lifecycle skills, and multi-model orchestration loops. Synchronized across ~/.agents/skills and LiteLLM catalog.",
        "metadata": {
            "tier": "agentic_skills",
            "count": 339,
            "standards": ["Agent Skills 1.0", "Claude Code Marketplace", "OpenAI Tool Spec"]
        }
    },
    {
        "key": "wolinet:mcp:integrated_hubs",
        "value": "Integrated Model Context Protocol (MCP) servers: ai_memory (http://host.containers.internal:49374/mcp), litellm_memory (http://host.containers.internal:8000/mcp), Obscura web retrieval adapter, and local agent tools.",
        "metadata": {
            "tier": "mcp_hub",
            "servers": ["ai_memory", "litellm_memory", "obscura"]
        }
    },
    {
        "key": "wolinet:security:governance",
        "value": "Sovereign zero-trust governance: Bearer token isolation, admin role authorization on /ui/ and management APIs, container loopback bindings with host bridge, and air-gapped cost map bypass.",
        "metadata": {
            "tier": "governance",
            "auth": "bearer_master_key",
            "audit": "active"
        }
    }
]

async def main():
    async with httpx.AsyncClient() as client:
        for mem in MEMORIES:
            try:
                # Upsert memory via PUT /v1/memory/{key}
                key = mem["key"]
                r = await client.put(f"{API_URL}/{key}", json=mem, headers=AUTH_HEADER, timeout=10.0)
                if r.status_code in (200, 201):
                    print(f"Registered memory: {key} (status: {r.status_code})")
                else:
                    # try POST
                    r2 = await client.post(API_URL, json=mem, headers=AUTH_HEADER, timeout=10.0)
                    print(f"POST fallback memory: {key} (status: {r2.status_code})")
            except Exception as e:
                print(f"Error registering {mem['key']}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
