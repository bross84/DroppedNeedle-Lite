from unittest.mock import AsyncMock, MagicMock

import pytest

from services.native.target_library_repository import TargetLibraryRepository


def _repo(
    artists: list[dict] | None = None, albums: list[dict] | None = None
) -> TargetLibraryRepository:
    store = MagicMock()
    store.list_target_artists = AsyncMock(return_value=(artists or [], len(artists or [])))
    store.list_target_albums = AsyncMock(return_value=(albums or [], len(albums or [])))
    return TargetLibraryRepository(store)


@pytest.mark.asyncio
async def test_returns_artists_and_albums_sorted_by_type_then_mbid() -> None:
    repo = _repo(
        artists=[
            {
                "provider_artist_mbid": "B1111111-1111-4111-8111-111111111111",
                "artist_mbid": "local-b",
                "artist_name": "Artist B",
            },
        ],
        albums=[
            {
                "provider_release_group_mbid": "a1111111-1111-4111-8111-111111111111",
                "release_group_mbid": "local-a",
                "album_title": "Album A",
                "album_artist_name": "Artist A",
            },
        ],
    )

    page = await repo.get_enrichment_candidates(after_mbid=None, limit=10)

    assert page == [
        (
            "album",
            "a1111111-1111-4111-8111-111111111111",
            {"title": "Album A", "artist_name": "Artist A"},
        ),
        (
            "artist",
            "b1111111-1111-4111-8111-111111111111",
            {"name": "Artist B"},
        ),
    ]


@pytest.mark.asyncio
async def test_keyset_cursor_resumes_after_last_seen_item() -> None:
    repo = _repo(
        artists=[
            {
                "provider_artist_mbid": "11111111-1111-4111-8111-111111111111",
                "artist_mbid": "local-1",
                "artist_name": "Artist One",
            },
            {
                "provider_artist_mbid": "22222222-1111-4111-8111-111111111111",
                "artist_mbid": "local-2",
                "artist_name": "Artist Two",
            },
        ],
    )

    first = await repo.get_enrichment_candidates(after_mbid=None, limit=1)
    cursor = f"{first[0][0]}:{first[0][1]}"
    second = await repo.get_enrichment_candidates(after_mbid=cursor, limit=1)

    assert first[0][1] == "11111111-1111-4111-8111-111111111111"
    assert second[0][1] == "22222222-1111-4111-8111-111111111111"


@pytest.mark.asyncio
async def test_entries_without_mbid_are_skipped() -> None:
    repo = _repo(
        artists=[
            {
                "provider_artist_mbid": None,
                "artist_mbid": "local-1",
                "artist_name": "No MBID",
            }
        ],
        albums=[
            {
                "provider_release_group_mbid": "",
                "release_group_mbid": "local-2",
                "album_title": "No MBID Album",
                "album_artist_name": "X",
            }
        ],
    )

    assert await repo.get_enrichment_candidates(after_mbid=None, limit=10) == []


@pytest.mark.asyncio
async def test_empty_library_terminates_immediately() -> None:
    repo = _repo()
    assert await repo.get_enrichment_candidates(after_mbid=None, limit=500) == []
