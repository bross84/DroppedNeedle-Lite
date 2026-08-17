<script lang="ts">
	import { page } from '$app/state';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import LibraryDashboard from '$lib/components/library/LibraryDashboard.svelte';
	import { authStore } from '$lib/stores/authStore.svelte';
	import { Headphones, LockKeyhole, SlidersHorizontal } from 'lucide-svelte';

	const musicBrainzCallbackFailed = $derived(
		page.url.searchParams.get('musicbrainz') === 'callback-error'
	);
</script>

<svelte:head><title>Library · DroppedNeedle</title></svelte:head>

<div class="min-h-[calc(100vh-200px)]">
	<PageHeader subtitle="Your scanned music library">
		{#snippet title()}Library{/snippet}
		{#snippet actions()}
			<a
				href="/library/local"
				class="group btn btn-sm gap-2 rounded-full border-0 bg-primary text-primary-content shadow-lg shadow-primary/25 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-primary/40 sm:btn-md"
			>
				<Headphones class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
				<span>Listen</span>
			</a>
			{#if authStore.isAdmin}
				<a
					href="/library/management"
					class="group btn btn-sm gap-2 rounded-full border border-base-content/15 bg-base-100/50 text-base-content backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-base-100/80 sm:btn-md"
				>
					<SlidersHorizontal
						class="h-4 w-4 transition-transform duration-200 group-hover:rotate-12"
					/>
					<span>Controls</span>
				</a>
			{:else}
				<button
					type="button"
					aria-disabled="true"
					aria-describedby="library-controls-admin-only"
					class="btn btn-sm cursor-not-allowed gap-2 rounded-full border border-base-content/10 bg-base-200/35 text-base-content/35 shadow-none sm:btn-md"
				>
					<LockKeyhole class="h-4 w-4" aria-hidden="true" />
					<span>Controls</span>
				</button>
				<span id="library-controls-admin-only" class="sr-only">
					Library controls require administrator access.
				</span>
			{/if}
		{/snippet}
	</PageHeader>
	<div class="space-y-10 px-4 pb-12 sm:space-y-12 sm:px-6 lg:px-8">
		{#if musicBrainzCallbackFailed}
			<div class="alert alert-warning" role="alert">
				<p>
					MusicBrainz couldn't return you to the contribution. Reopen it and paste the submitted
					release URL to verify it.
				</p>
			</div>
		{/if}
		<LibraryDashboard />
	</div>
</div>
