<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	import { getGravatarUrl } from '$lib/apis/utils';
	import { canvasPixelTest, generateInitialsImage } from '$lib/utils';
	import { WEBUI_BASE_URL } from '$lib/constants';

	export let profileImageUrl = '';
	export let user = null;
	export let imageClassName = 'size-20';

	let profileImageInputElement: HTMLInputElement;
</script>

<input
	id="profile-image-input"
	bind:this={profileImageInputElement}
	type="file"
	hidden
	accept="image/*"
	on:change={(e) => {
		const files = profileImageInputElement.files ?? [];
		if (files.length === 0) return;

		let reader = new FileReader();
		reader.onload = (event) => {
			let originalImageUrl = `${event.target?.result}`;

			const img = new Image();
			img.src = originalImageUrl;

			img.onload = function () {
				const canvas = document.createElement('canvas');
				const ctx = canvas.getContext('2d');
				if (!ctx) return;

				const aspectRatio = img.width / img.height;
				let newWidth, newHeight;
				if (aspectRatio > 1) {
					newWidth = 250 * aspectRatio;
					newHeight = 250;
				} else {
					newWidth = 250;
					newHeight = 250 / aspectRatio;
				}

				canvas.width = 250;
				canvas.height = 250;
				const offsetX = (250 - newWidth) / 2;
				const offsetY = (250 - newHeight) / 2;

				ctx.drawImage(img, offsetX, offsetY, newWidth, newHeight);
				const compressedSrc = canvas.toDataURL('image/webp', 0.85);
				profileImageUrl = compressedSrc;
				profileImageInputElement.value = '';
				toast.success($i18n.t('Profile image updated'));
			};
		};

		if (['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(files[0]['type'])) {
			reader.readAsDataURL(files[0]);
		} else {
			toast.error($i18n.t('Unsupported file type. Please upload a PNG, JPG, or WebP image.'));
		}
	}}
/>

<div class="flex flex-col items-center sm:items-start gap-3">
	<div class="relative group">
		<button
			class="relative block rounded-full ring-2 ring-gray-200 dark:ring-gray-700 hover:ring-emerald-500/50 dark:hover:ring-emerald-400/50 transition shadow-sm overflow-hidden focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
			type="button"
			title={$i18n.t('Click to upload new photo')}
			aria-label={$i18n.t('Change profile photo')}
			on:click={() => {
				profileImageInputElement.click();
			}}
		>
			<img
				src={profileImageUrl !== '' ? profileImageUrl : generateInitialsImage(user?.name)}
				alt="profile"
				class="{imageClassName} rounded-full object-cover transition duration-150 group-hover:brightness-90"
			/>

			<div
				class="absolute inset-0 bg-black/40 text-white flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-150"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="size-5"
				>
					<path
						d="m2.695 14.762-1.262 3.155a.5.5 0 0 0 .65.65l3.155-1.262a4 4 0 0 0 1.343-.886L17.5 5.501a2.121 2.121 0 0 0-3-3L3.58 13.419a4 4 0 0 0-.885 1.343Z"
					/>
				</svg>
				<span class="text-[10px] font-medium tracking-tight mt-0.5">{$i18n.t('Change')}</span>
			</div>
		</button>
	</div>

	<!-- Quick Avatar Actions -->
	<div class="flex flex-wrap items-center gap-1.5 w-full justify-center sm:justify-start">
		<button
			class="px-2 py-0.5 text-[11px] font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white bg-gray-100 dark:bg-gray-800/80 hover:bg-gray-200 dark:hover:bg-gray-700/80 border border-gray-200 dark:border-gray-700/60 rounded-md transition cursor-pointer"
			type="button"
			title={$i18n.t('Reset to default avatar')}
			on:click={async () => {
				profileImageUrl = `${WEBUI_BASE_URL}/user.png`;
				toast.info($i18n.t('Profile picture removed'));
			}}
		>
			{$i18n.t('Remove')}
		</button>

		<button
			class="px-2 py-0.5 text-[11px] font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white bg-gray-100 dark:bg-gray-800/80 hover:bg-gray-200 dark:hover:bg-gray-700/80 border border-gray-200 dark:border-gray-700/60 rounded-md transition cursor-pointer"
			type="button"
			title={$i18n.t('Generate avatar using your initials')}
			on:click={async () => {
				if (canvasPixelTest()) {
					profileImageUrl = generateInitialsImage(user?.name);
					toast.success($i18n.t('Generated initials avatar'));
				} else {
					toast.info(
						$i18n.t(
							'Fingerprint spoofing detected: Unable to use initials as avatar. Defaulting to default profile image.'
						),
						{ duration: 1000 * 10 }
					);
				}
			}}
		>
			{$i18n.t('Initials')}
		</button>

		<button
			class="px-2 py-0.5 text-[11px] font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white bg-gray-100 dark:bg-gray-800/80 hover:bg-gray-200 dark:hover:bg-gray-700/80 border border-gray-200 dark:border-gray-700/60 rounded-md transition cursor-pointer"
			type="button"
			title={$i18n.t('Fetch avatar from Gravatar')}
			on:click={async () => {
				const url = await getGravatarUrl(localStorage.token, user?.email);
				if (url) {
					profileImageUrl = url;
					toast.success($i18n.t('Gravatar avatar linked'));
				} else {
					toast.error($i18n.t('Could not load Gravatar for this email'));
				}
			}}
		>
			{$i18n.t('Gravatar')}
		</button>
	</div>
</div>
