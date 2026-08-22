"""SSO auto-link (issue #138, D4): a Plex login hands us a fresh
user-scoped token, so the login flow also upserts the matching per-user media
connection - and a failed upsert must never fail the login itself."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import AuthenticationError
from services.plex_user_auth_service import PlexUserAuthService

_PLEX_PROFILE = {
    "uuid": "px-uid-1",
    "email": "a@example.com",
    "display_name": "Alice Plex",
    "thumb": None,
    "auth_token": "px-tok",
}


def _auth_store() -> MagicMock:
    store = MagicMock()
    store.issue_token = MagicMock(return_value=("raw-token", "token-hash"))
    store.store_token = AsyncMock()
    store.update_last_login = AsyncMock()
    return store


def _user() -> SimpleNamespace:
    return SimpleNamespace(id="user-1", display_name="Alice", role="user")


@pytest.fixture
def plex_service():
    repo = MagicMock()
    repo.poll_oauth_pin = AsyncMock(return_value="px-tok")
    prefs = MagicMock()
    prefs.get_or_create_setting = MagicMock(return_value="client-1")
    connections = MagicMock()
    connections.upsert = AsyncMock()
    svc = PlexUserAuthService(
        auth_store=_auth_store(),
        plex_repository=repo,
        preferences_service=prefs,
        connections_store=connections,
    )
    svc._get_user_profile = AsyncMock(return_value=dict(_PLEX_PROFILE))
    svc._get_server_machine_id = AsyncMock(return_value="machine-1")
    svc._check_server_membership = AsyncMock(return_value=True)
    svc._get_server_access_token = AsyncMock(return_value="server-tok")
    svc._find_or_create_user = AsyncMock(return_value=_user())
    return svc, repo, connections


@pytest.mark.asyncio
async def test_plex_login_auto_links_connection(plex_service):
    svc, _, connections = plex_service
    result = await svc.poll_and_login(pin_id=1)
    assert result is not None
    connections.upsert.assert_awaited_once_with(
        "user-1",
        "plex",
        {
            "auth_token": "px-tok",
            "server_access_token": "server-tok",
            "plex_user_id": "px-uid-1",
            "username": "Alice Plex",
        },
    )


@pytest.mark.asyncio
async def test_plex_login_survives_auto_link_failure(plex_service):
    svc, _, connections = plex_service
    connections.upsert.side_effect = RuntimeError("db locked")
    result = await svc.poll_and_login(pin_id=1)
    assert result is not None


@pytest.mark.asyncio
async def test_plex_poll_for_link_pending_returns_none(plex_service):
    svc, repo, connections = plex_service
    repo.poll_oauth_pin = AsyncMock(return_value=None)
    assert await svc.poll_for_link(pin_id=1) is None
    connections.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_plex_poll_for_link_returns_profile_without_login_side_effects(plex_service):
    svc, _, connections = plex_service
    profile = await svc.poll_for_link(pin_id=1)
    assert profile == {**_PLEX_PROFILE, "server_access_token": "server-tok"}
    # link flow persists nothing itself (the route owns the upsert) and never logs in
    connections.upsert.assert_not_awaited()
    svc._find_or_create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_plex_poll_for_link_enforces_server_membership(plex_service):
    svc, _, _ = plex_service
    svc._get_server_machine_id = AsyncMock(return_value="machine-1")
    svc._check_server_membership = AsyncMock(return_value=False)
    with pytest.raises(AuthenticationError):
        await svc.poll_for_link(pin_id=1)
