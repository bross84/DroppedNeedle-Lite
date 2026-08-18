"""NewReleaseService: baseline detection, fan-out enqueue, and graceful
degradation (Phase 4)."""

import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.exceptions import ConfigurationError, ExternalServiceError
from infrastructure.persistence.follow_store import FollowStore
from infrastructure.queue.priority_queue import RequestPriority
from services.native.download_service import ALREADY_IN_LIBRARY
from services.native.new_release_service import NewReleaseService
from tests.helpers import make_builtin_dispatcher

ARTIST = "AAAAAAAA-1111-2222-3333-444444444444"
ARTIST_LOWER = ARTIST.lower()


def _seed_auth_users(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS auth_users "
            "(id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user')"
        )
        conn.executemany(
            "INSERT OR IGNORE INTO auth_users (id, display_name, role) VALUES (?, ?, ?)",
            [
                ("user-a", "Alice", "user"),
                ("user-b", "Bob", "user"),
                ("admin-1", "Admin", "admin"),
            ],
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS library_files "
            "(id TEXT PRIMARY KEY, release_group_mbid TEXT, deleted_at REAL)"
        )
        conn.commit()
    finally:
        conn.close()


def _rg(mbid: str, title: str, *, primary="Album", secondary=None, date="2020-01-01"):
    d = {
        "id": mbid,
        "title": title,
        "primary-type": primary,
        "first-release-date": date,
    }
    if secondary is not None:
        d["secondary-types"] = secondary
    return d


@pytest.fixture
def svc(tmp_path: Path):
    db = tmp_path / "library.db"
    store = FollowStore(db_path=db, write_lock=threading.Lock())
    _seed_auth_users(db)

    mb = AsyncMock()
    mb.get_artist_release_groups_or_raise = AsyncMock(return_value=([], 0))
    library = AsyncMock()
    library.get_library_mbids = AsyncMock(return_value=set())

    service = NewReleaseService(
        follow_store=store,
        mb_repo=mb,
        library_repo=library,
        inter_artist_delay=0.0,
    )
    return SimpleNamespace(
        service=service,
        store=store,
        mb=mb,
        library=library,
        db=db,
    )


async def _follow(store, user_id):
    await store.follow_artist(user_id, ARTIST, "Radiohead")


@pytest.mark.asyncio
async def test_first_poll_seeds_baseline_and_enqueues_nothing(svc):
    await _follow(svc.store, "user-a")
    svc.mb.get_artist_release_groups_or_raise.return_value = (
        [_rg("RG1", "Old 1"), _rg("RG2", "Old 2")],
        2,
    )
    summary = await svc.service.run_poll()
    assert summary.baselined == 1
    assert summary.new_releases == 0
    assert await svc.store.has_cursor(ARTIST_LOWER) is True
    assert await svc.store.known_release_set(ARTIST_LOWER) == {"rg1", "rg2"}
    items, total = await svc.store.list_new_releases_for_user("user-a", 50, 0)
    assert total == 0


@pytest.mark.asyncio
async def test_owned_release_group_is_excluded(svc):
    await _follow(svc.store, "user-a")
    await svc.store.seed_baseline(ARTIST_LOWER, ["rg1"])
    svc.library.get_library_mbids.return_value = {"rg2"}  # already owned
    svc.mb.get_artist_release_groups_or_raise.return_value = (
        [_rg("RG1", "Old"), _rg("RG2", "Owned New")],
        2,
    )
    summary = await svc.service.run_poll()
    assert summary.new_releases == 0


@pytest.mark.asyncio
async def test_future_dated_release_is_feed_only(svc):
    await _follow(svc.store, "user-a")
    await svc.store.seed_baseline(ARTIST_LOWER, ["rg1"])
    svc.mb.get_artist_release_groups_or_raise.return_value = (
        [_rg("RG1", "Old"), _rg("RG2", "Upcoming", date="2099-01-01")],
        2,
    )
    summary = await svc.service.run_poll()
    assert summary.new_releases == 1
    # in Wanted...
    _items, total = await svc.store.list_new_releases_for_user("user-a", 50, 0)
    assert total == 1
    # ...but NOT marked known, so a later (released) poll can still enqueue it
    assert "rg2" not in await svc.store.known_release_set(ARTIST_LOWER)


@pytest.mark.asyncio
async def test_noisy_secondary_type_is_filtered(svc):
    await _follow(svc.store, "user-a")
    await svc.store.seed_baseline(ARTIST_LOWER, ["rg1"])
    svc.mb.get_artist_release_groups_or_raise.return_value = (
        [_rg("RG1", "Old"), _rg("RG2", "Live Album", secondary=["Live"])],
        2,
    )
    summary = await svc.service.run_poll()
    assert summary.new_releases == 0


@pytest.mark.asyncio
async def test_mb_error_does_not_advance_baseline(svc):
    await _follow(svc.store, "user-a")
    svc.mb.get_artist_release_groups_or_raise.side_effect = ExternalServiceError(
        "MB down"
    )
    summary = await svc.service.run_poll()
    assert summary.errors == 1
    assert summary.baselined == 0
    # no cursor created -> the next run still baselines (never treats back-catalog as new)
    assert await svc.store.has_cursor(ARTIST_LOWER) is False


@pytest.mark.asyncio
async def test_mb_error_after_baseline_preserves_known_set(svc):
    await _follow(svc.store, "user-a")
    await svc.store.seed_baseline(ARTIST_LOWER, ["rg1", "rg2"])
    svc.mb.get_artist_release_groups_or_raise.side_effect = ExternalServiceError(
        "MB down"
    )
    summary = await svc.service.run_poll()
    assert summary.errors == 1
    assert await svc.store.known_release_set(ARTIST_LOWER) == {
        "rg1",
        "rg2",
    }  # unchanged
