"""Follow business logic.

Following an artist subscribes you to its new-release feed and the unseen
badges built on it. This fork does not auto-download on a new release, so there
is no per-artist approval to grant and no admin standing-grant to reconcile -
following is a plain per-user preference.
"""

import logging

from infrastructure.persistence.follow_store import (
    FollowedArtist,
    FollowState,
    FollowStore,
    NewRelease,
)

logger = logging.getLogger(__name__)

_UNKNOWN_ARTIST = "Unknown Artist"


class FollowService:
    def __init__(self, follow_store: FollowStore, mb_repo) -> None:
        self._store = follow_store
        self._mb_repo = mb_repo

    async def _resolve_artist_name(self, artist_mbid: str) -> str:
        # fall back to a placeholder rather than failing the follow if MB is down
        artist = await self._mb_repo.get_artist_by_id(artist_mbid)
        if artist and artist.get("name"):
            return artist["name"]
        return _UNKNOWN_ARTIST

    async def get_status(self, user_id: str, artist_mbid: str) -> FollowState:
        return await self._store.get_follow_state(user_id, artist_mbid)

    async def set_followed(
        self, user_id: str, artist_mbid: str, followed: bool
    ) -> FollowState:
        if followed:
            name = await self._resolve_artist_name(artist_mbid)
            await self._store.follow_artist(user_id, artist_mbid, name)
        else:
            await self._store.unfollow_artist(user_id, artist_mbid)
        return await self.get_status(user_id, artist_mbid)

    async def list_following(self, user_id: str) -> list[FollowedArtist]:
        return await self._store.list_followed_artists(user_id)

    async def list_new_releases(
        self, user_id: str, limit: int, offset: int
    ) -> tuple[list[NewRelease], int]:
        return await self._store.list_new_releases_for_user(user_id, limit, offset)

    async def list_recent_releases(
        self, user_id: str, days: int, limit: int, include_owned: bool = True
    ) -> tuple[list[NewRelease], int]:
        """The release-log view (hub + New Releases page): everything from the
        window, owned albums flagged - or filtered out when include_owned=False."""
        return await self._store.list_recent_releases_for_user(
            user_id, days, limit, include_owned
        )

    async def count_unseen_new_releases(self, user_id: str) -> int:
        return await self._store.count_unseen_new_releases_for_user(user_id)

    async def mark_new_releases_seen(self, user_id: str) -> None:
        await self._store.mark_new_releases_seen(user_id)
