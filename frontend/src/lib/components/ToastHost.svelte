<script lang="ts">
	import { toastStore } from '$lib/stores/toast';
	import Toast from './Toast.svelte';

	// Renders whatever toastStore currently holds. Mounted once in the root
	// layout: ~60 modules call toastStore.show(), but nothing subscribed to the
	// store, so every one of those messages - saved, failed, blocked - was
	// written to a variable no screen displayed. Toast.svelte is prop-driven and
	// used with local state on a few pages; this is the store's renderer.
	//
	// duration is 0 so Toast's own dismissal timer stays off: the store already
	// clears itself, and two timers racing would hide it early or leave it stuck.
	const current = $derived($toastStore);
</script>

{#if current}
	<Toast show message={current.message} type={current.type} duration={0} />
{/if}
