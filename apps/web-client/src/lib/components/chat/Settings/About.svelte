<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');
	const version = '1.0.0';
</script>

<div id="tab-about" class="flex flex-col h-full justify-between text-sm pr-1">
	<div class="overflow-y-auto max-h-[30rem] md:max-h-[calc(100vh-14rem)] space-y-4 pr-1">
		<!-- Header Banner -->
		<div
			class="relative overflow-hidden rounded-2xl bg-linear-to-br from-gray-950 via-gray-900 to-black text-white p-5 border border-gray-800 shadow-md"
		>
			<div class="relative z-10 flex flex-col sm:flex-row items-center sm:items-start gap-4 text-center sm:text-left">
				<div
					class="size-16 rounded-2xl bg-white/10 backdrop-blur-md border border-white/15 flex items-center justify-center p-2.5 shadow-inner shrink-0"
				>
					<img
						src="/static/logo.png"
						alt="Wolinet AI"
						class="w-full h-full object-contain filter drop-shadow"
						on:error={(e) => {
							const target = e.currentTarget as HTMLImageElement;
							if (target) {
								target.src = '/favicon.png';
							}
						}}
					/>
				</div>

				<div class="space-y-1">
					<div class="flex flex-wrap items-center justify-center sm:justify-start gap-2">
						<h1 class="text-xl font-bold tracking-tight text-white">Wolinet AI</h1>
						<span
							class="px-2.5 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full"
						>
							v{version} Sovereign Edition
						</span>
					</div>
					<p class="text-xs text-gray-300 font-normal">
						{$i18n.t('Sovereign LLM & High-Performance Inference Platform')}
					</p>
					<div class="pt-1 flex items-center justify-center sm:justify-start gap-1.5 text-xs text-emerald-400">
						<span class="size-2 rounded-full bg-emerald-400 inline-block shadow-xs"></span>
						<span class="font-medium">{$i18n.t('Created and engineered by')} <strong class="text-white">Wolinet Technology</strong></span>
					</div>
				</div>
			</div>

			<!-- Subtle ambient glow -->
			<div
				class="absolute -right-10 -bottom-10 size-44 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"
			></div>
		</div>

		<!-- Platform Mission & Overview -->
		<div
			class="p-4 rounded-xl bg-gray-50/80 dark:bg-gray-850/50 border border-gray-200/80 dark:border-gray-800 space-y-2 leading-relaxed text-xs text-gray-700 dark:text-gray-300"
		>
			<div class="font-semibold text-gray-900 dark:text-gray-100 text-sm">
				{$i18n.t('What Wolinet AI Delivers')}
			</div>
			<p>
				Wolinet AI gives organizations complete ownership of their artificial intelligence operations. Instead of sending sensitive internal queries and proprietary code to third-party endpoints, all model interactions, embeddings, and context retrievals route through your private, sovereign infrastructure.
			</p>
			<p>
				Whether writing software, querying proprietary datasets, or building multi-agent systems, Wolinet AI provides real-time spend attribution, isolated model routing, and deterministic inference.
			</p>
		</div>

		<!-- What Users Can Achieve -->
		<div
			class="p-4 rounded-xl bg-gray-50/80 dark:bg-gray-850/50 border border-gray-200/80 dark:border-gray-800 space-y-3"
		>
			<div class="font-semibold text-gray-900 dark:text-gray-100 text-xs uppercase tracking-wider">
				{$i18n.t('What You Can Achieve')}
			</div>

			<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
				<div class="p-3 rounded-lg bg-white dark:bg-gray-900/90 border border-gray-200/70 dark:border-gray-750 space-y-1">
					<div class="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
						<span class="size-1.5 rounded-full bg-emerald-500"></span>
						{$i18n.t('Full Model Sovereignty')}
					</div>
					<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-normal">
						Run top-tier coding, reasoning, and vision models without vendor telemetry, arbitrary rate limits, or training on your proprietary data.
					</p>
				</div>

				<div class="p-3 rounded-lg bg-white dark:bg-gray-900/90 border border-gray-200/70 dark:border-gray-750 space-y-1">
					<div class="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
						<span class="size-1.5 rounded-full bg-blue-500"></span>
						{$i18n.t('Real-Time Spend Metering')}
					</div>
					<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-normal">
						Track token usage and budgets down to fractions of a cent per user. Every workspace member gets allocated credits with strict limits.
					</p>
				</div>

				<div class="p-3 rounded-lg bg-white dark:bg-gray-900/90 border border-gray-200/70 dark:border-gray-750 space-y-1">
					<div class="font-semibold text-gray-900 dark:text-gray-100 flex items-center justify-between">
						<div class="flex items-center gap-1.5">
							<span class="size-1.5 rounded-full bg-purple-500"></span>
							<span>{$i18n.t('Universal Wolinet API')}</span>
						</div>
						<a
							href="/docs"
							target="_blank"
							class="text-[10px] text-purple-600 dark:text-purple-400 font-medium hover:underline inline-flex items-center gap-0.5 cursor-pointer"
						>
							<span>Docs ↗</span>
						</a>
					</div>
					<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-normal">
						Connect IDEs, command-line scripts, and backend services directly to the Wolinet API endpoint (<code class="font-mono text-gray-700 dark:text-gray-300">/v1</code>) on any server or domain deployment.
					</p>
				</div>

				<div class="p-3 rounded-lg bg-white dark:bg-gray-900/90 border border-gray-200/70 dark:border-gray-750 space-y-1">
					<div class="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
						<span class="size-1.5 rounded-full bg-amber-500"></span>
						{$i18n.t('Private Knowledge & RAG')}
					</div>
					<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-normal">
						Ingest source code and documents with the embedding provider configured for this workspace.
					</p>
				</div>
			</div>
		</div>

		<!-- Sovereign Core Architecture -->
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
			<div
				class="p-3.5 rounded-xl bg-gray-50/80 dark:bg-gray-850/50 border border-gray-200/80 dark:border-gray-800 space-y-1.5"
			>
				<div class="text-xs font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
					<div class="p-1 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">
						<svg class="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
						</svg>
					</div>
					{$i18n.t('Sovereign Gateway')}
				</div>
				<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed">
					Sovereign proxy layer managing distributed model execution with real-time per-user token metering and budget attribution.
				</p>
			</div>

			<div
				class="p-3.5 rounded-xl bg-gray-50/80 dark:bg-gray-850/50 border border-gray-200/80 dark:border-gray-800 space-y-1.5"
			>
				<div class="text-xs font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
					<div class="p-1 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
						<svg class="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
						</svg>
					</div>
					{$i18n.t('Privacy & Data Sovereignty')}
				</div>
				<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed">
					Zero external tracking, air-gapped readiness, and strict enterprise data isolation.
				</p>
			</div>
		</div>

		<!-- Sovereign Model Suite -->
		<div
			class="p-4 rounded-xl bg-gray-50/80 dark:bg-gray-850/50 border border-gray-200/80 dark:border-gray-800 space-y-2.5"
		>
			<div class="text-xs font-semibold text-gray-900 dark:text-gray-100 flex items-center justify-between">
				<span>{$i18n.t('Gateway Model Catalog')}</span>
				<span class="text-[10px] text-gray-400 font-mono">{$i18n.t('Wolinet Unified API')}</span>
			</div>

			<p class="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed">
				Models shown in chat come from the LiteLLM gateway and reflect models currently enabled for this account.
			</p>
		</div>

		<!-- Developer & API Documentation Links -->
		<div class="flex flex-wrap items-center gap-2 pt-1">
			<a
				href="/docs"
				target="_blank"
				class="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-black dark:hover:bg-gray-100 transition shadow-2xs cursor-pointer"
			>
				<span>{$i18n.t('Wolinet API Documentation')}</span>
				<svg class="size-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
					<path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
				</svg>
			</a>

			<a
				href="/api/version"
				target="_blank"
				class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xl bg-gray-100 hover:bg-gray-200/80 dark:bg-gray-800 dark:hover:bg-gray-700/80 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700/80 transition cursor-pointer"
			>
				<span>{$i18n.t('System Version & Status')}</span>
				<span class="size-1.5 rounded-full bg-emerald-500"></span>
			</a>
		</div>

		<!-- Footer -->
		<div class="border-t border-gray-100 dark:border-gray-800/80 pt-4 space-y-1">
			<div class="text-xs text-gray-600 dark:text-gray-400 font-medium">
				© {new Date().getFullYear()} <strong>Wolinet Technology</strong>. All rights reserved.
			</div>
			<div class="text-[11px] text-gray-400 dark:text-gray-500">
				Engineered and maintained by <strong>Wolinet Technology</strong> for sovereign enterprise artificial intelligence.
			</div>
		</div>
	</div>
</div>
