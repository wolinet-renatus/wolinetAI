<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';

	import { user, config, settings } from '$lib/stores';
	import { updateUserProfile, createAPIKey, getAPIKey, getSessionUser } from '$lib/apis/auths';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import UpdatePassword from './Account/UpdatePassword.svelte';
	import { generateInitialsImage } from '$lib/utils';
	import { copyToClipboard } from '$lib/utils';
	import Plus from '$lib/components/icons/Plus.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import UserProfileImage from './Account/UserProfileImage.svelte';

	const i18n = getContext('i18n');

	export let saveHandler: Function = () => {};
	export let saveSettings: Function = () => {};

	let loaded = false;
	let isSaving = false;

	let profileImageUrl = '';
	let name = '';
	let bio = '';

	let _gender = '';
	let gender = '';
	let dateOfBirth = '';

	let webhookUrl = '';
	let showAPIKeys = false;

	let JWTTokenCopied = false;
	let APIKey = '';
	let APIKeyCopied = false;

	const submitHandler = async () => {
		isSaving = true;
		try {
			if (name !== $user?.name) {
				if (profileImageUrl === generateInitialsImage($user?.name) || profileImageUrl === '') {
					profileImageUrl = generateInitialsImage(name);
				}
			}

			if (webhookUrl !== $settings?.notifications?.webhook_url) {
				saveSettings({
					notifications: {
						...$settings.notifications,
						webhook_url: webhookUrl
					}
				});
			}

			const updatedUser = await updateUserProfile(localStorage.token, {
				name: name,
				profile_image_url: profileImageUrl,
				bio: bio ? bio : null,
				gender: gender ? gender : null,
				date_of_birth: dateOfBirth ? dateOfBirth : null
			}).catch((error) => {
				toast.error(`${error}`);
			});

			if (updatedUser) {
				const sessionUser = await getSessionUser(localStorage.token).catch((error) => {
					toast.error(`${error}`);
					return null;
				});

				await user.set(sessionUser);
				return true;
			}
			return false;
		} finally {
			isSaving = false;
		}
	};

	const createAPIKeyHandler = async () => {
		APIKey = await createAPIKey(localStorage.token);
		if (APIKey) {
			toast.success($i18n.t('API Key created successfully'));
		} else {
			toast.error($i18n.t('Failed to create API Key'));
		}
	};

	onMount(async () => {
		const currentUser = await getSessionUser(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (currentUser) {
			name = currentUser?.name ?? '';
			profileImageUrl = currentUser?.profile_image_url ?? '';
			bio = currentUser?.bio ?? '';
			_gender = currentUser?.gender ?? '';
			gender = _gender;
			dateOfBirth = currentUser?.date_of_birth ?? '';
		}

		webhookUrl = $settings?.notifications?.webhook_url ?? '';

		if (
			currentUser &&
			($config?.features?.enable_api_keys ?? true) &&
			(currentUser?.role === 'admin' || (currentUser?.permissions?.features?.api_keys ?? false))
		) {
			APIKey = await getAPIKey(localStorage.token).catch((error) => {
				console.log(error);
				return '';
			});
		}

		loaded = true;
	});
</script>

<div id="tab-account" class="flex flex-col h-full justify-between text-sm pr-1">
	<div class="overflow-y-auto max-h-[30rem] md:max-h-[calc(100vh-14rem)] space-y-4 pr-1">
		<!-- Header -->
		<div class="border-b border-gray-100 dark:border-gray-800 pb-3">
			<div class="flex items-center justify-between">
				<div>
					<h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">
						{$i18n.t('Your Account')}
					</h2>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
						{$i18n.t('Manage your account information.')}
					</p>
				</div>
				<!-- Sovereign Role / Status Badge -->
				<div class="flex items-center gap-1.5">
					<span
						class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
					>
						<span class="size-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
						{$user?.role === 'admin' ? $i18n.t('Sovereign Admin') : $i18n.t('Cloud Member')}
					</span>
				</div>
			</div>
		</div>

		<!-- Identity & Profile Card -->
		<div
			class="bg-gray-50/70 dark:bg-gray-850/40 border border-gray-200/80 dark:border-gray-800 rounded-2xl p-4 transition shadow-xs"
		>
			<div class="flex flex-col sm:flex-row gap-5 items-start">
				<div class="shrink-0 self-center sm:self-start">
					<UserProfileImage bind:profileImageUrl user={$user} imageClassName="size-20" />
				</div>

				<div class="flex-1 w-full space-y-3">
					<!-- Full Name -->
					<div>
						<label for="account-name" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
							{$i18n.t('Name')}
						</label>
						<input
							id="account-name"
							class="w-full text-xs sm:text-sm bg-white dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700/80 rounded-xl px-3 py-2 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-hidden focus:ring-2 focus:ring-gray-900 dark:focus:ring-white transition"
							type="text"
							bind:value={name}
							aria-label={$i18n.t('Name')}
							required
							placeholder={$i18n.t('Enter your full name')}
						/>
					</div>

					<!-- Bio -->
					<div>
						<label for="account-bio" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
							{$i18n.t('Bio')}
						</label>
						<textarea
							id="account-bio"
							rows="2"
							class="w-full text-xs sm:text-sm bg-white dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700/80 rounded-xl px-3 py-2 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-hidden focus:ring-2 focus:ring-gray-900 dark:focus:ring-white transition resize-none"
							bind:value={bio}
							aria-label={$i18n.t('Bio')}
							placeholder={$i18n.t('Share your background and interests')}
						/>
					</div>

					<!-- Gender & Birth Date Grid -->
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
						<div>
							<label for="account-gender" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
								{$i18n.t('Gender')}
							</label>
							<div class="relative">
								<select
									id="account-gender"
									class="w-full appearance-none text-xs sm:text-sm bg-white dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700/80 rounded-xl px-3 py-2 pr-8 text-gray-900 dark:text-gray-100 focus:outline-hidden focus:ring-2 focus:ring-gray-900 dark:focus:ring-white transition cursor-pointer"
									bind:value={_gender}
									aria-label={$i18n.t('Gender')}
									on:change={() => {
										if (_gender === 'custom') {
											gender = '';
										} else {
											gender = _gender;
										}
									}}
								>
									<option value="">{$i18n.t('Prefer not to say')}</option>
									<option value="male">{$i18n.t('Male')}</option>
									<option value="female">{$i18n.t('Female')}</option>
									<option value="custom">{$i18n.t('Custom')}</option>
								</select>
								<div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-gray-400">
									<svg class="size-3.5" viewBox="0 0 20 20" fill="currentColor">
										<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
									</svg>
								</div>
							</div>

							{#if _gender === 'custom'}
								<input
									class="w-full text-xs sm:text-sm bg-white dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700/80 rounded-xl px-3 py-2 text-gray-900 dark:text-gray-100 mt-2 focus:outline-hidden focus:ring-2 focus:ring-gray-900 dark:focus:ring-white transition"
									type="text"
									aria-label={$i18n.t('Custom Gender')}
									placeholder={$i18n.t('Enter your gender')}
									bind:value={gender}
								/>
							{/if}
						</div>

						<div>
							<label for="account-dob" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
								{$i18n.t('Birth Date')}
							</label>
							<input
								id="account-dob"
								class="w-full text-xs sm:text-sm bg-white dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700/80 rounded-xl px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-hidden focus:ring-2 focus:ring-gray-900 dark:focus:ring-white transition"
								type="date"
								aria-label={$i18n.t('Birth Date')}
								bind:value={dateOfBirth}
							/>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Wolinet AI Cloud Status & Credits Banner -->
		<div
			class="bg-linear-to-r from-gray-50 via-slate-50 to-gray-100 dark:from-gray-900 dark:via-gray-850 dark:to-gray-900 border border-gray-200/90 dark:border-gray-800 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs"
		>
			<div class="flex items-center gap-3">
				<div
					class="size-9 rounded-xl bg-gray-900 dark:bg-white text-white dark:text-gray-900 flex items-center justify-center font-bold text-xs tracking-wider"
				>
					W
				</div>
				<div>
					<div class="text-xs font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
						<span>Wolinet AI Sovereign Gateway</span>
						<span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-mono">
							Active
						</span>
					</div>
					<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
						Default Model: <code class="font-mono text-gray-700 dark:text-gray-300">wolinex-coder</code> • Spend Metering Enabled
					</div>
				</div>
			</div>

			<div class="flex items-center gap-2 self-end sm:self-center">
				<a
					href="/docs"
					target="_blank"
					class="px-2.5 py-1 text-[11px] font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg transition shadow-2xs"
				>
					{$i18n.t('API Documentation')} ↗
				</a>
			</div>
		</div>

		<!-- Notification Webhook (if enabled) -->
		{#if $config?.features?.enable_user_webhooks}
			<div
				class="bg-gray-50/70 dark:bg-gray-850/40 border border-gray-200/80 dark:border-gray-800 rounded-2xl p-4"
			>
				<label for="account-webhook" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
					{$i18n.t('Notification Webhook')}
				</label>
				<input
					id="account-webhook"
					class="w-full text-xs sm:text-sm bg-white dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700/80 rounded-xl px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-hidden focus:ring-2 focus:ring-gray-900 dark:focus:ring-white transition"
					type="url"
					placeholder={$i18n.t('Enter your webhook URL')}
					aria-label={$i18n.t('Notification Webhook')}
					bind:value={webhookUrl}
				/>
			</div>
		{/if}

		<!-- Security & Password -->
		{#if $config?.features.enable_login_form && $config?.features.enable_password_change_form}
			<div
				class="bg-gray-50/70 dark:bg-gray-850/40 border border-gray-200/80 dark:border-gray-800 rounded-2xl p-4"
			>
				<UpdatePassword />
			</div>
		{/if}

		<!-- API Keys & Sovereign Tokens -->
		{#if ($config?.features?.enable_api_keys ?? true) && ($user?.role === 'admin' || ($user?.permissions?.features?.api_keys ?? false))}
			<div
				class="bg-gray-50/70 dark:bg-gray-850/40 border border-gray-200/80 dark:border-gray-800 rounded-2xl p-4 space-y-3"
			>
				<div class="flex justify-between items-center">
					<div>
						<div class="text-xs font-semibold text-gray-900 dark:text-gray-100">
							{$i18n.t('Developer & API Access')}
						</div>
						<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
							{$i18n.t('Manage your programmatic access keys and sovereign authorization tokens.')}
						</div>
					</div>
					<button
						class="px-2.5 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg transition cursor-pointer shadow-2xs"
						type="button"
						on:click={() => {
							showAPIKeys = !showAPIKeys;
						}}
					>
						{showAPIKeys ? $i18n.t('Hide Keys') : $i18n.t('Manage Keys')}
					</button>
				</div>

				{#if showAPIKeys}
					<div class="space-y-3 pt-2 border-t border-gray-200/80 dark:border-gray-800">
						<!-- JWT Token -->
						{#if $user?.role === 'admin'}
							<div>
								<div class="text-[11px] font-medium text-gray-700 dark:text-gray-300 mb-1">
									{$i18n.t('Session JWT Token')}
								</div>
								<div class="flex items-center gap-1.5">
									<div class="flex-1">
										<SensitiveInput value={localStorage.token} readOnly={true} />
									</div>
									<button
										class="p-2 text-xs font-medium bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-xl transition cursor-pointer"
										title={$i18n.t('Copy Token')}
										aria-label={$i18n.t('Copy Token')}
										on:click={() => {
											copyToClipboard(localStorage.token);
											JWTTokenCopied = true;
											toast.success($i18n.t('Token copied to clipboard'));
											setTimeout(() => {
												JWTTokenCopied = false;
											}, 2000);
										}}
									>
										{#if JWTTokenCopied}
											<svg class="size-4 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
												<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
											</svg>
										{:else}
											<svg class="size-4 text-gray-500" viewBox="0 0 16 16" fill="currentColor">
												<path fill-rule="evenodd" d="M11.986 3H12a2 2 0 0 1 2 2v6a2 2 0 0 1-1.5 1.937V7A2.5 2.5 0 0 0 10 4.5H4.063A2 2 0 0 1 6 3h.014A2.25 2.25 0 0 1 8.25 1h1.5a2.25 2.25 0 0 1 2.236 2ZM10.5 4v-.75a.75.75 0 0 0-.75-.75h-1.5a.75.75 0 0 0-.75.75V4h3Z" clip-rule="evenodd" />
												<path fill-rule="evenodd" d="M3 6a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H3Zm1.75 2.5a.75.75 0 0 0 0 1.5h3.5a.75.75 0 0 0 0-1.5h-3.5ZM4 11.75a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z" clip-rule="evenodd" />
											</svg>
										{/if}
									</button>
								</div>
							</div>
						{/if}

						<!-- API Secret Key -->
						<div>
							<div class="text-[11px] font-medium text-gray-700 dark:text-gray-300 mb-1">
								{$i18n.t('Wolinet Virtual API Key')}
							</div>
							<div class="flex items-center gap-1.5">
								{#if APIKey}
									<div class="flex-1">
										<SensitiveInput value={APIKey} readOnly={true} />
									</div>
									<button
										class="p-2 text-xs font-medium bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-xl transition cursor-pointer"
										title={$i18n.t('Copy API Key')}
										aria-label={$i18n.t('Copy API Key')}
										on:click={() => {
											copyToClipboard(APIKey);
											APIKeyCopied = true;
											toast.success($i18n.t('API key copied to clipboard'));
											setTimeout(() => {
												APIKeyCopied = false;
											}, 2000);
										}}
									>
										{#if APIKeyCopied}
											<svg class="size-4 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
												<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
											</svg>
										{:else}
											<svg class="size-4 text-gray-500" viewBox="0 0 16 16" fill="currentColor">
												<path fill-rule="evenodd" d="M11.986 3H12a2 2 0 0 1 2 2v6a2 2 0 0 1-1.5 1.937V7A2.5 2.5 0 0 0 10 4.5H4.063A2 2 0 0 1 6 3h.014A2.25 2.25 0 0 1 8.25 1h1.5a2.25 2.25 0 0 1 2.236 2ZM10.5 4v-.75a.75.75 0 0 0-.75-.75h-1.5a.75.75 0 0 0-.75.75V4h3Z" clip-rule="evenodd" />
												<path fill-rule="evenodd" d="M3 6a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H3Zm1.75 2.5a.75.75 0 0 0 0 1.5h3.5a.75.75 0 0 0 0-1.5h-3.5ZM4 11.75a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z" clip-rule="evenodd" />
											</svg>
										{/if}
									</button>

									<button
										class="p-2 text-xs font-medium bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-xl transition cursor-pointer"
										title={$i18n.t('Generate New Key')}
										aria-label={$i18n.t('Generate New Key')}
										on:click={() => {
											createAPIKeyHandler();
										}}
									>
										<svg class="size-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
											<path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
										</svg>
									</button>
								{:else}
									<button
										class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-gray-900 hover:bg-black text-white dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100 rounded-xl transition shadow-2xs"
										type="button"
										on:click={() => {
											createAPIKeyHandler();
										}}
									>
										<Plus strokeWidth="2" className="size-3.5" />
										{$i18n.t('Generate New Secret Key')}
									</button>
								{/if}
							</div>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Footer with Save Button -->
	<div class="flex justify-end pt-3 mt-2 border-t border-gray-100 dark:border-gray-800">
		<button
			class="px-5 py-2 text-xs font-semibold text-white bg-gray-900 hover:bg-black dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100 transition rounded-xl shadow-xs disabled:opacity-50 cursor-pointer"
			disabled={isSaving}
			on:click={async () => {
				const res = await submitHandler();
				if (res) {
					saveHandler();
					toast.success($i18n.t('Account changes saved successfully'));
				}
			}}
		>
			{isSaving ? $i18n.t('Saving...') : $i18n.t('Save Changes')}
		</button>
	</div>
</div>
