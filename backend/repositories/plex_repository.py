from __future__ import annotations

import logging
from typing import Any

import httpx

from core.exceptions import ExternalServiceError, PlexApiError, PlexAuthError
from infrastructure.cache.cache_keys import PLEX_PREFIX
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.degradation import try_get_degradation_context
from infrastructure.integration_result import IntegrationResult
from infrastructure.resilience.retry import CircuitBreaker
from repositories.plex_models import (
    PlexAccount,
    PlexOAuthPin,
    PlexUserProfile,
    parse_plex_user_profile,
    parse_plex_users,
)

logger = logging.getLogger(__name__)

_SOURCE = "plex"

_PLEX_TV_BASE = "https://plex.tv/api/v2"

_plex_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="plex",
)


def _record_degradation(msg: str) -> None:
    ctx = try_get_degradation_context()
    if ctx is not None:
        ctx.record(IntegrationResult.error(source=_SOURCE, msg=msg))


class PlexRepository:
    """Plex account/login surface only (Stage 2 removed the library/playback
    surface). Kept because the Plex login flow (``PlexUserAuthService``) and the
    admin bulk-user-import feature both authenticate against plex.tv and the
    configured server through this class."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: CacheInterface,
        cache_scope: str = "shared",
    ) -> None:
        self._client = http_client
        self._cache = cache
        self._cache_scope = cache_scope
        self._url: str = ""
        self._token: str = ""
        self._client_id: str = ""
        self._configured: bool = False

    def configure(self, url: str, token: str, client_id: str = "") -> None:
        self._url = url.rstrip("/") if url else ""
        self._token = token
        self._client_id = client_id
        self._configured = bool(self._url and self._token)

    def is_configured(self) -> bool:
        return self._configured

    @staticmethod
    def reset_circuit_breaker() -> None:
        _plex_circuit_breaker.reset()

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "X-Plex-Token": self._token,
            "X-Plex-Product": "DroppedNeedle",
            "X-Plex-Version": "1.0",
            "Accept": "application/json",
        }
        if self._client_id:
            headers["X-Plex-Client-Identifier"] = self._client_id
        return headers

    async def get_machine_identifier(self) -> str | None:
        cache_key = f"{PLEX_PREFIX}machine_identifier"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached if cached else None

        if not self._configured:
            return None

        try:
            response = await self._client.get(
                f"{self._url}/identity",
                headers = self._build_headers(),
                timeout = 10.0,
            )
        except httpx.HTTPError as exc:
            logger.warning(f"Failed to get Plex machine identifier: {exc}")
            raise ExternalServiceError("Plex request failed") from exc

        if response.status_code != 200:
            return None

        try:
            data = response.json()
        except Exception as exc:
            logger.warning(f"Plex returned invalid JSON for /identity: {exc}")
            raise PlexApiError("Plex returned invalid JSON for /identity") from exc

        machine_id = (
            data.get("MediaContainer", {}).get("machineIdentifier") or data.get("machineIdentifier")
        )
        if machine_id:
            await self._cache.set(cache_key, machine_id, ttl_seconds = 3600)
        else:
            await self._cache.set(cache_key, "", ttl_seconds = 300)
        return machine_id or None

    async def create_oauth_pin(self, client_id: str) -> PlexOAuthPin:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            response = await client.post(
                f"{_PLEX_TV_BASE}/pins",
                headers={
                    "X-Plex-Product": "DroppedNeedle",
                    "X-Plex-Client-Identifier": client_id,
                    "Accept": "application/json",
                },
                data={"strong": "true"},
            )
            if response.status_code != 201:
                raise PlexApiError(f"Failed to create OAuth pin ({response.status_code})")
            data = response.json()
            return PlexOAuthPin(
                id=data.get("id", 0),
                code=data.get("code", ""),
            )

    async def poll_oauth_pin(self, pin_id: int, client_id: str) -> str | None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(
                f"{_PLEX_TV_BASE}/pins/{pin_id}",
                headers={
                    "X-Plex-Client-Identifier": client_id,
                    "Accept": "application/json",
                },
            )
            if response.status_code != 200:
                return None
            data = response.json()
            token = data.get("authToken")
            return token if token else None

    async def _plex_tv_get(
        self,
        path: str,
        auth_token: str,
        client_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        # Account-scoped plex.tv call authenticated with a user's auth token (not
        # the configured server token). Used by the login flow.
        headers = {
            "X-Plex-Token": auth_token,
            "X-Plex-Product": "DroppedNeedle",
            "X-Plex-Client-Identifier": client_id,
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    f"{_PLEX_TV_BASE}{path}", params=params, headers=headers
                )
        except httpx.HTTPError as exc:
            raise PlexApiError(f"Plex request failed: {exc}") from exc
        if response.status_code in (401, 403):
            raise PlexAuthError(f"Plex authentication failed ({response.status_code})")
        if response.status_code != 200:
            raise PlexApiError(f"Plex request failed ({response.status_code})")
        try:
            return response.json()
        except Exception as exc:  # noqa: BLE001
            raise PlexApiError(f"Plex returned invalid JSON for {path}") from exc

    async def get_account_profile(self, auth_token: str, client_id: str) -> PlexUserProfile:
        data = await self._plex_tv_get("/user", auth_token, client_id)
        if not isinstance(data, dict):
            raise PlexApiError("Unexpected Plex /user response shape")
        profile = parse_plex_user_profile(data)
        if not profile.uuid:
            raise PlexApiError("Plex /user response missing uuid")
        return profile

    async def get_account_server_ids(self, auth_token: str, client_id: str) -> set[str]:
        # clientIdentifiers of servers the account can reach (plex.tv /resources).
        # Lenient parse - Plex lists client devices with no accessToken, which the
        # generated SDK model rejected, breaking login for everyone.
        devices = await self._get_account_resources(auth_token, client_id)
        server_ids: set[str] = set()
        for device in devices:
            cid = device.get("clientIdentifier")
            provides = device.get("provides") or ""
            if cid and "server" in provides:
                server_ids.add(str(cid))
        return server_ids

    async def get_server_access_token(
        self,
        auth_token: str,
        client_id: str,
        machine_id: str,
    ) -> str | None:
        """Resolve the PMS-specific token documented on plex.tv resources.

        Verified against the Plex API 1.2.2 resource contract on 2026-07-17:
        account tokens authorize ``/api/v2/resources`` and each PMS resource's
        ``accessToken`` is used for requests to that server.
        """
        devices = await self._get_account_resources(auth_token, client_id)
        for device in devices:
            provides = str(device.get("provides") or "")
            if (
                device.get("clientIdentifier") == machine_id
                and "server" in provides
            ):
                token = device.get("accessToken")
                return str(token) if token else None
        return None

    async def _get_account_resources(
        self, auth_token: str, client_id: str
    ) -> list[dict[str, Any]]:
        data = await self._plex_tv_get(
            "/resources",
            auth_token,
            client_id,
            params={"includeHttps": 1, "includeRelay": 1},
        )
        if not isinstance(data, list):
            return []
        return [device for device in data if isinstance(device, dict)]

    async def enumerate_users(self) -> list[PlexAccount]:
        # Enumerate Plex Home/managed users + shared friends for admin import
        # (Phase 6, D5). Hits the plex.tv account API with the admin account
        # token, NOT the server.
        # Home + friends are two calls merged and de-duplicated by uuid.
        if not self._token:
            return []
        headers = self._build_headers()
        home = await self._fetch_plex_tv_accounts(
            f"{_PLEX_TV_BASE}/home/users", "home", headers
        )
        friends = await self._fetch_plex_tv_accounts(
            f"{_PLEX_TV_BASE}/friends", "friend", headers
        )
        merged: dict[str, PlexAccount] = {}
        for account in (*home, *friends):
            merged.setdefault(account.uuid, account)
        return list(merged.values())

    async def _fetch_plex_tv_accounts(
        self, url: str, source: str, headers: dict[str, str]
    ) -> list[PlexAccount]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(url, headers=headers)
            if response.status_code != 200:
                _record_degradation(
                    f"Plex {source} enumeration failed ({response.status_code})"
                )
                return []
            return parse_plex_users(response.json(), source)
        except Exception as exc:  # noqa: BLE001
            _record_degradation(f"Plex {source} enumeration error: {exc}")
            return []

    async def clear_cache(self) -> None:
        await self._cache.clear_prefix(PLEX_PREFIX)
