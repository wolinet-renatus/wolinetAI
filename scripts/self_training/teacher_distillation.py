#!/usr/bin/env python3
"""
Wolinet AI — Teacher-Student Parent Distillation Engine (Pipeline 5)
Leverages the advanced Cloud Parent Model (Wolinet Max / Gemini Frontier)
to continuously train and elevate the sovereign local models (Wolinet Pro & Coder).

Workflow:
  1. Frontier Prompt Selection (Complex reasoning, architectural design, coding edge cases).
  2. Parent (Teacher) Reasoning: Queries Wolinet Max via Gateway with deep thinking.
  3. Child (Student) Comparison: Queries local Wolinet Pro/Coder with the same prompt.
  4. Synthesizes:
     • Teacher SFT dataset (Parent's reasoning chains and golden solutions).
     • DPO Preference dataset (y_w = Parent golden response, y_l = Child baseline response).
  5. Feeds directly into local LoRA training cycle on Apple Silicon MPS.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


GATEWAY_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-XvKFiwDoOtOe8i4lwbzb8Q")
PARENT_MODEL = "Wolinet Max"
CHILD_CODER = "Wolinet Coder"
CHILD_PRO = "Wolinet Pro"

# Curated frontier engineering & reasoning challenge seeds
CURATED_CHALLENGES = [
    {
        "category": "distributed_systems",
        "prompt": "Design a high-throughput, zero-allocation circular ring buffer in Python using multiprocessing.shared_memory for lock-free inter-process messaging. Include wraparound boundary handling and atomic memory barriers.",
        "target_student": CHILD_CODER
    },
    {
        "category": "security_architecture",
        "prompt": "Explain how to implement zero-trust mTLS and token rotation between LiteLLM gateway, local inference backends, and containerized microservices without storing static secrets on disk.",
        "target_student": CHILD_PRO
    },
    {
        "category": "concurrency_patterns",
        "prompt": "Write an asynchronous batching queue in Python that buffers streaming LLM tokens, flushes dynamically based on either 50ms timeout or 64-token threshold, and gracefully handles client disconnects.",
        "target_student": CHILD_CODER
    },
    {
        "category": "data_engineering",
        "prompt": "Provide a complete SQL migration and PostgreSQL 16 schema with partitioned tables, GiST and GIN indexes, and trigger functions for storing millisecond-accurate AI agent tool execution logs.",
        "target_student": CHILD_CODER
    },
    {
        "category": "scientific_nlp",
        "prompt": "Formulate a verifiable workflow for extracting biological gene entities and molecular interactions from unstructured PubMed abstracts using regex pre-filtering followed by structured JSON output validation.",
        "target_student": CHILD_PRO
    }
]


class TeacherStudentDistillation:
    def __init__(
        self,
        gateway_url: str = GATEWAY_URL,
        master_key: str = MASTER_KEY,
        output_dir: str = "data/training",
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.master_key = master_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def query_model(self, model: str, prompt: str, max_tokens: int = 600, temperature: float = 0.2) -> Dict[str, Any]:
        """Query any model (Parent or Child) through the sovereign LiteLLM Gateway."""
        url = f"{self.gateway_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.master_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - t0
                choice = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                return {
                    "success": True,
                    "content": choice or "",
                    "usage": usage,
                    "elapsed": round(elapsed, 3),
                    "model": model
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "elapsed": round(time.time() - t0, 3),
                "model": model
            }

    def distill_single_challenge(self, challenge: Dict[str, str]) -> Optional[Dict[str, Any]]:
        prompt = challenge["prompt"]
        student_model = challenge["target_student"]
        category = challenge["category"]

        print(f"\n[*] Processing Challenge [{category}]:")
        print(f"    Prompt: \"{prompt[:80]}...\"")

        # 1. Query Parent (Teacher) - Wolinet Max
        print(f"    • Consulting Parent Teacher: [{PARENT_MODEL}]...")
        parent_resp = self.query_model(PARENT_MODEL, prompt, max_tokens=700)
        if not parent_resp["success"] or not parent_resp["content"]:
            print(f"    [-] Parent query failed: {parent_resp.get('error')}")
            return None
        print(f"    ✓ Parent generated solution in {parent_resp['elapsed']}s ({len(parent_resp['content'])} chars)")

        # 2. Query Child (Student) - Wolinet Pro / Coder
        print(f"    • Consulting Child Student:  [{student_model}]...")
        child_resp = self.query_model(student_model, prompt, max_tokens=500)
        child_content = child_resp.get("content", "") if child_resp["success"] else "Incomplete baseline generation."
        print(f"    ✓ Child generated baseline in {child_resp['elapsed']}s ({len(child_content)} chars)")

        # 3. Create SFT Reasoning Entry (Teacher's golden response)
        sft_entry = {
            "messages": [
                {
                    "role": "system",
                    "content": f"You are {student_model}, fine-tuned from parent architecture Wolinet Max. Think rigorously and emit production-grade, secure implementations."
                },
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": f"<thought>\n1. Understand requirements.\n2. Adopt architectural precision from parent teacher.\n3. Verify syntax and error boundaries.\n</thought>\n\n{parent_resp['content']}"}
            ],
            "metadata": {
                "source": "teacher_distillation",
                "parent_model": PARENT_MODEL,
                "student_model": student_model,
                "category": category,
                "distilled_at": time.time()
            }
        }

        # 4. Create DPO Pair (Chosen = Parent golden output, Rejected = Child baseline)
        dpo_pair = {
            "prompt": prompt,
            "chosen": parent_resp["content"],
            "rejected": child_content,
            "parent_model": PARENT_MODEL,
            "student_model": student_model,
            "category": category
        }

        return {
            "sft": sft_entry,
            "dpo": dpo_pair
        }

    def run_distillation_cycle(self, max_challenges: int = 3) -> Dict[str, Any]:
        print("=" * 76)
        print(" 🧠 WOLINET AI — PARENT-TO-CHILD KNOWLEDGE DISTILLATION ENGINE")
        print(f"    Parent Teacher: {PARENT_MODEL} (Cloud Frontier via Sovereign Gateway)")
        print(f"    Child Students: {CHILD_PRO} & {CHILD_CODER} (Local Sovereign on Mitambo)")
        print("=" * 76)

        challenges = CURATED_CHALLENGES[:max_challenges]
        sft_records = []
        dpo_records = []

        for ch in challenges:
            res = self.distill_single_challenge(ch)
            if res:
                sft_records.append(res["sft"])
                dpo_records.append(res["dpo"])

        # Persist distilled datasets
        sft_file = self.output_dir / "teacher_distilled_sft.jsonl"
        dpo_file = self.output_dir / "teacher_student_dpo.jsonl"

        with open(sft_file, "a", encoding="utf-8") as f:
            for r in sft_records:
                f.write(json.dumps(r) + "\n")

        with open(dpo_file, "a", encoding="utf-8") as f:
            for r in dpo_records:
                f.write(json.dumps(r) + "\n")

        print("\n" + "=" * 76)
        print(f"[✓] Distillation cycle complete!")
        print(f"    • Distilled SFT Examples: {len(sft_records)} appended to {sft_file}")
        print(f"    • Teacher-Student DPO:   {len(dpo_records)} pairs appended to {dpo_file}")
        print(f"    • Local students now possess golden reasoning traces from {PARENT_MODEL}.")
        print("=" * 76 + "\n")

        return {
            "distilled_sft_count": len(sft_records),
            "distilled_dpo_count": len(dpo_records),
            "sft_path": str(sft_file),
            "dpo_path": str(dpo_file)
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parent Teacher-Student Distillation")
    parser.add_argument("--count", type=int, default=2, help="Number of frontier challenges to distill")
    args = parser.parse_args()

    distiller = TeacherStudentDistillation()
    distiller.run_distillation_cycle(max_challenges=args.count)
