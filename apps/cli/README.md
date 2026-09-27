# Wolinet AI CLI (Terminal Coding Agent)

A sovereign, local-first terminal coding agent powered by the Wolinet AI Platform.

## Quick Benchmark
Test your local model speed, time-to-first-token (TTFT), and generation rate:
```bash
./apps/cli/wolinet test
```

## Available Commands

### ⚡ Fast Autonomous Coding Agent (Lean Context & Zero Token Lag)
Optimized for local CPU execution with live status spinners, syntax highlighting, and surgical tool execution:
* `./apps/cli/wolinet agent "Inspect src/auth.py and add password hashing"`: Run an autonomous coding task.
* `./apps/cli/wolinet chat`: Open an interactive terminal coding chat session.
* `./apps/cli/wolinet test`: Benchmark latency and tokens/sec against `wolinex-coder`.

### 🌐 Full Workspace & Gateway Commands
* `./apps/cli/wolinet run "Refactor this function"`: Run a headless coding task through the Litespeed server with real-time spinner feedback.
* `./apps/cli/wolinet models`: List available models configured on the gateway.
* `./apps/cli/wolinet sessions`: List recent coding sessions.
* `./apps/cli/wolinet doctor`: Run diagnostics on server, database, and providers.
* `./apps/cli/wolinet serve`: Start the web workspace on `http://localhost:3210`.
* `./apps/cli/wolinet --help`: View all available commands.

## Global Terminal Alias
To run `wolinet` from any directory on your Mac, add this line to your `~/.zshrc`:
```bash
alias wolinet="/Users/apple/Documents/wolinetai/apps/cli/wolinet"
```
Then run:
```bash
source ~/.zshrc
```
