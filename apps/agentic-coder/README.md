# Wolinet Agentic Coder

A reference autonomous agentic coding assistant built to demonstrate how client applications interact with the **Wolinet AI Gateway**.

## Features
- **OpenAI-Compatible Tool Loop**: Implements tool calling for any model enabled for the supplied gateway key. If `--model` is omitted, the agent selects the first model returned by `GET /v1/models`.
- **Autonomous Toolset**:
  - `read_file`: Inspects files and code ranges.
  - `write_file`: Writes or modifies files safely.
  - `list_directory`: Recursively lists directories and files.
  - `run_command`: Executes terminal commands (builds, tests, lints, git).
- **Multi-Turn Reasoning**: Executes iterative loop until task completion or step limit reached.

## Quickstart
From repository root:
```bash
# Launch interactive session
make agent

# Or pass a single prompt directly
.venv/bin/python3 apps/agentic-coder/main.py --prompt "Check git status and summarize recent changes"

# Select a specific enabled gateway model
.venv/bin/python3 apps/agentic-coder/main.py --model YOUR_ENABLED_MODEL_ID --prompt "Analyze a distributed consensus algorithm"
```

## Adding Custom Tools
Add new tool functions to `apps/agentic-coder/src/tools.py` and register their OpenAI JSON schema in the `AVAILABLE_TOOLS` array. The agent will automatically gain access to them in subsequent turns.
