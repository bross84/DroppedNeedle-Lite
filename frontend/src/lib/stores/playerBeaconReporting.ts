import type { QueueItem } from '$lib/player/types';

export function createBeforeUnloadHandler(
	getState: () => {
		currentItem: QueueItem | null;
		progress: number;
	},
	navidromeScrobbleUrl: (trackSourceId: string) => string
): () => void {
	return () => {
		if (typeof navigator === 'undefined' || typeof navigator.sendBeacon !== 'function') return;
		const { currentItem, progress } = getState();

		if (currentItem?.sourceType === 'navidrome' && progress > 30) {
			navigator.sendBeacon(
				navidromeScrobbleUrl(currentItem.trackSourceId),
				new Blob([], { type: 'application/json' })
			);
		}
	};
}
