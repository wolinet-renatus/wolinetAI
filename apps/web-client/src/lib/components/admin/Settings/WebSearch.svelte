<script lang="ts">
	import { getRAGConfig, updateRAGConfig } from '$lib/apis/retrieval';
	import Switch from '$lib/components/common/Switch.svelte';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	let webConfig = null;

	const submitHandler = async () => {
		if (!webConfig) return;

		// Force sovereign Obscura engine natively
		webConfig.WEB_SEARCH_ENGINE = 'obscura';
		webConfig.WEB_LOADER_ENGINE = 'obscura';

		// Convert domain filter string to array before sending
		if (
			typeof webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST === 'string' &&
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST
		) {
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST.split(',')
				.map((domain) => domain.trim())
				.filter((domain) => domain.length > 0);
		} else if (!Array.isArray(webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST)) {
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = [];
		}

		try {
			await updateRAGConfig(localStorage.token, {
				web: webConfig
			});
			toast.success($i18n.t('Wolinet Obscura settings saved successfully'));
		} catch (error) {
			toast.error($i18n.t('Failed to save settings: ') + error);
		}

		// Convert array back to string for UI
		if (Array.isArray(webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST)) {
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST.join(', ');
		}
	};

	onMount(async () => {
		const res = await getRAGConfig(localStorage.token);
		if (res && res.web) {
			webConfig = res.web;
			webConfig.WEB_SEARCH_ENGINE = 'obscura';
			webConfig.WEB_LOADER_ENGINE = 'obscura';

			if (Array.isArray(webConfig?.WEB_SEARCH_DOMAIN_FILTER_LIST)) {
				webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST.join(', ');
			} else if (!webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST) {
				webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = '';
			}
		}
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-4 text-sm"
	on:submit|preventDefault={async () => {
		await submitHandler();
		saveHandler();
	}}
>
	<div class="space-y-4 overflow-y-scroll scrollbar-hidden h-full pr-1">
		{#if webConfig}
			<!-- Sovereign Obscura Hero Status Card -->
			<div class="p-4 rounded-2xl bg-gray-50/80 dark:bg-gray-850/60 border border-gray-100 dark:border-gray-800/80 space-y-3">
				<div class="flex items-center justify-between">
					<div class="flex items-center space-x-2.5">
						<div class="w-8 h-8 rounded-xl bg-black dark:bg-white flex items-center justify-center text-white dark:text-black font-semibold text-xs tracking-wider shadow-sm">
							WO
						</div>
						<div>
							<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
								{$i18n.t('Wolinet Obscura Sovereign Browser')}
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400">
								{$i18n.t('Native Autonomous Web Fetcher & Search Engine')}
							</div>
						</div>
					</div>
					<div class="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-medium border border-emerald-500/20">
						<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
						<span>{$i18n.t('Native & Active')}</span>
					</div>
				</div>

				<p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
					{$i18n.t('Wolinet Obscura operates autonomously inside your sovereign cluster with in-memory TTL acceleration, dual-tier fast extraction, and zero external telemetry. No user or browser engine configuration required.')}
				</p>
			</div>

			<!-- Core Configuration Controls -->
			<div class="space-y-3">
				<div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider px-1">
					{$i18n.t('Browsing & Grounding Controls')}
				</div>

				<!-- Toggle: Enable Web Search -->
				<div class="p-3.5 rounded-xl bg-gray-50/50 dark:bg-gray-850/40 border border-gray-100 dark:border-gray-800/60 flex items-center justify-between">
					<div>
						<div class="text-xs font-semibold text-gray-900 dark:text-gray-200">
							{$i18n.t('Live Web Grounding')}
						</div>
						<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
							{$i18n.t('Allow models to autonomously query the web and extract live articles in real time')}
						</div>
					</div>
					<Switch bind:state={webConfig.ENABLE_WEB_SEARCH} />
				</div>

				<!-- Toggle: Direct Grounding (Fast Stream Mode) -->
				<div class="p-3.5 rounded-xl bg-gray-50/50 dark:bg-gray-850/40 border border-gray-100 dark:border-gray-800/60 flex items-center justify-between">
					<div>
						<div class="text-xs font-semibold text-gray-900 dark:text-gray-200">
							{$i18n.t('Direct High-Speed Grounding')}
						</div>
						<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
							{$i18n.t('Stream extracted web text directly into model context without embedding latency')}
						</div>
					</div>
					<Switch bind:state={webConfig.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL} />
				</div>

				<!-- Grid: Result Count & Concurrent Requests -->
				<div class="grid grid-cols-2 gap-3">
					<div class="p-3.5 rounded-xl bg-gray-50/50 dark:bg-gray-850/40 border border-gray-100 dark:border-gray-800/60 space-y-1.5">
						<div class="text-xs font-semibold text-gray-900 dark:text-gray-200">
							{$i18n.t('Search Result Count')}
						</div>
						<div class="text-[11px] text-gray-500 dark:text-gray-400">
							{$i18n.t('Top ranked pages to extract')}
						</div>
						<input
							class="w-full rounded-lg py-1.5 px-3 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700/80 outline-hidden font-medium"
							type="number"
							min="1"
							max="10"
							bind:value={webConfig.WEB_SEARCH_RESULT_COUNT}
						/>
					</div>

					<div class="p-3.5 rounded-xl bg-gray-50/50 dark:bg-gray-850/40 border border-gray-100 dark:border-gray-800/60 space-y-1.5">
						<div class="text-xs font-semibold text-gray-900 dark:text-gray-200">
							{$i18n.t('Parallel Connections')}
						</div>
						<div class="text-[11px] text-gray-500 dark:text-gray-400">
							{$i18n.t('Concurrent stream workers')}
						</div>
						<input
							class="w-full rounded-lg py-1.5 px-3 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700/80 outline-hidden font-medium"
							type="number"
							min="1"
							max="10"
							bind:value={webConfig.WEB_LOADER_CONCURRENT_REQUESTS}
						/>
					</div>
				</div>

				<!-- Domain Filter List -->
				<div class="p-3.5 rounded-xl bg-gray-50/50 dark:bg-gray-850/40 border border-gray-100 dark:border-gray-800/60 space-y-2">
					<div class="text-xs font-semibold text-gray-900 dark:text-gray-200">
						{$i18n.t('Domain Filter List (Optional)')}
					</div>
					<div class="text-[11px] text-gray-500 dark:text-gray-400">
						{$i18n.t('Specify allowed or blocked domains separated by commas (e.g. "wikipedia.org, !example.com")')}
					</div>
					<input
						class="w-full rounded-lg py-2 px-3 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700/80 outline-hidden"
						type="text"
						placeholder="e.g. bloomberg.com, reuters.com, arxiv.org"
						bind:value={webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST}
						autocomplete="off"
					/>
				</div>

				<!-- SSL Verification -->
				<div class="p-3.5 rounded-xl bg-gray-50/50 dark:bg-gray-850/40 border border-gray-100 dark:border-gray-800/60 flex items-center justify-between">
					<div>
						<div class="text-xs font-semibold text-gray-900 dark:text-gray-200">
							{$i18n.t('SSL Certificate Verification')}
						</div>
						<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
							{$i18n.t('Validate TLS/SSL certificates when fetching external URLs')}
						</div>
					</div>
					<Switch bind:state={webConfig.ENABLE_WEB_LOADER_SSL_VERIFICATION} />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium border-t border-gray-100 dark:border-gray-800/60">
		<button
			class="px-5 py-2 text-xs font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full shadow-sm"
			type="submit"
		>
			{$i18n.t('Save Settings')}
		</button>
	</div>
</form>
