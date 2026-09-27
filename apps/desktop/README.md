# Wolinet AI Studio (Desktop & Web IDE)

**Wolinet AI Studio** is the flagship IDE component of the Wolinet AI platform, built on **Eclipse Theia v1.76.0**. It provides an enterprise-grade development environment with full VS Code extension protocol compatibility, native AI coding assistance, and seamless integration with the local sovereign **Wolinet Gateway**.

---

## 🌟 Key Features

1. **Full Eclipse Theia v1.76.0 Source Tree**:
   - Complete monorepo source containing all 83 `@theia/*` packages (`core`, `editor`, `monaco`, `navigator`, `terminal`, `workspace`, `vsx-registry`, `plugin-ext-vscode`, etc.).
   - Both Web/Browser and Electron Native desktop modes supported.

2. **Native AI Framework (`@theia/ai-*`)**:
   - **AI Chat & Code Assistance**: Interactive assistant sidebar with file context, diff suggestions, and multi-turn reasoning.
   - **Inline Code Completion**: Real-time code completions powered by local LLMs.
   - **Model Context Protocol (MCP)**: Native tool calling via `@theia/ai-mcp` and `@theia/ai-mcp-server`.
   - **Local Gateway Integration**: Pre-configured out of the box to connect directly to the sovereign Wolinet Gateway at `http://127.0.0.1:4000/v1` with models:
     - `qwen2.5-coder` (Primary coding and autocomplete engine)
     - `deepseek-r1` (Reasoning and architectural planning engine)
     - `wolinex-general` (General-purpose development assistant)

3. **VS Code Extension Compatibility & Open-VSX**:
   - Direct compatibility with standard VS Code extensions (`.vsix`).
   - Integrated with the **Open-VSX Registry** (`https://open-vsx.org/`) for searching and installing extensions.

4. **Zero Cloud Dependencies**:
   - Runs 100% locally with zero external telemetry or cloud lock-in.
   - All AI requests stay on your local hardware or private sovereign cluster.

---

## 🚀 Quickstart

### Launch via Script
To start Wolinet AI Studio in browser mode on port `3090`:
```bash
./apps/desktop/run_desktop.sh browser
```
Open `http://localhost:3090` in your browser.

To start in native desktop mode (Electron):
```bash
./apps/desktop/run_desktop.sh electron
```

### Build from Source
To compile and build the packages and applications:
```bash
./apps/desktop/run_desktop.sh build
# Or manually:
cd apps/desktop
npm run compile
npm run build:browser
```

---

## ⚙️ Configuration & Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `OPENAI_API_BASE_URL` | `http://127.0.0.1:4000/v1` | URL of the local Wolinet AI LiteLLM Gateway |
| `OPENAI_API_KEY` | `sk-wolinet-admin-2026` | Authentication key for the local Gateway |
| `THEIA_PORT` | `3090` | Port for the browser-based IDE server |
| `THEIA_HOST` | `127.0.0.1` | Binding interface for local security |

---

## 📂 Architecture Overview

```
apps/desktop/
├── packages/              # 83 Core Theia Packages (ai-*, core, editor, monaco, etc.)
│   ├── ai-chat/           # AI Chat UI and conversation engine
│   ├── ai-code-completion/# Inline intelligent completion engine
│   ├── ai-mcp/            # Model Context Protocol tools & server integration
│   ├── ai-openai/         # OpenAI-compatible provider adapter (Wolinet Gateway)
│   ├── editor/            # Multi-tab code editor base
│   ├── monaco/            # Monaco editor integration
│   ├── navigator/         # File explorer tree & context menus
│   ├── plugin-ext-vscode/ # VS Code Extension API compatibility layer
│   ├── terminal/          # Integrated terminal emulator
│   └── vsx-registry/      # Open-VSX extension marketplace registry client
├── examples/
│   ├── browser/           # Web/Browser IDE application target (Wolinet AI Studio)
│   └── electron/          # Native Desktop Electron application target
├── dev-packages/          # CLI tooling, linter plugins, and patch utilities
├── run_desktop.sh         # Top-level executable launcher
└── package.json           # Monorepo workspaces manifest
```

---

## 🛡️ License
Eclipse Public License 2.0 (EPL-2.0) OR GPL-2.0-only WITH Classpath-exception-2.0.
Commercial friendly.
