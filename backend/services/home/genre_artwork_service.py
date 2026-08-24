"""Navidrome-grounded artwork selection for every genre surface."""

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

from api.v1.schemas.home import GenreArtwork, GenreArtworkAlbum

if TYPE_CHECKING:
    from services.navidrome_library_service import NavidromeLibraryService


class GenreArtworkService:
    """Picks a handful of real album covers per genre, straight from Navidrome.

    Deliberately uncached beyond NavidromeRepository's own short-lived list
    cache (5 minutes): this runs fresh on every Home/Discover load (see
    HomeService._apply_genre_artwork), so a tag correction made in Navidrome
    shows up on the user's next page load instead of waiting out a long TTL.
    """

    def __init__(self, navidrome: "NavidromeLibraryService") -> None:
        self._navidrome = navidrome

    @staticmethod
    def _select(candidates: list[dict[str, str]]) -> GenreArtwork:
        selected: list[GenreArtworkAlbum] = []
        selected_artists: set[str] = set()
        remaining = list(candidates)

        while remaining and len(selected) < 4:
            unseen = [c for c in remaining if c["artist_key"] not in selected_artists]
            candidate = (unseen or remaining)[0]
            remaining.remove(candidate)
            selected_artists.add(candidate["artist_key"])
            selected.append(
                GenreArtworkAlbum(
                    album_id=candidate["album_id"],
                    album_title=candidate["album_title"],
                    album_artist_name=candidate["album_artist_name"] or None,
                    image_url=f"/api/v1/navidrome/cover/{candidate['album_id']}",
                )
            )

        digest = hashlib.sha256(
            "|".join(album.album_id for album in selected).encode()
        ).hexdigest()[:12]
        return GenreArtwork(
            kind="collage" if selected else "gradient",
            albums=selected,
            version=digest,
        )

    async def get_artwork_batch(self, genres: list[str]) -> dict[str, GenreArtwork]:
        candidate_lists = await asyncio.gather(
            *(self._navidrome.get_genre_artwork_candidates(genre) for genre in genres)
        )
        return {
            genre: self._select(candidates)
            for genre, candidates in zip(genres, candidate_lists)
        }
