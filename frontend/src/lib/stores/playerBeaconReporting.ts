import type { QueueItem } from '$lib/player/types';
import { isPlexScrobbleEnabled } from '$lib/player/plexPlaybackApi';

export function createBeforeUnloadHandler(
	getState: () => {
		currentItem: QueueItem | null;
		progress: number;
	},
	navidromeScrobbleUrl: (trackSourceId: string) => string,
	plexScrobbleUrl: (ratingKey: string) => string
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

		if (
			currentItem?.sourceType === 'plex' &&
			currentItem.plexRatingKey &&
			progress > 30 &&
			isPlexScrobbleEnabled()
		) {
			navigator.sendBeacon(
				plexScrobbleUrl(currentItem.plexRatingKey),
				new Blob([], { type: 'application/json' })
			);
		}
	};
}
