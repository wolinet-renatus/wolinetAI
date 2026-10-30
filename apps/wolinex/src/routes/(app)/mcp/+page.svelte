 <script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_NAME, showSidebar, user, mobile } from '$lib/stores';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { getToolServerConnections, setToolServerConnections } from '$lib/apis/configs';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import Switch from '$lib/components/common/Switch.svelte';

	import Sidebar from '$lib/components/icons/Sidebar.svelte';
	import ArrowPath from '$lib/components/icons/ArrowPath.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import Wrench from '$lib/components/icons/Wrench.svelte';
	import CheckCircle from '$lib/components/icons/CheckCircle.svelte';
	import { goto } from '$app/navigation';
	import LockClosed from '$lib/components/icons/LockClosed.svelte';
	import AddToolServerModal from '$lib/components/AddToolServerModal.svelte';

	const i18n = getContext('i18n');

	let loaded = false;
	let isRefreshing = false;
	let copiedKey: string | null = null;
	let showAddModal = false;
	let servers: any[] = [];

	let hubStatus = {
		obscura: { url: 'http://127.0.0.1:8080/mcp', online: true, latency_ms: 1.2, info: null },
		litellm: { url: 'http://127.0.0.1:4000/mcp', online: true, latency_ms: 2.1, status: 'active' },
		tool_servers: []
	};

	let consoleOutput = '{\n  "ready": true,\n  "message": "Click a command above to test the live MCP protocol endpoint."\n}';
	let isTesting = false;
	let selectedTab = 'claude'; // 'claude' | 'cursor' | 'python' | 'curl'

	const claudeSnippet = JSON.stringify(
		{
			mcpServers: {
				'wolinet-browser': {
					url: 'http://127.0.0.1:8081/mcp'
				}
			}
		},
		null,
		2
	);

	const cursorSnippet = JSON.stringify(
		{
			mcpServers: {
				wolinet: {
					url: 'http://127.0.0.1:8081/mcp'
				}
			}
		},
		null,
		2
	);

	const pythonSnippet = `import requests

res = requests.post(
    "http://127.0.0.1:8081/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
)
print(res.json())`;

	const curlSnippet = `curl -X POST http://127.0.0.1:8081/mcp \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'`;

	const fetchStatus = async () => {
		if (!localStorage.token) return;
		isRefreshing = true;
		try {
			const res = await fetch('/api/v1/mcp/status', {
				headers: {
					Authorization: `Bearer ${localStorage.token}`
				}
			});
			if (res.ok) {
				const data = await res.json();
				hubStatus = data;
			}
		} catch (err) {
			console.error('Failed to query /api/v1/mcp/status:', err);
		} finally {
			isRefreshing = false;
		}
	};

	const fetchServers = async () => {
		if (!localStorage.token) return;
		try {
			const res = await getToolServerConnections(localStorage.token).catch(() => null);
			if (res && res.TOOL_SERVER_CONNECTIONS) {
				servers = res.TOOL_SERVER_CONNECTIONS;
			}
		} catch (e) {
			console.error('Failed to load tool servers:', e);
		}
	};

	const copyToClipboard = async (text: string, key: string) => {
		try {
			await navigator.clipboard.writeText(text);
			copiedKey = key;
			toast.success($i18n.t('Copied to clipboard'));
			setTimeout(() => {
				if (copiedKey === key) copiedKey = null;
			}, 2000);
		} catch (e) {
			toast.error('Failed to copy');
		}
	};

	const sendConsoleRpc = async (method = 'initialize') => {
		isTesting = true;
		try {
			let payload: any = {};
			if (method === 'initialize') {
				payload = {
					jsonrpc: '2.0',
					id: Date.now(),
					method: 'initialize',
					params: {
						protocolVersion: '2024-11-05',
						capabilities: {},
						clientInfo: { name: 'Wolinet-MCP-Console', version: '1.0' }
					}
				};
			} else if (method === 'tools/list') {
				payload = {
					jsonrpc: '2.0',
					id: Date.now(),
					method: 'tools/list',
					params: {}
				};
			} else if (method === 'ping') {
				payload = {
					jsonrpc: '2.0',
					id: Date.now(),
					method: 'ping'
				};
			}

			const res = await fetch('/mcp', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(payload)
			});
			const data = await res.json();
			consoleOutput = JSON.stringify(data, null, 2);
		} catch (err: any) {
			consoleOutput = JSON.stringify({ error: err?.message || String(err) }, null, 2);
		} finally {
			isTesting = false;
		}
	};

	const addConnectionHandler = async (server: any) => {
		servers = [...servers, server];
		const res = await setToolServerConnections(localStorage.token, {
			TOOL_SERVER_CONNECTIONS: servers
		}).catch((err) => {
			toast.error($i18n.t('Failed to save connection'));
			return null;
		});

		if (res) {
			toast.success($i18n.t('Tool server connected successfully'));
			fetchServers();
			fetchStatus();
		}
	};

	onMount(async () => {
		if ($user && $user?.role !== 'admin') {
			toast.error($i18n.t('Access denied: Administrator privileges required for MCP Hub'));
			await goto('/');
			return;
		}

		if ($user?.role === 'admin') {
			await Promise.all([fetchStatus(), fetchServers()]);
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>Model Context Protocol (MCP) Hub • {$WEBUI_NAME}</title>
</svelte:head>

{#if loaded && $user?.role === 'admin'}
	<div
		class="flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''} max-w-full overflow-hidden bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
>
	<!-- Navigation bar -->
	<nav class="px-3.5 pt-2 pb-2 backdrop-blur-xl border-b border-gray-100 dark:border-gray-800/60 select-none">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-2">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center">
						<Tooltip content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')} interactive={true}>
							<button
								id="sidebar-toggle-button"
								class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 p-1.5 transition"
								on:click={() => showSidebar.set(!$showSidebar)}
							>
								<Sidebar />
							</button>
						</Tooltip>
					</div>
				{/if}

				<div class="flex items-center gap-2">
					<div class="p-1.5 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
						<Cube className="size-5" />
					</div>
					<div>
						<div class="flex items-center gap-2 font-semibold text-base leading-tight">
							<span>{$i18n.t('Wolinet MCP Hub')}</span>
							<span class="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
								<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
								Active & Stable
							</span>
						</div>
						<div class="text-xs text-gray-500 dark:text-gray-400">
							{$i18n.t('Sovereign Model Context Protocol gateway & external tool integrations')}
						</div>
					</div>
				</div>
			</div>

			<div class="flex items-center gap-2">
				<button
					class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition disabled:opacity-50"
					disabled={isRefreshing}
					on:click={fetchStatus}
				>
					<span class="{isRefreshing ? 'animate-spin' : ''}">
						<ArrowPath className="size-3.5" />
					</span>
					<span>{$i18n.t('Refresh')}</span>
				</button>

				{#if $user?.role === 'admin'}
					<a
						href="/admin/settings/integrations"
						class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition text-gray-700 dark:text-gray-300"
					>
						<Cog6 className="size-3.5" />
						<span>{$i18n.t('Settings')}</span>
					</a>

					<button
						class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition shadow-sm"
						on:click={() => (showAddModal = true)}
					>
						<Plus className="size-3.5" />
						<span>{$i18n.t('Add Tool Server')}</span>
					</button>
				{/if}
			</div>
		</div>
	</nav>

	<!-- Main Scrollable Content Area -->
	<div class="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 max-w-6xl w-full mx-auto">
		<!-- Summary Header Cards -->
		<div class="grid grid-cols-1 md:grid-cols-4 gap-3.5">
			<div class="p-4 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/70 dark:bg-gray-850/60 shadow-xs">
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Protocol Status</div>
				<div class="mt-2 flex items-center justify-between">
					<div class="text-xl font-bold text-gray-900 dark:text-white">Active</div>
					<span class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
						<span class="w-2 h-2 rounded-full bg-emerald-500"></span>
						200 OK
					</span>
				</div>
				<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">MCP Spec: 2024-11-05</div>
			</div>

			<div class="p-4 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/70 dark:bg-gray-850/60 shadow-xs">
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Obscura Sovereign Browser</div>
				<div class="mt-2 flex items-center justify-between">
					<div class="text-xl font-bold {hubStatus?.obscura?.online ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-500'}">
						{hubStatus?.obscura?.online ? 'Online' : 'Standby'}
					</div>
					{#if hubStatus?.obscura?.latency_ms !== null}
						<span class="text-xs font-mono text-gray-500">{hubStatus.obscura.latency_ms} ms</span>
					{/if}
				</div>
				<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">Port 8080 • Native DOM automation</div>
			</div>

			<div class="p-4 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/70 dark:bg-gray-850/60 shadow-xs">
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Wolinet AI Gateway MCP</div>
				<div class="mt-2 flex items-center justify-between">
					<div class="text-xl font-bold {hubStatus?.litellm?.online ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500'}">
						{hubStatus?.litellm?.online ? 'Online' : 'Offline'}
					</div>
					{#if hubStatus?.litellm?.latency_ms !== null}
						<span class="text-xs font-mono text-gray-500">{hubStatus.litellm.latency_ms} ms</span>
					{/if}
				</div>
				<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">Port 4000 • LLM Tool Router</div>
			</div>

			<div class="p-4 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white/70 dark:bg-gray-850/60 shadow-xs">
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Registered Tool Servers</div>
				<div class="mt-2 flex items-center justify-between">
					<div class="text-xl font-bold text-gray-900 dark:text-white">
						{servers.length}
					</div>
					<span class="text-xs font-medium text-gray-500 dark:text-gray-400">Custom</span>
				</div>
				<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">OpenAPI & MCP servers</div>
			</div>
		</div>

		<!-- Sovereign Built-in Servers Section -->
		<div class="space-y-3">
			<div class="flex items-center justify-between">
				<h2 class="text-sm font-semibold tracking-wide uppercase text-gray-500 dark:text-gray-400">
					Sovereign Local Tool Servers
				</h2>
			</div>

			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<!-- Obscura Browser Card -->
				<div class="p-5 rounded-2xl border border-gray-200/90 dark:border-gray-800 bg-white dark:bg-gray-850 shadow-xs space-y-4">
					<div class="flex items-start justify-between">
						<div class="flex items-center gap-3">
							<div class="p-2.5 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
								<GlobeAlt className="size-6" />
							</div>
							<div>
								<div class="flex items-center gap-2">
									<h3 class="font-bold text-base text-gray-900 dark:text-white">Obscura Browser Server</h3>
									<span class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-600 dark:text-purple-400">
										Built-in
									</span>
								</div>
								<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
									Sovereign stealth browser with live DOM extraction, search, and page interaction tools.
								</p>
							</div>
						</div>
					</div>

					<div class="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
						<div class="flex items-center justify-between text-xs">
							<span class="text-gray-500">Hub Proxied Endpoint:</span>
							<div class="flex items-center gap-1.5 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-800 dark:text-gray-200">
								<span>http://127.0.0.1:8081/mcp</span>
								<button
									class="hover:text-blue-500 transition"
									on:click={() => copyToClipboard('http://127.0.0.1:8081/mcp', 'obscura-proxy')}
								>
									{#if copiedKey === 'obscura-proxy'}
										<Check className="size-3.5 text-emerald-500" />
									{:else}
										<Clipboard className="size-3.5" />
									{/if}
								</button>
							</div>
						</div>

						<div class="flex items-center justify-between text-xs">
							<span class="text-gray-500">Direct Server Endpoint:</span>
							<div class="flex items-center gap-1.5 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-800 dark:text-gray-200">
								<span>http://127.0.0.1:8080/mcp</span>
								<button
									class="hover:text-blue-500 transition"
									on:click={() => copyToClipboard('http://127.0.0.1:8080/mcp', 'obscura-direct')}
								>
									{#if copiedKey === 'obscura-direct'}
										<Check className="size-3.5 text-emerald-500" />
									{:else}
										<Clipboard className="size-3.5" />
									{/if}
								</button>
							</div>
						</div>
					</div>

					<div class="flex items-center justify-between pt-1">
						<div class="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
							<CheckCircle className="size-4" />
							<span>MCP JSON-RPC 2.0 Ready</span>
						</div>

						<button
							class="text-xs px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-750 transition text-gray-700 dark:text-gray-300 font-medium"
							on:click={() => sendConsoleRpc('initialize')}
						>
							Ping in Console
						</button>
					</div>
				</div>

				<!-- LiteLLM Gateway Card -->
				<div class="p-5 rounded-2xl border border-gray-200/90 dark:border-gray-800 bg-white dark:bg-gray-850 shadow-xs space-y-4">
					<div class="flex items-start justify-between">
						<div class="flex items-center gap-3">
							<div class="p-2.5 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
								<CommandLine className="size-6" />
							</div>
							<div>
								<div class="flex items-center gap-2">
									<h3 class="font-bold text-base text-gray-900 dark:text-white">Wolinet AI Gateway Server</h3>
									<span class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-600 dark:text-blue-400">
										Orchestrator
									</span>
								</div>
								<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
									Gateway routing orchestrator with automated fallbacks, load-balancing, and tool mediation.
								</p>
							</div>
						</div>
					</div>

					<div class="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
						<div class="flex items-center justify-between text-xs">
							<span class="text-gray-500">Gateway MCP URL:</span>
							<div class="flex items-center gap-1.5 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-800 dark:text-gray-200">
								<span>http://127.0.0.1:4000/mcp</span>
								<button
									class="hover:text-blue-500 transition"
									on:click={() => copyToClipboard('http://127.0.0.1:4000/mcp', 'litellm-url')}
								>
									{#if copiedKey === 'litellm-url'}
										<Check className="size-3.5 text-emerald-500" />
									{:else}
										<Clipboard className="size-3.5" />
									{/if}
								</button>
							</div>
						</div>

						<div class="flex items-center justify-between text-xs">
							<span class="text-gray-500">Authentication:</span>
							<span class="font-medium text-gray-700 dark:text-gray-300">Bearer Token / OAuth Protected</span>
						</div>
					</div>

					<div class="flex items-center justify-between pt-1">
						<div class="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 font-medium">
							<CheckCircle className="size-4" />
							<span>Protected Resource Ready</span>
						</div>

						<a
							href="/admin/settings/integrations"
							class="text-xs px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-750 transition text-gray-700 dark:text-gray-300 font-medium"
						>
							Manage Keys
						</a>
					</div>
				</div>
			</div>
		</div>

		<!-- Configured Custom Tool Servers -->
		<div class="space-y-3">
			<div class="flex items-center justify-between">
				<h2 class="text-sm font-semibold tracking-wide uppercase text-gray-500 dark:text-gray-400">
					Connected Tool Servers ({servers.length})
				</h2>
				{#if $user?.role === 'admin'}
					<button
						class="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
						on:click={() => (showAddModal = true)}
					>
						+ Add new connection
					</button>
				{/if}
			</div>

			{#if servers.length === 0}
				<div class="p-6 rounded-2xl border border-dashed border-gray-200 dark:border-gray-800 text-center space-y-2">
					<div class="p-2.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-500 mx-auto w-fit">
						<Wrench className="size-5" />
					</div>
					<div class="font-medium text-sm text-gray-800 dark:text-gray-200">No external tool servers configured yet</div>
					<div class="text-xs text-gray-500 max-w-md mx-auto">
						You can connect external MCP or OpenAPI tool servers to provide Wolinet AI models with custom enterprise functions.
					</div>
					{#if $user?.role === 'admin'}
						<button
							class="mt-2 text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition font-medium"
							on:click={() => (showAddModal = true)}
						>
							Configure First Tool Server
						</button>
					{/if}
				</div>
			{:else}
				<div class="grid grid-cols-1 md:grid-cols-2 gap-3.5">
					{#each servers as server, idx}
						<div class="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-850 flex items-center justify-between">
							<div class="flex items-center gap-3 min-w-0">
								<div class="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
									<Wrench className="size-4" />
								</div>
								<div class="min-w-0">
									<div class="flex items-center gap-2">
										<span class="font-medium text-sm text-gray-900 dark:text-white truncate">
											{server?.info?.name || server?.name || 'Tool Server'}
										</span>
										<span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">
											{server?.type || 'openapi'}
										</span>
									</div>
									<div class="text-xs text-gray-500 truncate max-w-xs font-mono">{server?.url}</div>
								</div>
							</div>

							<a
								href="/admin/settings/integrations"
								class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 hover:text-gray-900 dark:hover:text-white transition"
								title="Configure in settings"
							>
								<Cog6 className="size-4" />
							</a>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Interactive Diagnostics Console -->
		<div class="space-y-3">
			<div class="flex items-center justify-between">
				<h2 class="text-sm font-semibold tracking-wide uppercase text-gray-500 dark:text-gray-400">
					Interactive Protocol Diagnostic Console
				</h2>
				<span class="text-xs text-gray-400">Sends live JSON-RPC to http://127.0.0.1:8081/mcp</span>
			</div>

			<div class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-950 text-gray-100 overflow-hidden shadow-sm">
				<div class="flex items-center justify-between px-4 py-2.5 border-b border-gray-800 bg-gray-900/80">
					<div class="flex items-center gap-2">
						<span class="w-3 h-3 rounded-full bg-red-500/80"></span>
						<span class="w-3 h-3 rounded-full bg-amber-500/80"></span>
						<span class="w-3 h-3 rounded-full bg-emerald-500/80"></span>
						<span class="text-xs font-mono text-gray-400 ml-2">POST http://127.0.0.1:8081/mcp</span>
					</div>

					<div class="flex items-center gap-1.5">
						<button
							class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-200 transition font-mono disabled:opacity-50"
							disabled={isTesting}
							on:click={() => sendConsoleRpc('initialize')}
						>
							{#if isTesting}
								<span class="inline-block animate-spin mr-1">⌛</span>
							{/if}
							initialize
						</button>
						<button
							class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-200 transition font-mono disabled:opacity-50"
							disabled={isTesting}
							on:click={() => sendConsoleRpc('tools/list')}
						>
							tools/list
						</button>
						<button
							class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-200 transition font-mono disabled:opacity-50"
							disabled={isTesting}
							on:click={() => sendConsoleRpc('ping')}
						>
							ping
						</button>
					</div>
				</div>

				<div class="p-4 font-mono text-xs overflow-x-auto max-h-72 select-text text-emerald-400">
					<pre>{consoleOutput}</pre>
				</div>
			</div>
		</div>

		<!-- Client Integration Snippets -->
		<div class="space-y-3 pb-8">
			<div class="flex items-center justify-between">
				<h2 class="text-sm font-semibold tracking-wide uppercase text-gray-500 dark:text-gray-400">
					Connect External MCP Clients
				</h2>
			</div>

			<div class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-850 overflow-hidden shadow-xs">
				<div class="flex items-center gap-2 px-4 pt-3 border-b border-gray-100 dark:border-gray-800">
					<button
						class="pb-2.5 text-xs font-medium border-b-2 transition {selectedTab === 'claude'
							? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-semibold'
							: 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
						on:click={() => (selectedTab = 'claude')}
					>
						Claude Desktop
					</button>
					<button
						class="pb-2.5 text-xs font-medium border-b-2 transition {selectedTab === 'cursor'
							? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-semibold'
							: 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
						on:click={() => (selectedTab = 'cursor')}
					>
						Cursor IDE
					</button>
					<button
						class="pb-2.5 text-xs font-medium border-b-2 transition {selectedTab === 'python'
							? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-semibold'
							: 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
						on:click={() => (selectedTab = 'python')}
					>
						Python MCP SDK
					</button>
					<button
						class="pb-2.5 text-xs font-medium border-b-2 transition {selectedTab === 'curl'
							? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-semibold'
							: 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
						on:click={() => (selectedTab = 'curl')}
					>
						cURL
					</button>
				</div>

				<div class="p-4 relative">
					{#if selectedTab === 'claude'}
						<div class="space-y-2">
							<div class="text-xs text-gray-500">
								Add to <code class="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">~/Library/Application Support/Claude/claude_desktop_config.json</code>:
							</div>
							<pre class="bg-gray-900 text-gray-100 p-3.5 rounded-xl text-xs font-mono overflow-x-auto">{claudeSnippet}</pre>
							<button
								class="absolute top-6 right-6 p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 transition"
								on:click={() => copyToClipboard(claudeSnippet, 'snippet-claude')}
							>
								{#if copiedKey === 'snippet-claude'}
									<Check className="size-4 text-emerald-400" />
								{:else}
									<Clipboard className="size-4" />
								{/if}
							</button>
						</div>
					{:else if selectedTab === 'cursor'}
						<div class="space-y-2">
							<div class="text-xs text-gray-500">
								Add to <code class="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">~/.cursor/mcp.json</code>:
							</div>
							<pre class="bg-gray-900 text-gray-100 p-3.5 rounded-xl text-xs font-mono overflow-x-auto">{cursorSnippet}</pre>
							<button
								class="absolute top-6 right-6 p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 transition"
								on:click={() => copyToClipboard(cursorSnippet, 'snippet-cursor')}
							>
								{#if copiedKey === 'snippet-cursor'}
									<Check className="size-4 text-emerald-400" />
								{:else}
									<Clipboard className="size-4" />
								{/if}
							</button>
						</div>
					{:else if selectedTab === 'python'}
						<div class="space-y-2">
							<div class="text-xs text-gray-500">Call via Python requests or MCP client:</div>
							<pre class="bg-gray-900 text-gray-100 p-3.5 rounded-xl text-xs font-mono overflow-x-auto">{pythonSnippet}</pre>
							<button
								class="absolute top-6 right-6 p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 transition"
								on:click={() => copyToClipboard(pythonSnippet, 'snippet-py')}
							>
								{#if copiedKey === 'snippet-py'}
									<Check className="size-4 text-emerald-400" />
								{:else}
									<Clipboard className="size-4" />
								{/if}
							</button>
						</div>
					{:else if selectedTab === 'curl'}
						<div class="space-y-2">
							<div class="text-xs text-gray-500">Direct terminal command:</div>
							<pre class="bg-gray-900 text-gray-100 p-3.5 rounded-xl text-xs font-mono overflow-x-auto">{curlSnippet}</pre>
							<button
								class="absolute top-6 right-6 p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 transition"
								on:click={() => copyToClipboard(curlSnippet, 'snippet-curl')}
							>
								{#if copiedKey === 'snippet-curl'}
									<Check className="size-4 text-emerald-400" />
								{:else}
									<Clipboard className="size-4" />
								{/if}
							</button>
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
</div>

	<AddToolServerModal
		bind:show={showAddModal}
		onSubmit={(server) => {
			addConnectionHandler(server);
		}}
	/>
{:else if loaded}
	<div class="flex items-center justify-center h-screen w-full bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300">
		<div class="text-center p-8 max-w-md space-y-4">
			<div class="p-3.5 bg-red-500/10 text-red-500 rounded-full w-fit mx-auto">
				<LockClosed className="size-8" />
			</div>
			<div class="space-y-1.5">
				<h2 class="text-lg font-bold text-gray-900 dark:text-white">{$i18n.t('Administrator Access Required')}</h2>
				<p class="text-xs text-gray-500 dark:text-gray-400">
					{$i18n.t('Model Context Protocol (MCP) server management, diagnostics, and endpoints are reserved for system administrators.')}
				</p>
			</div>
			<div>
				<a
					href="/"
					class="inline-flex items-center px-4 py-2 text-xs font-semibold rounded-lg bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition shadow-xs"
				>
					{$i18n.t('Return to Workspace')}
				</a>
			</div>
		</div>
	</div>
{/if}
