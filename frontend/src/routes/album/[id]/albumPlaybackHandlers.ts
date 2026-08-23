import type {
	AlbumBasicInfo,
	LocalAlbumMatch,
	LocalTrackInfo,
	NavidromeAlbumMatch,
	NavidromeTrackInfo,
	Track
} from '$lib/types';
import type { QueueItem, PlaybackMeta } from '$lib/player/types';
import type { TrackMeta, TrackSourceData } from '$lib/player/queueHelpers';
import {
	buildQueueItem,
	buildQueueItemsFromLocal,
	buildQueueItemsFromNavidrome,
	compareDiscTrack,
	getDiscTrackKey,
	normalizeDiscNumber
} from '$lib/player/queueHelpers';
import { getCoverUrl } from '$lib/utils/errorHandling';
import { launchLocalPlayback } from '$lib/player/launchLocalPlayback';
import { launchNavidromePlayback } from '$lib/player/launchNavidromePlayback';
import { playerStore } from '$lib/stores/player.svelte';
import type { MenuItem } from '$lib/components/ContextMenu.svelte';
import { ListPlus, ListStart, ListMusic, Download } from 'lucide-svelte';
import { downloadFile } from '$lib/utils/downloadHelper';
import { API } from '$lib/constants';
import type { SourceCallbacks } from './albumPageState.svelte';

function getPlaybackMeta(album: AlbumBasicInfo): PlaybackMeta {
	return {
		albumId: album.musicbrainz_id,
		albumName: album.title,
		artistName: album.artist_name,
		coverUrl: getCoverUrl(album.cover_url ?? null, album.musicbrainz_id),
		artistId: album.artist_id
	};
}

function getTrackMeta(album: AlbumBasicInfo): TrackMeta {
	return {
		albumId: album.musicbrainz_id,
		albumName: album.title,
		artistName: album.artist_name,
		coverUrl: album.cover_url ?? null,
		artistId: album.artist_id
	};
}

type SourceTrack = {
	track_number: number;
	disc_number?: number | null;
	title: string;
};

function withCanonicalTrackTitles<T extends SourceTrack>(
	tracks: T[],
	canonicalTracks: Track[]
): T[] {
	if (canonicalTracks.length === 0) return tracks;

	const titlesByPosition = new Map(
		canonicalTracks.map((track) => [getDiscTrackKey(track), track.title] as const)
	);
	const sourceKeys = tracks
		.filter(
			(track) => Number.isFinite(Number(track.track_number)) && Number(track.track_number) > 0
		)
		.map((track) => getDiscTrackKey(track));
	const numberingIsUnusable =
		sourceKeys.length < tracks.length || new Set(sourceKeys).size < sourceKeys.length;
	const orderedCanonicalTracks = [...canonicalTracks].sort(compareDiscTrack);

	return tracks.map((track, index) => {
		const canonicalTitle =
			titlesByPosition.get(getDiscTrackKey(track)) ??
			(numberingIsUnusable ? orderedCanonicalTracks[index]?.title : undefined);
		return canonicalTitle && canonicalTitle !== track.title
			? { ...track, title: canonicalTitle }
			: track;
	});
}

function playSource<T extends SourceTrack>(
	match: { tracks: T[] } | null,
	launcher: (tracks: T[], startIndex: number, shuffle: boolean, meta: PlaybackMeta) => void,
	album: AlbumBasicInfo,
	canonicalTracks: Track[],
	opts: {
		startTrack?: number;
		startDisc?: number;
		startTitle?: string;
		shuffle?: boolean;
	} = {}
): void {
	if (!match?.tracks.length) return;
	const orderedTracks = withCanonicalTrackTitles(
		[...match.tracks].sort(compareDiscTrack),
		canonicalTracks
	);
	let idx = 0;
	if (opts.startTrack !== undefined) {
		idx = orderedTracks.findIndex(
			(t) =>
				t.track_number === opts.startTrack &&
				normalizeDiscNumber(t.disc_number) === normalizeDiscNumber(opts.startDisc)
		);
		if (idx === -1 && opts.startTitle) {
			const lower = opts.startTitle.toLowerCase();
			const titleMatcher = (t: T) => {
				const tLower = t.title.toLowerCase();
				return tLower === lower || tLower.includes(lower) || lower.includes(tLower);
			};
			if (opts.startDisc !== undefined) {
				const targetDisc = normalizeDiscNumber(opts.startDisc);
				idx = orderedTracks.findIndex(
					(t) => normalizeDiscNumber(t.disc_number) === targetDisc && titleMatcher(t)
				);
			}
			if (idx === -1) idx = orderedTracks.findIndex(titleMatcher);
		}
		if (idx === -1) return;
	}
	launcher(orderedTracks, idx, opts.shuffle ?? false, getPlaybackMeta(album));
}

export function playSourceTrack(
	source: 'local' | 'navidrome',
	trackPosition: number,
	discNumber: number,
	title: string,
	album: AlbumBasicInfo,
	localMatch: LocalAlbumMatch | null,
	navidromeMatch: NavidromeAlbumMatch | null,
	canonicalTracks: Track[]
): void {
	const opts = { startTrack: trackPosition, startDisc: discNumber, startTitle: title };
	if (source === 'local') playSource(localMatch, launchLocalPlayback, album, canonicalTracks, opts);
	else playSource(navidromeMatch, launchNavidromePlayback, album, canonicalTracks, opts);
}

