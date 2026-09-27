"""
Wolinet Agentic Tools
Provides standard tool schemas and execution handlers for autonomous coding agents.
"""

import json
import os
import subprocess
from typing import Any, Dict, List

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite content to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target file path"},
                    "content": {"type": "string", "description": "Complete text content to write"}
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list (default: current directory)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command safely and return stdout and stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command line to execute"}
                },
                "required": ["command"],
            },
        },
    },
]


def execute_tool(name: str, arguments: Dict[str, Any], workspace_root: str = ".") -> str:
    """Execute a tool call safely within the target workspace."""
    try:
        if name == "read_file":
            filepath = os.path.expanduser(arguments["path"])
            if not os.path.isabs(filepath):
                filepath = os.path.join(workspace_root, filepath)
            if not os.path.exists(filepath):
                return f"Error: File '{arguments['path']}' does not exist."
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        elif name == "write_file":
            filepath = os.path.expanduser(arguments["path"])
            if not os.path.isabs(filepath):
                filepath = os.path.join(workspace_root, filepath)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(arguments["content"])
            return f"Successfully wrote {len(arguments['content'])} bytes to {arguments['path']}."

        elif name == "list_directory":
            target = arguments.get("path", ".")
            filepath = os.path.expanduser(target)
            if not os.path.isabs(filepath):
                filepath = os.path.join(workspace_root, filepath)
            if not os.path.exists(filepath):
                return f"Error: Path '{target}' does not exist."
            entries = []
            for item in sorted(os.listdir(filepath)):
                full_item = os.path.join(filepath, item)
                kind = "directory" if os.path.isdir(full_item) else "file"
                entries.append({"name": item, "type": kind})
            return json.dumps(entries, indent=2)

        elif name == "run_command":
            cmd = arguments["command"]
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            res = []
            if out:
                res.append(f"STDOUT:\n{out}")
            if err:
                res.append(f"STDERR:\n{err}")
            return "\n".join(res) if res else "(Command completed with no output)"

        else:
            return f"Error: Unknown tool '{name}'."

    except Exception as e:
        return f"Tool Execution Error ({name}): {str(e)}"
