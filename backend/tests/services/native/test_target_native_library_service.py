from unittest.mock import AsyncMock

import pytest

from api.v1.schemas.navidrome import (
    NavidromeAlbumSummary,
    NavidromeArtistSummary,
    NavidromeLibraryStats,
    NavidromeTrackInfo,
)
from services.native.target_native_library_service import TargetNativeLibraryService


def _store(
    *,
    albums: tuple[list[dict], int] = ([], 0),
    artists: tuple[list[dict], int] = ([], 0),
    tracks: tuple[list[dict], int] = ([], 0),
    stats: dict | None = None,
) -> AsyncMock:
    store = AsyncMock()
    store.list_target_albums = AsyncMock(return_value=albums)
    store.list_target_artists = AsyncMock(return_value=artists)
    store.list_target_tracks = AsyncMock(return_value=tracks)
    store.get_target_library_stats = AsyncMock(
        return_value=stats
        or {
            "total_albums": 0,
            "total_artists": 0,
            "total_tracks": 0,
            "total_size_bytes": 0,
            "format_breakdown": {},
            "unmatched_count": 0,
            "local_only_count": 0,
            "last_scan_at": None,
        }
    )
    return store


def _populated_album_row() -> dict:
    return {
        "release_group_mbid": "rg-1",
        "album_title": "Native Album",
        "album_artist_name": "Native Artist",
    }


def _populated_artist_row() -> dict:
    return {"artist_mbid": "a-1", "artist_name": "Native Artist"}


@pytest.mark.asyncio
async def test_albums_falls_back_to_navidrome_when_native_store_empty() -> None:
    navidrome = AsyncMock()
    navidrome.get_albums = AsyncMock(
        return_value=[
            NavidromeAlbumSummary(
                navidrome_id="nd-1",
                name="Owned Album",
                artist_name="Owned Artist",
                year=2021,
                track_count=10,
                image_url="/api/v1/navidrome/cover/nd-1",
                musicbrainz_id=None,
                artist_musicbrainz_id=None,
            )
        ]
    )
    navidrome.get_stats = AsyncMock(
        return_value=NavidromeLibraryStats(total_tracks=10, total_albums=1, total_artists=1)
    )
    service = TargetNativeLibraryService(_store(), navidrome_service=navidrome)

    items, total = await service.albums(
        limit=50, offset=0, sort="recent", search=None, file_format=None
    )

    navidrome.get_albums.assert_awaited_once()
    assert total == 1
    assert items[0].id == "nd-1"
    assert items[0].title == "Owned Album"
    assert items[0].image_url == "/api/v1/navidrome/cover/nd-1"
    assert items[0].album_identity_state == "local_only"


@pytest.mark.asyncio
async def test_albums_stays_native_when_store_is_populated() -> None:
    navidrome = AsyncMock()
    store = _store(albums=([_populated_album_row()], 1))
    service = TargetNativeLibraryService(store, navidrome_service=navidrome)

    items, total = await service.albums(
        limit=50, offset=0, sort="recent", search=None, file_format=None
    )

    navidrome.get_albums.assert_not_called()
    assert total == 1
    assert items[0].title == "Native Album"


@pytest.mark.asyncio
async def test_albums_stays_native_when_no_navidrome_service_wired() -> None:
    service = TargetNativeLibraryService(_store(), navidrome_service=None)

    items, total = await service.albums(
        limit=50, offset=0, sort="recent", search=None, file_format=None
    )

    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_artists_falls_back_to_navidrome_when_native_store_empty() -> None:
    navidrome = AsyncMock()
    navidrome.browse_artists = AsyncMock(
        return_value=(
            [
                NavidromeArtistSummary(
                    navidrome_id="nd-a1",
                    name="Owned Artist",
                    image_url="/api/v1/navidrome/cover/nd-a1",
                    album_count=3,
                    musicbrainz_id=None,
                )
            ],
            1,
        )
    )
    service = TargetNativeLibraryService(_store(), navidrome_service=navidrome)

    items, total = await service.artists(
        limit=50, offset=0, search=None, sort_order="asc"
    )

    navidrome.browse_artists.assert_awaited_once()
    assert total == 1
    assert items[0].id == "nd-a1"
    assert items[0].name == "Owned Artist"


