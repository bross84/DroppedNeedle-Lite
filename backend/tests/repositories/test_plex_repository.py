from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.exceptions import PlexApiError, PlexAuthError
from repositories.plex_repository import PlexRepository, _plex_circuit_breaker


def _make_cache() -> MagicMock:
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.clear_prefix = AsyncMock(return_value=0)
    return cache


def _make_repo(
    configured: bool = True, cache_scope: str = "shared"
) -> tuple[PlexRepository, AsyncMock, MagicMock]:
    client = AsyncMock(spec=httpx.AsyncClient)
    cache = _make_cache()
    repo = PlexRepository(http_client=client, cache=cache, cache_scope=cache_scope)
    if configured:
        repo.configure("http://plex:32400", "test-token", "client-id-123")
    _plex_circuit_breaker.reset()
    return repo, client, cache


class TestConfigure:
    def test_configure_sets_state(self):
        repo, _, _ = _make_repo(configured=False)
        assert repo.is_configured() is False

        repo.configure("http://plex:32400", "my-token", "my-client")
        assert repo.is_configured() is True

    def test_configure_strips_trailing_slash(self):
        repo, _, _ = _make_repo(configured=False)
        repo.configure("http://plex:32400/", "tok")
        assert repo._url == "http://plex:32400"

    def test_configure_empty_url_not_configured(self):
        repo, _, _ = _make_repo(configured=False)
        repo.configure("", "tok")
        assert repo.is_configured() is False

    def test_configure_empty_token_not_configured(self):
        repo, _, _ = _make_repo(configured=False)
        repo.configure("http://plex:32400", "")
        assert repo.is_configured() is False


class TestBuildHeaders:
    def test_contains_required_keys(self):
        repo, _, _ = _make_repo()
        headers = repo._build_headers()
        assert headers["X-Plex-Token"] == "test-token"
        assert headers["X-Plex-Product"] == "DroppedNeedle"
        assert headers["X-Plex-Version"] == "1.0"
        assert headers["Accept"] == "application/json"

    def test_client_identifier_included_when_set(self):
        repo, _, _ = _make_repo()
        headers = repo._build_headers()
        assert headers["X-Plex-Client-Identifier"] == "client-id-123"

    def test_client_identifier_omitted_when_empty(self):
        repo, _, _ = _make_repo(configured=False)
        repo.configure("http://plex:32400", "tok", "")
        headers = repo._build_headers()
        assert "X-Plex-Client-Identifier" not in headers


class TestOAuthPin:
    @pytest.mark.asyncio
    async def test_create_pin(self):
        repo, _, _ = _make_repo()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 42, "code": "ABCD1234"}

        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            pin = await repo.create_oauth_pin("client-123")
            assert pin.id == 42
            assert pin.code == "ABCD1234"

    @pytest.mark.asyncio
    async def test_create_pin_failure(self):
        repo, _, _ = _make_repo()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            with pytest.raises(PlexApiError, match="Failed to create"):
                await repo.create_oauth_pin("client-123")

    @pytest.mark.asyncio
    async def test_poll_pin_token_found(self):
        repo, _, _ = _make_repo()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"authToken": "fresh-token"}

        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            token = await repo.poll_oauth_pin(42, "client-123")
            assert token == "fresh-token"

    @pytest.mark.asyncio
    async def test_poll_pin_not_ready(self):
        repo, _, _ = _make_repo()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"authToken": ""}

        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            token = await repo.poll_oauth_pin(42, "client-123")
            assert token is None

    @pytest.mark.asyncio
    async def test_poll_pin_non_200(self):
        repo, _, _ = _make_repo()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            token = await repo.poll_oauth_pin(42, "client-123")
            assert token is None


def _mock_fresh_client(response: MagicMock):
    instance = AsyncMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=False)
    instance.get = AsyncMock(return_value=response)
    return instance


