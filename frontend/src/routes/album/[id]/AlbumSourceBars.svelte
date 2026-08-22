<script lang="ts">
	import type {
		AlbumBasicInfo,
		AlbumTracksInfo,
		YouTubeTrackLink,
		YouTubeLink,
		YouTubeQuotaStatus,
		LocalAlbumMatch,
		NavidromeAlbumMatch
	} from '$lib/types';
	import type { SourceCallbacks } from './albumPageState.svelte';
	import AlbumYouTubeBar from '$lib/components/AlbumYouTubeBar.svelte';
	import AlbumSourceBar from '$lib/components/AlbumSourceBar.svelte';
	import LocalFilesIcon from '$lib/components/LocalFilesIcon.svelte';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';

	interface Props {
		album: AlbumBasicInfo;
		tracksInfo: AlbumTracksInfo;
		trackLinks: YouTubeTrackLink[];
		albumLink: YouTubeLink | null;
		localMatch: LocalAlbumMatch | null;
		navidromeMatch: NavidromeAlbumMatch | null;
		loadingLocal: boolean;
		loadingNavidrome: boolean;
		youtubeEnabled: boolean;
		youtubeApiConfigured: boolean;
		localfilesEnabled: boolean;
		navidromeEnabled: boolean;
		localCallbacks: SourceCallbacks;
		localDownloadCallback?: { callback: (() => void) | undefined };
		navidromeCallbacks: SourceCallbacks;
		onTrackLinksUpdate: (links: YouTubeTrackLink[]) => void;
		onAlbumLinkUpdate: (link: YouTubeLink) => void;
		onQuotaUpdate: (q: YouTubeQuotaStatus) => void;
	}

	let {
		album,
		tracksInfo,
		trackLinks,
		albumLink,
		localMatch,
		navidromeMatch,
		loadingLocal,
		loadingNavidrome,
		youtubeEnabled,
		youtubeApiConfigured,
		localfilesEnabled,
		navidromeEnabled,
		localCallbacks,
		localDownloadCallback,
		navidromeCallbacks,
		onTrackLinksUpdate,
		onAlbumLinkUpdate,
		onQuotaUpdate
	}: Props = $props();
</script>

{#if youtubeEnabled}
	<AlbumYouTubeBar
		albumId={album.musicbrainz_id}
		albumName={album.title}
		artistName={album.artist_name}
		artistId={album.artist_id}
		coverUrl={album.cover_url ?? null}
		tracks={tracksInfo.tracks}
		{trackLinks}
		{albumLink}
		apiConfigured={youtubeApiConfigured}
		{onTrackLinksUpdate}
		{onAlbumLinkUpdate}
		{onQuotaUpdate}
	/>
{/if}

{#if localfilesEnabled}
	{#if loadingLocal}
		<div class="skeleton h-14 w-full rounded-box"></div>
	{:else if localMatch?.found}
		<AlbumSourceBar
			sourceLabel="Local Files"
			sourceColor="rgb(var(--brand-localfiles))"
			trackCount={localMatch.tracks.length}
			totalTracks={tracksInfo.tracks.length}
			extraBadge={localMatch.primary_format?.toUpperCase() ?? null}
			onPlayAll={localCallbacks.onPlayAll}
			onShuffle={localCallbacks.onShuffle}
			onAddAllToQueue={localCallbacks.onAddAllToQueue}
			onPlayAllNext={localCallbacks.onPlayAllNext}
			onAddAllToPlaylist={localCallbacks.onAddAllToPlaylist}
			onDownload={localDownloadCallback?.callback}
		>
			{#snippet icon()}
				<LocalFilesIcon class="h-5 w-5" />
			{/snippet}
		</AlbumSourceBar>
	{/if}
{/if}

{#if navidromeEnabled}
	{#if loadingNavidrome}
		<div class="skeleton h-14 w-full rounded-box"></div>
	{:else if navidromeMatch?.found}
		<AlbumSourceBar
			sourceLabel="Navidrome"
			sourceColor="rgb(var(--brand-navidrome))"
			trackCount={navidromeMatch.tracks.length}
			totalTracks={tracksInfo.tracks.length}
			onPlayAll={navidromeCallbacks.onPlayAll}
			onShuffle={navidromeCallbacks.onShuffle}
			onAddAllToQueue={navidromeCallbacks.onAddAllToQueue}
			onPlayAllNext={navidromeCallbacks.onPlayAllNext}
			onAddAllToPlaylist={navidromeCallbacks.onAddAllToPlaylist}
		>
			{#snippet icon()}
				<NavidromeIcon class="h-5 w-5" />
			{/snippet}
		</AlbumSourceBar>
	{/if}
{/if}
