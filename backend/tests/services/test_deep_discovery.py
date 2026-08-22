"""Tests for deep discovery and analytics features."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.v1.schemas.navidrome import NavidromeArtistInfoSchema, NavidromeTrackInfo
from repositories.navidrome_models import SubsonicArtist, SubsonicArtistInfo, SubsonicSong
from services.navidrome_library_service import NavidromeLibraryService


def _make_navidrome_service() -> tuple[NavidromeLibraryService, MagicMock]:
    repo = MagicMock()
    repo.get_album_list = AsyncMock(return_value=[])
    repo.get_album = AsyncMock()
    repo.get_artists = AsyncMock(return_value=[])
    repo.get_artist = AsyncMock()
    repo.get_starred = AsyncMock()
    repo.get_genres = AsyncMock(return_value=[])
    repo.search = AsyncMock()
    repo.get_top_songs = AsyncMock(return_value=[])
    repo.get_similar_songs = AsyncMock(return_value=[])
    repo.get_artist_info = AsyncMock(return_value=None)
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = MagicMock()
    service = NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)
    return service, repo


def _subsonic_song(id: str = "s1", title: str = "Song", artist: str = "Artist",
                   album: str = "Album", track: int = 1, duration: int = 200) -> SubsonicSong:
    return SubsonicSong(id=id, title=title, artist=artist, album=album,
                        track=track, duration=duration)


class TestNavidromeTopSongs:
    @pytest.mark.asyncio
    async def test_returns_mapped_tracks(self):
        service, repo = _make_navidrome_service()
        repo.get_top_songs.return_value = [
            _subsonic_song("s1", "Hit Song", "Radiohead"),
            _subsonic_song("s2", "Another Hit", "Radiohead"),
        ]
        result = await service.get_top_songs("Radiohead")
        assert len(result) == 2
        assert isinstance(result[0], NavidromeTrackInfo)
        assert result[0].title == "Hit Song"
        repo.get_top_songs.assert_awaited_once_with("Radiohead", count=20)

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        service, repo = _make_navidrome_service()
        repo.get_top_songs.side_effect = Exception("Last.fm unavailable")
        result = await service.get_top_songs("Unknown Artist")
        assert result == []


class TestNavidromeSimilarSongs:
    @pytest.mark.asyncio
    async def test_returns_mapped_tracks(self):
        service, repo = _make_navidrome_service()
        repo.get_similar_songs.return_value = [_subsonic_song("s3", "Similar")]
        result = await service.get_similar_songs("s1")
        assert len(result) == 1
        assert result[0].title == "Similar"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        service, repo = _make_navidrome_service()
        repo.get_similar_songs.side_effect = Exception("Fail")
        result = await service.get_similar_songs("s1")
        assert result == []


class TestNavidromeArtistInfo:
    @pytest.mark.asyncio
    async def test_returns_info_schema(self):
        service, repo = _make_navidrome_service()
        repo.get_artist_info.return_value = SubsonicArtistInfo(
            biography="A great band.",
            musicBrainzId="mbid-123",
            smallImageUrl="http://img/sm.jpg",
            mediumImageUrl="http://img/md.jpg",
            largeImageUrl="http://img/lg.jpg",
            similarArtist=[SubsonicArtist(id="ar2", name="Similar Band")],
        )
        result = await service.get_artist_info("ar1")
        assert result is not None
        assert isinstance(result, NavidromeArtistInfoSchema)
        assert result.biography == "A great band."
        assert result.image_url == "http://img/lg.jpg"
        assert len(result.similar_artists) == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_not_available(self):
        service, repo = _make_navidrome_service()
        repo.get_artist_info.return_value = None
        result = await service.get_artist_info("ar1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        service, repo = _make_navidrome_service()
        repo.get_artist_info.side_effect = Exception("Fail")
        result = await service.get_artist_info("ar1")
        assert result is None