class TestAccountAuthCalls:
    @pytest.mark.asyncio
    async def test_server_ids_ignores_tokenless_client_devices(self):
        # Regression: /api/v2/resources lists client devices (e.g. Plexamp) with
        # no accessToken. The old generated SDK model rejected those and broke
        # login for everyone. The lenient parse must skip them and still find the
        # server by clientIdentifier + provides.
        repo, _, _ = _make_repo()
        devices = [
            {"clientIdentifier": "server-machine-id", "provides": "server", "accessToken": "abc"},
            {"clientIdentifier": "plexamp-device", "provides": "client,player,pubsub-player"},
        ]
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = devices

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_fresh_client(response)
            server_ids = await repo.get_account_server_ids("user-token", "client-123")

        assert server_ids == {"server-machine-id"}

    @pytest.mark.asyncio
    async def test_server_ids_auth_failure_raises(self):
        repo, _, _ = _make_repo()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_fresh_client(response)
            with pytest.raises(PlexAuthError):
                await repo.get_account_server_ids("user-token", "client-123")

    @pytest.mark.asyncio
    async def test_resolves_server_specific_access_token(self):
        repo, _, _ = _make_repo()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = [
            {
                "clientIdentifier": "server-machine-id",
                "provides": "server",
                "accessToken": "server-specific-token",
            },
            {
                "clientIdentifier": "other-server",
                "provides": "server",
                "accessToken": "wrong-token",
            },
        ]

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_fresh_client(response)
            token = await repo.get_server_access_token(
                "account-token", "client-123", "server-machine-id"
            )

        assert token == "server-specific-token"

    @pytest.mark.asyncio
    async def test_account_profile_prefers_friendly_name(self):
        repo, _, _ = _make_repo()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {
            "uuid": "user-uuid",
            "email": "a@b.com",
            "friendlyName": "Friendly",
            "username": "uname",
            "title": "Title",
            "thumb": "http://thumb",
        }

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_fresh_client(response)
            profile = await repo.get_account_profile("user-token", "client-123")

        assert profile.uuid == "user-uuid"
        assert profile.email == "a@b.com"
        assert profile.display_name == "Friendly"
        assert profile.thumb == "http://thumb"

    @pytest.mark.asyncio
    async def test_account_profile_missing_uuid_raises(self):
        repo, _, _ = _make_repo()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {"email": "a@b.com"}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_fresh_client(response)
            with pytest.raises(PlexApiError, match="missing uuid"):
                await repo.get_account_profile("user-token", "client-123")


class TestEnumerateUsers:
    @pytest.mark.asyncio
    async def test_sends_client_identifier_and_merges_home_friends(self):
        # plex.tv /api/v2/home/users returns 400 without X-Plex-Client-Identifier
        # (verified live). enumerate_users must send it on
        # both calls, or admin import comes back silently empty.
        repo, _, _ = _make_repo()  # configured with client-id-123

        home = MagicMock(spec=httpx.Response)
        home.status_code = 200
        home.json.return_value = {
            "users": [
                {
                    "uuid": "u1",
                    "username": "alice",
                    "title": "Alice",
                    "email": "a@b.com",
                    "thumb": "http://t/a",
                }
            ]
        }
        friends = MagicMock(spec=httpx.Response)
        friends.status_code = 200
        friends.json.return_value = []

        captured_headers: list[dict] = []
        captured_urls: list[str] = []

        async def _get(url, headers=None):
            captured_urls.append(url)
            captured_headers.append(headers or {})
            return home if "home/users" in url else friends

        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(side_effect=_get)
            MockClient.return_value = instance

            accounts = await repo.enumerate_users()

        assert len(captured_headers) == 2
        assert all(
            h.get("X-Plex-Client-Identifier") == "client-id-123"
            for h in captured_headers
        )
        assert any("home/users" in u for u in captured_urls)
        assert any("friends" in u for u in captured_urls)
        assert [a.uuid for a in accounts] == ["u1"]
        assert accounts[0].source == "home"

    @pytest.mark.asyncio
    async def test_no_token_returns_empty(self):
        repo, _, _ = _make_repo(configured=False)
        accounts = await repo.enumerate_users()
        assert accounts == []


class TestClearCache:
    @pytest.mark.asyncio
    async def test_clears_plex_prefix(self):
        repo, _, cache = _make_repo()
        await repo.clear_cache()
        cache.clear_prefix.assert_awaited_once()


class TestCircuitBreaker:
    def test_reset_circuit_breaker(self):
        PlexRepository.reset_circuit_breaker()
        assert _plex_circuit_breaker.failure_count == 0
