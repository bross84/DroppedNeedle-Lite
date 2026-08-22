<script lang="ts">
	import type {
		AlbumBasicInfo,
		YouTubeTrackLink,
		YouTubeQuotaStatus,
		LocalAlbumMatch,
		LocalTrackInfo,
		NavidromeAlbumMatch,
		NavidromeTrackInfo
	} from '$lib/types';
	import type { MenuItem } from '$lib/components/ContextMenu.svelte';
	import type { RenderedTrackSection } from './albumTrackResolvers';
	import { resolveSourceTrack } from './albumTrackResolvers';
	import { normalizeDiscNumber, getDiscTrackKey } from '$lib/player/queueHelpers';
	import { formatDuration } from '$lib/utils/formatting';
	import { colors } from '$lib/colors';
	import { playerStore } from '$lib/stores/player.svelte';
	import NowPlayingIndicator from '$lib/components/NowPlayingIndicator.svelte';
	import TrackPlayButton from '$lib/components/TrackPlayButton.svelte';
	import SampleButton from '$lib/components/discover/SampleButton.svelte';
	import TrackSourceButton from '$lib/components/TrackSourceButton.svelte';
	import ContextMenu from '$lib/components/ContextMenu.svelte';
	import LocalFilesIcon from '$lib/components/LocalFilesIcon.svelte';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';
	import LibraryFormatBadge from '$lib/components/library/LibraryFormatBadge.svelte';
	import LibraryTrackRow from '$lib/components/library/LibraryTrackRow.svelte';
	import { ChevronDown, TriangleAlert, TrendingUp, Check } from 'lucide-svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import type { LibraryFileMeta, DownloadTask, HeldImport } from '$lib/types';
	import TrackRequestButton from '$lib/components/downloads/TrackRequestButton.svelte';
	import TrackDownloadStatus from '$lib/components/downloads/TrackDownloadStatus.svelte';
	import HeldTrackReview from '$lib/components/downloads/HeldTrackReview.svelte';
	import { integrationStore } from '$lib/stores/integration';
	import { authStore } from '$lib/stores/authStore.svelte';
	import { requestUpgradeTrack } from '$lib/queries/downloads/UpgradeQueries.svelte';
	import { toastStore } from '$lib/stores/toast';

	interface Props {
		album: AlbumBasicInfo;
		renderedTrackSections: RenderedTrackSection[];
		trackLinkMap: Map<string, YouTubeTrackLink>;
		localMatch: LocalAlbumMatch | null;
		navidromeMatch: NavidromeAlbumMatch | null;
		localTrackMap: Map<string, LocalTrackInfo>;
		navidromeTrackMap: Map<string, NavidromeTrackInfo>;
		localTracks: LocalTrackInfo[];
		navidromeTracks: NavidromeTrackInfo[];
		trackLinks: YouTubeTrackLink[];
		youtubeEnabled: boolean;
		youtubeApiConfigured: boolean;
		localfilesEnabled: boolean;
		navidromeEnabled: boolean;
		libraryTracksByRecording?: Map<string, LibraryFileMeta>;
		libraryTracksByPosition?: Map<string, LibraryFileMeta>;
		heldByRecording?: Map<string, HeldImport>;
		heldByPosition?: Map<string, HeldImport>;
		trackDownloadTasks?: Map<string, DownloadTask>;
		releaseGroupMbid?: string;
		onPlaySourceTrack: (
			source: 'local' | 'navidrome',
			trackPosition: number,
			discNumber: number,
			title: string
		) => void;
		onTrackGenerated: (link: YouTubeTrackLink) => void;
		onQuotaUpdate: (q: YouTubeQuotaStatus) => void;
		getTrackContextMenuItems: (
			track: { position: number; disc_number?: number | null; title: string },
			resolvedLocal: LocalTrackInfo | null,
			resolvedNavidrome: NavidromeTrackInfo | null
		) => MenuItem[];
	}

	let {
		album,
		renderedTrackSections,
		trackLinkMap,
		localMatch,
		navidromeMatch,
		localTrackMap,
		navidromeTrackMap,
		localTracks,
		navidromeTracks,
		trackLinks,
		youtubeEnabled,
		youtubeApiConfigured,
		localfilesEnabled,
		navidromeEnabled,
		libraryTracksByRecording = new Map(),
		libraryTracksByPosition = new Map(),
		heldByRecording = new Map(),
		heldByPosition = new Map(),
		trackDownloadTasks = new Map(),
		releaseGroupMbid = '',
		onPlaySourceTrack,
		onTrackGenerated,
		onQuotaUpdate,
		getTrackContextMenuItems
	}: Props = $props();

	const expandedRows = new SvelteSet<number>();
	function toggleRow(idx: number) {
		if (expandedRows.has(idx)) expandedRows.delete(idx);
		else expandedRows.add(idx);
	}

	// rows whose "held · couldn't verify" review panel is open
	const heldOpen = new SvelteSet<number>();
	function toggleHeld(idx: number) {
		if (heldOpen.has(idx)) heldOpen.delete(idx);
		else heldOpen.add(idx);
	}

	// Per-track quality upgrade (admin/trusted, CollectionManagement D18): shown on
	// in-library tracks sitting below the cutoff while upgrades are on.
	const upgradeTrack = requestUpgradeTrack();
	const upgradeQueuedRecordings = new SvelteSet<string>();
	async function handleTrackUpgrade(
		recordingMbid: string,
		title: string,
		durationMs: number | null | undefined
	) {
		try {
			const result = await upgradeTrack.mutateAsync({
				recording_mbid: recordingMbid,
				artist_name: album.artist_name,
				track_title: title,
				album_title: album.title,
				duration_seconds: durationMs ? Math.round(durationMs / 1000) : null,
				release_group_mbid: releaseGroupMbid || album.musicbrainz_id,
				artist_mbid: album.artist_id
			});
			if (result.status === 'queued') {
				upgradeQueuedRecordings.add(recordingMbid);
				toastStore.show({ message: `Looking for a better copy of ${title}`, type: 'success' });
			} else {
				toastStore.show({ message: 'Already at or above the cutoff', type: 'info' });
			}
		} catch (e) {
			toastStore.show({
				message: e instanceof Error ? e.message : "Couldn't start that upgrade",
				type: 'error'
			});
		}
	}
