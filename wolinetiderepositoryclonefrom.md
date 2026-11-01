1.PandaCode: a calm desktop workspace for coding agents

## Languages

* [Rust47.9%](https://github.com/aicodeking/pandacode/search?l=rust)  
* [TypeScript43.4%](https://github.com/aicodeking/pandacode/search?l=typescript)  
* [CSS4.5%](https://github.com/aicodeking/pandacode/search?l=css)  
* [JavaScript2.9%](https://github.com/aicodeking/pandacode/search?l=javascript)  
* [Astro0.6%](https://github.com/aicodeking/pandacode/search?l=astro)  
* [Python0.5%](https://github.com/aicodeking/pandacode/search?l=python)  
* [Other0.2%](https://github.com/aicodeking/pandacode/search?l=Other)

                          [Readme.md](http://Readme.md) “ \# PandaCode

A small, native desktop workspace for coding agents. PandaCode runs the coding  
CLIs you already use — \*\*Claude Code, Codex, Kimi Code, OpenCode, GLM Coding  
Plan and Xiaomi MiMo\*\* (through Claude Code), \*\*GitHub Copilot CLI, Antigravity,  
xAI's Grok Build, DeepSeek, Command Code, Cline, Kilo Code, Devin CLI and Hermes Agent\*\* (through ACP), \*\*ZCode\*\* (through its app-server protocol), \*\*Pi\*\* and its  
fork \*\*omp\*\* (through Pi's RPC mode), and Meta's \*\*Muse Code\*\* (through its MSP  
protocol) — side by side, with your projects, Git, a  
terminal and a browser in one window.

PandaCode is free and open source under the \[PandaCode License\](LICENSE), the MIT  
License with one addition: forks that are used commercially or released publicly  
must say "This is a fork of PandaCode" and link to this repository. There is no  
account, no license key and no telemetry.

Built with Tauri 2, Rust, SQLite and plain TypeScript. It uses the operating  
system's webview: no bundled Chromium, resident Node server, React runtime or  
embedded editor engine.

\<p align="center"\>  
  \<b\>Download:\</b\>  
  \<a href="https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-macOS-arm64.dmg"\>macOS (Apple silicon)\</a\> ·  
  \<a href="https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-macOS-x64.dmg"\>macOS (Intel)\</a\> ·  
  \<a href="https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Windows-x64-setup.exe"\>Windows x64\</a\> ·  
  \<a href="https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Windows-arm64-setup.exe"\>Windows arm64\</a\> ·  
  \<a href="https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Linux-x86\_64.AppImage"\>Linux x64\</a\> ·  
  \<a href="https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Linux-aarch64.AppImage"\>Linux arm64\</a\> ·  
  \<a href="https\://github.com/aicodeking/pandacode/releases"\>All releases\</a\>  
\</p\>

\<p align="center"\>  
  \<img src="docs/screenshots/conversation.webp" alt="PandaCode with a finished Claude Code task: the reply explains the change, with the project's tasks in the sidebar and the composer below" width="100%"\>  
\</p\>

\#\# Features

\- \*\*Every harness in one place.\*\* Pick the harness, model and reasoning effort  
  per task; switch between them from the composer. See \[providers\](docs/providers.md).  
\- \*\*Tasks and a task board.\*\* Parallel tasks across projects, a Pending → In  
  progress → Review → Completed \[board\](docs/task-board.md), message queueing  
  and steering while an agent runs.  
\- \*\*Agent teams.\*\* An \[architect and up to three workers\](docs/architect-workers.md),  
  mixing harnesses and models, or named team profiles. Each spawned worker is one  
  line in the turn that started it; click it to open the worker.  
\- \*\*Model routing.\*\* In automatic teams (Cheap, Balanced or Best, from the Team  
  button) the lead can let a local router pick each worker's model, in about 10–25 ms  
  and without sending the task anywhere; a failed worker's replacement escalates to a  
  stronger model. See  
  \[model routing\](docs/model-routing.md).  
\- \*\*Bots.\*\* Put an agent behind Telegram, Slack, Discord, WhatsApp or a local web  
  chat; each conversation is an ordinary task. The sidebar's \*\*Bots\*\* view lists  
  every bot with its latest message. See \[bots\](docs/bots.md).  
\- \*\*Local VMs and cloud sandboxes.\*\* Headless macOS/Linux VMs on Apple silicon  
  (Tart), and Daytona, Cloudflare and AWS sandboxes that agents can drive.  
\- \*\*Cloud agents.\*\* Pick a cloud provider in a New task's \*\*Run on\*\* menu and the  
  agent runs on a machine in your own account (Daytona, Cloudflare, AWS, Google Cloud,  
  E2B, Modal, Vercel Sandbox, CodeSandbox, Runloop, Blaxel, Tensorlake, Freestyle,  
  boat). PandaCode installs the harness there, copies your login, and keeps the run  
  going while your laptop sleeps; changes come back to a local worktree. See  
  \[cloud agents\](docs/cloud-agents.md).  
\- \*\*Simulators.\*\* iOS Simulator and Android emulator tools for agents.  
\- \*\*Deploys.\*\* Start a deploy task for Vercel, Cloudflare, Railway, Netlify, AWS or Google  
  Cloud from the header (\[Netlify setup\](docs/netlify.md)), with approval-gated CLI runs (AWS and Google Cloud use  
  your installed CLI and its login).  
\- \*\*GitHub view.\*\* Your repositories with their threads, pull requests and issues;  
  review, fix checks, merge or solve an issue in one click. Each opens as a linked  
  thread beside the GitHub view, where you can keep chatting. See \[GitHub\](docs/github.md).  
\- \*\*Git and worktrees.\*\* Diffs, staging, commits, per-task \[worktrees\](docs/worktrees.md)  
  with a one-click local \*\*Merge into main\*\*, branch switching from the branch chip,  
  and optional \[GitHub\](docs/github.md) issues and pull requests through \`gh\`,  
  including merging a task's linked pull request.  
\- \*\*Approvals at hand.\*\* Requests wait in a slim bar above the prompt, one line  
  each, grouped with \*\*Approve all\*\* when there are several.  
\- \*\*Find in thread.\*\* \`⌘/Ctrl F\` searches your messages and the agent's, with  
  every match highlighted.  
\- \*\*Review every turn.\*\* Saved \[turn changes\](docs/turn-changes.md) with  
  unified/split diffs, an embedded \[browser\](docs/browser.md), and file previews.  
\- \*\*Token saver.\*\* Per-task response-style packs that cut output tokens.  
\- \*\*Quick overlay.\*\* A global shortcut (default ⌘/Ctrl \+ Shift \+ Space) opens a  
  launcher for new and running tasks from anywhere.  
\- \*\*Agent usage.\*\* Account limits and cost estimates for each installed harness  
  (\[agent usage\](docs/agent-usage.md)), and one-click CLI updates  
  (\[agent updates\](docs/agent-updates.md)).  
\- \*\*Attachments.\*\* Images, PDFs, documents, folders and a built-in mockup  
  sketcher (\[attachments\](docs/attachments.md)).

\#\# Screenshots

\*\*A board for everything in flight.\*\* Tasks from every project move from Pending to  
Review, each with its harness, model and linked issue.

\<img src="docs/screenshots/board.webp" alt="The task board with Pending, In progress, Review and Completed columns" width="100%"\>

\<table\>  
  \<tr\>  
    \<td width="62%" valign="top"\>\<img src="docs/screenshots/streaming.webp" alt="A reply streaming in, with the live working row and tool activity above it" width="100%"\>\<br\>\<sub\>\<b\>Live replies.\</b\> Responses stream in as Markdown, with tool activity folded above.\</sub\>\</td\>  
    \<td width="38%" valign="top"\>\<img src="docs/screenshots/model-picker.webp" alt="The harness and model picker listing Claude Code, Codex and Kimi Code models" width="100%"\>\<br\>\<sub\>\<b\>Any harness, any model.\</b\> Switch per task, with context size and reasoning effort.\</sub\>\</td\>  
  \</tr\>  
\</table\>

\*\*Agent teams.\*\* An architect plans the work, runs workers in parallel across  
harnesses, and reviews what they bring back.

\<img src="docs/screenshots/agent-team.webp" alt="An agent team's finished run: the architect's summary, the combined changed files and two completed workers" width="100%"\>

\*\*Your app beside the chat.\*\* The iOS Simulator and Android emulator run in the  
inspector on a lifelike device, so you can tap through what an agent just built.

\<img src="docs/screenshots/simulator.webp" alt="The inspector showing an iPhone 17 Pro simulator next to the conversation" width="100%"\>

\*\*Bots that keep working.\*\* A bot's conversation is an ordinary task thread, with  
the same streaming, composer and model picker; reach it from Telegram, Slack,  
Discord, WhatsApp or a browser too.

\<img src="docs/screenshots/bot.webp" alt="A bot named Scout replying with a morning digest" width="100%"\>

\<table\>  
  \<tr\>  
    \<td width="58%" valign="top"\>\<img src="docs/screenshots/diff.webp" alt="The changed-files viewer with a syntax-highlighted unified diff" width="100%"\>\<br\>\<sub\>\<b\>Review every turn.\</b\> Each turn saves its changes, with unified and split diffs.\</sub\>\</td\>  
    \<td width="42%" valign="top"\>\<img src="docs/screenshots/bot-settings.webp" alt="Bot settings with tabs for profile, conversations, memory, schedules, channels, rules and activity" width="100%"\>\<br\>\<sub\>\<b\>Bot settings.\</b\> Memory, schedules, channels and rules, in one place.\</sub\>\</td\>  
  \</tr\>  
\</table\>

\<sub\>Screenshots come from the browser preview with sample data. Regenerate them with  
\`npm run screenshots\` (see \[\`scripts/screenshots\`\](scripts/screenshots/capture.spec.ts)).\</sub\>

\#\# Privacy

\- \*\*No telemetry, no analytics, no accounts.\*\* PandaCode does not phone home.  
\- \*\*Your code stays on your machine.\*\* Projects, conversations and settings are  
  stored locally in SQLite. Prompts go only to the coding CLI or service you  
  pick, under that provider's own terms.  
\- \*\*It only talks to services you choose.\*\* Provider keys (GLM, MiMo, DeepSeek, Command Code, cloud  
  sandboxes, bot channels, connection secrets) are sent only to that provider.  
  On macOS they live in \`secrets.json\` in PandaCode's app data folder, readable  
  only by your user (0600), never the Keychain, so updates never ask for your  
  login password; keys saved in the Keychain by older versions move there on  
  first use. Linux keeps them in the Secret Service and Windows in Credential  
  Manager.  
\- \*\*Agent telemetry can be turned off in one place.\*\* Settings → Agents →  
  Privacy → \*\*Turn off agent telemetry\*\* starts every agent with its vendor's  
  own opt-outs (Claude Code, Codex, Kimi, Grok, DeepSeek, Command Code, Pi,  
  Muse, and OpenCode sharing) plus \`DO\_NOT\_TRACK=1\`. Your agent config files  
  are not changed. Each agent's row shows what the switch covers. Cline has no  
  per-launch switch, so turn it off in Cline's own settings. With the switch on,  
  Claude Code also stops fetching remote feature flags (it uses its defaults)  
  and can't take sessions started remotely on this computer.

A few automatic checks send no personal data — just plain requests for public  
information:

\| What \| Where \| How often \|  
\| \--- \| \--- \| \--- \|  
\| Latest versions of installed coding CLIs \| \`formulae.brew.sh\`, \`downloads.claude.ai\`, \`api.github.com\`, \`cdn.kimi.com\`, \`registry.npmjs.org\` (Cline) \| About every 6 hours \|  
\| Plan usage checks for your signed-in agents \| That agent's provider \| When you open the menu bar item or the Usage dialog \|  
\| Public model price list (for cost estimates) \| \`raw.githubusercontent.com\` \| Daily \|  
\| PandaCode's own updates (\`latest.json\` on this repository's latest release) \| \`github.com\` \| At launch and about every 6 hours unless Settings → About → Updates is Off \|  
\| Jev decision model list (optional) \| \`openrouter.ai\` \| Only when you choose OpenRouter for Jev decisions and open the model menu or press Refresh; no key is sent \|  
\| Jev decisions on OpenRouter (optional) \| \`openrouter.ai\` \| Only when you choose OpenRouter in Settings → Agents → Jev and run a decision check; sends the selected evidence with your key \|  
\| Cloud agents (optional): the task's checkout, prompt and harness login go to the machine you chose; PandaCode checks on its active runs \| The cloud provider you connected \| Only for tasks you start on a cloud provider; while a run is active and at launch to re-attach \|  
\| Model routing profiler (optional): \`model.int8.onnx\` and \`tokenizer.json\`, from a pinned commit, verified by SHA-256 \| \`raw.githubusercontent.com\` \| Once, the first time you turn on a team (with routing on) or click Download or Route in Settings → Agents → Model routing; never at launch \|  
\| PandaCode Connect (optional): GitHub sign-in, then the relay that forwards your devices' end-to-end encrypted messages \| \`github.com\`, the PandaCode relay \| Only after you sign in under Settings → Remote access; nothing before \|  
\| Push notifications (optional, mobile app): the relay sends a generic alert ("A task finished") with a \`pandacode://inbox\` link to your phone's device token, never task content \| Apple Push Notification service, Firebase Cloud Messaging (sent by the PandaCode relay) \| Only after you allow notifications in the mobile app while signed in to Connect \|  
\| Netlify token check (optional): verifies the token and project you enter \| \`api.netlify.com\` \| Only when you save a Netlify token in Settings → Agents → Cloud sandboxes \|

\#\# Install

Download the latest build from  
\[GitHub Releases\](https\://github.com/aicodeking/pandacode/releases/latest):

\| Platform \| File \| Requirements \|  
\| \--- \| \--- \| \--- \|  
\| macOS (Apple silicon) \| \[\`PandaCode-macOS-arm64.dmg\`\](https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-macOS-arm64.dmg) \| macOS 12+ \|  
\| macOS (Intel) \| \[\`PandaCode-macOS-x64.dmg\`\](https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-macOS-x64.dmg) \| macOS 12+ \|  
\| Windows x64 \| \[\`PandaCode-Windows-x64-setup.exe\`\](https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Windows-x64-setup.exe) \| Windows 10 1809+ or Windows 11 \|  
\| Windows arm64 \| \[\`PandaCode-Windows-arm64-setup.exe\`\](https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Windows-arm64-setup.exe) \| Windows 11 on ARM (Snapdragon X and similar) \|  
\| Linux x64 \| \[\`PandaCode-Linux-x86\_64.AppImage\`\](https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Linux-x86\_64.AppImage) \| Ubuntu 22.04+ or compatible, X11 or XWayland \|  
\| Linux arm64 \| \[\`PandaCode-Linux-aarch64.AppImage\`\](https\://github.com/aicodeking/pandacode/releases/latest/download/PandaCode-Linux-aarch64.AppImage) \| Ubuntu 24.04+ aarch64 or compatible, X11 or XWayland \|

Or from a terminal: \`npx pandacode\` downloads the latest build, verifies its  
signature and installs it (on macOS it is signed locally for you, so no  
Gatekeeper prompt). \`npx pandacode \--dry-run\` only downloads and verifies.

With \[Homebrew\](https\://brew.sh): \`brew install \--cask aicodeking/pandacode/pandacode\`  
on macOS, or \`brew install aicodeking/pandacode/pandacode\` on Linux  
(\[details\](docs/homebrew.md)).

Release builds are not code-signed, so your OS will warn the first time:

\- \*\*macOS:\*\* the build carries an ad-hoc signature and is not notarized, so macOS  
  refuses to open it, and \*\*Open Anyway\*\* in \*\*System Settings → Privacy &  
  Security\*\* does not always clear it. Run \`xattr \-dr com.apple.quarantine  
  /Applications/PandaCode.app\` once instead; \`npx pandacode\` signs the app locally  
  and needs no such step.  
\- \*\*Windows:\*\* if SmartScreen appears, click \*\*More info → Run anyway\*\*.  
\- \*\*Linux:\*\* \`chmod \+x PandaCode-Linux-x86\_64.AppImage\` (or \`-aarch64\`), then run it. Some  
  distributions need FUSE 2 (\`libfuse2\`), or set \`APPIMAGE\_EXTRACT\_AND\_RUN=1\`.  
  The AppImage runs through X11 (XWayland on Wayland) by default; if the window  
  stays blank there, try GTK's native Wayland backend with  
  \`GDK\_BACKEND=wayland ./PandaCode-Linux-x86\_64.AppImage\`.

Each file has a \`.sha256\` checksum beside it. Once installed, PandaCode updates  
itself: it checks the latest release, downloads a newer version in the background,  
verifies its signature, and restarts to install it when no agent is working and  
you've stepped away (or when you click \*\*Restart to update\*\*). In Settings → About,  
\*\*Notify me\*\* checks but asks first (\*\*Install and restart\*\* / \*\*Later\*\*), and \*\*Off\*\*  
stops checking. On Linux only the AppImage updates itself; an unpacked AppImage or a  
package just reports new versions. See \[platform support\](docs/platform-support.md) for details.

Then install Git and at least one coding CLI and sign in with its normal login.  
PandaCode does not include provider plans or usage.

\[Pi\](https\://github.com/earendil-works/pi) installs with \`npm i \-g @earendil-works/pi-coding-agent\`; sign in through Pi's own CLI. PandaCode drives it over Pi's RPC mode and gives it PandaCode's app tools through a local loopback bridge extension. Pi has no approval system of its own, so PandaCode's extension enforces the permission modes; the integrated console needs Full access.

\[omp (Oh My Pi)\](https\://github.com/can1357/oh-my-pi), a Pi fork that runs on Bun, installs with \`bun install \-g @oh-my-pi/pi-coding-agent\`; sign in through \`omp\` itself. PandaCode drives it with the same RPC bridge as Pi and passes \`--approval-mode yolo\` so the bridge stays the only approval gate.

\[DeepSeek\](https\://platform.deepseek.com/api\_keys) installs with \`npm i \-g @deepseek-ai/dsh\`; PandaCode launches \`dsh \--profile acp\`. An API key is optional (Settings → Providers, or \`DEEPSEEK\_API\_KEY\`); dsh can use its own stored credentials. With a saved key (or \`DEEPSEEK\_API\_KEY\`), the Usage dialog shows the account balance from \`api.deepseek.com\`.

\[Command Code\](https\://commandcode.ai/docs/acp) installs with \`npm i \-g command-code\` (Node 22 or newer); PandaCode launches \`command-code acp\`. Sign in once with \`command-code login\`, or save an API key in Settings → Providers (or set \`COMMAND\_CODE\_API\_KEY\`); either one authenticates the same account. Usage limits are not shown in PandaCode; check Command Code Studio.  
\[Cline\](https\://docs.cline.bot/usage/cli-overview) installs with \`npm i \-g cline\`; PandaCode launches \`cline \--acp\`. Sign in once with \`cline auth\` (or set \`CLINE\_API\_KEY\`); the provider and models chosen in Cline apply. See \[provider details\](docs/providers.md\#cline).

\[Kilo Code\](https\://kilo.ai/docs/code-with-ai/platforms/cli) installs with \`npm i \-g @kilocode/cli\`; sign in with \`kilo auth login\`, then select \*\*Kilo Code\*\* in PandaCode. PandaCode launches \`kilo acp\` and uses Kilo's configured providers and models. See \[provider details\](docs/providers.md\#kilo-code).

Muse Code installs with Meta's launcher into \`\~/.local/bin/muse\`; run \`muse login\` once in a terminal. PandaCode launches \`muse serve\` and speaks MSP, Muse's JSON-RPC session protocol, with its sandbox and approval modes; see \[docs/providers.md\](docs/providers.md\#muse-code) for what each mode does and what Muse cannot express.

\[GitHub Copilot CLI\](https\://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) installs with \`npm install \-g @github/copilot\`; run \`copilot login\` in a terminal, then select \*\*GitHub Copilot CLI\*\* in PandaCode. PandaCode launches the local \`copilot\` executable over ACP. The CLI manages its own sign-in. See \[provider details\](docs/providers.md\#github-copilot-cli).

\[Devin CLI\](https\://docs.devin.ai/cli) installs with \`curl \-fsSL https\://cli.devin.ai/install.sh \| bash\` (or \`brew install \--cask devin-cli\`, or the copy bundled with Devin Desktop); run \`devin auth login\` once in a terminal, then select \*\*Devin CLI\*\* in PandaCode. PandaCode launches \`devin acp\` with the CLI's own sign-in and lists every Devin model with its own thinking levels. See \[provider details\](docs/providers.md\#devin-cli).

\[ZCode\](https\://github.com/zai-org/ZCode) installs with its install script (\`\~/.local/bin/zcode\`, Node 24); run \`zcode\` once in a terminal and sign in, then select \*\*ZCode\*\* in PandaCode. PandaCode talks to \`zcode app-server\` directly — the CLI's own protocol, since it exposes no ACP mode — listing every model the account can reach with its own reasoning levels. See \[provider details\](docs/providers.md\#zcode).

\[Hermes Agent\](https\://hermes-agent.org) installs with \`curl \-fsSL https\://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh \| bash\`; run \`hermes acp \--setup\` or configure \`\~/.hermes/config.yaml\`, then select \*\*Hermes Agent\*\* in PandaCode. PandaCode launches \`hermes acp\` and uses Hermes' configured provider and models. See \[provider details\](docs/providers.md\#hermes-agent).

\#\# Build from source

You need Node.js 22, stable Rust, and the  
\[Tauri prerequisites\](https\://v2.tauri.app/start/prerequisites/) for your OS.

\`\`\`sh  
git clone https\://github.com/aicodeking/pandacode.git  
cd pandacode  
npm ci  
npm run desktop        \# same as: npm run tauri dev  
\`\`\`

\`npm run dev\` serves only the frontend. In a regular browser it runs a labeled,  
device-local sample workspace for UI work; files, Git and terminals are  
simulated there. \`npm run tauri build\` makes a local installer, and  
\`npm run release:build\` builds the release asset for your OS (see  
\[releasing\](docs/releasing.md)).

The website lives in \[website/\](website/): \`npm run site:dev\` and  
\`npm run site:build\`.

\#\# Use

Open a project folder, then click \*\*New task\*\* or press \`⌘/Ctrl N\`. A centered  
"What should we build in …?" page opens in the last active project with the  
message box focused. Choose the harness and model from the searchable picker in  
the message box; new tasks remember your last choice. The \*\*+\*\* button attaches  
images, documents, folders, project files or a mockup. Open \*\*Changes\*\* to  
inspect and stage diffs, or the terminal to run shell commands. Conversations  
and provider session IDs persist across restarts; agents start only for active  
turns.

In \*\*Files\*\*, click an HTML, SVG, image or PDF to open it in the sidebar browser.  
Filenames mentioned in responses become clickable and resolve against the task's  
own project or worktree.

The bar above the prompt shows the project, checkout and branch. Its branch chip  
is the one place for \[worktrees\](docs/worktrees.md): an unstarted task moves into  
a new worktree in place, a started one spawns a sibling task, and settling a  
clean worktree task offers to remove its checkout and merged branch.

Choose \*\*Board\*\* in the header to manage tasks by status. Choose \*\*Team\*\* in the  
composer for an automatic team, or set up an architect and workers. Each turn's  
tool calls sit inside a compact \*\*Worked for …\*\* row; final answers and errors  
stay visible, and approval requests wait in the bar above the prompt.

The branch chip also switches the project checkout to \`main\` or another local  
branch, and in a worktree task offers \*\*Merge into main\*\*: it merges the  
worktree's committed work locally, refuses uncommitted changes or conflicts  
without touching anything, then offers to remove the worktree.

\*\*Standard\*\* permissions keep each provider's native checks. Claude's \*\*Accept  
edits\*\* allows its editing tools; Codex uses its workspace sandbox with  
on-request approvals. \*\*Full access\*\* enables the harness's broadest mode. See  
\[provider details\](docs/providers.md).

Type \`/\` at the start of a message for the harness's commands and skills  
(\[slash commands\](docs/slash-commands.md)).

Keyboard shortcuts: \`⌘/Ctrl N\` new task, \`⌘/Ctrl K\` command palette,  
\`⌘/Ctrl J\` terminal, \`⌘/Ctrl B\` sidebar, \`⌘/Ctrl ,\` settings, \`⌘/Ctrl F\` find  
in thread (\`⌘/Ctrl G\` next match), \`Enter\` send (queues while an agent runs),  
\`⌘/Ctrl Enter\` steer, \`Shift Enter\` newline, \`⌘/Ctrl \+/−/0\` interface size (the  
whole interface scales, not just text).

On macOS, if folder access is denied, use \*\*Browse\*\* to select the folder, or  
allow PandaCode under \*\*System Settings → Privacy & Security → Files & Folders\*\*.

PandaCode includes \[21 anime scenery wallpapers\](docs/wallpapers.md), a  
different morning, afternoon and night scene for each weekday. \*\*Settings →  
Daily wallpapers\*\* turns them off. You can also import VS Code color themes.

The \[optional Jev add-on\](docs/jev.md) adds work review, project-rule checks and  
app testing in isolated Chrome profiles. It is off by default and PandaCode works  
fully without it.

\#\# Resource limits

No background directory polling or recursive file watchers. Agents exit after  
each turn and resume by provider session ID. After a Claude Code turn, the next  
turn's process starts in the background so a follow-up skips the CLI's startup;  
at most two wait at a time, each for up to 10 minutes. PandaCode's fixed  
instructions go to Claude-family harnesses once as a cached system prompt rather  
than in every message. The interface has no transitions: everything appears at  
once, and a thread you return to is drawn in a single frame. Terminal and Markdown code load only  
when needed. Terminal history, provider frames, files, diffs and streamed text  
all have explicit limits; only the current 100-message page of a conversation is  
loaded. \*\*Resource usage\*\* reports native core RSS, active agents, terminals and  
database size (core RSS excludes the system webview and provider processes).

\#\# Tests

\`\`\`sh  
npx tsc \--noEmit           \# typecheck  
npm run build && npm test  \# unit tests (some read dist/)  
npm run test:release       \# release script tests  
npm run test:rust          \# cargo test  
npx playwright test        \# browser suite (Chrome)  
npx playwright test \-c playwright.webkit.config.ts   \# WebKit  
\`\`\`

Ordinary tests make no paid model calls. Opt-in live tests are \`\#\[ignore\]\`d;  
see \[providers\](docs/providers.md).

\#\# Contributing

Contributions are welcome. Read \[CONTRIBUTING.md\](CONTRIBUTING.md) for setup and  
the pull request process, and \[AGENTS.md\](AGENTS.md) for code conventions. Please  
follow the \[Code of Conduct\](CODE\_OF\_CONDUCT.md), and report security issues  
privately as described in \[SECURITY.md\](SECURITY.md). Bugs and ideas go in  
\[GitHub issues\](https\://github.com/aicodeking/pandacode/issues).

Architecture notes: \[design\](docs/design.md), \[native IPC\](docs/ipc.md),  
\[research\](docs/research.md). Provider protocols live in  
\`src-tauri/src/providers.rs\` behind one normalized event interface; ACP harnesses  
share \`acp.rs\`.

\#\# Data

Data lives in Tauri's per-user application data directory (on macOS,  
\`\~/Library/Application Support/ai.pandacode.desktop/\`) in \`kingcode.sqlite3\`; the  
database keeps its legacy internal name. Project source stays in the folders you  
open, and removing a project from the app never deletes its files.

\#\# License

\[PandaCode License\](LICENSE) (MIT with an attribution requirement for forks) ©  
2026 PandaCode contributors. Provider names and logos belong to  
their owners and do not imply endorsement (\[brand assets\](docs/brand-assets.md)).  
“

2\.  [https\://github.com/aaif-goose/goose.git](https://github.com/aaif-goose/goose.git) an open source, extensible AI agent that goes beyond code suggestions \- install, execute, edit, and test with any LLM  

                \= Languages

* [TypeScript97.7%](https://github.com/getpaseo/paseo/search?l=typescript)  
* [JavaScript1.7%](https://github.com/getpaseo/paseo/search?l=javascript)  
* [Kotlin0.2%](https://github.com/getpaseo/paseo/search?l=kotlin)  
* [Shell0.2%](https://github.com/getpaseo/paseo/search?l=shell)  
* [Swift0.1%](https://github.com/getpaseo/paseo/search?l=swift)  
* [Nix0.1%](https://github.com/getpaseo/paseo/search?l=nix)

    [Readme.md](http://Readme.md)  
                “Your open source AI agent. Use goose on desktop or in the terminal, or build agents into your own applications with the [goose Development Kit (GDK)](https://goose-docs.ai/docs/gdk/).  
**55k+**GitHub stars  
**600+**Contributors  
**70+**MCP extensions

## What goose does

goose is a general-purpose AI agent that runs on your machine. Not just for code — use it for research, writing, automation, data analysis, or anything you need to get done.

🖥️

### Desktop app, CLI, and API

A native desktop app for macOS, Linux, and Windows. A full CLI for terminal workflows. An API to embed it anywhere. Built in Rust for performance and portability.  
🛠️

### goose Development Kit (GDK)

Build agents that run across native apps, servers, and the browser, and resume from saved state. Use the runtime components behind goose, with control over models, tools, and agent behavior. [Explore GDK](https://goose-docs.ai/docs/gdk/).  
🤖

### Any LLM, including your subscriptions

Works with 15+ providers — Anthropic, OpenAI, Google, Ollama, OpenRouter, Azure, Bedrock, and more. Use API keys or your existing Claude, ChatGPT, or Gemini subscriptions via [ACP](https://goose-docs.ai/docs/guides/acp-providers).  
📋

### Recipes

Capture workflows as portable YAML configs. Share with your team, run in CI, include instructions, extensions, parameters, and [subrecipes](https://goose-docs.ai/docs/guides/recipes/session-recipes).  
🧩

### MCP Apps

Extensions can render interactive UIs directly inside goose Desktop — buttons, forms, visualizations. A new way to build [agent-powered tools](https://goose-docs.ai/docs/tutorials/building-mcp-apps).  
🔀

### Subagents

Spawn independent [subagents](https://goose-docs.ai/docs/guides/context-engineering/subagents) to handle tasks in parallel — code review, research, file processing — keeping the main conversation clean.  
🔒

### Security

Prompt injection detection, tool permission controls, sandbox mode, and an [adversary reviewer](https://goose-docs.ai/docs/guides/security/adversary-mode) that watches for unsafe actions.

## Built on open standards

### Model Context Protocol

[MCP](https://modelcontextprotocol.io/) is the open standard for connecting AI agents to tools and data sources. goose was one of the earliest adopters and has one of the deepest integrations in the ecosystem — with 70+ documented extensions and growing.

[Browse MCP extensions →](https://goose-docs.ai/docs/category/mcp-servers)

### Agent Client Protocol

[ACP](https://agentclientprotocol.com/) is a standard for communicating with coding agents. goose works as an ACP server — connect from Zed, JetBrains, or VS Code — and can use ACP agents like Claude Code and Codex as providers.

[Set up goose in Zed →](https://goose-docs.ai/docs/guides/zed)

### Agentic AI Foundation

goose is part of the [Agentic AI Foundation](https://aaif.io/) at the Linux Foundation — ensuring the project remains vendor-neutral, community-governed, and open for the long term.

[Learn about AAIF →](https://aaif.io/)  
“ and  “\<div align="center"\>

\# goose

\_your native open source AI agent — desktop app, CLI, and API — for code, workflows, and everything in between\_

\<p align="center"\>  
  \<a href="https\://opensource.org/licenses/Apache-2.0"  
    \>\<img src="https\://img.shields.io/badge/License-Apache\_2.0-blue.svg"\>\</a\>  
  \<a href="https\://discord.gg/n8R5VaWDAn"  
    \>\<img src="https\://img.shields.io/discord/1287729918100246654?logo=discord\&logoColor=white\&label=Join+Us\&color=blueviolet" alt="Discord"\>\</a\>  
  \<a href="https\://github.com/aaif-goose/goose/actions/workflows/ci.yml"  
     \>\<img src="https\://img.shields.io/github/actions/workflow/status/aaif-goose/goose/ci.yml?branch=main" alt="CI"\>\</a\>  
  \<a href="https\://insights.linuxfoundation.org/project/goose"\>\<img src="https\://insights.linuxfoundation.org/api/badge/health-score?project=goose"\>\</a\>  
  \<a href="https\://repology.org/project/goose-cli/versions"\>\<img src="https\://repology.org/badge/tiny-repos/goose-cli.svg" alt="Packaging status"\>\</a\>  
\</p\>

\<a href="https\://trendshift.io/repositories/25298?utm\_source=repository-badge\&amp;utm\_medium=badge\&amp;utm\_campaign=badge-repository-25298" target="\_blank" rel="noopener noreferrer"\>\<img src="https\://trendshift.io/api/badge/repositories/25298" alt="aaif-goose%2Fgoose \| Trendshift" width="250" height="55"/\>\</a\>

\</div\>

goose is a general-purpose AI agent that runs on your machine. Not just for code — use it for research, writing, automation, data analysis, or anything you need to get done.

A native desktop app for macOS, Linux, and Windows. A full CLI for terminal workflows. An API to embed it anywhere. Built in Rust for performance and portability.

goose works with 15+ providers — Anthropic, OpenAI, Google, Ollama, OpenRouter, Azure, Bedrock, and more. Use API keys or your existing Claude, ChatGPT, or Gemini subscriptions via \[ACP\](https\://goose-docs.ai/docs/guides/acp-providers). Connect to 70+ extensions via the \[Model Context Protocol\](https\://modelcontextprotocol.io/) open standard.

goose is part of the \[Agentic AI Foundation (AAIF)\](https\://aaif.io/) at the Linux Foundation.

\# Get started

\*\*\[Download the desktop app\](https\://goose-docs.ai/docs/getting-started/installation)\*\* for macOS, Linux, and Windows.

Or install the CLI:

\`\`\`bash  
curl \-fsSL https\://github.com/aaif-goose/goose/releases/download/stable/download\_cli.sh \| bash  
\`\`\`

\# Quick links  
\- \[Quickstart\](https\://goose-docs.ai/docs/quickstart)  
\- \[Installation\](https\://goose-docs.ai/docs/getting-started/installation)  
\- \[Tutorials\](https\://goose-docs.ai/docs/category/tutorials)  
\- \[Documentation\](https\://goose-docs.ai/docs/category/getting-started)  
\- \[Governance\](https\://github.com/aaif-goose/goose/blob/main/GOVERNANCE.md)  
\- \[Custom Distributions\](https\://github.com/aaif-goose/goose/blob/main/CUSTOM\_DISTROS.md) — build your own goose distro with preconfigured providers, extensions, and branding

\#\# Need help?  
\- \[Diagnostics & Reporting\](https\://goose-docs.ai/docs/troubleshooting/diagnostics-and-reporting)  
\- \[Known Issues\](https\://goose-docs.ai/docs/troubleshooting/known-issues)

\# a little goose humor 🪿

\> Why did the developer choose goose as their AI agent?  
\>
\> Because it always helps them "migrate" their code to production\! 🚀

\# goose around with us  
\- \[Discord\](https\://discord.gg/n8R5VaWDAn)  
\- \[YouTube\](https\://www\.youtube.com/@goose-oss)  
\- \[LinkedIn\](https\://www\.linkedin.com/company/goose-oss)  
\- \[Twitter/X\](https\://x.com/goose\_oss)  
“

3\. [https\://github.com/getpaseo/paseo.git](https://github.com/getpaseo/paseo.git)
                                                    About

Orchestrate multiple coding agents from desktop and mobile

               [Readme.md](http://Readme.md) “\<p align="center"\>

  \<img src="packages/website/public/logo.svg" width="64" height="64" alt="Paseo logo"\>

\</p\>

\<h1 align="center"\>Paseo\</h1\>

\<p align="center"\>

  \<a href="README.md"\>English\</a\> ·

  \<a href="README.zh-CN.md"\>简体中文\</a\> ·

  \<a href="README.ja.md"\>日本語\</a\> ·

  \<a href="README.ko.md"\>한국어\</a\>

\</p\>

\<p align="center"\>

  \<a href="https\://github.com/getpaseo/paseo/stargazers"\>

    \<img src="https\://img.shields.io/github/stars/getpaseo/paseo?style=flat\&logo=github" alt="GitHub stars"\>

  \</a\>

  \<a href="https\://github.com/getpaseo/paseo/releases"\>

    \<img src="https\://img.shields.io/github/v/release/getpaseo/paseo?style=flat\&logo=github" alt="GitHub release"\>

  \</a\>

  \<a href="https\://x.com/moboudra"\>

    \<img src="https\://img.shields.io/badge/%40moboudra-555?logo=x" alt="X"\>

  \</a\>

  \<a href="https\://discord.gg/jz8T2uahpH"\>

    \<img src="https\://img.shields.io/badge/Discord-555?logo=discord" alt="Discord"\>

  \</a\>

  \<a href="https\://www\.reddit.com/r/PaseoAI/"\>

    \<img src="https\://img.shields.io/badge/Reddit-555?logo=reddit" alt="Reddit"\>

  \</a\>

\</p\>

\<p align="center"\>One interface for Claude Code, Codex, Copilot, OpenCode, Pi, Antigravity, and Muse Code agents.\</p\>

\<p align="center"\>

  \<img src="https\://paseo.sh/hero-mockup.png" alt="Paseo app screenshot" width="100%"\>

\</p\>

\<p align="center"\>

  \<img src="https\://paseo.sh/mobile-mockup.png" alt="Paseo mobile app" width="100%"\>

\</p\>

Paseo is an open source agentic development environment for desktop, mobile, web, and CLI. Open the desktop app and work: agents, editor, terminals, diffs, pull requests, and a browser in one window. Run many agents at once, each in its own worktree, on one machine or several. The mobile app is the full app, native on iOS and Android.

\- \*\*Parallel agents:\*\* Run many agents at once, each in its own worktree.

\- \*\*Built-in orchestration:\*\* Agents in Paseo can create worktrees, launch other agents, and talk to them, across providers.

\- \*\*Complete development workflow:\*\* Edit files, review diffs, open pull requests, and run terminals, in split panes you arrange how you want.

\- \*\*Self-hosted:\*\* Agents run on your machine with your full dev environment. Use your tools, your configs, and your skills.

\- \*\*Multi-provider:\*\* Claude Code, Codex, Copilot, OpenCode, Pi, Antigravity, and Muse Code through the same interface. Pick the right model for each job.

\- \*\*Voice control:\*\* Dictate tasks or talk through problems in voice mode. Hands-free when you need it.

\- \*\*Cross-device:\*\* iOS, Android, desktop, web, and CLI. Start work at your desk, check in from your phone, script it from the terminal.

\- \*\*Privacy-first:\*\* Paseo doesn't have any telemetry, tracking, or forced log-ins.

\[Run parallel tasks in Paseo\](https\://paseo.sh/docs/parallel-development): start agents in separate worktrees, review their diffs, run each app, and check it in the built-in browser.

\#\# Sponsors

\<\!-- Sponsors: one cell per sponsor in the order of packages/website/src/data/sponsors.ts, then "become a sponsor" cells up to three. \--\>

\<table\>

  \<tr\>

    \<td align="center" width="33%"\>\<a href="https\://hoplite.sh/?utm\_source=paseo\&utm\_medium=readme\&utm\_campaign=sponsor"\>\<picture\>\<source media="(prefers-color-scheme: dark)" srcset="packages/website/public/sponsors/hoplite-on-dark.svg"\>\<img src="packages/website/public/sponsors/hoplite-on-light.svg" alt="Hoplite" height="56"\>\</picture\>\</a\>\<br\>\<sub\>Cloud coding agents\</sub\>\</td\>

    \<td align="center" width="33%"\>\<a href="https\://paseo.sh/sponsor"\>Become a sponsor\</a\>\</td\>

    \<td align="center" width="33%"\>\<a href="https\://paseo.sh/sponsor"\>Become a sponsor\</a\>\</td\>

  \</tr\>

\</table\>

\#\# Plugins

Plugins run on the daemon and show up in every client you connect, with the same UI on desktop, web,

iOS, and Android. Write a plugin once and it is on your phone.

\- \*\*UI:\*\* screens, sidebar items, workspace panels, Command Center items, slash commands, composer pills, attachment sources, timeline items, themes.

\- \*\*Agent lifecycle:\*\* change configuration, environment, and MCP servers, answer permissions, follow up when a turn ends.

\- \*\*Providers:\*\* add a coding agent as a provider.

Install from the registry with \`paseo plugin add owner/slug\`, or from Git or a local directory.

\*\*\[Browse plugins\](https\://paseo.sh/plugins)\*\* · \*\*\[Plugin docs\](https\://paseo.sh/docs/plugins)\*\*

Plugins run with access to your daemon machine and inside connected clients; install only code you trust.

\#\# Getting Started

Paseo runs a local server called the daemon that manages your coding agents. Clients like the desktop app, mobile app, web app, and CLI connect to it.

\#\#\# Prerequisites

You need at least one agent CLI installed and configured with your credentials:

\- \[Claude Code\](https\://docs.anthropic.com/en/docs/claude-code)

\- \[Codex\](https\://github.com/openai/codex)

\- \[GitHub Copilot\](https\://github.com/features/copilot/cli/)

\- \[OpenCode\](https\://github.com/anomalyco/opencode)

\- \[Pi\](https\://pi.dev)

\- \[Antigravity\](https\://paseo.sh/docs/supported-providers\#antigravity)

\- \[Muse Code\](https\://paseo.sh/docs/muse-code)

\#\#\# Desktop app (recommended)

Download it from \[paseo.sh/download\](https\://paseo.sh/download) or the \[GitHub releases page\](https\://github.com/getpaseo/paseo/releases). Open the app and the daemon starts automatically. Nothing else to install.

To connect from your phone, open \*\*Settings → your host → Pair Device\*\*.

\#\#\# Server

For a server, a VM, or any machine without the desktop app. Install the CLI and start the daemon:

\`\`\`bash

npm install \-g @getpaseo/cli

paseo

\`\`\`

Paseo starts, then asks whether to enable the end-to-end encrypted relay for device pairing. If you decline, connect directly over TCP, Tailscale, or another VPN. The desktop, mobile, and web apps connect to this daemon like any other host.

For full setup and configuration, see:

\- \[Docs\](https\://paseo.sh/docs)

\- \[Connectivity guide\](https\://paseo.sh/docs/connectivity)

\- \[Configuration reference\](https\://paseo.sh/docs/configuration)

\#\#\# Docker

Run the Paseo daemon and self-hosted web UI in Docker:

\`\`\`bash

docker run \-d \--name paseo \\

  \-p 6767:6767 \\

  \-e PASEO\_PASSWORD=change-me \\

  \-v "\$PWD/paseo-home:/home/paseo" \\

  \-v "\$PWD:/workspace" \\

  ghcr.io/getpaseo/paseo:latest

\`\`\`

Open \`http\://localhost:6767\` after it starts. Extend the base image with the agent CLIs you use, then provide credentials through environment variables or the persistent \`/home/paseo\` volume. See the \[Docker documentation\](docs/docker.md) for full setup details.

\#\# CLI

Everything you can do in the app, you can do from the terminal.

\`\`\`bash

paseo run \--provider claude/opus-4.6 "implement user authentication"

paseo run \--provider codex/gpt-5.5 \--worktree feature-x "implement feature X"

paseo ls                           \# list running agents

paseo attach abc123                \# stream live output

paseo send abc123 "also add tests" \# follow-up task

\# run on a remote daemon; \--cwd is a path on that host

paseo run \--host workstation.local:6767 \--cwd /workspace "run the full test suite"

\`\`\`

See the \[full CLI reference\](https\://paseo.sh/docs/cli) for more.

\#\# TypeScript SDK

Build issue integrations, dashboards, and orchestration services with \`@getpaseo/client\`:

\`\`\`ts

import { createPaseoClient } from "@getpaseo/client";

const client \= createPaseoClient({ url: "ws://127.0.0.1:6767/ws" });

await client.connect();

const agent \= await client.agents.create({

  config: { provider: "codex/gpt-5.5" },

  cwd: "/Users/me/dev/storefront",

  prompt: "Review the current diff and name the riskiest change.",

});

const result \= await agent.waitForFinish();

console.log(result.lastMessage);

await client.close();

\`\`\`

See the \[SDK quickstart\](https\://paseo.sh/docs/sdk/quickstart), \[recipes\](https\://paseo.sh/docs/sdk/recipes), and \[API reference\](https\://paseo.sh/docs/sdk/reference).

\#\# Skills

Skills teach your agent to use Paseo to orchestrate other agents.

\`\`\`bash

npx skills add getpaseo/paseo

\`\`\`

Then use them in any agent conversation:

\- \`/paseo-handoff\` — hand off work between agents. I use this to plan with Claude and then handoff to Codex to implement.

\- \`/paseo-advisor\` — spin up a single agent as an advisor for a second opinion, without delegating the work itself.

\- \`/paseo-committee\` — form a committee of two contrasting agents to step back, do root cause analysis, and produce a plan.

\#\# Development

Quick monorepo package map:

\- \`packages/server\`: Paseo daemon (agent process orchestration, WebSocket API, MCP server)

\- \`packages/app\`: Expo client (iOS, Android, web)

\- \`packages/cli\`: \`paseo\` CLI for daemon and agent workflows

\- \`packages/desktop\`: Electron desktop app

\- \`packages/relay\`: Relay transport and encryption used by the daemon and clients

\- \`packages/website\`: Marketing site and documentation (\`paseo.sh\`)

Common commands:

\`\`\`bash

\# run all local dev services

npm run dev

\# run individual surfaces

npm run dev:server

npm run dev:app

npm run dev:desktop

npm run dev:website

\# build the server stack

npm run build:server

\# repo-wide checks

npm run typecheck

\`\`\`

\#\# Support Paseo

Paseo is an independent project used by tens of thousands of developers daily, built by one person and funded by the people who use it. Support the work on \[GitHub Sponsors\](https\://github.com/sponsors/boudra). Companies can \[sponsor Paseo\](https\://paseo.sh/sponsor\#spot) monthly and have their logo shown at the top of this README and on the paseo.sh homepage and docs.

\#\# Related projects

\- \[getpaseo/paseo-relay\](https\://github.com/getpaseo/paseo-relay) — official distributed relay, written in Elixir

\- \[paseo-vscode\](https\://marketplace.visualstudio.com/items?itemName=hinnes.paseo-vscode) — VS Code extension

\#\# License

Apache-2.0

“

And its have those built in “[paseo](https://github.com/getpaseo/paseo) Public

* Orchestrate multiple coding agents from desktop and mobile  
* TypeScript [22,586](https://github.com/getpaseo/paseo/stargazers) [2,761](https://github.com/getpaseo/paseo/forks) [803](https://github.com/getpaseo/paseo/issues) [839](https://github.com/getpaseo/paseo/pulls) Updated 1 minute ago  
* [plugins](https://github.com/getpaseo/plugins) Public  
* Paseo plugin registry: reviewed, pinned plugins for paseo.sh/plugins  
* TypeScript [14](https://github.com/getpaseo/plugins/stargazers) MIT [49](https://github.com/getpaseo/plugins/forks) [43](https://github.com/getpaseo/plugins/issues) [16](https://github.com/getpaseo/plugins/pulls) Updated 2 minutes ago  
* [hub](https://github.com/getpaseo/hub) Public  
* Self-hosted automation for Paseo daemons  
* TypeScript [58](https://github.com/getpaseo/hub/stargazers) Apache-2.0 [50](https://github.com/getpaseo/hub/forks) [27](https://github.com/getpaseo/hub/issues) [26](https://github.com/getpaseo/hub/pulls) Updated 2 days ago  
* [claude-code-entrypoint-env](https://github.com/getpaseo/claude-code-entrypoint-env) Public  
* Optional Claude Code entrypoint environment plugin for Paseo  
* TypeScript [0](https://github.com/getpaseo/claude-code-entrypoint-env/stargazers) MIT [0](https://github.com/getpaseo/claude-code-entrypoint-env/forks) [0](https://github.com/getpaseo/claude-code-entrypoint-env/issues) [0](https://github.com/getpaseo/claude-code-entrypoint-env/pulls) Updated 2 days ago  
* [paseo-relay](https://github.com/getpaseo/paseo-relay) Public  
* A distributed, protocol-compatible relay for Paseo  
* Elixir [116](https://github.com/getpaseo/paseo-relay/stargazers) Apache-2.0 [34](https://github.com/getpaseo/paseo-relay/forks) [1](https://github.com/getpaseo/paseo-relay/issues) [0](https://github.com/getpaseo/paseo-relay/pulls) Updated 3 days ago  
* [import](https://github.com/getpaseo/import) Public  
* Import projects and workspaces into Paseo  
* TypeScri

“  Run it anywhere

Use Paseo locally, from another machine, or with a team

### Desktop app

The one click experience, download the app and it just works, no server required

### Mobile

Full client and native, not a WebView  
[Download](https://paseo.sh/download)

### Remote machines

Run Paseo on a home lab, or a cloud machine  
[Docs](https://paseo.sh/docs#server--cli)

### Teams and triggers

Share access or start work from GitHub, Slack, and Discord  
[Paseo Hub](https://paseo.sh/hub)

4\. [https\://github.com/vastsa/PI-Desktop.git](https://github.com/vastsa/PI-Desktop.git)

    About

Local-first AI coding agent desktop: Electron \+ Rust host core \+ pi Agent Harness \+ user-installable plugins

 . Languages

* [TypeScript54.8%](https://github.com/vastsa/PI-Desktop/search?l=typescript)  
* [JavaScript26.8%](https://github.com/vastsa/PI-Desktop/search?l=javascript)  
* [Rust15.1%](https://github.com/vastsa/PI-Desktop/search?l=rust)  
* [CSS2.9%](https://github.com/vastsa/PI-Desktop/search?l=css)  
* [Shell0.1%](https://github.com/vastsa/PI-Desktop/search?l=shell)  
* [HTML0.1%](https://github.com/vastsa/PI-Desktop/search?l=html)  
* [Other0.2%](https://github.com/vastsa/PI-Desktop/search?l=Other)

[Readme.md](http://Readme.md)  
              \<div align="center"\>

\<img src="docs/image/readme/logo.png" alt="PI-Desktop" width="108" /\>

\# PI-Desktop

\#\#\# A modular desktop workspace for AI agents

\*\*Bring projects, agents, models, plugins, and workflows into one persistent desktop environment.\*\*

Local-first · Model-agnostic · Plugin-powered · macOS / Windows / Linux

\<br /\>

\[\!\[Release\](https\://img.shields.io/github/v/release/vastsa/PI-Desktop?label=release)\](https\://github.com/vastsa/PI-Desktop/releases/latest)  
\[\!\[Downloads\](https\://img.shields.io/github/downloads/vastsa/PI-Desktop/total?label=downloads)\](https\://github.com/vastsa/PI-Desktop/releases)  
\[\!\[Stars\](https\://img.shields.io/github/stars/vastsa/PI-Desktop?style=flat\\\&label=stars)\](https\://github.com/vastsa/PI-Desktop/stargazers)  
\[\!\[CI\](https\://github.com/vastsa/PI-Desktop/actions/workflows/ci.yml/badge.svg)\](https\://github.com/vastsa/PI-Desktop/actions/workflows/ci.yml)  
\[\!\[License\](https\://img.shields.io/github/license/vastsa/PI-Desktop)\](LICENSE)  
\[\!\[Reddit\](https\://img.shields.io/badge/Reddit-r%2FAIUO-FF4500?logo=reddit\\\&logoColor=white)\](https\://www\.reddit.com/r/AIUO/)

\<br /\>

\*\*\[Download\](https\://github.com/vastsa/PI-Desktop/releases/latest)\*\* ·  
\[Documentation\](https\://pi-docs.aiuo.net/) ·  
\[Build a Plugin\](docs/plugin-development.md) ·  
\[Screenshots\](docs/guide/screenshots.md) ·  
\[简体中文\](README.zh-CN.md)

\<br /\>

\<img src="docs/image/readme/home.webp" alt="PI-Desktop" width="94%" /\>

\<br /\>

\*\*Your projects stay local · Your models stay replaceable · Your workspace stays yours\*\*

\</div\>

\> \*\*Current release line: 0.21.x (Early Preview).\*\*

\---

\#\# Why PI-Desktop?

Terminal agents are great at execution. IDE agents are great at living inside an editor.

PI-Desktop goes one step further:

\> \*\*Give AI agents a persistent, independent, and extensible desktop workspace of their own.\*\*

\<table\>  
\<tr\>

\<td width="25%" valign="top"\>

\#\#\# Independent Workspace

No dependency on a specific IDE or terminal.

Projects, sessions, reviews, previews, and agents all live in their own workspace.

\</td\>

\<td width="25%" valign="top"\>

\#\#\# Plugin-Powered

Plugins extend more than the agent.

Add panels, views, widgets, tools, MCP servers, themes, and background services.

\</td\>

\<td width="25%" valign="top"\>

\#\#\# Agent Orchestration

One agent is not always enough.

Delegate to Subagents or coordinate full Worker Sessions in parallel.

\</td\>

\<td width="25%" valign="top"\>

\#\#\# Model Freedom

Cloud models, local models, custom gateways, compatible APIs.

Switch models without rebuilding your workflow.

\</td\>

\</tr\>  
\</table\>

\<div align="center"\>

\*\*It is not a wrapper around one model. It is not another IDE extension.\*\*

\#\#\# It is a desktop platform for agent workflows.

\</div\>

\---

\#\# Plugins are part of the workspace, not an afterthought

PI-Desktop keeps the Core focused.

\*\*Your actual workflow is assembled through extensions.\*\*

\<table\>  
\<tr\>

\<td width="33%" valign="top"\>

\#\#\# Agent

Extend what the agent can do

\*\*Agent Tools\*\*  
\*\*Skills\*\*  
\*\*Completion\*\*  
\*\*pi Extensions\*\*

\</td\>

\<td width="33%" valign="top"\>

\#\#\# Workspace

Extend the desktop itself

\*\*Commands\*\*  
\*\*Panels\*\*  
\*\*Work Panel Views\*\*  
\*\*Floating Widgets\*\*  
\*\*Themes\*\*

\</td\>

\<td width="33%" valign="top"\>

\#\#\# Platform

Extend the runtime

\*\*MCP Servers\*\*  
\*\*Resident Services\*\*  
\*\*Plugin Message Bus\*\*

\</td\>

\</tr\>  
\</table\>

A plugin does not have to be “just another tool.”

It can be an entire product:

\`\`\`text  
Voice Agent  
├── Floating Widget  
├── Speech Service  
├── Agent Tool  
└── Commands

GitHub Workspace  
├── Work Panel  
├── MCP Server  
├── Agent Tools  
└── Background Service

Session Analytics  
├── Dashboard  
├── Commands  
└── Workspace View  
\`\`\`

\#\#\# What can a plugin add?

\| Capability          \| What it enables                                                \|  
\| \------------------- \| \-------------------------------------------------------------- \|  
\| \*\*Command\*\*         \| Add actions to the global command system                       \|  
\| \*\*Panel\*\*           \| Open a standalone plugin interface                             \|  
\| \*\*Floating Widget\*\* \| Build voice orbs, status lights, timers, and other floating UI \|  
\| \*\*Work Panel View\*\* \| Add new views to the right-side workspace                      \|  
\| \*\*Agent Tool\*\*      \| Register tools callable by the agent                           \|  
\| \*\*Completion\*\*      \| Use the models already configured by the user                  \|  
\| \*\*Skill\*\*           \| Add reusable agent capabilities and workflows                  \|  
\| \*\*Theme\*\*           \| Customize workspace appearance                                 \|  
\| \*\*MCP Server\*\*      \| Connect local or remote MCP servers                            \|  
\| \*\*Service\*\*         \| Run persistent background work                                 \|  
\| \*\*Message Bus\*\*     \| Let plugins communicate with each other                        \|

Plugins can be distributed as \`.piplug\` packages or installed through the marketplace.

\<div align="center"\>

\#\#\# \[Build your first plugin →\](docs/plugin-development.md)

\</div\>

\---

\#\# One foundation, many workflows

\`\`\`text  
                         PI-Desktop  
                             │  
          ┌──────────────────┼──────────────────┐  
          │                  │                  │  
        Agent            Workspace           Platform  
          │                  │                  │  
     Agent Tools           Panels              MCP  
       Skills             Widgets            Services  
     Subagents             Views            Message Bus  
   pi Extensions          Themes  
          │                  │                  │  
          └──────────────────┼──────────────────┘  
                             │  
                       Your Workflow  
\`\`\`

PI-Desktop can simply be your coding agent.

Or you can turn it into:

\*\*AI Development Workspace · Voice Agent · DevOps Console · GitHub Workspace · Data Assistant · Multi-Agent Control Center · Automation Platform\*\*

\> \*\*The Core provides the foundation. Plugins decide what your workspace becomes.\*\*

\---

\#\# Three ways to work

\<table\>  
\<tr\>

\<td width="33%" valign="top"\>

\#\#\# Agent

\*\*Give it a task. Let it work.\*\*

Read code, edit files, run commands, test, and iterate.

Best for day-to-day development.

\</td\>

\<td width="33%" valign="top"\>

\#\#\# Plan

\*\*Review the approach before execution.\*\*

The agent studies the project first and produces an implementation plan.

Best for refactors and high-risk changes.

\</td\>

\<td width="33%" valign="top"\>

\#\#\# Goal

\*\*Define the outcome. Let the agent choose the path.\*\*

Lock the objective and acceptance criteria, then let the agent drive execution.

Best for complex and long-running tasks.

\</td\>

\</tr\>  
\</table\>

Privileged operations still pass through PI-Desktop's permission layer.

\---

\#\# When one agent is not enough

Complex work should not be forced into one context window.

PI-Desktop provides two levels of delegation.

\#\#\# Subagents

Delegate independent work to background agents:

\*\*Code exploration · Implementation · Test analysis · Research · Review\*\*

Each Subagent gets its own context and reports the result back to the parent agent.

\#\#\# Session Orchestrator

For longer-lived work, delegate to full Worker Sessions.

\`\`\`text  
Main Session  
│  
├── Worker A  
│   └── Frontend  
│  
├── Worker B  
│   └── Backend  
│  
├── Worker C  
│   └── Tests  
│  
└── Worker D  
    └── Review  
\`\`\`

Workers are full PI-Desktop sessions:

\*\*Independent context · Independent execution · Directly inspectable · Reusable · Full transcript\*\*

\<table\>  
\<tr\>

\<td width="50%"\>

\<img src="docs/image/readme/session-orchestrator-overview.png" alt="Session Orchestrator" /\>

\<p align="center"\>\<sub\>Coordinate multiple Worker Sessions from one parent Session\</sub\>\</p\>

\</td\>

\<td width="50%"\>

\<img src="docs/image/readme/session-orchestrator-worker.png" alt="Worker Session" /\>

\<p align="center"\>\<sub\>Each Worker remains a full, inspectable Session\</sub\>\</p\>

\</td\>

\</tr\>  
\</table\>

\<div align="center"\>

\*\*Move from “one agent helps me code” to “multiple agents divide and complete the work.”\*\*

\</div\>

\---

\#\# Built for work that lasts

PI-Desktop is organized around:

\<div align="center"\>

\#\#\# Project → Session → Agent → Work

\</div\>

—not around disposable chat threads.

You can:

\* Manage multiple projects and sessions  
\* Pin, archive, branch, and search sessions  
\* Queue prompts while an agent is already running  
\* Reference project files with \`@\`  
\* Use slash commands  
\* Review diffs  
\* Inspect command output  
\* Work with the right-side Work Panel  
\* Keep streaming checkpoints  
\* Recover interrupted work whenever possible

\*\*A Session can continue across multiple app launches.\*\*

\---

\#\# See what the agent is doing

\<table\>  
\<tr\>

\<td width="50%"\>

\<img src="docs/image/readme/chat\_en.png" alt="PI-Desktop Session" /\>

\<p align="center"\>\<sub\>Persistent Sessions instead of disposable chats\</sub\>\</p\>

\</td\>

\<td width="50%"\>

\<img src="docs/image/readme/model\_en.png" alt="PI-Desktop Model" /\>

\<p align="center"\>\<sub\>Switch models and reasoning levels inside the Session\</sub\>\</p\>

\</td\>

\</tr\>

\<tr\>

\<td width="50%"\>

\<img src="docs/image/readme/plugins\_en.png" alt="PI-Desktop Plugins" /\>

\<p align="center"\>\<sub\>A plugin marketplace that extends both the agent and the desktop\</sub\>\</p\>

\</td\>

\<td width="50%"\>

\<img src="docs/image/readme/addmodel\_en.png" alt="PI-Desktop Providers" /\>

\<p align="center"\>\<sub\>Connect your own provider, gateway, or local model\</sub\>\</p\>

\</td\>

\</tr\>  
\</table\>

\<div align="center"\>

\*\*\[Explore more screenshots →\](docs/guide/screenshots.md)\*\*

\</div\>

\---

\#\# Swap the model, keep the workflow

PI-Desktop does not tie your workflow to a single model vendor.

Use:

\*\*OpenAI · Anthropic · OpenAI-Compatible APIs · Custom Gateways · Ollama · LM Studio · Local Models\*\*

Configure each model independently:

\*\*Provider · Model ID · Context Window · Output Limit · Reasoning / Thinking · Temperature · OAuth · API Key · Endpoint\*\*

Different Sessions can use different models.

The same Session can switch models at any time.

\`\`\`text  
Planning     → Model A  
Coding       → Model B  
Review       → Model C  
Private Task → Local Model  
\`\`\`

\> \*\*The model is a replaceable component of the workflow — not the workflow itself.\*\*

\---

\#\# Already using another coding agent?

Keep your existing work.

PI-Desktop can import local sessions from:

\*\*Claude Code · Codex · OpenCode · Pi\*\*

\---

\#\# Local-first

PI-Desktop does not require you to move your development environment into our cloud.

\| Data                 \| Default behavior                          \|  
\| \-------------------- \| \----------------------------------------- \|  
\| Projects             \| Local                                     \|  
\| Sessions             \| Local                                     \|  
\| Settings             \| Local                                     \|  
\| Logs                 \| Local                                     \|  
\| API credentials      \| OS Keychain                               \|  
\| PI-Desktop telemetry \| None                                      \|  
\| Model requests       \| Sent directly to your configured provider \|

\*\*No mandatory PI-Desktop account.\*\*

\*\*No mandatory PI-Desktop relay.\*\*

When using a remote model, the context required for the request is sent directly to that provider.

\---

\#\# You control the permissions

Agents can read files, edit code, run commands, call tools, use extensions, and delegate work.

Privileged operations still pass through the permission layer:

\`\`\`text  
Agent  
  ↓  
Tool Request  
  ↓  
Permission Layer  
  ↓  
Allow / Ask / Deny  
  ↓  
Execution  
\`\`\`

\*\*You decide how much autonomy each Session gets.\*\*

\---

\#\# Get started

\<table\>  
\<tr\>

\<td width="25%" valign="top"\>

\#\#\# 01

\*\*Download\*\*

Install PI-Desktop

\</td\>

\<td width="25%" valign="top"\>

\#\#\# 02

\*\*Connect a model\*\*

Configure a Provider

\</td\>

\<td width="25%" valign="top"\>

\#\#\# 03

\*\*Open a project\*\*

Choose a local repository

\</td\>

\<td width="25%" valign="top"\>

\#\#\# 04

\*\*Start working\*\*

Agent / Plan / Goal

\</td\>

\</tr\>  
\</table\>

\<div align="center"\>

\#\#\# \[Download PI-Desktop →\](https\://github.com/vastsa/PI-Desktop/releases/latest)

\*\*macOS · Windows · Linux\*\*

\</div\>

\#\#\# Packages

\| Platform \| Architecture  \| Package                                 \|  
\| \-------- \| \------------- \| \--------------------------------------- \|  
\| macOS    \| Apple Silicon \| \`.dmg\` / \`.zip\`                         \|  
\| macOS    \| Intel         \| \`.dmg\` / \`.zip\`                         \|  
\| Windows  \| x64           \| Installer / \`.zip\`                      \|  
\| Linux    \| x64 / ARM64   \| \`.AppImage\` / \`.deb\` / \`.rpm\` / \`.asar\` \|

macOS releases are signed with a Developer ID certificate and notarized by Apple.

\<details\>  
\<summary\>\<strong\>Linux Compatibility\</strong\>\</summary\>

\<br /\>

Linux packages require \*\*glibc 2.35+\*\*.

Common supported distributions include:

\* Ubuntu 22.04+  
\* Debian 12+  
\* Fedora 36+

Check your current version with:

\`\`\`bash  
ldd \--version  
\`\`\`

\</details\>

\---

\#\# Built on Pi

PI-Desktop is built on the \[pi\](https\://github.com/badlogic/pi-mono) ecosystem.

The Agent Runtime uses:

\* \`pi-ai\`  
\* \`pi-agent-core\`  
\* \`pi-coding-agent\`

\> \*\*Pi provides the Agent Engine. PI-Desktop builds the persistent desktop workspace, sessions, permissions, plugins, and agent orchestration around it.\*\*

\---

\#\# For Developers

PI-Desktop can also serve as a host platform for building agent products.

You can build:

\*\*Plugins · MCP Servers · Skills · Agent Tools · pi Extensions · Themes · Panels · Floating Widgets · Background Services\*\*

\#\#\# Plugin quick start

Built-in templates include:

\* \`panel-basic\`  
\* \`agent-tool-basic\`  
\* \`skill-pack\`  
\* \`full-demo\`

Plugins can be created and loaded directly as Development Plugins.

\*\*\[Plugin Development Guide →\](docs/plugin-development.md)\*\*

\#\#\# Run from source

\<details\>  
\<summary\>\<strong\>Development Setup\</strong\>\</summary\>

\<br /\>

\#\#\#\# Requirements

\* Node.js \`\>=22.19\`  
\* pnpm \`\>=10\`  
\* Stable Rust Toolchain

\#\#\#\# Start

\`\`\`bash  
git clone https\://github.com/vastsa/PI-Desktop.git  
cd PI-Desktop

pnpm install

cargo build \-p host-core  
pnpm build:js

pnpm dev  
\`\`\`

\#\#\#\# Validate

\`\`\`bash  
pnpm typecheck  
pnpm lint  
pnpm test  
\`\`\`

\</details\>

\#\#\# Documentation

\[Documentation\](https\://pi-docs.aiuo.net/) ·  
\[Architecture\](docs/spec/02-architecture/01-architecture.md) ·  
\[Specification\](docs/spec/README.md) ·  
\[Plugin Development\](docs/plugin-development.md) ·  
\[E2E Test Plan\](docs/spec/06-delivery/04-e2e-test-plan.md) ·  
\[Release Runbook\](docs/spec/06-delivery/06-release-runbook.md) ·  
\[AGENTS.md\](AGENTS.md)

\---

\#\# Contributing

Contributions are welcome:

\*\*Issues · Pull Requests · Plugins · Skills · MCP Integrations · Documentation · Translations\*\*

For standalone capabilities, consider one question first:

\> \*\*Would this be better as a Plugin?\*\*

Keep the Core focused. Let the ecosystem grow.

\*\*\[Report an Issue\](https\://github.com/vastsa/PI-Desktop/issues/new/choose)\*\* ·  
\[Open Issues\](https\://github.com/vastsa/PI-Desktop/issues) ·  
\[Build a Plugin\](docs/plugin-development.md)

\---

\#\# Project Trend

\<div align="center"\>

\<a href="https\://trendshift.io/repositories/178787?utm\_source=repository-badge\&amp;utm\_medium=badge\&amp;utm\_campaign=badge-repository-178787"\>  
\<img src="https\://trendshift.io/api/badge/repositories/178787" alt="PI-Desktop on Trendshift" width="230" height="51" /\>  
\</a\>

\</div\>

\---

\#\# Friends

\[Linux.Do\](https\://linux.do/) — A new ideal community

\---

\#\# Model Acknowledgements

\> \*\*Not by a lone genius, but by a token-powered construction crew.\*\*

PI-Desktop has been built with the help of models from multiple providers.

More than \*\*27 billion tokens\*\* have been used across development, refactoring, review, design, and debugging.

Thanks to every human contributor — and every model that helped us build it.

\---

\#\# License

PI-Desktop is licensed under the \*\*GNU Lesser General Public License v3.0\*\*.

See \[LICENSE\](LICENSE) for details.

\---

\<div align="center"\>

\<img src="docs/image/readme/logo.png" alt="PI-Desktop" width="72" /\>

\#\# PI-Desktop

\#\#\# Build your own Agent workspace.

\*\*Your models · Your agents · Your plugins · Your workspace\*\*

\<br /\>

\*\*\[Download\](https\://github.com/vastsa/PI-Desktop/releases/latest)\*\* ·  
\[Documentation\](https\://pi-docs.aiuo.net/) ·  
\[Build a Plugin\](docs/plugin-development.md)

\<br /\>\<br /\>

\<sub\>Local-first · Model-agnostic · Plugin-powered\</sub\>

\</div\>

5\. [https\://github.com/l0ng-ai/openidea.git](https://github.com/l0ng-ai/openidea.git)  
           About

The IDE you know, rebuilt in Rust. IntelliJ IDEA–style keymap, tool windows and search-everywhere in a fast native app: editor, code insight, debugger, Git, terminal, database and HTTP clients for 60+ languages.

[TypeScript60.9%](https://github.com/l0ng-ai/openidea/search?l=typescript)

* [Rust35.7%](https://github.com/l0ng-ai/openidea/search?l=rust)  
* [CSS2.7%](https://github.com/l0ng-ai/openidea/search?l=css)  
* [Tree-sitter Query0.5%](https://github.com/l0ng-ai/openidea/search?l=tree-sitter-query)  
* [Python0.2%](https://github.com/l0ng-ai/openidea/search?l=python)  
* [HTML0%](https://github.com/l0ng-ai/openidea/search?l=html)

[Readme.md](http://Readme.md)  
                  \<p align="center"\>  
  \<picture\>  
    \<source media="(prefers-color-scheme: dark)" srcset="src-tauri/icons/source/openidea-wordmark-dark.svg"\>  
    \<img src="src-tauri/icons/source/openidea-wordmark.svg" alt="OpenIDEA" height="56"\>  
  \</picture\>  
\</p\>

\<p align="center"\>  
  The IDE you know, rebuilt in Rust.  
\</p\>

\<p align="center"\>  
  \<a href="https\://github.com/l0ng-ai/openidea/releases/latest"\>\<b\>Download\</b\>\</a\>  
  \&nbsp;·\&nbsp;  
  \<a href="\#benchmark"\>Benchmark\</a\>  
  \&nbsp;·\&nbsp;  
  \<a href="\#build"\>Build\</a\>  
  \&nbsp;·\&nbsp;  
  \<a href="https\://discord.gg/2Zy4yn7gP"\>Discord\</a\>  
\</p\>

https\://github.com/user-attachments/assets/234dd54c-1255-4b3a-b35c-533d78d737c0

OpenIDEA brings the IntelliJ IDEA way of working — its keymap, its tool windows,  
its search-everything habits — to a native app with a Rust core.

Editor, code insight, debugger, Git, terminal, database and HTTP clients,  
for 60+ languages. Builds for macOS, Windows and Linux.

\#\# Benchmark

Opening \[freqtrade\](https\://github.com/freqtrade/freqtrade) (Python, \~770 files)  
with warm caches, median of 5 runs:

\|                             \| OpenIDEA          \| IntelliJ IDEA 2026.2.3 \|  
\| \--------------------------- \| \----------------- \| \---------------------- \|  
\| Window with the project     \| \*\*0.9 s\*\*         \| 3.1 s                  \|  
\| Ready (CPU settled)         \| \*\*1.1 s\*\*         \| 13.2 s                 \|  
\| Memory (USS, all processes) \| \*\*169 MB\*\*        \| 2011 MB                \|  
\| CPU time until ready        \| \*\*2.4 s\*\*         \| 47.9 s                 \|  
\| Idle CPU                    \| \*\*4 %\*\* of a core \| 7 % of a core          \|  
\| Quit                        \| \*\*0.3 s\*\*         \| 5.9 s                  \|

A release build of OpenIDEA from \`main\` and IDEA with default settings and plugins, on  
Windows 11, 32-core AMD, 62 GB RAM.  
IDEA analyses Python more deeply, so "ready" doesn't mean the same work on  
both sides. Both are measured from the outside, the same way: see  
\[\`perf/compare\`\](perf/compare) to run it on your machine and projects.

\#\# Build

\`\`\`sh  
pnpm install  
pnpm tauri dev  
\`\`\`

Rust 1.96, Node 22, pnpm and the \[Tauri prerequisites\](https\://v2.tauri.app/start/prerequisites/).

Native notebook execution tests are opt-in and need two distinct Python environments  
with \`ipykernel\` installed:

\`\`\`sh  
OPENIDEA\_TEST\_PYTHON=/first/env/bin/python \\  
OPENIDEA\_TEST\_PYTHON\_SECOND=/second/env/bin/python \\  
cargo test \-p ide-notebook \--test kernel\_runtime \-- \--ignored \--test-threads=1  
\`\`\`

\#\# License

\[Apache 2.0\](LICENSE). Bundled third-party assets are listed in \[\`THIRD\_PARTY\_LICENSES.md\`\](THIRD\_PARTY\_LICENSES.md).

\<sub\>Not affiliated with JetBrains. IntelliJ IDEA is a trademark of JetBrains s.r.o.\</sub\>
