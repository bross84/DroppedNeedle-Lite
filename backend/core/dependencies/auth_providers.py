"""Auth dependency providers, wired into the singleton DI system."""

from __future__ import annotations

from core.config import get_settings
from infrastructure.persistence.auth_store import AuthStore

from ._registry import singleton
from .cache_providers import (
    get_cache,
    get_discovery_snapshot_store,
    get_persistence_write_lock,
    get_preferences_service,
)


@singleton
def get_auth_store() -> AuthStore:
    settings = get_settings()
    lock = get_persistence_write_lock()
    return AuthStore(db_path = settings.library_db_path, write_lock = lock)


@singleton
def get_auth_service() -> "AuthService":
    from services.auth_service import AuthService
    return AuthService(
        get_auth_store(), discovery_snapshot_store=get_discovery_snapshot_store()
    )


@singleton
def get_oidc_user_auth_service() -> "OIDCUserAuthService":
    from services.oidc_user_auth_service import OIDCUserAuthService
    from core.dependencies.cache_providers import get_cache
    return OIDCUserAuthService(
        auth_store = get_auth_store(),
        preferences_service = get_preferences_service(),
        cache = get_cache(),
    )
