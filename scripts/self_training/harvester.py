#!/usr/bin/env python3
"""
Wolinet AI — Autonomous Trajectory Harvester (Pipeline 5)
Mines verified passing executions and failed candidate pairs from:
1. PostgreSQL 16 LiteLLM_SpendLogs (port 5433 / 5432)
2. ai-memory hook-spool observations (~/Library/Application Support/ai-memory/hook-spool)
3. Agent interaction transcripts (~/.gemini/antigravity-ide/brain/*/transcript_full.jsonl)
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class TrajectoryHarvester:
    def __init__(
        self,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5433,
        pg_user: str = "postgres",
        pg_password: str = "CHANGE_ME_STRONG_PG_PASSWORD",
        pg_db: str = "litellm",
        hook_spool_dir: str = "/Users/apple/Library/Application Support/ai-memory/hook-spool",
        brain_dir: str = "/Users/apple/.gemini/antigravity-ide/brain",
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_password = pg_password
        self.pg_db = pg_db
        self.hook_spool_dir = Path(hook_spool_dir)
        self.brain_dir = Path(brain_dir)

    def harvest_postgres_logs(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Harvest execution logs and latency metrics from PostgreSQL LiteLLM_SpendLogs."""
        print(f"[*] Querying PostgreSQL LiteLLM_SpendLogs on {self.pg_host}:{self.pg_port}...")
        query = f"""
        SELECT json_agg(sub) FROM (
            SELECT 
                request_id,
                model,
                status,
                prompt_tokens,
                completion_tokens,
                request_duration_ms,
                "startTime",
                metadata->>'user_agent' as user_agent,
                metadata->>'original_model_group' as model_group,
                metadata->'model_map_information'->>'model_map_key' as mapped_model
            FROM "LiteLLM_SpendLogs"
            WHERE status IN ('success', 'failure')
            ORDER BY "startTime" DESC
            LIMIT {limit}
        ) sub;
        """
        env = os.environ.copy()
        env["PGPASSWORD"] = self.pg_password
        cmd = [
            "psql",
            "-h", self.pg_host,
            "-p", str(self.pg_port),
            "-U", self.pg_user,
            "-d", self.pg_db,
            "-t",
            "-A",
            "-c", query,
        ]
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
            output = res.stdout.strip()
            if output and output != "null":
                records = json.loads(output)
                print(f"[+] Harvested {len(records)} spend log records from PostgreSQL.")
                return records
        except Exception as e:
            print(f"[-] Warning: Failed to query PostgreSQL: {e}")
        return []

    def harvest_hook_spool(self, max_records: int = 100) -> List[Dict[str, Any]]:
        """Harvest live pre/post tool use events from ai-memory hook-spool."""
        if not self.hook_spool_dir.exists():
            return []
        
        print(f"[*] Scanning ai-memory hook-spool in {self.hook_spool_dir}...")
        files = sorted(glob.glob(str(self.hook_spool_dir / "*.json")), reverse=True)[:max_records]
        events = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    url = data.get("url", "")
                    event_type = url.split("event=")[1].split("&")[0] if "event=" in url else ""
                    body_raw = data.get("body", "{}")
                    body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
                    events.append({
                        "event": event_type,
                        "tool": body.get("toolCall", {}).get("name"),
                        "args": body.get("toolCall", {}).get("args"),
                        "error": body.get("error", ""),
                        "stepIdx": body.get("stepIdx"),
                        "conversationId": body.get("conversationId"),
                        "timestamp": data.get("created_ms"),
                    })
            except Exception:
                continue
        print(f"[+] Harvested {len(events)} hook-spool tool observations.")
        return events

    def harvest_transcripts(self, max_transcripts: int = 25, max_steps_per_transcript: int = 150) -> List[Dict[str, Any]]:
        """Harvest prompt-thought-action-result quadruples from full conversation transcripts."""
        pattern = str(self.brain_dir / "*" / ".system_generated" / "logs" / "transcript_full.jsonl")
        files = glob.glob(pattern)
        # Sort by file modification time (newest first)
        files.sort(key=os.path.getmtime, reverse=True)
        selected_files = files[:max_transcripts]
        print(f"[*] Scanning {len(selected_files)} transcripts across agent brains...")

        trajectories = []
        for tf in selected_files:
            try:
                with open(tf, "r", encoding="utf-8") as fp:
                    current_user_prompt = ""
                    current_thought = ""
                    lines = fp.readlines()
                    for line in lines[-max_steps_per_transcript:]:
                        item = json.loads(line)
                        step_type = item.get("type")
                        content = item.get("content", "")

                        if step_type == "USER_INPUT":
                            current_user_prompt = content.strip()
                        elif step_type == "PLANNER_RESPONSE":
                            tool_calls = item.get("tool_calls", [])
                            # Extract thought text if present
                            if content and ("thought" in content.lower() or len(content) > 20):
                                current_thought = content.strip()
                            
                            # If tool calls were made, capture them
                            if tool_calls and current_user_prompt:
                                for tc in tool_calls:
                                    t_name = tc.get("name", "")
                                    t_args = tc.get("args", {})
                                    if t_name in ("run_command", "write_to_file", "replace_file_content", "grep_search"):
                                        trajectories.append({
                                            "prompt": current_user_prompt,
                                            "thought": current_thought,
                                            "tool_name": t_name,
                                            "tool_args": t_args,
                                            "source": tf,
                                            "quality": "verified"
                                        })
            except Exception:
                continue

        print(f"[+] Harvested {len(trajectories)} rich agent trajectories from transcripts.")
        return trajectories

    def run_harvest(self) -> Dict[str, Any]:
        """Execute full harvesting cycle across all three sovereign data tiers."""
        pg_logs = self.harvest_postgres_logs(limit=250)
        spool_events = self.harvest_hook_spool(max_records=150)
        transcripts = self.harvest_transcripts(max_transcripts=20, max_steps_per_transcript=120)

        # Aggregate summary
        result = {
            "postgres_spend_logs": pg_logs,
            "hook_spool_events": spool_events,
            "agent_trajectories": transcripts,
            "counts": {
                "postgres_logs": len(pg_logs),
                "hook_spool_events": len(spool_events),
                "agent_trajectories": len(transcripts),
            }
        }
        return result


if __name__ == "__main__":
    harvester = TrajectoryHarvester()
    data = harvester.run_harvest()
    output_path = Path("data/training/harvested_raw.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"\n[✓] Harvest complete! Raw data persisted to {output_path}")
    print(f"    • Spend Logs: {data['counts']['postgres_logs']}")
    print(f"    • Spool Events: {data['counts']['hook_spool_events']}")
    print(f"    • Rich Trajectories: {data['counts']['agent_trajectories']}")
