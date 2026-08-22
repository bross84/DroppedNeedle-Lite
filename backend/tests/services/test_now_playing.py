"""Tests for now-playing and session service methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.navidrome_models import SubsonicNowPlayingEntry
from services.navidrome_library_service import NavidromeLibraryService


def _make_navidrome_service() -> tuple[NavidromeLibraryService, MagicMock]:
    repo = MagicMock()
    repo.get_now_playing = AsyncMock(return_value=[])
    repo.get_albums = AsyncMock(return_value=[])
    repo.get_album_info = AsyncMock()
    repo.get_album_tracks = AsyncMock(return_value=[])
    repo.get_starred = AsyncMock()
    repo.get_artists = AsyncMock(return_value=[])
    repo.get_artist = AsyncMock()
    repo.get_artist_info = AsyncMock()
    repo.search = AsyncMock()
    repo.get_genres = AsyncMock(return_value=[])
    repo.now_playing = AsyncMock(return_value=True)
    repo.get_playlists = AsyncMock(return_value=[])
    repo.get_playlist = AsyncMock()
    repo.get_random_songs = AsyncMock(return_value=[])

    prefs = MagicMock()
    prefs.get_navidrome_connection_raw.return_value = MagicMock(enabled=True)

    svc = NavidromeLibraryService(navidrome_repo=repo, preferences_service=prefs)
    return svc, repo


def _navidrome_entry(**overrides) -> SubsonicNowPlayingEntry:
    defaults = dict(
        id="np1",
        title="Song N",
        artist="Artist N",
        album="Album N",
        albumId="al1",
        artistId="ar1",
        coverArt="cov1",
        duration=240,
        bitRate=320,
        suffix="mp3",
        username="bob",
        minutesAgo=2,
        playerId=1,
        playerName="Firefox",
    )
    defaults.update(overrides)
    return SubsonicNowPlayingEntry(**defaults)


class TestNavidromeGetNowPlaying:
    @pytest.mark.asyncio
    async def test_returns_mapped_entries(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.return_value = [_navidrome_entry()]

        result = await svc.get_now_playing()

        assert len(result.entries) == 1
        e = result.entries[0]
        assert e.user_name == "bob"
        assert e.track_name == "Song N"
        assert e.artist_name == "Artist N"
        assert e.album_name == "Album N"
        assert e.cover_art_id == "cov1"
        assert e.duration_seconds == 240
        assert e.minutes_ago == 2
        assert e.player_name == "Firefox"

    @pytest.mark.asyncio
    async def test_empty_entries(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.return_value = []

        result = await svc.get_now_playing()

        assert result.entries == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.side_effect = RuntimeError("timeout")

        result = await svc.get_now_playing()

        assert result.entries == []

    @pytest.mark.asyncio
    async def test_multiple_entries(self):
        svc, repo = _make_navidrome_service()
        repo.get_now_playing.return_value = [
            _navidrome_entry(username="bob"),
            _navidrome_entry(username="charlie", title="Song X"),
        ]

        result = await svc.get_now_playing()

        assert len(result.entries) == 2
        assert result.entries[0].user_name == "bob"
        assert result.entries[1].user_name == "charlie"


# Live presence registry (NowPlayingService) + external poller

from types import SimpleNamespace  # noqa: E402

from services.now_playing_service import ExternalSession, NowPlayingService  # noqa: E402
from services import now_playing_poller as poller  # noqa: E402
from api.v1.schemas.navidrome import (  # noqa: E402
    NavidromeNowPlayingEntrySchema,
    NavidromeNowPlayingResponse,
)


class _RecordingSSE:
    def __init__(self):
        self.published: list[tuple[str, str, dict]] = []

    async def publish(self, channel, event, data):
        self.published.append((channel, event, data))


class _FakePrefs:
    def __init__(self, visibility_by_user=None):
        self._vis = visibility_by_user or {}

    async def get(self, user_id):
        return SimpleNamespace(now_playing_visibility=self._vis.get(user_id, "full"))


def _update_kwargs(**overrides):
    base = dict(
        key="u1:web",
        user_id="u1",
        user_name="Alice",
        source="local",
        device_name="Web",
        track_name="Song",
        artist_name="Artist",
        album_name="Album",
        cover_url="/c.jpg",
        is_paused=False,
        progress_ms=1000,
        duration_ms=200000,
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_presence_update_publishes_full_entry():
    sse = _RecordingSSE()
    svc = NowPlayingService(sse, _FakePrefs())
    await svc.update(**_update_kwargs())
    assert sse.published
    channel, event, data = sse.published[-1]
    assert channel == "now-playing" and event == "snapshot"
    sessions = data["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["track_name"] == "Song"
    assert sessions[0]["redacted"] is False
    assert sessions[0]["progress_ms"] == 1000


@pytest.mark.asyncio
async def test_presence_track_hidden_redacts_song_but_keeps_progress():
    svc = NowPlayingService(_RecordingSSE(), _FakePrefs({"u1": "track_hidden"}))
    await svc.update(
        **_update_kwargs(track_name="Secret", artist_name="SArtist", progress_ms=5000)
    )
    snap = svc.snapshot()
    assert len(snap) == 1
    entry = snap[0]
    assert entry.redacted is True
    assert entry.track_name == "" and entry.artist_name == ""
    assert entry.album_name is None and entry.cover_url == ""
    # identity + progress survive redaction
    assert entry.user_name == "Alice"
    assert entry.progress_ms == 5000 and entry.duration_ms == 200000


@pytest.mark.asyncio
async def test_presence_offline_hides_entry_entirely():
    svc = NowPlayingService(_RecordingSSE(), _FakePrefs({"u1": "offline"}))
    await svc.update(**_update_kwargs())
    assert svc.snapshot() == []


@pytest.mark.asyncio
async def test_presence_remove_drops_entry_and_publishes_empty():
    sse = _RecordingSSE()
    svc = NowPlayingService(sse, _FakePrefs())
    await svc.update(**_update_kwargs())
    await svc.remove("u1:web")
    assert svc.snapshot() == []
    assert sse.published[-1][2]["sessions"] == []


@pytest.mark.asyncio
async def test_presence_reconcile_external_replaces_and_noops_when_empty():
    sse = _RecordingSSE()
    svc = NowPlayingService(sse, _FakePrefs())
    # empty + nothing existing -> no publish (idle integration doesn't churn)
    await svc.reconcile_source("navidrome", [])
    assert sse.published == []
    session = ExternalSession(
        key="navidrome:s1",
        user_name="Bob",
        device_name="TV",
        track_name="T",
        artist_name="A",
        album_name=None,
        cover_url="",
        is_paused=False,
        progress_ms=0,
        duration_ms=1000,
    )
    await svc.reconcile_source("navidrome", [session])
    assert len(svc.snapshot()) == 1
    # external sessions carry no user_id, so they're never redacted
    assert svc.snapshot()[0].redacted is False
    await svc.reconcile_source("navidrome", [])
    assert svc.snapshot() == []


@pytest.mark.asyncio
async def test_presence_sweep_drops_stale_sessions():
    import asyncio

    svc = NowPlayingService(_RecordingSSE(), _FakePrefs(), ttl_seconds=0.0)
    await svc.update(**_update_kwargs())
    await asyncio.sleep(0.01)
    await svc.sweep()
    assert svc.snapshot() == []


@pytest.mark.asyncio
async def test_presence_set_visibility_changes_projection_live():
    svc = NowPlayingService(_RecordingSSE(), _FakePrefs())
    await svc.update(**_update_kwargs())
    assert svc.snapshot()[0].track_name == "Song"
    await svc.set_visibility("u1", "track_hidden")
    assert svc.snapshot()[0].redacted is True
    assert svc.snapshot()[0].track_name == ""
    await svc.set_visibility("u1", "offline")
    assert svc.snapshot() == []


def test_poller_map_navidrome_builds_cover_and_progress():
    resp = NavidromeNowPlayingResponse(
        entries=[
            NavidromeNowPlayingEntrySchema(
                user_name="Al",
                player_name="P",
                album_id="alb",
                track_name="T",
                artist_name="A",
                album_name="Alb",
                cover_art_id="cov",
                duration_seconds=300,
                estimated_position_seconds=10.0,
                minutes_ago=0,
            )
        ]
    )
    out = poller.map_navidrome(resp)
    assert out[0].cover_url == "/api/v1/navidrome/cover/cov"
    assert out[0].progress_ms == 10000
    assert out[0].is_paused is False


@pytest.mark.asyncio
async def test_poller_gates_each_source_on_integration_status():
    from unittest.mock import AsyncMock, MagicMock

    now_playing = AsyncMock()
    home = MagicMock()
    home.get_integration_status.return_value = SimpleNamespace(navidrome=True)
    nav = MagicMock()
    nav.get_now_playing = AsyncMock(
        return_value=NavidromeNowPlayingResponse(entries=[])
    )

    await poller.poll_external_once(now_playing, home, nav)

    nav.get_now_playing.assert_awaited_once()
    assert now_playing.reconcile_source.await_count == 1


@pytest.mark.asyncio
async def test_presence_loop_resolves_rebuilt_services_each_cycle(monkeypatch):
    import asyncio

    now_playing = AsyncMock()
    instances = [MagicMock() for _ in range(2)]
    getters = [MagicMock(return_value=instance) for instance in instances]
    poll_once = AsyncMock()

    async def stop_after_cycle(_interval):
        raise asyncio.CancelledError

    monkeypatch.setattr(poller, "poll_external_once", poll_once)
    monkeypatch.setattr(poller.asyncio, "sleep", stop_after_cycle)

    with pytest.raises(asyncio.CancelledError):
        await poller.run_now_playing_presence_loop(now_playing, *getters)

    for getter in getters:
        getter.assert_called_once_with()
    poll_once.assert_awaited_once_with(now_playing, *instances)


class _FailingPrefs:
    async def get(self, user_id):
        raise RuntimeError("prefs DB unavailable")


@pytest.mark.asyncio
async def test_presence_fails_closed_when_visibility_load_errors():
    # a transient prefs-DB error must not leak a hidden track: project conservatively
    svc = NowPlayingService(_RecordingSSE(), _FailingPrefs())
    await svc.update(**_update_kwargs(track_name="Secret", artist_name="SecretArtist"))
    snap = svc.snapshot()
    assert len(snap) == 1
    assert snap[0].redacted is True
    assert snap[0].track_name == "" and snap[0].artist_name == ""
    # presence + progress still surface; only the track is withheld
    assert snap[0].user_name == "Alice"
    assert snap[0].progress_ms == 1000
