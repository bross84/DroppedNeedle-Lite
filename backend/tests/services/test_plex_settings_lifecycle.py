from __future__ import annotations

import os
import tempfile

os.environ.setdefault("ROOT_APP_DIR", tempfile.mkdtemp())

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.settings_service import SettingsService


def _make_settings_service() -> tuple[SettingsService, MagicMock, MagicMock]:
    cache = MagicMock()
    cache.clear_prefix = AsyncMock()
    prefs = MagicMock()

    service = SettingsService(
        preferences_service=prefs,
        cache=cache,
    )
    return service, cache, prefs


def _patch_plex_dependencies():
    """Return a context manager that patches all dependencies used inside on_plex_settings_changed."""
    mock_repo_class = MagicMock()
    mock_repo_class.reset_circuit_breaker = MagicMock()

    mock_new_repo = MagicMock()
    mock_new_repo.clear_cache = AsyncMock()

    mock_get_repo = MagicMock(return_value=mock_new_repo)
    mock_get_repo.cache_clear = MagicMock()

    mock_get_user_import = MagicMock()
    mock_get_user_import.cache_clear = MagicMock()

    mock_get_plex_user_auth = MagicMock()
    mock_get_plex_user_auth.cache_clear = MagicMock()

    mbid_store = MagicMock()
    mbid_store.clear_plex_mbid_indexes = AsyncMock()
    mock_get_mbid = MagicMock(return_value=mbid_store)

    return {
        "repo_class": mock_repo_class,
        "new_repo": mock_new_repo,
        "get_repo": mock_get_repo,
        "get_user_import": mock_get_user_import,
        "get_plex_user_auth": mock_get_plex_user_auth,
        "mbid_store": mbid_store,
        "get_mbid": mock_get_mbid,
    }


class TestOnPlexSettingsChanged:
    @pytest.mark.asyncio
    async def test_resets_caches(self):
        service, cache, _ = _make_settings_service()
        mocks = _patch_plex_dependencies()

        with patch("repositories.plex_repository.PlexRepository", mocks["repo_class"]), \
             patch("core.dependencies.get_plex_repository", mocks["get_repo"]), \
             patch("core.dependencies.get_mbid_store", mocks["get_mbid"]), \
             patch("core.dependencies.auth_providers.get_user_import_service", mocks["get_user_import"]), \
             patch("core.dependencies.auth_providers.get_plex_user_auth_service", mocks["get_plex_user_auth"]):
            await service.on_plex_settings_changed()

            mocks["repo_class"].reset_circuit_breaker.assert_called_once()
            mocks["get_repo"].cache_clear.assert_called_once()
            mocks["get_user_import"].cache_clear.assert_called_once()
            mocks["get_plex_user_auth"].cache_clear.assert_called_once()
            mocks["new_repo"].clear_cache.assert_awaited_once()
            mocks["mbid_store"].clear_plex_mbid_indexes.assert_awaited_once()


class TestGetPlexRepositoryClientId:
    """Regression for the admin Plex-user-import bug: plex.tv account endpoints
    return 400 without X-Plex-Client-Identifier. An admin who set up Plex by
    pasting a token never ran the OAuth flow that creates `plex_client_id`, so the
    header was dropped and enumeration silently returned []. The provider has to
    create the id, not just read it."""

    def test_configures_client_id_even_when_setting_absent(self):
        from core.dependencies import repo_providers

        prefs = MagicMock()
        prefs.get_plex_connection_raw.return_value = MagicMock(
            enabled=True, plex_url="http://plex:32400", plex_token="tok"
        )
        # The bug condition: the setting was never created (token-paste setup).
        prefs.get_setting.return_value = None
        prefs.get_or_create_setting.return_value = "created-client-id"

        with patch.object(repo_providers, "get_preferences_service", return_value=prefs), \
             patch.object(repo_providers, "get_cache", return_value=AsyncMock()), \
             patch.object(
                 repo_providers,
                 "_get_configured_http_client",
                 return_value=AsyncMock(spec=httpx.AsyncClient),
             ):
            repo_providers.get_plex_repository.cache_clear()
            try:
                repo = repo_providers.get_plex_repository()
            finally:
                repo_providers.get_plex_repository.cache_clear()

        prefs.get_or_create_setting.assert_called_once()
        assert repo._client_id == "created-client-id"
        # The header that plex.tv 400s without now reaches the API.
        assert repo._build_headers()["X-Plex-Client-Identifier"] == "created-client-id"
