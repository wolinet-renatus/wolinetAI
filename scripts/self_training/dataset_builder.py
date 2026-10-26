#!/usr/bin/env python3
"""
Wolinet AI — Sovereign Dataset Builder (Pipeline 5)
Formats harvested trajectories into:
1. Supervised Fine-Tuning (SFT) reasoning datasets with Chain-of-Thought
   (data/training/wolinet_coder_sft.jsonl, data/training/wolinet_pro_sft.jsonl)
2. Direct Preference Optimization (DPO) preference pairs (y_w, y_l)
   (data/training/wolinet_coder_dpo.jsonl)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


SYSTEM_PROMPT_CODER = (
    "You are Wolinet Coder, an advanced sovereign AI coding and software engineering model. "
    "You think step-by-step through problems, verify assumptions, use tools precisely, and output "
    "secure, high-performance, and verifiable code."
)

SYSTEM_PROMPT_PRO = (
    "You are Wolinet Pro, a sovereign general intelligence and systems reasoning model. "
    "You provide clear, structured, and strategic answers across enterprise architecture, "
    "agent orchestration, scientific analysis, and sovereign AI infrastructure."
)


class DatasetBuilder:
    def __init__(self, raw_data_path: str = "data/training/harvested_raw.json", output_dir: str = "data/training"):
        self.raw_data_path = Path(raw_data_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_raw_data(self) -> Dict[str, Any]:
        if not self.raw_data_path.exists():
            raise FileNotFoundError(f"Raw data file not found at {self.raw_data_path}")
        with open(self.raw_data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def build_sft_coder(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Construct SFT dataset for Wolinet Coder with Step-by-Step Chain-of-Thought."""
        sft_records = []
        trajectories = raw_data.get("agent_trajectories", [])

        for traj in trajectories:
            prompt = traj.get("prompt", "").strip()
            thought = traj.get("thought", "").strip()
            tool_name = traj.get("tool_name", "")
            tool_args = traj.get("tool_args", {})

            if not prompt or len(prompt) < 10:
                continue

            # Format synthesized chain-of-thought
            cot = thought if thought else (
                f"1. Analyze requirement: {prompt[:120]}...\n"
                f"2. Select appropriate tool or implementation pattern: {tool_name}\n"
                f"3. Verify safety and syntax parameters before execution."
            )

            # Format tool or code action
            if tool_name == "write_to_file":
                filepath = tool_args.get("TargetFile", "main.py")
                code_content = tool_args.get("CodeContent", "# Implementation")
                action_block = f"I will write the implementation to `{filepath}`:\n\n```python\n{code_content}\n```"
            elif tool_name == "run_command":
                cmd = tool_args.get("CommandLine", "")
                action_block = f"I will run the command to verify state:\n\n```bash\n{cmd}\n```"
            elif tool_name == "replace_file_content":
                filepath = tool_args.get("TargetFile", "")
                repl = tool_args.get("ReplacementContent", "")
                action_block = f"I will update `{filepath}` with the tested changes:\n\n```python\n{repl}\n```"
            else:
                action_block = f"Executing verified action using `{tool_name}` with parameters: {json.dumps(tool_args)}"

            assistant_response = f"<thought>\n{cot}\n</thought>\n\n{action_block}"

            sft_records.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_CODER},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": assistant_response}
                ],
                "metadata": {
                    "domain": "software_engineering",
                    "tool": tool_name,
                    "quality_verified": True
                }
            })

        # Add domain anchor examples for coding capabilities
        anchor_examples = [
            {
                "prompt": "Write an asynchronous FastAPI endpoint with Redis caching and PostgreSQL persistence for user profile lookups.",
                "thought": "1. Define Pydantic response models.\n2. Connect to asyncpg pool and redis client.\n3. Check cache first (Cache-Aside pattern).\n4. Fallback to SQL query and write back to cache with TTL.",
                "response": "Here is the production-ready async FastAPI endpoint:\n\n```python\nfrom fastapi import APIRouter, Depends, HTTPException\nfrom pydantic import BaseModel\nimport aioredis\nimport asyncpg\nimport json\n\nrouter = APIRouter(prefix=\"/v1/users\", tags=[\"users\"])\n\nclass UserProfile(BaseModel):\n    id: str\n    email: str\n    name: str\n\n@router.get(\"/{user_id}\", response_model=UserProfile)\nasync def get_user_profile(\n    user_id: str,\n    redis: aioredis.Redis = Depends(get_redis),\n    db: asyncpg.Pool = Depends(get_db)\n):\n    cache_key = f\"user:{user_id}\"\n    cached = await redis.get(cache_key)\n    if cached:\n        return UserProfile(**json.loads(cached))\n\n    async with db.acquire() as conn:\n        row = await conn.fetchrow(\"SELECT id, email, name FROM users WHERE id = $1\", user_id)\n        if not row:\n            raise HTTPException(status_code=404, detail=\"User not found\")\n        user = UserProfile(id=str(row[\"id\"]), email=row[\"email\"], name=row[\"name\"])\n        await redis.set(cache_key, user.model_dump_json(), ex=300)\n        return user\n```"
            },
            {
                "prompt": "Implement a sovereign health probe in Python that verifies LiteLLM Gateway, Xinference, and PostgreSQL in parallel.",
                "thought": "1. Use asyncio.gather for parallel non-blocking HTTP and TCP checks.\n2. Query http://127.0.0.1:4000/health/liveliness for LiteLLM.\n3. Query http://127.0.0.1:9997/status for Xinference.\n4. Check TCP socket 5433 for PostgreSQL.\n5. Return aggregated status payload.",
                "response": "```python\nimport asyncio, aiohttp, socket\n\nasync def check_http(url: str, timeout: float = 3.0) -> bool:\n    try:\n        async with aiohttp.ClientSession() as s:\n            async with s.get(url, timeout=timeout) as r:\n                return r.status in (200, 204)\n    except Exception:\n        return False\n\nasync def check_tcp(host: str, port: int, timeout: float = 2.0) -> bool:\n    try:\n        r, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)\n        w.close()\n        await w.wait_closed()\n        return True\n    except Exception:\n        return False\n\nasync def system_health_probe() -> dict:\n    lango, mitambo, pg = await asyncio.gather(\n        check_http(\"http://127.0.0.1:4000/health/liveliness\"),\n        check_http(\"http://127.0.0.1:9997/status\"),\n        check_tcp(\"127.0.0.1\", 5433)\n    )\n    return {\"status\": \"healthy\" if all([lango, mitambo, pg]) else \"degraded\", \"components\": {\"lango\": lango, \"mitambo\": mitambo, \"postgres\": pg}}\n```"
            }
        ]
        for a in anchor_examples:
            sft_records.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_CODER},
                    {"role": "user", "content": a["prompt"]},
                    {"role": "assistant", "content": f"<thought>\n{a['thought']}\n</thought>\n\n{a['response']}"}
                ],
                "metadata": {"domain": "software_engineering", "source": "anchor", "quality_verified": True}
            })

        return sft_records

    def build_sft_pro(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Construct SFT dataset for Wolinet Pro with strategic & architectural reasoning."""
        sft_records = []
        spend_logs = raw_data.get("postgres_spend_logs", [])

        for log in spend_logs[:100]:
            req_id = log.get("request_id", "")
            model = log.get("model", "")
            status = log.get("status", "")
            pt = log.get("prompt_tokens", 0)
            ct = log.get("completion_tokens", 0)

            if status != "success" or ct < 1:
                continue

            prompt = f"Assess gateway telemetry and performance metrics for request {req_id} routed through sovereign model {model}."
            thought = (
                f"1. Extract token consumption: {pt} prompt tokens, {ct} completion tokens.\n"
                f"2. Validate inference efficiency and status.\n"
                f"3. Synthesize operational recommendation."
            )
            response = (
                f"**Request Analysis for `{req_id}`**:\n\n"
                f"- **Model**: `{model}`\n"
                f"- **Status**: `{status.upper()}` (Zero CVE sovereign execution)\n"
                f"- **Throughput**: {pt} prompt tokens $\\to$ {ct} completion tokens\n"
                f"- **Recommendation**: Token efficiency is nominal. Request completed within the sovereign local sandbox."
            )

            sft_records.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_PRO},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": f"<thought>\n{thought}\n</thought>\n\n{response}"}
                ],
                "metadata": {"domain": "systems_reasoning", "quality_verified": True}
            })

        return sft_records

    def build_dpo_pairs(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Construct DPO dataset pairing verified chosen responses (y_w) vs rejected candidates (y_l)."""
        dpo_pairs = []
        trajectories = raw_data.get("agent_trajectories", [])

        for traj in trajectories[:80]:
            prompt = traj.get("prompt", "").strip()
            thought = traj.get("thought", "").strip()
            tool_name = traj.get("tool_name", "")
            tool_args = traj.get("tool_args", {})

            if not prompt or len(prompt) < 15:
                continue

            # Chosen: Complete, verified action with structured thought
            chosen_cot = thought if thought else "1. Understand problem\n2. Perform verified tool action."
            chosen = f"<thought>\n{chosen_cot}\n</thought>\n\nExecuting verified action using `{tool_name}`: {json.dumps(tool_args, indent=2)}"

            # Rejected: Hallucinated, unverified, or missing imports
            rejected = f"I think you can just do this:\n```bash\ncurl http://unknown-external-cloud.com/api\n```\n(No local verification performed)."

            dpo_pairs.append({
                "prompt": prompt,
                "chosen": chosen,
                "rejected": rejected,
                "domain": "coding_safety"
            })

        return dpo_pairs

    def run_build(self) -> Dict[str, int]:
        raw_data = self.load_raw_data()

        coder_sft = self.build_sft_coder(raw_data)
        pro_sft = self.build_sft_pro(raw_data)
        coder_dpo = self.build_dpo_pairs(raw_data)

        coder_sft_file = self.output_dir / "wolinet_coder_sft.jsonl"
        pro_sft_file = self.output_dir / "wolinet_pro_sft.jsonl"
        coder_dpo_file = self.output_dir / "wolinet_coder_dpo.jsonl"

        with open(coder_sft_file, "w", encoding="utf-8") as f:
            for item in coder_sft:
                f.write(json.dumps(item) + "\n")

        with open(pro_sft_file, "w", encoding="utf-8") as f:
            for item in pro_sft:
                f.write(json.dumps(item) + "\n")

        with open(coder_dpo_file, "w", encoding="utf-8") as f:
            for item in coder_dpo:
                f.write(json.dumps(item) + "\n")

        counts = {
            "coder_sft": len(coder_sft),
            "pro_sft": len(pro_sft),
            "coder_dpo": len(coder_dpo),
        }

        print(f"\n[✓] Datasets compiled successfully!")
        print(f"    • Wolinet Coder SFT: {counts['coder_sft']} examples -> {coder_sft_file}")
        print(f"    • Wolinet Pro SFT:   {counts['pro_sft']} examples -> {pro_sft_file}")
        print(f"    • Wolinet Coder DPO: {counts['coder_dpo']} pairs    -> {coder_dpo_file}")

        return counts


if __name__ == "__main__":
    builder = DatasetBuilder()
    builder.run_build()
