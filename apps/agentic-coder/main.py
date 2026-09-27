#!/usr/bin/env python3
"""
Wolinet Agentic Coder CLI
Interactive agentic coding assistant powered by Wolinet AI Platform.
"""

import argparse
import os
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from src.agent import AgenticCoder
from openai import OpenAI

console = Console()


def run_benchmark(endpoint: str, model: str, api_key: str | None = None):
    """Run an instant speed, latency, and tokens/sec benchmark against the local model."""
    resolved_key = (
        api_key
        or os.getenv("LITELLM_MASTER_KEY")
        or os.getenv("WOLINET_GATEWAY_MASTER_KEY")
        or "not-needed"
    )
    console.print(Panel.fit(
        f"[bold cyan]⚡ Wolinet AI Performance Benchmark[/bold cyan]\n"
        f"Gateway: [yellow]{endpoint}[/yellow] | Model: [green]{model}[/green]",
        border_style="cyan"
    ))

    client = OpenAI(base_url=endpoint, api_key=resolved_key)

    with console.status("[bold cyan]Pinging gateway and testing model latency...[/bold cyan]", spinner="dots"):
        t0 = time.time()
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": "Write a fast Python function to calculate Fibonacci numbers with memoization."}
                ],
                stream=True,
                max_tokens=150,
                temperature=0.1
            )
        except Exception as e:
            console.print(f"[bold red]✗ Benchmark failed to connect:[/bold red] {e}")
            return

        ttft = None
        tokens = 0
        output_chunks = []
        for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            if content:
                if ttft is None:
                    ttft = time.time() - t0
                tokens += 1
                output_chunks.append(content)
        total_time = time.time() - t0

    tps = tokens / (total_time - (ttft or 0)) if (total_time - (ttft or 0)) > 0 else 0
    full_output = "".join(output_chunks)

    console.print(f"\n[bold green]✓ Benchmark Completed Successfully![/bold green]")
    console.print(f"  • [bold white]Time to First Token (TTFT):[/bold white] [cyan]{(ttft or 0):.2f}s[/cyan]")
    console.print(f"  • [bold white]Total Generation Time:[/bold white]     [cyan]{total_time:.2f}s[/cyan]")
    console.print(f"  • [bold white]Output Tokens Generated:[/bold white]   [cyan]{tokens}[/cyan]")
    console.print(f"  • [bold white]Inference Speed:[/bold white]           [bold green]{tps:.1f} tokens/sec[/bold green]\n")

    console.print(Panel(Markdown(full_output), title="Sample Generated Output", border_style="dim"))


def main():
    parser = argparse.ArgumentParser(description="Wolinet Autonomous Coding Agent")
    parser.add_argument(
        "positional_prompt", nargs="?", type=str, help="Optional inline prompt"
    )
    parser.add_argument(
        "--prompt", "-p", type=str, help="Prompt or task instruction for the agent"
    )
    parser.add_argument(
        "--model", "-m", type=str, default="wolinex-coder", help="Model name (default: wolinex-coder)"
    )
    parser.add_argument(
        "--endpoint", "-e", type=str,
        default=os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
        help="Gateway endpoint (default: $LITELLM_BASE_URL or http://localhost:4000/v1)"
    )
    parser.add_argument(
        "--workspace", "-w", type=str, default=".", help="Target workspace path (default: current directory)"
    )
    parser.add_argument(
        "--test", action="store_true", help="Run model speed and latency benchmark"
    )
    args = parser.parse_args()

    # Route benchmark
    if args.test or (args.positional_prompt and args.positional_prompt.lower() == "test"):
        run_benchmark(endpoint=args.endpoint, model=args.model)
        return

    instruction = args.prompt or args.positional_prompt

    agent = AgenticCoder(
        base_url=args.endpoint,
        model=args.model,
        workspace_root=args.workspace,
    )

    if instruction:
        result = agent.run(instruction)
        console.print(Panel(Markdown(result) if result else "[dim](No output returned)[/dim]", title="Result", border_style="green"))
        return

    console.print(Panel.fit(
        "🤖 [bold green]Wolinet Agentic Coder[/bold green] - Interactive Terminal\n"
        f"[dim]Endpoint:[/dim] [cyan]{args.endpoint}[/cyan] | [dim]Model:[/dim] [green]{args.model}[/green]\n"
        "[dim]Type your coding goal, or 'exit' / 'quit' to close.[/dim]",
        border_style="cyan"
    ))

    while True:
        try:
            instruction = console.input("\n[bold cyan]wolinet-agent > [/bold cyan]").strip()
            if not instruction:
                continue
            if instruction.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            if instruction.lower() == "test":
                run_benchmark(endpoint=args.endpoint, model=args.model)
                continue

            result = agent.run(instruction)
            console.print(Panel(Markdown(result) if result else "[dim](No output returned)[/dim]", title="Result", border_style="green"))
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            break


if __name__ == "__main__":
    main()
