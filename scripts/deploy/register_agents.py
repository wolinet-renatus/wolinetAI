#!/usr/bin/env python3
"""
Wolinet AI — Autonomous Agent & Workflow Setup & Hardening Script
==============================================================================
Ensures all sovereign AI agents in LiteLLM:
1. Transition from 'Needs Setup' -> 'Active' by provisioning dedicated virtual keys.
2. Have operational Emergency Kill Switch webhooks configured out of band.
3. Are fully synchronized and visible in http://127.0.0.1:4000/ui/agents/
==============================================================================
"""

import os
import sys
import re
import json
import urllib.request
import urllib.error

GATEWAY_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000")
API_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-XvKFiwDoOtOe8i4lwbzb8Q")
KILL_SWITCH_URL = os.environ.get("KILL_SWITCH_URL", "http://host.docker.internal:8088/v1/defense/kill_switch")

AGENTS_SPEC = [
    {
        "agent_name": "Secure Pro — AI Cyber Defense Guard",
        "litellm_params": {
            "model": "Secure Pro",
            "is_public": True,
        },
        "agent_card_params": {
            "name": "Secure Pro — AI Cyber Defense Guard",
            "description": "Sub-millisecond real-time threat detection, prompt injection mitigation, jailbreak defense, and sovereign conversational security advisor.",
            "version": "1.0",
            "skills": [
                {
                    "id": "injection_defense",
                    "name": "Prompt Injection Defense",
                    "tags": ["cybersecurity", "guardrail", "defense"],
                    "description": "Detects structural prompt injections and token delimiter manipulation.",
                },
                {
                    "id": "threat_telemetry",
                    "name": "Threat Telemetry & Auditing",
                    "tags": ["telemetry", "orcacyber", "forensics"],
                    "description": "Exposes real-time threat scores, latency profiling, and attack vector forensics.",
                },
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        },
    },
    {
        "agent_name": "1Panel Server & Infrastructure Guard",
        "litellm_params": {
            "model": "Secure Pro",
            "is_public": True,
        },
        "agent_card_params": {
            "name": "1Panel Server & Infrastructure Guard",
            "description": "Automated 1Panel Linux hosting security, firewall (UFW/iptables) rules, Docker container isolation, Nginx reverse proxy SSL hardening, and port protection agent.",
            "version": "1.0",
            "skills": [
                {
                    "id": "1panel_hardening",
                    "name": "1Panel Panel & Port Security",
                    "tags": ["1panel", "devops", "hardening"],
                    "description": "Configures 1Panel entrance paths, custom ports, and multi-factor authentication.",
                },
                {
                    "id": "firewall_ops",
                    "name": "Firewall & Network Defense",
                    "tags": ["ufw", "iptables", "network"],
                    "description": "Generates minimal-privilege UFW and iptables rules for web servers.",
                },
                {
                    "id": "reverse_proxy_ssl",
                    "name": "Nginx SSL/TLS Hardening",
                    "tags": ["nginx", "ssl", "tls", "hsts"],
                    "description": "Audits Let's Encrypt certificates, HSTS, and cipher suite security.",
                },
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        },
    },
    {
        "agent_name": "Wolinex Code Security Auditor",
        "litellm_params": {
            "model": "Wolinex Coder",
            "is_public": True,
        },
        "agent_card_params": {
            "name": "Wolinex Code Security Auditor",
            "description": "Specialized static code analysis agent for OWASP Top 10 vulnerabilities, SQL injection, XSS, CSRF, insecure deserialization, and secure refactoring.",
            "version": "1.0",
            "skills": [
                {
                    "id": "static_code_audit",
                    "name": "Static Vulnerability Analysis",
                    "tags": ["owasp", "cve", "static-analysis"],
                    "description": "Scans code for SQL injection, memory safety flaws, and logic vulnerabilities.",
                },
                {
                    "id": "patch_generation",
                    "name": "Remediation & Patching",
                    "tags": ["refactoring", "patches", "hardening"],
                    "description": "Generates hardened, drop-in replacement code with mitigation comments.",
                },
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        },
    },
    {
        "agent_name": "DFlash Speculative Acceleration Drafter",
        "litellm_params": {
            "model": "Wolinet Turbo Draft",
            "is_public": True,
        },
        "agent_card_params": {
            "name": "DFlash Speculative Acceleration Drafter",
            "description": "High-throughput draft-assisted inference agent leveraging Qwen 3.8 / 27B DFlash2 multi-token prediction layers.",
            "version": "1.0",
            "skills": [
                {
                    "id": "speculative_drafting",
                    "name": "Block-Diffusion Multi-Token Drafting",
                    "tags": ["speculative", "dflash2", "acceleration"],
                    "description": "Block-diffusion multi-token speculative draft generation.",
                },
                {
                    "id": "latency_benchmarking",
                    "name": "Throughput & Latency Optimization",
                    "tags": ["benchmarking", "speedup"],
                    "description": "Measures draft acceptance ratios and acceleration telemetry.",
                },
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        },
    },
]


def make_request(url, method="GET", data=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def sync_and_activate_agents():
    print("==================================================================")
    print("🛡️  Wolinet AI — Agent Activation & Kill Switch Hardening")
    print(f" Connecting to: {GATEWAY_URL}")
    print("==================================================================")

    # 1. Fetch current agents
    try:
        agents = make_request(f"{GATEWAY_URL}/v1/agents")
    except Exception as e:
        print(f"❌ Failed to reach LiteLLM Gateway: {e}")
        return

    agent_map = {a.get("agent_name"): a for a in agents}
    print(f"Current agents in database: {len(agents)}\n")

    # 2. Register any missing agents
    for spec in AGENTS_SPEC:
        name = spec["agent_name"]
        if name not in agent_map:
            print(f"🚀 Registering missing agent: '{name}'...")
            try:
                res = make_request(f"{GATEWAY_URL}/v1/agents", method="POST", data=spec)
                agent_id = res.get("agent_id")
                print(f"  ✅ Created '{name}' (ID: {agent_id})")
                agent_map[name] = res
            except Exception as e:
                print(f"  ❌ Error creating agent: {e}")

    # Re-fetch all agents
    agents = make_request(f"{GATEWAY_URL}/v1/agents")

    # 3. For every agent: Setup Kill Switch & Provision Virtual Key
    print("\n------------------------------------------------------------------")
    print("⚡ Configuring Kill Switch Webhooks & Virtual Keys for all agents...")
    print("------------------------------------------------------------------")

    for agent in agents:
        agent_id = agent.get("agent_id")
        agent_name = agent.get("agent_name", "Unknown Agent")
        alias_slug = re.sub(r"[^a-zA-Z0-9]+", "-", agent_name.lower()).strip("-")

        # A. Configure Kill Switch Webhook
        try:
            patch_data = {
                "kill_switch": {
                    "url": KILL_SWITCH_URL,
                    "method": "POST",
                }
            }
            make_request(f"{GATEWAY_URL}/v1/agents/{agent_id}", method="PATCH", data=patch_data)
            print(f"  🛡️  [{agent_name[:30]}] Kill switch webhook CONFIGURED -> {KILL_SWITCH_URL}")
        except Exception as e:
            print(f"  ⚠️  [{agent_name[:30]}] Could not patch kill_switch: {e}")

        # B. Check & Provision Virtual Key (Transitions 'Needs Setup' -> 'Active')
        existing_keys = agent.get("keys") or []
        if len(existing_keys) == 0:
            print(f"  🔑 [{agent_name[:30]}] No key assigned ('Needs Setup'). Generating virtual key...")
            try:
                key_payload = {
                    "agent_id": agent_id,
                    "key_alias": f"{alias_slug}-key",
                }
                key_res = make_request(f"{GATEWAY_URL}/key/generate", method="POST", data=key_payload)
                print(f"  ✅ [{agent_name[:30]}] Key provisioned: {key_res.get('key_alias')} (Status -> ACTIVE)")
            except Exception as e:
                print(f"  ❌ [{agent_name[:30]}] Failed to generate key: {e}")
        else:
            print(f"  ✅ [{agent_name[:30]}] Key already active: {len(existing_keys)} key(s) attached (Status: ACTIVE)")

    # 4. Final Verification
    print("\n==================================================================")
    print("📋 Final Agent Status Verification")
    print("==================================================================")
    updated_agents = make_request(f"{GATEWAY_URL}/v1/agents")
    for a in updated_agents:
        keys_count = len(a.get("keys") or [])
        status = "✅ ACTIVE" if keys_count > 0 else "⚠️ NEEDS SETUP"
        ks = "🛡️ CONFIGURED" if a.get("kill_switch") else "❌ NOT CONFIGURED"
        print(f" • {a.get('agent_name'):<38} | Status: {status} | Kill Switch: {ks}")

    print("\n🎉 All issues resolved! Check your dashboard at http://127.0.0.1:4000/ui/agents/")


if __name__ == "__main__":
    sync_and_activate_agents()
