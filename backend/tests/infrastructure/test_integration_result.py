"""Tests for IntegrationResult and aggregate_status."""

import pytest

from infrastructure.integration_result import (
    IntegrationResult,
    aggregate_status,
)




class TestIntegrationResultOk:
    def test_ok_carries_data(self):
        r = IntegrationResult.ok(data=["a", "b"], source="musicbrainz")
        assert r.data == ["a", "b"]
        assert r.source == "musicbrainz"
        assert r.status == "ok"
        assert r.error_message is None

    def test_is_ok_true(self):
        r = IntegrationResult.ok(data=42, source="navidrome")
        assert r.is_ok is True
        assert r.is_degraded is False
        assert r.is_error is False


class TestIntegrationResultDegraded:
    def test_degraded_carries_partial_data(self):
        r = IntegrationResult.degraded(
            data={"stale": True}, source="audiodb", msg="rate limited"
        )
        assert r.data == {"stale": True}
        assert r.source == "audiodb"
        assert r.status == "degraded"
        assert r.error_message == "rate limited"

    def test_is_degraded_true(self):
        r = IntegrationResult.degraded(data=[], source="lastfm", msg="timeout")
        assert r.is_degraded is True
        assert r.is_ok is False
        assert r.is_error is False


class TestIntegrationResultError:
    def test_error_has_no_data(self):
        r = IntegrationResult.error(source="musicbrainz", msg="503 Service Unavailable")
        assert r.data is None
        assert r.source == "musicbrainz"
        assert r.status == "error"
        assert r.error_message == "503 Service Unavailable"

    def test_is_error_true(self):
        r = IntegrationResult.error(source="wikidata", msg="boom")
        assert r.is_error is True
        assert r.is_ok is False
        assert r.is_degraded is False




class TestDataOr:
    def test_returns_data_when_present(self):
        r = IntegrationResult.ok(data=[1, 2, 3], source="mb")
        assert r.data_or([]) == [1, 2, 3]

    def test_returns_default_when_none(self):
        r = IntegrationResult.error(source="mb", msg="down")
        assert r.data_or([]) == []

    def test_returns_data_for_degraded(self):
        r = IntegrationResult.degraded(data={"partial": True}, source="mb", msg="slow")
        assert r.data_or({}) == {"partial": True}




class TestImmutability:
    def test_frozen(self):
        r = IntegrationResult.ok(data="hello", source="test")
        with pytest.raises(AttributeError):
            r.data = "goodbye"  # type: ignore[misc]




class TestAggregateStatus:
    def test_all_ok(self):
        assert aggregate_status(
            IntegrationResult.ok(1, "a"),
            IntegrationResult.ok(2, "b"),
        ) == "ok"

    def test_one_degraded(self):
        assert aggregate_status(
            IntegrationResult.ok(1, "a"),
            IntegrationResult.degraded(2, "b", "slow"),
        ) == "degraded"

    def test_one_error(self):
        assert aggregate_status(
            IntegrationResult.ok(1, "a"),
            IntegrationResult.degraded(2, "b", "slow"),
            IntegrationResult.error("c", "down"),
        ) == "error"

    def test_empty(self):
        assert aggregate_status() == "ok"

    def test_error_short_circuits(self):
        assert aggregate_status(
            IntegrationResult.error("a", "x"),
            IntegrationResult.ok(1, "b"),
        ) == "error"
