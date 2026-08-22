"""Phase 6 (AuthMultiUser D5) UserImportService tests: idempotent admin import of
Plex users into pre-provisioned auth_users + pre-linked auth_providers,
driven through a real temp AuthStore with faked media repositories."""

from __future__ import annotations

import asyncio

import pytest

from core.exceptions import RegistrationError
from infrastructure.persistence.auth_store import AuthStore
from repositories.plex_models import PlexAccount
from services.plex_user_auth_service import PlexUserAuthService
from services.user_import_service import UserImportService


class _FakePlexRepo:
    def __init__(self, accounts):
        self._accounts = accounts

    async def enumerate_users(self):
        return list(self._accounts)


class _FakePrefs:
    pass


def _service(store, *, plex=None, prefs=None):
    return UserImportService(
        store,
        _FakePlexRepo(plex or []),
        prefs or _FakePrefs(),
    )


def test_reimport_is_idempotent(tmp_path):
    async def scenario():
        store = AuthStore(tmp_path / "library.db")
        account = PlexAccount(
            uuid="plex-uuid-3",
            username="carol",
            title="Carol",
            email=None,
            thumb=None,
            source="home",
        )
        svc = _service(store, plex=[account])

        first = await svc.import_users("plex", ["plex-uuid-3"])
        assert len(first.imported) == 1
        before = await store.count_users()

        second = await svc.import_users("plex", ["plex-uuid-3"])
        assert second.imported == []
        assert second.skipped == ["plex-uuid-3"]
        assert await store.count_users() == before  # no duplicate row

    asyncio.run(scenario())


def test_username_dedup_for_same_display_name(tmp_path):
    async def scenario():
        store = AuthStore(tmp_path / "library.db")
        accounts = [
            PlexAccount(uuid="plex-uuid-4", username="john4", title="John", email=None, thumb=None, source="home"),
            PlexAccount(uuid="plex-uuid-5", username="john5", title="John", email=None, thumb=None, source="home"),
        ]
        svc = _service(store, plex=accounts)

        result = await svc.import_users("plex", ["plex-uuid-4", "plex-uuid-5"])

        assert len(result.imported) == 2
        usernames = sorted(u.username for u in result.imported)
        assert usernames == ["john", "john-2"]

    asyncio.run(scenario())


def test_plex_uuid_join_matches_first_login(tmp_path, monkeypatch):
    async def scenario():
        store = AuthStore(tmp_path / "library.db")
        account = PlexAccount(
            uuid="plex-uuid-1",
            username="bob",
            title="Bob",
            email=None,
            thumb="https://plex.tv/u/1/avatar",
            source="home",
        )
        svc = _service(store, plex=[account])

        result = await svc.import_users("plex", ["plex-uuid-1"])
        assert len(result.imported) == 1
        imported = result.imported[0]
        assert imported.avatar_url == "https://plex.tv/u/1/avatar"  # real thumb persisted

        provider = await store.get_auth_provider("plex", "plex-uuid-1")
        assert provider is not None
        assert provider.user_id == imported.id

        # First SSO login: _find_or_create_user keys on profile["uuid"]. It must
        # return the pre-provisioned user and NOT create a second account.
        monkeypatch.setattr("services.plex_user_auth_service.encrypt", lambda s: s)
        plex_auth = PlexUserAuthService(store, _FakePlexRepo([]), _FakePrefs())
        before = await store.count_users()
        profile = {"uuid": "plex-uuid-1", "email": None, "display_name": "Bob", "thumb": None}
        logged_in = await plex_auth._find_or_create_user(profile, auth_token="tok")
        assert logged_in.id == imported.id
        assert await store.count_users() == before

    asyncio.run(scenario())


def test_email_collision_links_to_existing_user(tmp_path, monkeypatch):
    async def scenario():
        store = AuthStore(tmp_path / "library.db")
        existing = await store.create_user(
            id="u-existing",
            display_name="Existing",
            role="user",
            email="a@b.c",
            username="existing",
            username_display="Existing",
        )
        account = PlexAccount(
            uuid="plex-uuid-2",
            username="alias",
            title="Alias",
            email="a@b.c",
            thumb=None,
            source="friend",
        )
        svc = _service(store, plex=[account])
        before = await store.count_users()

        result = await svc.import_users("plex", ["plex-uuid-2"])

        assert result.imported == []
        assert len(result.linked) == 1
        assert result.linked[0].id == existing.id
        assert await store.count_users() == before  # L1: no new auth_users row

        provider = await store.get_auth_provider("plex", "plex-uuid-2")
        assert provider is not None
        assert provider.user_id == existing.id
        assert provider.provider_data is None

        refreshed = await store.get_user_by_id(existing.id)
        assert refreshed.email == "a@b.c"  # untouched
        assert refreshed.username == "existing"

        # Subsequent SSO login resolves into the existing account, not a new one.
        monkeypatch.setattr("services.plex_user_auth_service.encrypt", lambda s: s)
        plex_auth = PlexUserAuthService(store, _FakePlexRepo([]), _FakePrefs())
        profile = {"uuid": "plex-uuid-2", "email": "a@b.c", "display_name": "Alias", "thumb": None}
        logged_in = await plex_auth._find_or_create_user(profile, auth_token="tok")
        assert logged_in.id == existing.id

    asyncio.run(scenario())


def test_list_plex_marks_already_imported(tmp_path):
    async def scenario():
        store = AuthStore(tmp_path / "library.db")
        accounts = [
            PlexAccount(uuid="plex-uuid-7", username="alice7", title="Alice", email=None, thumb=None, source="home"),
            PlexAccount(uuid="plex-uuid-8", username="bob8", title="Bob", email=None, thumb=None, source="home"),
        ]
        svc = _service(store, plex=accounts)
        await svc.import_users("plex", ["plex-uuid-7"])

        candidates = await svc.list_plex_users()
        by_uid = {c.provider_uid: c for c in candidates}
        assert by_uid["plex-uuid-7"].already_imported is True
        assert by_uid["plex-uuid-8"].already_imported is False

    asyncio.run(scenario())


def test_unsupported_provider_raises_registration_error(tmp_path):
    async def scenario():
        store = AuthStore(tmp_path / "library.db")
        svc = _service(store)
        with pytest.raises(RegistrationError):
            await svc.import_users("navidrome", ["x"])

    asyncio.run(scenario())


def test_unknown_uid_is_skipped_not_imported(tmp_path):
    async def scenario():
        store = AuthStore(tmp_path / "library.db")
        account = PlexAccount(uuid="plex-uuid-9", username="dave9", title="Dave", email=None, thumb=None, source="home")
        svc = _service(store, plex=[account])

        result = await svc.import_users("plex", ["does-not-exist"])

        assert result.imported == []
        assert result.skipped == ["does-not-exist"]

    asyncio.run(scenario())
