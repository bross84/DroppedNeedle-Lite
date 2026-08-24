import inspect
from unittest.mock import AsyncMock

import pytest

from api.v1.schemas.home import GenreArtwork
from services.home.genre_artwork_service import GenreArtworkService


def test_service_constructor_takes_navidrome_only() -> None:
    assert list(inspect.signature(GenreArtworkService).parameters) == ["navidrome"]


def _candidate(
    album_id: str, *, artist_key: str, title: str | None = None
) -> dict[str, str]:
    return {
        "album_id": album_id,
        "album_title": title or f"Album {album_id}",
        "album_artist_name": f"Artist {artist_key}",
        "artist_key": artist_key,
    }


def _navidrome(payload: dict[str, list[dict[str, str]]]) -> AsyncMock:
    navidrome = AsyncMock()

    async def get_genre_artwork_candidates(genre: str, count: int = 60):
        return payload.get(genre, [])

    navidrome.get_genre_artwork_candidates.side_effect = get_genre_artwork_candidates
    return navidrome


@pytest.mark.asyncio
async def test_batch_fetches_every_genre_from_navidrome_in_parallel() -> None:
    navidrome = _navidrome({"Latin": [], "Electronic": []})
    service = GenreArtworkService(navidrome)

    result = await service.get_artwork_batch(["Latin", "Electronic"])

    assert navidrome.get_genre_artwork_candidates.await_count == 2
    assert all(item.kind == "gradient" for item in result.values())


@pytest.mark.asyncio
async def test_selection_prefers_artist_diversity_and_caps_at_four() -> None:
    candidates = [
        _candidate("a", artist_key="same"),
        _candidate("b", artist_key="same"),
        _candidate("c", artist_key="other"),
        _candidate("d", artist_key="third"),
        _candidate("e", artist_key="fourth"),
    ]
    navidrome = _navidrome({"Rock": candidates})
    service = GenreArtworkService(navidrome)

    result = await service.get_artwork_batch(["Rock"])
    selected = result["Rock"].albums

    assert result["Rock"].kind == "collage"
    assert len(selected) == 4
    assert {album.album_id for album in selected} == {"a", "c", "d", "e"}
    assert all(
        album.image_url == f"/api/v1/navidrome/cover/{album.album_id}"
        for album in selected
    )


@pytest.mark.asyncio
async def test_no_candidates_falls_back_to_gradient() -> None:
    navidrome = _navidrome({"Jazz": []})
    service = GenreArtworkService(navidrome)

    result = await service.get_artwork_batch(["Jazz"])

    assert result["Jazz"] == GenreArtwork(kind="gradient", version="e3b0c44298fc")


@pytest.mark.asyncio
async def test_every_call_asks_navidrome_fresh_no_internal_cache() -> None:
    navidrome = _navidrome({"Indie": [_candidate("x", artist_key="one")]})
    service = GenreArtworkService(navidrome)

    await service.get_artwork_batch(["Indie"])
    await service.get_artwork_batch(["Indie"])

    assert navidrome.get_genre_artwork_candidates.await_count == 2
