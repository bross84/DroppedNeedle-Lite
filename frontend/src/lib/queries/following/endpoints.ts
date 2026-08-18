import { API } from '$lib/constants';

// the current user is resolved server-side from the session cookie
export const FOLLOW_ENDPOINTS = {
	status: (mbid: string) => API.artist.follow(mbid),
	setFollow: (mbid: string) => API.artist.follow(mbid),
	followedArtists: () => API.following.artists(),
	recentReleases: (days: number, limit: number, includeOwned: boolean) =>
		API.following.recentReleases(days, limit, includeOwned),
	newReleasesUnseenCount: () => API.following.newReleasesUnseenCount(),
	markNewReleasesSeen: () => API.following.markNewReleasesSeen(),
	concerts: () => API.following.concerts(),
	concertCities: () => API.following.concertCities(),
	concertCitySearch: (q: string) => API.following.concertCitySearch(q),
	concertsUnseenCount: () => API.following.concertsUnseenCount(),
	markConcertsSeen: () => API.following.markConcertsSeen()
} as const;