</script>

<div class="bg-base-200 rounded-box overflow-visible">
	<ul class="list">
		{#each renderedTrackSections as section (section.discNumber)}
			{#if renderedTrackSections.length > 1}
				<li class="list-row min-h-0 cursor-default px-3 sm:px-4 pt-4 pb-2">
					<div
						class="inline-flex items-center gap-2 rounded-full border border-base-content/10 bg-base-100/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] opacity-70"
					>
						<span class="h-1.5 w-1.5 rounded-full bg-accent"></span>
						Disc {section.discNumber}
					</div>
				</li>
			{/if}
			{#each section.items as row (row.globalIndex)}
				{@const track = row.track}
				{@const trackDiscNumber = normalizeDiscNumber(track.disc_number)}
				{@const tl = trackLinkMap.get(getDiscTrackKey(track)) ?? null}
				{@const localTrack = resolveSourceTrack(
					trackDiscNumber,
					track.position,
					row.globalIndex,
					localTrackMap,
					localTracks
				)}
				{@const navidromeTrack = resolveSourceTrack(
					trackDiscNumber,
					track.position,
					row.globalIndex,
					navidromeTrackMap,
					navidromeTracks
				)}
				{@const isCurrentlyPlaying =
					playerStore.nowPlaying?.albumId === album.musicbrainz_id &&
					(playerStore.currentQueueItem?.discNumber ?? 1) === trackDiscNumber &&
					playerStore.currentQueueItem?.trackNumber === track.position &&
					playerStore.isPlaying}
				{@const showLocalBtn = localfilesEnabled && localMatch?.found}
				{@const showNavidromeBtn = navidromeEnabled && navidromeMatch?.found}
				{@const hasAnySource = tl !== null || localTrack !== null || navidromeTrack !== null}
				{@const showPreview = !hasAnySource}
				{@const libMeta =
					(track.recording_id ? libraryTracksByRecording.get(track.recording_id) : undefined) ??
					libraryTracksByPosition.get(
						getDiscTrackKey({ disc_number: trackDiscNumber, track_number: track.position })
					)}
				{@const heldMeta = libMeta
					? undefined
					: ((track.recording_id ? heldByRecording.get(track.recording_id) : undefined) ??
						heldByPosition.get(
							getDiscTrackKey({ disc_number: trackDiscNumber, track_number: track.position })
						))}
				{@const trackTask = track.recording_id
					? (trackDownloadTasks.get(track.recording_id) ?? null)
					: null}
				{@const showTrackDownload = !libMeta && !!trackTask}
				{@const showRequest =
					!libMeta &&
					!trackTask &&
					!heldMeta &&
					!!track.recording_id &&
					$integrationStore.download_client}
				{@const upgradeRecordingId =
					track.recording_id ?? libMeta?.musicbrainz_recording_id ?? null}
				{@const showUpgrade =
					!!libMeta?.below_cutoff &&
					authStore.isTrusted &&
					!!upgradeRecordingId &&
					!trackTask &&
					$integrationStore.download_client}
				<li
					class="list-row group hover:bg-base-300/50 transition-colors p-3 sm:p-4"
					style={isCurrentlyPlaying ? `background-color: ${colors.accent}20;` : ''}
				>
					<div class="list-col-grow flex items-center gap-4 w-full">
						<div
							class="font-medium w-8 text-center shrink-0 {isCurrentlyPlaying
								? ''
								: 'text-base-content/60'}"
							style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}
						>
							{#if isCurrentlyPlaying}
								<NowPlayingIndicator />
							{:else}
								{track.position}
							{/if}
						</div>

						{#if libMeta}
							<div class="shrink-0">
								<LibraryFormatBadge format={libMeta.format} size="badge-xs" />
							</div>
						{/if}

						<div class="flex-1 min-w-0">
							<div
								class="font-medium truncate"
								style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}
							>
								{track.title}
							</div>
							{#if libMeta?.artist_name && libMeta.artist_name !== album.artist_name}
								<div class="truncate text-xs text-base-content/60">{libMeta.artist_name}</div>
							{/if}
						</div>

						<div class="text-base-content/60 text-sm shrink-0">
							{formatDuration(track.length)}
						</div>

						{#if youtubeEnabled || showPreview || showLocalBtn || showNavidromeBtn || showRequest || showTrackDownload || heldMeta || showUpgrade}
							<div class="flex items-center gap-1.5 shrink-0 ml-auto">
								{#if showTrackDownload && trackTask}
									<TrackDownloadStatus task={trackTask} />
								{/if}
								{#if heldMeta}
									<button
										class="btn btn-ghost btn-xs gap-1 text-warning"
										onclick={() => toggleHeld(row.globalIndex)}
										aria-expanded={heldOpen.has(row.globalIndex)}
										title="Downloaded but couldn't verify - review it"
									>
										<TriangleAlert class="h-3.5 w-3.5" /> held
									</button>
								{/if}
								{#if showRequest && track.recording_id}
									<TrackRequestButton
										recordingMbid={track.recording_id}
										trackTitle={track.title}
										artistName={album.artist_name}
										albumMbid={releaseGroupMbid || album.musicbrainz_id}
										albumTitle={album.title}
										durationSeconds={track.length ? Math.round(track.length / 1000) : null}
										artistMbid={album.artist_id}
									/>
								{/if}
								{#if showUpgrade && upgradeRecordingId}
									{#if upgradeQueuedRecordings.has(upgradeRecordingId)}
										<span class="btn btn-ghost btn-xs gap-1 pointer-events-none text-success">
											<Check class="h-3.5 w-3.5" /> queued
										</span>
									{:else}
										<button
											class="btn btn-ghost btn-xs gap-1 text-primary"
											disabled={upgradeTrack.isPending}
											onclick={() =>
												void handleTrackUpgrade(upgradeRecordingId, track.title, track.length)}
											title="Below your quality cutoff - find a better copy"
										>
											<TrendingUp class="h-3.5 w-3.5" /> upgrade
										</button>
									{/if}
								{/if}
								{#if showPreview}
									<SampleButton
										sampleKey={`track:${album.artist_name}|${track.title}`}
										artist={album.artist_name}
										title={track.title}
										kind="track"
										size="xs"
										albumMbid={album.musicbrainz_id}
										artistMbid={album.artist_id}
										coverUrl={album.cover_url ?? null}
									/>
								{/if}

								{#if youtubeEnabled}
									<TrackPlayButton
										trackNumber={track.position}
										discNumber={trackDiscNumber}
										trackName={track.title}
										trackLink={tl}
										allTrackLinks={trackLinks}
										albumId={album.musicbrainz_id}
										albumName={album.title}
										artistName={album.artist_name}
										coverUrl={album.cover_url ?? null}
										artistId={album.artist_id}
										apiConfigured={youtubeApiConfigured}
										onGenerated={onTrackGenerated}
										{onQuotaUpdate}
									/>
								{/if}

								{#if showLocalBtn}
									<TrackSourceButton
										available={localTrack !== null}
										sourceColor="rgb(var(--brand-localfiles))"
										onclick={() =>
											onPlaySourceTrack('local', track.position, trackDiscNumber, track.title)}
										ariaLabel={localTrack ? 'Play local file' : 'Not available locally'}
									>
										{#snippet icon()}
											<LocalFilesIcon class="h-4 w-4" />
										{/snippet}
									</TrackSourceButton>
								{/if}

								{#if showNavidromeBtn}
									<TrackSourceButton
										available={navidromeTrack !== null}
										sourceColor="rgb(var(--brand-navidrome))"
										onclick={() =>
											onPlaySourceTrack('navidrome', track.position, trackDiscNumber, track.title)}
										ariaLabel={navidromeTrack ? 'Play on Navidrome' : 'Not available on Navidrome'}
									>
										{#snippet icon()}
											<NavidromeIcon class="h-4 w-4" />
										{/snippet}
									</TrackSourceButton>
								{/if}

								<div>
									<ContextMenu
										items={getTrackContextMenuItems(track, localTrack, navidromeTrack)}
										position="end"
										size="xs"
									/>
								</div>
							</div>
						{/if}

						{#if libMeta}
							<button
								class="btn btn-ghost btn-xs btn-circle shrink-0"
								onclick={() => toggleRow(row.globalIndex)}
								aria-label={expandedRows.has(row.globalIndex)
									? 'Hide file details'
									: 'Show file details'}
							>
								<ChevronDown
									class="h-4 w-4 transition-transform {expandedRows.has(row.globalIndex)
										? 'rotate-180'
										: ''}"
								/>
							</button>
						{/if}
					</div>
				</li>
				{#if libMeta && expandedRows.has(row.globalIndex)}
					<li class="list-row p-0">
						<LibraryTrackRow meta={libMeta} />
					</li>
				{/if}
				{#if heldMeta && heldOpen.has(row.globalIndex)}
					<li class="list-row p-0">
						<div class="w-full px-3 pb-3 sm:px-4">
							<HeldTrackReview held={heldMeta} />
						</div>
					</li>
				{/if}
			{/each}
		{/each}
	</ul>
</div>
