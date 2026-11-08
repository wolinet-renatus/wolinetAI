<script lang="ts">
	import { onMount, getContext, onDestroy } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_NAME, showSidebar, mobile } from '$lib/stores';
	import { synthesizeOpenAISpeech } from '$lib/apis/audio';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Voice from '$lib/components/icons/Voice.svelte';
	import SoundHigh from '$lib/components/icons/SoundHigh.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';

	const i18n = getContext('i18n');

	interface GenerationHistoryItem {
		id: string;
		text: string;
		engine: string;
		engineLabel: string;
		voice: string;
		audioUrl: string;
		timestamp: number;
		durationStr?: string;
	}

	// State
	let selectedEngine = 'sauti'; // 'sauti' | 'underdog'
	let selectedVoice = 'Renatus'; // 'Renatus' | 'Witness'
	let inputText =
		'Mimi ni Renatus Bernardo, mwanzilishi wa Wolinet AI, nawakaribisha wote kuja na kutumia mifumo yetu ya bei nafuu, tuliyoijenga kwa ajili yenu na kwa lugha adhimu yetu ya Kiswahili.';
	let generating = false;
	let generationTimeSeconds = 0;
	let timerInterval: any = null;

	// Audio Playback
	let audioElement: HTMLAudioElement | null = null;
	let currentAudioUrl: string | null = null;
	let isPlaying = false;
	let currentTime = 0;
	let duration = 0;
	let currentItem: GenerationHistoryItem | null = null;

	// History
	let history: GenerationHistoryItem[] = [];

	const presets = [
		{
			title: 'Founder Welcome (Swahili)',
			engine: 'sauti',
			voice: 'Renatus',
			text: 'Mimi ni Renatus Bernardo, mwanzilishi wa Wolinet AI, nawakaribisha wote kuja na kutumia mifumo yetu ya bei nafuu, tuliyoijenga kwa ajili yenu na kwa lugha adhimu yetu ya Kiswahili.'
		},
		{
			title: 'Wolinet Sovereign AI (Swahili)',
			engine: 'sauti',
			voice: 'Witness',
			text: 'Wolinet AI inaleta mageuzi ya kiteknolojia barani Afrika kwa kutoa miundombinu huru ya akili mnemba inayozungumza na kuelewa Kiswahili fasaha.'
		},
		{
			title: 'Enterprise Platform (English)',
			engine: 'underdog',
			voice: 'Renatus',
			text: 'Welcome to Wolinet AI, Africa’s sovereign intelligence platform offering frontier AI infrastructure, low latency, and native language understanding.'
		}
	];

	function applyPreset(p: (typeof presets)[0]) {
		selectedEngine = p.engine;
		selectedVoice = p.voice;
		inputText = p.text;
	}

	function formatTime(seconds: number): string {
		if (isNaN(seconds) || seconds <= 0) return '0:00';
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return `${m}:${s < 10 ? '0' : ''}${s}`;
	}

	async function generateSpeech() {
		const text = inputText.trim();
		if (!text) {
			toast.error('Please enter text to generate speech');
			return;
		}

		generating = true;
		generationTimeSeconds = 0;
		if (timerInterval) clearInterval(timerInterval);
		timerInterval = setInterval(() => {
			generationTimeSeconds += 1;
		}, 1000);

		const modelName = selectedEngine === 'underdog' ? 'underdog-woof' : 'Wolinet Voice';
		const engineLabel = selectedEngine === 'underdog' ? 'Underdog-Woof (English)' : 'Sauti-TTS (Kiswahili)';

		try {
			const token = localStorage.token || '';
			const res = await synthesizeOpenAISpeech(token, selectedVoice, text, modelName);

			if (!res || !res.ok) {
				throw new Error('Voice generation failed from backend server');
			}

			const blob = await res.blob();
			const audioUrl = URL.createObjectURL(blob);

			const item: GenerationHistoryItem = {
				id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
				text,
				engine: modelName,
				engineLabel,
				voice: selectedVoice,
				audioUrl,
				timestamp: Date.now()
			};

			history = [item, ...history];
			loadAudio(item, true);
			toast.success(`Voice generated in ${generationTimeSeconds}s`);
		} catch (err: any) {
			console.error('Speech generation error:', err);
			toast.error(err?.message || 'Failed to generate voice. Ensure voice service is running.');
		} finally {
			generating = false;
			if (timerInterval) {
				clearInterval(timerInterval);
				timerInterval = null;
			}
		}
	}

	function loadAudio(item: GenerationHistoryItem, autoplay = false) {
		currentItem = item;
		currentAudioUrl = item.audioUrl;
		currentTime = 0;
		isPlaying = false;

		if (audioElement) {
			audioElement.src = item.audioUrl;
			audioElement.load();
			if (autoplay) {
				audioElement.play().catch(() => {});
			}
		}
	}

	function togglePlay() {
		if (!audioElement) return;
		if (audioElement.paused) {
			audioElement.play().catch(() => {});
		} else {
			audioElement.pause();
		}
	}

	function handleAudioTimeUpdate() {
		if (!audioElement) return;
		currentTime = audioElement.currentTime;
		duration = audioElement.duration || 0;
	}

	function handleSeek(e: Event) {
		const target = e.target as HTMLInputElement;
		const val = parseFloat(target.value);
		if (audioElement && !isNaN(val)) {
			audioElement.currentTime = val;
		}
	}

	function downloadCurrentAudio(item?: GenerationHistoryItem) {
		const target = item || currentItem;
		if (!target || !target.audioUrl) return;
		const a = document.createElement('a');
		a.href = target.audioUrl;
		const cleanVoice = target.voice.toLowerCase();
		const dateStr = new Date(target.timestamp).toISOString().replace(/[:.]/g, '-');
		a.download = `wolinet-voice-${cleanVoice}-${dateStr}.mp3`;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
	}

	onDestroy(() => {
		if (timerInterval) clearInterval(timerInterval);
		if (audioElement) {
			audioElement.pause();
			audioElement.src = '';
		}
		for (const h of history) {
			if (h.audioUrl) {
				URL.revokeObjectURL(h.audioUrl);
			}
		}
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Voice Studio')} • {$WEBUI_NAME}
	</title>
</svelte:head>

<div
	class="flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''} max-w-full"
>
	<!-- Top Navigation Bar -->
	<nav class="px-3 py-2 border-b border-gray-100 dark:border-gray-850 backdrop-blur-xl drag-region select-none">
		<div class="flex items-center justify-between">
			<div class="flex items-center space-x-2">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center">
						<Tooltip
							content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							interactive={true}
						>
							<button
								id="sidebar-toggle-button"
								class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition p-1.5"
								on:click={() => {
									showSidebar.set(!$showSidebar);
								}}
							>
								<Sidebar />
							</button>
						</Tooltip>
					</div>
				{/if}

				<div class="flex items-center space-x-2.5">
					<div class="flex items-center justify-center p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
						<Voice className="size-5" strokeWidth="2" />
					</div>
					<div>
						<div class="text-base font-semibold text-gray-900 dark:text-gray-100 leading-tight">
							Wolinet Voice Studio
						</div>
						<div class="text-xs text-gray-500 dark:text-gray-400">
							Sovereign Kiswahili & English Neural Speech
						</div>
					</div>
				</div>
			</div>

			<div class="flex items-center space-x-2">
				<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
					24kHz High Definition
				</span>
			</div>
		</div>
	</nav>

	<!-- Main Workspace Area -->
	<div class="flex-1 overflow-y-auto px-4 py-6 md:px-8 max-w-5xl mx-auto w-full space-y-6">
		<!-- Quick Presets -->
		<div class="space-y-2">
			<div class="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
				Sample Presets
			</div>
			<div class="flex flex-wrap gap-2">
				{#each presets as p}
					<button
						type="button"
						class="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-850 text-gray-700 dark:text-gray-300 hover:border-emerald-500 hover:text-emerald-600 dark:hover:text-emerald-400 transition cursor-pointer"
						on:click={() => applyPreset(p)}
					>
						{p.title}
					</button>
				{/each}
			</div>
		</div>

		<!-- Configuration Grid -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<!-- Sovereign Engine Selector -->
			<div class="p-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-850 space-y-3">
				<div class="flex items-center justify-between">
					<div class="text-sm font-medium text-gray-900 dark:text-gray-100">
						Language & Engine
					</div>
					<span class="text-xs text-gray-500 dark:text-gray-400">Backend Sovereign Models</span>
				</div>

				<div class="grid grid-cols-2 gap-2">
					<button
						type="button"
						class="flex flex-col p-3 rounded-xl border text-left transition cursor-pointer {selectedEngine ===
						'sauti'
							? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20 ring-1 ring-emerald-500'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						on:click={() => {
							selectedEngine = 'sauti';
						}}
					>
						<div class="flex items-center justify-between">
							<span class="text-sm font-semibold text-gray-900 dark:text-gray-100">Kiswahili</span>
							{#if selectedEngine === 'sauti'}
								<span class="size-2 rounded-full bg-emerald-500"></span>
							{/if}
						</div>
						<span class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							Sauti-TTS (24kHz DiT Neural Engine)
						</span>
					</button>

					<button
						type="button"
						class="flex flex-col p-3 rounded-xl border text-left transition cursor-pointer {selectedEngine ===
						'underdog'
							? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20 ring-1 ring-emerald-500'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						on:click={() => {
							selectedEngine = 'underdog';
						}}
					>
						<div class="flex items-center justify-between">
							<span class="text-sm font-semibold text-gray-900 dark:text-gray-100">English</span>
							{#if selectedEngine === 'underdog'}
								<span class="size-2 rounded-full bg-emerald-500"></span>
							{/if}
						</div>
						<span class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							Underdog-Woof (Fast INT8 Vocoder)
						</span>
					</button>
				</div>
			</div>

			<!-- Voice Switcher (Renatus vs Witness) -->
			<div class="p-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-850 space-y-3">
				<div class="flex items-center justify-between">
					<div class="text-sm font-medium text-gray-900 dark:text-gray-100">
						Voice Persona
					</div>
					<span class="text-xs text-gray-500 dark:text-gray-400">Gender & Persona</span>
				</div>

				<div class="grid grid-cols-2 gap-2">
					<!-- Male (Renatus) -->
					<button
						type="button"
						class="flex flex-col p-3 rounded-xl border text-left transition cursor-pointer {selectedVoice ===
						'Renatus'
							? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20 ring-1 ring-emerald-500'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						on:click={() => {
							selectedVoice = 'Renatus';
						}}
					>
						<div class="flex items-center justify-between">
							<div class="flex items-center space-x-2">
								<span class="text-sm font-semibold text-gray-900 dark:text-gray-100">Renatus</span>
								<span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
									Male
								</span>
							</div>
							{#if selectedVoice === 'Renatus'}
								<span class="size-2 rounded-full bg-emerald-500"></span>
							{/if}
						</div>
						<span class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							Authoritative, clear native pronunciation
						</span>
					</button>

					<!-- Female (Witness) -->
					<button
						type="button"
						class="flex flex-col p-3 rounded-xl border text-left transition cursor-pointer {selectedVoice ===
						'Witness'
							? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20 ring-1 ring-emerald-500'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						on:click={() => {
							selectedVoice = 'Witness';
						}}
					>
						<div class="flex items-center justify-between">
							<div class="flex items-center space-x-2">
								<span class="text-sm font-semibold text-gray-900 dark:text-gray-100">Witness</span>
								<span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-pink-100 dark:bg-pink-950/40 text-pink-700 dark:text-pink-300">
									Female
								</span>
							</div>
							{#if selectedVoice === 'Witness'}
								<span class="size-2 rounded-full bg-emerald-500"></span>
							{/if}
						</div>
						<span class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							Warm, articulate, natural vocal cadence
						</span>
					</button>
				</div>
			</div>
		</div>

		<!-- Text Input Area -->
		<div class="p-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-850 space-y-3">
			<div class="flex items-center justify-between">
				<label for="voice-text-input" class="text-sm font-medium text-gray-900 dark:text-gray-100">
					Speech Script
				</label>
				<span class="text-xs text-gray-400 dark:text-gray-500">
					{inputText.length} characters • {inputText.trim() ? inputText.trim().split(/\s+/).length : 0} words
				</span>
			</div>

			<textarea
				id="voice-text-input"
				bind:value={inputText}
				rows="4"
				placeholder="Type or paste Kiswahili or English text here..."
				class="w-full p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition resize-y"
			></textarea>

			<div class="flex items-center justify-between pt-1">
				<button
					type="button"
					class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition cursor-pointer"
					on:click={() => {
						inputText = '';
					}}
				>
					Clear text
				</button>

				<button
					type="button"
					disabled={generating || !inputText.trim()}
					class="inline-flex items-center px-5 py-2.5 rounded-xl font-medium text-sm text-white bg-emerald-600 hover:bg-emerald-700 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none transition shadow-sm cursor-pointer space-x-2"
					on:click={generateSpeech}
				>
					{#if generating}
						<Spinner className="size-4" />
						<span>Synthesizing ({generationTimeSeconds}s)...</span>
					{:else}
						<SoundHigh className="size-4" />
						<span>Generate Voice</span>
					{/if}
				</button>
			</div>
		</div>

		<!-- Audio Playback Card -->
		{#if currentItem}
			<div class="p-5 rounded-2xl border border-emerald-500/30 bg-white dark:bg-gray-850 shadow-sm space-y-4">
				<div class="flex items-center justify-between">
					<div class="flex items-center space-x-2.5">
						<div class="size-3 rounded-full bg-emerald-500 animate-pulse"></div>
						<div>
							<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
								{currentItem.voice} ({currentItem.engineLabel})
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 truncate max-w-md">
								"{currentItem.text}"
							</div>
						</div>
					</div>

					<button
						type="button"
						class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 transition cursor-pointer"
						on:click={() => downloadCurrentAudio()}
					>
						<ArrowDownTray className="size-3.5" />
						<span>Download MP3</span>
					</button>
				</div>

				<!-- Hidden Audio Element -->
				<audio
					bind:this={audioElement}
					on:timeupdate={handleAudioTimeUpdate}
					on:play={() => {
						isPlaying = true;
					}}
					on:pause={() => {
						isPlaying = false;
					}}
					on:ended={() => {
						isPlaying = false;
					}}
				></audio>

				<!-- Custom Scrubber and Controls -->
				<div class="flex items-center space-x-3">
					<button
						type="button"
						class="size-10 rounded-full flex items-center justify-center bg-emerald-600 hover:bg-emerald-700 text-white transition shadow-sm cursor-pointer shrink-0"
						on:click={togglePlay}
					>
						{#if isPlaying}
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="size-5">
								<path fill-rule="evenodd" d="M6.75 5.25a.75.75 0 0 1 .75.75v12a.75.75 0 0 1-1.5 0v-12a.75.75 0 0 1 .75-.75Zm9 0a.75.75 0 0 1 .75.75v12a.75.75 0 0 1-1.5 0v-12a.75.75 0 0 1 .75-.75Z" clip-rule="evenodd" />
							</svg>
						{:else}
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="size-5 translate-x-0.5">
								<path fill-rule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653Z" clip-rule="evenodd" />
							</svg>
						{/if}
					</button>

					<div class="flex-1 space-y-1">
						<input
							type="range"
							min="0"
							max={duration || 100}
							step="0.05"
							value={currentTime}
							on:input={handleSeek}
							class="w-full accent-emerald-600 cursor-pointer h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none"
						/>
						<div class="flex justify-between text-[11px] text-gray-400 font-mono">
							<span>{formatTime(currentTime)}</span>
							<span>{formatTime(duration)}</span>
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Generation History -->
		{#if history.length > 1}
			<div class="space-y-3 pt-4 border-t border-gray-100 dark:border-gray-850">
				<div class="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
					Session History ({history.length})
				</div>
				<div class="space-y-2">
					{#each history as item}
						<div
							class="flex items-center justify-between p-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-850 hover:border-gray-300 dark:hover:border-gray-700 transition {currentItem?.id ===
							item.id
								? 'ring-1 ring-emerald-500'
								: ''}"
						>
							<div class="flex items-center space-x-3 overflow-hidden">
								<button
									type="button"
									class="size-8 rounded-full flex items-center justify-center bg-gray-100 dark:bg-gray-800 hover:bg-emerald-100 dark:hover:bg-emerald-950 text-gray-700 dark:text-gray-300 hover:text-emerald-600 transition cursor-pointer shrink-0"
									on:click={() => loadAudio(item, true)}
								>
									<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="size-4">
										<path fill-rule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653Z" clip-rule="evenodd" />
									</svg>
								</button>
								<div class="truncate">
									<div class="text-xs font-medium text-gray-900 dark:text-gray-100">
										{item.voice} • {item.engineLabel}
									</div>
									<div class="text-[11px] text-gray-500 dark:text-gray-400 truncate max-w-sm">
										{item.text}
									</div>
								</div>
							</div>

							<button
								type="button"
								class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition cursor-pointer"
								on:click={() => downloadCurrentAudio(item)}
							>
								<ArrowDownTray className="size-4" />
							</button>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>
