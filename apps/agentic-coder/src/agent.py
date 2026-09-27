"""
Autonomous Agentic Coder
Orchestrates autonomous multi-turn reasoning and tool execution loop with live rich feedback.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .tools import TOOLS_SPEC, execute_tool

logger = logging.getLogger("wolinet-agent")
console = Console()


class AgenticCoder:
    def __init__(
        self,
        base_url: str = "http://localhost:4000/v1",
        api_key: str | None = None,
        model: str = "wolinex-coder",
        workspace_root: str = ".",
        max_iterations: int = 15,
    ):
        resolved_key = (
            api_key
            or os.getenv("LITELLM_MASTER_KEY")
            or os.getenv("WOLINET_GATEWAY_MASTER_KEY")
        )
        if not resolved_key:
            raise EnvironmentError(
                "No API key found. Set LITELLM_MASTER_KEY or WOLINET_GATEWAY_MASTER_KEY in your environment or .env file."
            )
        resolved_url = base_url or os.getenv("LITELLM_BASE_URL") or "http://localhost:4000/v1"
        self.client = OpenAI(base_url=resolved_url, api_key=resolved_key)
        self.base_url = resolved_url
        self.model = model
        self.workspace_root = os.path.abspath(workspace_root)
        self.max_iterations = max_iterations

        self.system_prompt = (
            "You are Wolinex Coder, an autonomous AI software engineer developed by Wolinet Tech.\n"
            "You have access to 4 workspace tools:\n"
            "1. read_file(path: str) - Read full content of a file\n"
            "2. write_file(path: str, content: str) - Write or overwrite a file\n"
            "3. list_directory(path: str) - List directory entries\n"
            "4. run_command(command: str) - Execute shell commands\n\n"
            "Rules:\n"
            "- If you need to inspect or edit files or run shell commands, call the appropriate tool.\n"
            "- You can format tool calls as <tool_call>{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}}</tool_call> or standard JSON.\n"
            "- When you have completed the request, summarize your answer clearly without calling more tools."
        )

    def _extract_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract function name and arguments from text when model emits XML or markdown JSON."""
        calls: List[Dict[str, Any]] = []
        if not text:
            return calls

        # 1. XML tags: <tool_call>...</tool_call>
        xml_matches = re.findall(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
        for m in xml_matches:
            try:
                data = json.loads(m.strip())
                if isinstance(data, dict) and "name" in data:
                    calls.append({
                        "name": data["name"],
                        "arguments": data.get("arguments", {})
                    })
            except Exception:
                pass
        if calls:
            return calls

        # 2. Markdown json blocks: ```json ... ```
        md_matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        for m in md_matches:
            try:
                data = json.loads(m.strip())
                if isinstance(data, dict) and "name" in data and "arguments" in data:
                    calls.append({
                        "name": data["name"],
                        "arguments": data.get("arguments", {})
                    })
            except Exception:
                pass
        if calls:
            return calls

        # 3. Direct JSON: {"name": "...", "arguments": {...}}
        direct_match = re.search(
            r"\{\s*\"name\"\s*:\s*\"([^\"]+)\"\s*,\s*\"arguments\"\s*:\s*(\{.*?\})\s*\}",
            text,
            re.DOTALL,
        )
        if direct_match:
            try:
                name = direct_match.group(1)
                args = json.loads(direct_match.group(2))
                calls.append({"name": name, "arguments": args})
            except Exception:
                pass

        return calls

    def run(self, user_instruction: str) -> str:
        """Run the autonomous agent loop until the goal is accomplished."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_instruction},
        ]

        console.print(Panel.fit(
            f"[bold green]Wolinet Autonomous Agent[/bold green]\n"
            f"[dim]Model:[/dim] [cyan]{self.model}[/cyan] | "
            f"[dim]Gateway:[/dim] [cyan]{self.base_url}[/cyan]\n"
            f"[dim]Workspace:[/dim] [yellow]{self.workspace_root}[/yellow]\n"
            f"[dim]Task:[/dim] [bold white]{user_instruction}[/bold white]",
            border_style="cyan"
        ))

        start_time = time.time()

        for step in range(1, self.max_iterations + 1):
            step_start = time.time()

            with console.status(
                f"[bold cyan]Step {step}/{self.max_iterations}[/bold cyan] Thinking with [yellow]{self.model}[/yellow]...",
                spinner="dots"
            ) as status:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=TOOLS_SPEC,
                        tool_choice="auto",
                        temperature=0.1,
                    )
                except Exception as e:
                    console.print(f"[bold red]Inference Error:[/bold red] {e}")
                    return f"Error communicating with {self.model}: {e}"

                choice = response.choices[0]
                message = choice.message
                elapsed_step = time.time() - step_start

            raw_content = message.content or ""
            native_tool_calls = message.tool_calls

            # Check for native tool calls or fallback text tool calls
            parsed_tools: List[Tuple[str, str, Dict[str, Any]]] = []

            if native_tool_calls:
                for tc in native_tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    parsed_tools.append((tc.id, tc.function.name, args))
            else:
                fallback_calls = self._extract_tool_calls_from_text(raw_content)
                for i, fc in enumerate(fallback_calls):
                    call_id = f"call_{step}_{i}_{int(time.time())}"
                    parsed_tools.append((call_id, fc["name"], fc.get("arguments", {})))

            # If no tools called, agent provided final answer
            if not parsed_tools:
                total_time = time.time() - start_time
                console.print(f"[bold green]✓ Completed in {step} step(s) ({total_time:.2f}s total)[/bold green]\n")
                return raw_content

            # Log assistant reasoning text only if it is not purely the tool call block
            clean_text = raw_content
            for _, fn_name, _ in parsed_tools:
                clean_text = re.sub(r"<tool_call>.*?</tool_call>", "", clean_text, flags=re.DOTALL)
                clean_text = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", clean_text, flags=re.DOTALL)
                clean_text = re.sub(r"\{\s*\"name\"\s*:\s*\"" + re.escape(fn_name) + r"\".*?\}", "", clean_text, flags=re.DOTALL)
            clean_text = clean_text.strip()
            # Only print if there is actual meaningful text beyond residual braces/brackets
            if clean_text and re.search(r"[a-zA-Z0-9]", clean_text):
                console.print(f"[dim]{clean_text}[/dim]")

            # Add assistant message to history
            messages.append(message.model_dump())

            # Execute tool calls
            for tc_id, fn_name, fn_args in parsed_tools:
                arg_preview = json.dumps(fn_args, ensure_ascii=False)
                if len(arg_preview) > 80:
                    arg_preview = arg_preview[:77] + "..."

                console.print(f"  [bold cyan]🛠 Tool:[/bold cyan] [bold yellow]{fn_name}[/bold yellow]({arg_preview}) [dim]({elapsed_step:.2f}s)[/dim]")

                tool_result = execute_tool(fn_name, fn_args, workspace_root=self.workspace_root)
                res_lines = tool_result.strip().splitlines()
                first_line = res_lines[0] if res_lines else "(Empty)"
                if len(first_line) > 100:
                    first_line = first_line[:97] + "..."
                preview_extra = f" (+{len(res_lines) - 1} lines)" if len(res_lines) > 1 else ""

                console.print(f"  [bold green]↳ Result:[/bold green] [dim]{first_line}{preview_extra}[/dim]")

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": fn_name,
                    "content": tool_result,
                })

        return "Agent exceeded maximum iteration limit."
