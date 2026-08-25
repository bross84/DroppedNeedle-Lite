from unittest.mock import AsyncMock

import pytest

from api.v1.schemas.navidrome import NavidromeAlbumSummary, NavidromeArtistSummary
from services.home.charts_service import HomeChartsService


def _service(
    *, navidrome: AsyncMock | None = None, genre_index: AsyncMock | None = None
) -> HomeChartsService:
    mb_repo = AsyncMock()
    mb_repo.search_artists_by_tag = AsyncMock(return_value=[])
    mb_repo.search_release_groups_by_tag = AsyncMock(return_value=[])
    return HomeChartsService(
        listenbrainz_repo=AsyncMock(),
        library_repo=AsyncMock(),
        musicbrainz_repo=mb_repo,
        genre_index=genre_index,
        navidrome_service=navidrome,
    )


@pytest.mark.asyncio
async def test_genre_library_section_reads_through_navidrome_when_available() -> None:
    navidrome = AsyncMock()
    navidrome.get_library_by_genre = AsyncMock(
        return_value=(
            [
                NavidromeAlbumSummary(
                    navidrome_id="alb-1",
                    name="Owned Album",
                    artist_name="Owned Artist",
                    year=2020,
                    image_url="/api/v1/navidrome/cover/alb-1",
                    musicbrainz_id="mb-alb-1",
                    artist_musicbrainz_id="mb-artist-1",
                )
            ],
            [
                NavidromeArtistSummary(
                    navidrome_id="art-1",
                    name="Owned Artist",
                    image_url="/api/v1/navidrome/cover/art-1",
                    album_count=1,
                    musicbrainz_id="mb-artist-1",
                )
            ],
        )
    )
    genre_index = AsyncMock()
    service = _service(navidrome=navidrome, genre_index=genre_index)

    result = await service.get_genre_artists("Punk", limit=10)

    navidrome.get_library_by_genre.assert_awaited_once_with("Punk", limit=50)
    genre_index.get_artists_by_genre.assert_not_awaited()
    genre_index.get_albums_by_genre.assert_not_awaited()
    assert result.library is not None
    assert result.library.artist_count == 1
    assert result.library.album_count == 1
    assert result.library.artists[0].name == "Owned Artist"
    assert result.library.artists[0].local_id == "art-1"
    assert result.library.artists[0].in_library is True
    assert result.library.albums[0].name == "Owned Album"
    assert result.library.albums[0].mbid == "mb-alb-1"
    assert result.library.albums[0].in_library is True


@pytest.mark.asyncio
async def test_genre_library_section_falls_back_to_genre_index_without_navidrome() -> (
    None
):
    genre_index = AsyncMock()
    genre_index.get_artists_by_genre = AsyncMock(
        return_value=[{"mbid": "m1", "name": "Native Artist", "album_count": 2}]
    )
    genre_index.get_albums_by_genre = AsyncMock(
        return_value=[{"mbid": "m2", "title": "Native Album"}]
    )
    service = _service(navidrome=None, genre_index=genre_index)

    result = await service.get_genre_artists("Punk", limit=10)

    genre_index.get_artists_by_genre.assert_awaited_once()
    assert result.library is not None
    assert result.library.artists[0].name == "Native Artist"
    assert result.library.albums[0].name == "Native Album"
