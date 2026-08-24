"""Navidrome-grounded artwork selection for every genre surface."""

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

from api.v1.schemas.home import GenreArtwork, GenreArtworkAlbum
from infrastructure.cache.cache_keys import GENRE_ARTWORK_PREFIX
from infrastructure.cache.memory_cache import CacheInterface

if TYPE_CHECKING:
    from services.navidrome_library_service import NavidromeLibraryService

ALGORITHM_VERSION = "v3"
GENRE_ARTWORK_TTL_SECONDS = 86_400


class GenreArtworkService:
    def __init__(
        self,
        navidrome: "NavidromeLibraryService",
        cache: CacheInterface,
    ) -> None:
        self._navidrome = navidrome
        self._cache = cache

    @staticmethod
    def _cache_key(genre: str) -> str:
        folded = genre.strip().casefold()
        return f"{GENRE_ARTWORK_PREFIX}{ALGORITHM_VERSION}:{folded}"

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
            version=f"{ALGORITHM_VERSION}:{digest}",
        )

    async def get_artwork_batch(self, genres: list[str]) -> dict[str, GenreArtwork]:
        result: dict[str, GenreArtwork] = {}
        misses: list[str] = []
        for genre in genres:
            cached = await self._cache.get(self._cache_key(genre))
            if isinstance(cached, GenreArtwork):
                result[genre] = cached
            else:
                misses.append(genre)

        if misses:
            candidate_lists = await asyncio.gather(
                *(self._navidrome.get_genre_artwork_candidates(genre) for genre in misses)
            )
            for genre, candidates in zip(misses, candidate_lists):
                artwork = self._select(candidates)
                await self._cache.set(
                    self._cache_key(genre), artwork, GENRE_ARTWORK_TTL_SECONDS
                )
                result[genre] = artwork

        return result