function buildTrackQueueItem(
	track: { position: number; disc_number?: number | null; title: string },
	album: AlbumBasicInfo,
	resolvedLocal: LocalTrackInfo | null,
	resolvedNavidrome: NavidromeTrackInfo | null = null
): QueueItem | null {
	const sourceData: TrackSourceData = {
		trackPosition: track.position,
		discNumber: normalizeDiscNumber(track.disc_number),
		trackTitle: track.title,
		trackLength:
			resolvedLocal?.duration_seconds ?? resolvedNavidrome?.duration_seconds ?? undefined,
		localTrack: resolvedLocal,
		navidromeTrack: resolvedNavidrome
	};
	return buildQueueItem(getTrackMeta(album), sourceData);
}

export function getTrackContextMenuItems(
	track: { position: number; disc_number?: number | null; title: string },
	album: AlbumBasicInfo,
	resolvedLocal: LocalTrackInfo | null,
	resolvedNavidrome: NavidromeTrackInfo | null,
	playlistModalRef: { open: (tracks: QueueItem[]) => void } | null
): MenuItem[] {
	const queueItem = buildTrackQueueItem(track, album, resolvedLocal, resolvedNavidrome);
	const hasSource = queueItem !== null;
	const items: MenuItem[] = [
		{
			label: 'Add to Queue',
			icon: ListPlus,
			onclick: () => {
				if (queueItem) playerStore.addToQueue(queueItem);
			},
			disabled: !hasSource
		},
		{
			label: 'Play Next',
			icon: ListStart,
			onclick: () => {
				if (queueItem) playerStore.playNext(queueItem);
			},
			disabled: !hasSource
		},
		{
			label: 'Add to Playlist',
			icon: ListMusic,
			onclick: () => {
				if (queueItem) playlistModalRef?.open([queueItem]);
			},
			disabled: !hasSource
		}
	];
	if (resolvedLocal) {
		items.push({
			label: 'Download',
			icon: Download,
			onclick: () => downloadFile(API.download.localTrack(resolvedLocal.track_file_id))
		});
	}
	return items;
}

function getSourceQueueItems(
	source: 'local' | 'navidrome',
	album: AlbumBasicInfo,
	localTracks: LocalTrackInfo[],
	navidromeTracks: NavidromeTrackInfo[],
	canonicalTracks: Track[]
): QueueItem[] {
	const meta = getTrackMeta(album);
	if (source === 'navidrome')
		return buildQueueItemsFromNavidrome(
			withCanonicalTrackTitles([...navidromeTracks].sort(compareDiscTrack), canonicalTracks),
			meta
		);
	return buildQueueItemsFromLocal(
		withCanonicalTrackTitles([...localTracks].sort(compareDiscTrack), canonicalTracks),
		meta
	);
}

export function buildSourceCallbacks<
	TTrack extends { track_number: number; disc_number?: number | null; title: string },
	TMatch extends { tracks: TTrack[] } | null
>(
	matchGetter: () => TMatch,
	launcher: (
		tracks: TTrack[],
		startIndex: number | undefined,
		shuffle: boolean | undefined,
		meta: PlaybackMeta
	) => void,
	source: 'local' | 'navidrome',
	albumGetter: () => AlbumBasicInfo | null,
	tracksGetters: {
		local: () => LocalTrackInfo[];
		navidrome: () => NavidromeTrackInfo[];
	},
	canonicalTracksGetter: () => Track[],
	playlistModalRefGetter: () => { open: (tracks: QueueItem[]) => void } | null
): SourceCallbacks {
	return {
		onPlayAll: () => {
			const a = albumGetter();
			if (a) playSource(matchGetter(), launcher, a, canonicalTracksGetter());
		},
		onShuffle: () => {
			const a = albumGetter();
			if (a) playSource(matchGetter(), launcher, a, canonicalTracksGetter(), { shuffle: true });
		},
		onAddAllToQueue: () => {
			const a = albumGetter();
			if (!a) return;
			const items = getSourceQueueItems(
				source,
				a,
				tracksGetters.local(),
				tracksGetters.navidrome(),
				canonicalTracksGetter()
			);
			if (items.length > 0) playerStore.addMultipleToQueue(items);
		},
		onPlayAllNext: () => {
			const a = albumGetter();
			if (!a) return;
			const items = getSourceQueueItems(
				source,
				a,
				tracksGetters.local(),
				tracksGetters.navidrome(),
				canonicalTracksGetter()
			);
			if (items.length > 0) playerStore.playMultipleNext(items);
		},
		onAddAllToPlaylist: () => {
			const a = albumGetter();
			if (!a) return;
			const items = getSourceQueueItems(
				source,
				a,
				tracksGetters.local(),
				tracksGetters.navidrome(),
				canonicalTracksGetter()
			);
			if (items.length > 0) playlistModalRefGetter()?.open(items);
		}
	};
}
