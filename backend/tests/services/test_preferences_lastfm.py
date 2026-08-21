import pytest
from pathlib import Path
from unittest.mock import MagicMock

from api.v1.schemas.settings import (
    LastFmConnectionSettings,
    LASTFM_SECRET_MASK,
)
from core.config import Settings
from services.preferences_service import PreferencesService


@pytest.fixture
def tmp_config(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")
    settings = MagicMock(spec=Settings)
    settings.config_file_path = config_file
    return settings, config_file


@pytest.fixture
def service(tmp_config):
    settings, _ = tmp_config
    return PreferencesService(settings=settings)


def test_get_lastfm_returns_defaults_when_missing(service):
    result = service.get_lastfm_connection()
    assert isinstance(result, LastFmConnectionSettings)
    assert result.api_key == ""
    assert result.shared_secret == ""
    assert result.session_key == ""
    assert result.username == ""
    assert result.enabled is False


def test_save_and_load_lastfm_connection(service):
    settings = LastFmConnectionSettings(
        api_key="my-key",
        shared_secret="my-secret",
        session_key="",
        username="",
        enabled=True,
    )
    service.save_lastfm_connection(settings)
    loaded = service.get_lastfm_connection()
    assert loaded.api_key == "my-key"
    assert loaded.shared_secret == "my-secret"
    assert loaded.enabled is True


def test_save_trims_whitespace(service):
    settings = LastFmConnectionSettings(
        api_key="  my-key  ",
        shared_secret="  my-secret  ",
        session_key="",
        username="  user  ",
        enabled=True,
    )
    service.save_lastfm_connection(settings)
    loaded = service.get_lastfm_connection()
    assert loaded.api_key == "my-key"
    assert loaded.shared_secret == "my-secret"
    assert loaded.username == "user"


def test_save_preserves_masked_secret(service):
    service.save_lastfm_connection(
        LastFmConnectionSettings(
            api_key="key",
            shared_secret="real-secret-value",
            session_key="",
            username="",
            enabled=True,
        )
    )
    service.save_lastfm_connection(
        LastFmConnectionSettings(
            api_key="key",
            shared_secret=LASTFM_SECRET_MASK + "alue",
            session_key="",
            username="",
            enabled=True,
        )
    )
    loaded = service.get_lastfm_connection()
    assert loaded.shared_secret == "real-secret-value"


def test_clearing_credentials_disables_and_clears_session(service):
    service.save_lastfm_connection(
        LastFmConnectionSettings(
            api_key="key",
            shared_secret="secret",
            session_key="sk-123",
            username="user1",
            enabled=True,
        )
    )
    service.save_lastfm_connection(
        LastFmConnectionSettings(
            api_key="",
            shared_secret="",
            session_key="",
            username="",
            enabled=True,
        )
    )
    loaded = service.get_lastfm_connection()
    assert loaded.enabled is False
    assert loaded.session_key == ""
    assert loaded.username == ""


def test_clearing_api_key_only_disables(service):
    service.save_lastfm_connection(
        LastFmConnectionSettings(
            api_key="key",
            shared_secret="secret",
            session_key="sk-123",
            username="user1",
            enabled=True,
        )
    )
    service.save_lastfm_connection(
        LastFmConnectionSettings(
            api_key="",
            shared_secret="secret",
            session_key=LASTFM_SECRET_MASK,
            username="user1",
            enabled=True,
        )
    )
    loaded = service.get_lastfm_connection()
    assert loaded.enabled is False
    assert loaded.session_key == ""
    assert loaded.username == ""


def test_is_lastfm_enabled_requires_credentials(service):
    """Credentials decide it; the `enabled` flag no longer gates it.

    This previously also required `enabled`, and asserted that True/False
    switched the result. That contract was unreachable in the running app: the
    settings form never sends `enabled`, the save path only ever forces it
    False, and the OAuth exchange passes the old value through, so it was False
    on every install and a valid API key never reached Discover. The assertion
    only held because the test called the service directly with enabled=True.
    """
    assert service.is_lastfm_enabled() is False

    service.save_lastfm_connection(
        LastFmConnectionSettings(
            api_key="key",
            shared_secret="secret",
            session_key="",
            username="",
        )
    )
    assert service.is_lastfm_enabled() is True


def test_lastfm_is_enabled_from_a_config_the_ui_could_actually_produce(service, tmp_config):
    """Regression: the exact on-disk shape a real install has.

    A server with a key and secret saved through the settings screen stores
    `"enabled": false`, because no screen writes that field. Discover must still
    treat Last.fm as available, otherwise the ListenBrainz -> Last.fm fallback
    can never fire and the operator's API key silently does nothing.
    """
    import json

    _, config_file = tmp_config
    service.save_lastfm_connection(
        LastFmConnectionSettings(api_key="key", shared_secret="secret")
    )
    on_disk = json.loads(config_file.read_text())
    assert on_disk["lastfm_settings"]["enabled"] is False, (
        "precondition: this is the shape a real install has on disk"
    )

    assert service.is_lastfm_enabled() is True
