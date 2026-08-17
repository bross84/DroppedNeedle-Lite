"""DI providers for the target-library consumer composition and the two
services that outlived the Connect Apps removal.

The Subsonic/Jellyfin server shims are gone, but three things under
``services/compat/`` are consumed by native routes and stay: the lyrics service
(``/api/v1/local_library`` track lyrics), the avatar service
(``/api/v1/profile/avatar/{user_id}``), and the target consumer composition
itself, which native settings, playlists, scrobbling and cover art all build on.
"""

from __future__ import annotations

from core.config import get_settings

from ._registry import singleton
from .auth_providers import get_auth_store


@singleton
def get_native_lyrics_service() -> "NativeLyricsService":
    from services.compat.native_lyrics_service import NativeLyricsService
    from .service_providers import get_target_local_files_service

    return NativeLyricsService(get_target_local_files_service())


@singleton
def get_compat_avatar_service() -> "CompatAvatarService":
    from services.compat.avatar_service import CompatAvatarService

    return CompatAvatarService(get_settings().cache_dir)


@singleton
def get_target_consumer_composition() -> "TargetConsumerComposition":
    from services.native.target_consumer_composition import (
        build_target_consumer_composition,
    )

    from .cache_providers import (
        get_cache,
        get_native_library_store,
        get_preferences_service,
    )
    from .repo_providers import (
        get_request_history_store,
        get_target_coverart_repository,
        get_user_listening_prefs_store,
    )
    from .service_providers import get_per_user_client_factory

    return build_target_consumer_composition(
        store=get_native_library_store(),
        preferences=get_preferences_service(),
        auth_store=get_auth_store(),
        provider_covers=get_target_coverart_repository(),
        cache=get_cache(),
        cache_dir=get_settings().cache_dir,
        client_factory=get_per_user_client_factory(),
        listening_prefs_store=get_user_listening_prefs_store(),
        request_history=get_request_history_store(),
    )
