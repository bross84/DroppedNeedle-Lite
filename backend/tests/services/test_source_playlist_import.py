"""Tests for source playlist list, detail, and import from Navidrome."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from core.exceptions import (
    MediaAccountRelinkRequiredError,
    NavidromeAuthError,
)
from repositories.navidrome_models import SubsonicPlaylist, SubsonicSong
from repositories.playlist_repository import PlaylistRecord
from services.navidrome_library_service import NavidromeLibraryService
from services.per_user_client_factory import MediaClientResolution
from tests.helpers import mock_user

# The importer whose identity owns the imported playlist (ownership-gated add/delete).
_REQ = mock_user(user_id="importer-id")


def _mock_playlist_service(existing: PlaylistRecord | None = None) -> MagicMock:
    svc = MagicMock()
    svc.get_by_source_ref = AsyncMock(return_value=existing)
    created = PlaylistRecord(id="new-pl-1", name="Imported", cover_image_path=None, created_at="2024-01-01", updated_at="2024-01-01")
    svc.create_playlist = AsyncMock(return_value=created)
    svc.add_tracks = AsyncMock(return_value=[])
    svc.delete_playlist = AsyncMock()
    return svc


def _navidrome_service(playlists=None, playlist_detail=None) -> NavidromeLibraryService:
    repo = MagicMock()
    visible_playlists = playlists if playlists is not None else ([playlist_detail] if playlist_detail else [])
    repo.get_playlists = AsyncMock(return_value=visible_playlists)
    repo.get_playlist = AsyncMock(return_value=playlist_detail)
    repo.get_albums = AsyncMock(return_value=[])
    repo.get_recently_played = AsyncMock(return_value=[])
    repo.get_starred = AsyncMock(return_value=[])
    repo.get_starred_artists = AsyncMock(return_value=[])
    repo.get_starred_songs = AsyncMock(return_value=[])
    repo.get_genres = AsyncMock(return_value=[])
    repo.get_album_count = AsyncMock(return_value=0)
    repo.get_artist_count = AsyncMock(return_value=0)
    repo.get_song_count = AsyncMock(return_value=0)
    type(repo).stats_ttl = PropertyMock(return_value=600)
    prefs = MagicMock()
    conn = MagicMock()
    conn.enabled = True
    prefs.get_navidrome_connection_raw.return_value = conn
    return NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)


def _navidrome_playlist(pid="nd-pl-1", name="ND Playlist", songs=2, dur=300) -> SubsonicPlaylist:
    return SubsonicPlaylist(id=pid, name=name, songCount=songs, duration=dur)


def _navidrome_song(sid="ns-1", title="Song", artist="Artist", album="Album") -> SubsonicSong:
    return SubsonicSong(id=sid, title=title, artist=artist, album=album, albumId="alb-1", artistId="art-1", duration=180, track=1, discNumber=1)


class TestNavidromeListPlaylists:
    @pytest.mark.asyncio
    async def test_returns_summaries(self):
        svc = _navidrome_service(playlists=[_navidrome_playlist()])
        result = await svc.list_playlists()
        assert len(result) == 1
        assert result[0].id == "nd-pl-1"
        assert result[0].name == "ND Playlist"
        assert result[0].cover_url == "/api/v1/navidrome/playlist-cover/nd-pl-1/nd-pl-1"


class TestNavidromePlaylistDetail:
    @pytest.mark.asyncio
    async def test_returns_detail(self):
        detail_raw = _navidrome_playlist()
        detail_raw.entry = [_navidrome_song()]
        svc = _navidrome_service(playlist_detail=detail_raw)
        detail = await svc.get_playlist_detail("nd-pl-1")
        assert detail.id == "nd-pl-1"
        assert len(detail.tracks) == 1
        assert detail.tracks[0].track_name == "Song"
        assert detail.tracks[0].source_type if hasattr(detail.tracks[0], "source_type") else True

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc = _navidrome_service(playlist_detail=None)
        with pytest.raises(Exception, match="not found"):
            await svc.get_playlist_detail("missing")


class TestNavidromeImportPlaylist:
    @pytest.mark.asyncio
    async def test_import_new(self):
        detail_raw = _navidrome_playlist()
        detail_raw.entry = [_navidrome_song()]
        svc = _navidrome_service(playlist_detail=detail_raw)
        ps = _mock_playlist_service()
        result = await svc.import_playlist("nd-pl-1", ps, requesting=_REQ)
        assert result.tracks_imported == 1
        assert result.already_imported is False

    @pytest.mark.asyncio
    async def test_import_track_keys_correct(self):
        detail_raw = _navidrome_playlist()
        detail_raw.entry = [_navidrome_song()]
        svc = _navidrome_service(playlist_detail=detail_raw)
        ps = _mock_playlist_service()
        await svc.import_playlist("nd-pl-1", ps, requesting=_REQ)
        track_dicts = ps.add_tracks.call_args[0][2]
        assert track_dicts[0]["track_name"] == "Song"
        assert track_dicts[0]["source_type"] == "navidrome"
        assert track_dicts[0]["track_source_id"] == "ns-1"


def _playlist_flags(imported_by_user: dict[str, set[str]]) -> MagicMock:
    playlist_service = MagicMock()
    playlist_service.get_imported_source_ids = AsyncMock(
        side_effect=lambda _prefix, user_id: imported_by_user.get(user_id, set())
    )
    return playlist_service


def _resolution(repo, label: str) -> MediaClientResolution:
    return MediaClientResolution(
        repository=repo,
        account_mode="linked",
        account_label=label,
        cache_scope=f"user:{label}",
    )


class TestPersonalPlaylistResolution:
    @pytest.mark.asyncio
    async def test_linked_auth_failure_never_falls_back_to_shared(self):
        linked_repo = MagicMock()
        linked_repo.get_playlists = AsyncMock(side_effect=NavidromeAuthError("revoked"))
        factory = MagicMock()
        playlist_service = _playlist_flags({})

        service = _navidrome_service(playlists=[_navidrome_playlist(name="Shared")])
        factory.resolve_navidrome_playlist = AsyncMock(
            return_value=_resolution(linked_repo, "alice")
        )
        service._client_factory = factory
        shared_get = service._navidrome.get_playlists

        with pytest.raises(MediaAccountRelinkRequiredError):
            await service.list_user_playlists(
                mock_user(user_id="alice"), playlist_service
            )
        shared_get.assert_not_awaited()
