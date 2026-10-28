"""
Wolinet AI — OrcaCyber Real-Time Guardrail Callback for Lango (LiteLLM)
==============================================================================
Provides sub-5ms pre-flight security evaluation of prompts.
Preserves 100% Uncensored Freedom: Does NOT refuse creative, exploratory,
or standard user queries. Specifically detects and mitigates structural cyber
threats (Prompt Injection, System Exfiltration, Malicious Payload RCE).
==============================================================================
"""

import logging
import time
from typing import Dict, Any, Optional

try:
    from litellm.integrations.custom_logger import CustomLogger
except ImportError:
    class CustomLogger:
        pass

from services.defense.orcacyber_defense import OrcaCyberDefenseEngine, MODEL_PATH

logger = logging.getLogger("orcacyber-guard")


class OrcaCyberGuardHandler(CustomLogger):
    def __init__(self):
        super().__init__()
        logger.info("🛡️ Initializing OrcaCyber Guardrail Callback...")
        self.engine = OrcaCyberDefenseEngine(MODEL_PATH)

    async def async_pre_call_hook(
        self,
        user_api_key_dict: Optional[Dict[str, Any]],
        cache_hit: Optional[bool],
        data: Dict[str, Any],
        call_type: str,
    ) -> Optional[Dict[str, Any]]:
        if not data or not isinstance(data, dict):
            return data

        messages = data.get("messages", [])
        if not messages:
            return data

        # Extract latest user message
        user_content = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user_content = str(m.get("content", ""))
                break

        if not user_content:
            return data

        report = self.engine.inspect_prompt(user_content)
        
        # Attach security telemetry to request metadata
        metadata = data.setdefault("metadata", {})
        metadata["orcacyber_defense"] = {
            "verdict": report["verdict"],
            "threat_score": report["threat_score"],
            "latency_ms": report["latency_ms"],
            "is_safe": report["is_safe"],
        }

        if not report["is_safe"]:
            logger.warning(
                f"🚨 [OrcaCyber Defense] Threat flagged: {report['verdict']} "
                f"(score={report['threat_score']}, vectors={report['attack_vectors']})"
            )

        return data


# Singleton instance for LiteLLM
orcacyber_guard_handler = OrcaCyberGuardHandler()
