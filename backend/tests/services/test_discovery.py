"""Tests for discovery features across Navidrome."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.navidrome_models import SubsonicSong
from services.navidrome_library_service import NavidromeLibraryService


def _make_navidrome_service() -> tuple[NavidromeLibraryService, MagicMock]:
    repo = MagicMock()
    repo.get_random_songs = AsyncMock(return_value=[])
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = MagicMock()
    service = NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)
    return service, repo


def _song(id: str = "s1", title: str = "Song", album: str = "Album",
          artist: str = "Artist", track: int = 1, duration: int = 200,
          suffix: str = "mp3", bit_rate: int = 320) -> SubsonicSong:
    return SubsonicSong(
        id=id, title=title, album=album, artist=artist,
        track=track, duration=duration, suffix=suffix, bitRate=bit_rate,
    )


class TestNavidromeRandomSongs:
    @pytest.mark.asyncio
    async def test_returns_mapped_tracks(self):
        service, repo = _make_navidrome_service()
        repo.get_random_songs = AsyncMock(return_value=[
            _song(id="s1", title="Track A"),
            _song(id="s2", title="Track B"),
        ])
        tracks = await service.get_random_songs(size=10)
        assert len(tracks) == 2
        assert tracks[0].title == "Track A"
        assert tracks[1].navidrome_id == "s2"
        repo.get_random_songs.assert_awaited_once_with(
            size=10, genre=None, music_folder_ids=None
        )

    @pytest.mark.asyncio
    async def test_forwards_genre_filter(self):
        service, repo = _make_navidrome_service()
        repo.get_random_songs = AsyncMock(return_value=[_song()])
        await service.get_random_songs(size=5, genre="Rock")
        repo.get_random_songs.assert_awaited_once_with(
            size=5, genre="Rock", music_folder_ids=None
        )

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        service, repo = _make_navidrome_service()
        repo.get_random_songs = AsyncMock(side_effect=Exception("fail"))
        result = await service.get_random_songs()
        assert result == []

    @pytest.mark.asyncio
    async def test_default_size_is_20(self):
        service, repo = _make_navidrome_service()
        repo.get_random_songs = AsyncMock(return_value=[])
        await service.get_random_songs()
        repo.get_random_songs.assert_awaited_once_with(
            size=20, genre=None, music_folder_ids=None
        )
