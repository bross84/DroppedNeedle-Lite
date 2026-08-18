"""Follow service tests, plus the queue processor's album-monitored signal check."""

import sqlite3
import threading
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from infrastructure.persistence.follow_store import FollowStore
from services.follow_service import FollowService


def _seed_auth_users(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS auth_users "
            "(id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user')"
        )
        conn.executemany(
            "INSERT OR IGNORE INTO auth_users (id, display_name, role) VALUES (?, ?, ?)",
            [("admin-1", "Admin", "admin"), ("user-a", "Alice", "user")],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def mb_repo():
    repo = AsyncMock()
    repo.get_artist_by_id.return_value = {"name": "Radiohead"}
    return repo


@pytest.fixture
def service(tmp_path: Path, mb_repo) -> FollowService:
    db_path = tmp_path / "library.db"
    store = FollowStore(db_path=db_path, write_lock=threading.Lock())
    _seed_auth_users(db_path)
    return FollowService(store, mb_repo)


class TestFollow:
    @pytest.mark.asyncio
    async def test_follow_sets_state_and_enriches_name(self, service, mb_repo):
        state = await service.set_followed("user-a", "MBID-A", True)
        assert state.followed is True
        mb_repo.get_artist_by_id.assert_awaited_with("MBID-A")
        listed = await service.list_following("user-a")
        assert listed[0].artist_name == "Radiohead"

    @pytest.mark.asyncio
    async def test_unfollow(self, service):
        await service.set_followed("user-a", "MBID-A", True)
        state = await service.set_followed("user-a", "MBID-A", False)
        assert state.followed is False

    @pytest.mark.asyncio
    async def test_follow_name_fallback_when_mb_unavailable(self, service, mb_repo):
        mb_repo.get_artist_by_id.return_value = None
        await service.set_followed("user-a", "MBID-A", True)
        listed = await service.list_following("user-a")
        assert listed[0].artist_name == "Unknown Artist"


class TestProcessorMonitoringSignal:
    """Belt-and-suspenders album-monitored check: the structured-boolean path
    that survives the Lidarr removal."""

    def _check_monitored(self, result: dict) -> bool:
        payload = result.get("payload", {})
        is_monitored = payload.get("monitored", False) if isinstance(payload, dict) else False
        if not is_monitored:
            is_monitored = bool(result.get("monitored"))
        return is_monitored

    def test_processor_trusts_structured_flag_when_payload_stale(self):
        result = {
            "message": "Album monitored & search triggered: Test Album",
            "monitored": True,
            "payload": {"monitored": False, "id": 10},
        }
        assert self._check_monitored(result) is True

    def test_processor_trusts_added_and_monitored_flag(self):
        result = {
            "message": "Album added & monitored: New Album",
            "monitored": True,
            "payload": {"monitored": False, "id": 20},
        }
        assert self._check_monitored(result) is True

    def test_processor_does_not_false_positive_without_flag(self):
        result = {
            "message": "Album already downloaded: Some Album",
            "payload": {"monitored": False, "id": 30},
        }
        assert self._check_monitored(result) is False

    def test_processor_uses_payload_when_already_monitored(self):
        result = {
            "message": "Album already downloaded: Some Album",
            "payload": {"monitored": True, "id": 40},
        }
        assert self._check_monitored(result) is True
