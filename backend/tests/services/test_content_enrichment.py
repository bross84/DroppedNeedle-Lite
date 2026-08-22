"""Tests for lyrics, album info, and audio-quality enrichment."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.navidrome_models import SubsonicAlbumInfo, SubsonicLyrics
from services.navidrome_library_service import NavidromeLibraryService


def _navidrome_service(
    album_info=None,
    lyrics=None,
    lyrics_by_id=None,
) -> NavidromeLibraryService:
    repo = MagicMock()
    repo.get_albums = AsyncMock(return_value=[])
    repo.get_recently_played = AsyncMock(return_value=[])
    repo.get_recently_added = AsyncMock(return_value=[])
    repo.get_starred_albums = AsyncMock(return_value=[])
    repo.get_starred_artists = AsyncMock(return_value=[])
    repo.get_starred_songs = AsyncMock(return_value=[])
    repo.get_genres = AsyncMock(return_value=[])
    repo.get_album_count = AsyncMock(return_value=0)
    repo.get_track_count = AsyncMock(return_value=0)
    repo.get_artist_count = AsyncMock(return_value=0)
    repo.get_album_info = AsyncMock(return_value=album_info)
    repo.get_lyrics = AsyncMock(return_value=lyrics)
    repo.get_lyrics_by_song_id = AsyncMock(return_value=lyrics_by_id)
    prefs = MagicMock()
    return NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)


@pytest.mark.asyncio
async def test_navidrome_album_info_returns_schema():
    info = SubsonicAlbumInfo(
        notes="Great album with <a>link</a>.",
        musicBrainzId="mb-123",
        lastFmUrl="https://last.fm/music/album",
        smallImageUrl="https://img/s.jpg",
        mediumImageUrl="https://img/m.jpg",
        largeImageUrl="https://img/l.jpg",
    )
    svc = _navidrome_service(album_info=info)
    result = await svc.get_album_info("album-1")
    assert result is not None
    assert result.album_id == "album-1"
    assert result.musicbrainz_id == "mb-123"
    assert result.lastfm_url == "https://last.fm/music/album"
    assert result.image_url == "https://img/l.jpg"
    assert "<a>" not in result.notes


@pytest.mark.asyncio
async def test_navidrome_album_info_returns_none_when_empty():
    info = SubsonicAlbumInfo()
    svc = _navidrome_service(album_info=info)
    result = await svc.get_album_info("album-1")
    assert result is None


@pytest.mark.asyncio
async def test_navidrome_album_info_returns_none_on_error():
    svc = _navidrome_service()
    svc._navidrome.get_album_info = AsyncMock(side_effect=RuntimeError("fail"))
    result = await svc.get_album_info("album-1")
    assert result is None


@pytest.mark.asyncio
async def test_navidrome_lyrics_by_song_id_first():
    lyrics = SubsonicLyrics(value="Hello world\nLine two", artist="A", title="T")
    svc = _navidrome_service(lyrics_by_id=lyrics)
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is not None
    assert "Hello world" in result.text


@pytest.mark.asyncio
async def test_navidrome_lyrics_fallback_to_artist_title():
    lyrics = SubsonicLyrics(value="Fallback lyrics", artist="A", title="T")
    svc = _navidrome_service(lyrics_by_id=None, lyrics=lyrics)
    svc._navidrome.get_lyrics_by_song_id = AsyncMock(side_effect=RuntimeError("not supported"))
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is not None
    assert result.text == "Fallback lyrics"


@pytest.mark.asyncio
async def test_navidrome_lyrics_returns_none_when_empty():
    lyrics = SubsonicLyrics(value="", artist="A", title="T")
    svc = _navidrome_service(lyrics_by_id=lyrics)
    svc._navidrome.get_lyrics = AsyncMock(return_value=SubsonicLyrics(value="", artist="A", title="T"))
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is None


@pytest.mark.asyncio
async def test_navidrome_lyrics_returns_none_on_all_errors():
    svc = _navidrome_service()
    svc._navidrome.get_lyrics_by_song_id = AsyncMock(side_effect=RuntimeError("fail"))
    svc._navidrome.get_lyrics = AsyncMock(side_effect=RuntimeError("fail"))
    result = await svc.get_lyrics("song-1", artist="A", title="T")
    assert result is None