@pytest.mark.asyncio
async def test_artists_contributors_scope_never_falls_back() -> None:
    navidrome = AsyncMock()
    service = TargetNativeLibraryService(_store(), navidrome_service=navidrome)

    items, total = await service.artists(
        limit=50, offset=0, search=None, sort_order="asc", scope="contributors"
    )

    navidrome.browse_artists.assert_not_called()
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_stats_falls_back_to_navidrome_when_native_store_empty() -> None:
    navidrome = AsyncMock()
    navidrome.get_stats = AsyncMock(
        return_value=NavidromeLibraryStats(total_tracks=42, total_albums=7, total_artists=3)
    )
    service = TargetNativeLibraryService(_store(), navidrome_service=navidrome)

    stats = await service.stats()

    navidrome.get_stats.assert_awaited_once()
    assert stats.total_albums == 7
    assert stats.total_artists == 3
    assert stats.total_tracks == 42
    assert stats.total_size_bytes == 0


@pytest.mark.asyncio
async def test_stats_stays_native_when_populated() -> None:
    navidrome = AsyncMock()
    store = _store(
        stats={
            "total_albums": 5,
            "total_artists": 2,
            "total_tracks": 40,
            "total_size_bytes": 1000,
            "format_breakdown": {"flac": 40},
            "unmatched_count": 0,
            "local_only_count": 0,
            "last_scan_at": 123.0,
        }
    )
    service = TargetNativeLibraryService(store, navidrome_service=navidrome)

    stats = await service.stats()

    navidrome.get_stats.assert_not_called()
    assert stats.total_albums == 5
    assert stats.total_size_bytes == 1000


@pytest.mark.asyncio
async def test_tracks_falls_back_to_navidrome_when_native_store_empty() -> None:
    navidrome = AsyncMock()
    navidrome.browse_tracks = AsyncMock(
        return_value=(
            [
                NavidromeTrackInfo(
                    navidrome_id="song-1",
                    title="Owned Track",
                    track_number=3,
                    duration_seconds=210.0,
                    disc_number=1,
                    album_name="Owned Album",
                    artist_name="Owned Artist",
                    album_id="nd-1",
                    artist_id="nd-a1",
                    musicbrainz_recording_id=None,
                    codec="flac",
                    bitrate=900,
                    image_url="/api/v1/navidrome/cover/nd-1",
                )
            ],
            1,
        )
    )
    service = TargetNativeLibraryService(_store(), navidrome_service=navidrome)

    items, total = await service.tracks(limit=50, offset=0, sort="recent", search=None)

    navidrome.browse_tracks.assert_awaited_once_with(size=50, offset=0, search="")
    assert total == 1
    track = items[0]
    assert track.id == "song-1"
    assert track.title == "Owned Track"
    assert track.album_id == "nd-1"
    assert track.artist_id == "nd-a1"
    assert track.source == "navidrome"
    assert track.stream_url == "/api/v1/stream/navidrome/song-1"
    assert track.image_url == "/api/v1/navidrome/cover/nd-1"
    assert track.format == "FLAC"


@pytest.mark.asyncio
async def test_tracks_stays_native_when_store_is_populated() -> None:
    navidrome = AsyncMock()
    row = {
        "id": "native-track-1",
        "track_title": "Native Track",
        "release_group_mbid": "rg-1",
        "album_title": "Native Album",
        "artist_mbid": "a-1",
        "artist_name": "Native Artist",
    }
    store = _store(tracks=([row], 1))
    service = TargetNativeLibraryService(store, navidrome_service=navidrome)

    items, total = await service.tracks(limit=50, offset=0, sort="recent", search=None)

    navidrome.browse_tracks.assert_not_called()
    assert total == 1
    assert items[0].source == "local"
    assert items[0].title == "Native Track"


@pytest.mark.asyncio
async def test_recently_added_falls_back_to_navidrome_with_newest_type() -> None:
    navidrome = AsyncMock()
    navidrome.get_albums = AsyncMock(
        return_value=[
            NavidromeAlbumSummary(navidrome_id="nd-2", name="Fresh Album", artist_name="X")
        ]
    )
    service = TargetNativeLibraryService(_store(), navidrome_service=navidrome)

    items = await service.recently_added(limit=20)

    navidrome.get_albums.assert_awaited_once_with(type="newest", size=20, offset=0)
    assert items[0].id == "nd-2"
