<script lang="ts">
	import { Heart } from 'lucide-svelte';
	import { getFollowStatusQuery } from '$lib/queries/following/FollowQueries.svelte';
	import { createSetFollowMutation } from '$lib/queries/following/FollowMutations.svelte';
	import type { FollowStatus } from '$lib/queries/following/types';

	interface Props {
		artistMbid: string;
	}

	let { artistMbid }: Props = $props();

	const NOT_FOLLOWING: FollowStatus = {
		followed: false
	};

	const statusQuery = getFollowStatusQuery(() => artistMbid);
	const followMutation = createSetFollowMutation(() => artistMbid);

	const status = $derived(statusQuery.data ?? NOT_FOLLOWING);
	const busy = $derived(statusQuery.isPending || followMutation.isPending);
</script>

<div class="flex flex-col gap-2">
	<button
		type="button"
		onclick={() => followMutation.mutate(!status.followed)}
		disabled={busy}
		aria-pressed={status.followed}
		aria-label={status.followed ? 'Following this artist, click to unfollow' : 'Follow this artist'}
		class="btn btn-sm w-fit gap-2 {status.followed ? 'btn-accent' : 'btn-outline btn-accent'}"
	>
		<Heart class="h-4 w-4" fill={status.followed ? 'currentColor' : 'none'} />
		{status.followed ? 'Following' : 'Follow'}
	</button>
</div>
