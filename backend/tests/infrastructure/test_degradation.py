"""Tests for DegradationContext and contextvar lifecycle."""

import asyncio

import pytest

from infrastructure.degradation import (
    DegradationContext,
    clear_degradation_context,
    get_degradation_context,
    init_degradation_context,
    try_get_degradation_context,
)
from infrastructure.integration_result import IntegrationResult




class TestDegradationContext:
    def test_empty_context(self):
        ctx = DegradationContext()
        assert ctx.summary() == {}
        assert ctx.has_degradation() is False
        assert ctx.degraded_summary() == {}

    def test_record_ok(self):
        ctx = DegradationContext()
        ctx.record(IntegrationResult.ok(data=[1], source="musicbrainz"))
        assert ctx.summary() == {"musicbrainz": "ok"}
        assert ctx.has_degradation() is False

    def test_record_error(self):
        ctx = DegradationContext()
        ctx.record(IntegrationResult.error(source="navidrome", msg="timeout"))
        assert ctx.summary() == {"navidrome": "error"}
        assert ctx.has_degradation() is True
        assert ctx.degraded_summary() == {"navidrome": "error"}

    def test_record_degraded(self):
        ctx = DegradationContext()
        ctx.record(
            IntegrationResult.degraded(data=[], source="audiodb", msg="rate limit")
        )
        assert ctx.summary() == {"audiodb": "degraded"}
        assert ctx.has_degradation() is True

    def test_worst_status_wins(self):
        ctx = DegradationContext()
        ctx.record(IntegrationResult.ok(data=[], source="musicbrainz"))
        ctx.record(IntegrationResult.degraded(data=[], source="musicbrainz", msg="slow"))
        assert ctx.summary() == {"musicbrainz": "degraded"}

    def test_error_beats_degraded(self):
        ctx = DegradationContext()
        ctx.record(
            IntegrationResult.degraded(data=[], source="musicbrainz", msg="slow")
        )
        ctx.record(IntegrationResult.error(source="musicbrainz", msg="503"))
        assert ctx.summary() == {"musicbrainz": "error"}

    def test_cannot_downgrade(self):
        ctx = DegradationContext()
        ctx.record(IntegrationResult.error(source="navidrome", msg="down"))
        ctx.record(IntegrationResult.ok(data=[1], source="navidrome"))
        assert ctx.summary() == {"navidrome": "error"}

    def test_multiple_sources(self):
        ctx = DegradationContext()
        ctx.record(IntegrationResult.ok(data=[], source="musicbrainz"))
        ctx.record(IntegrationResult.error(source="navidrome", msg="down"))
        ctx.record(
            IntegrationResult.degraded(data={}, source="audiodb", msg="slow")
        )
        assert ctx.summary() == {
            "musicbrainz": "ok",
            "navidrome": "error",
            "audiodb": "degraded",
        }
        assert ctx.degraded_summary() == {
            "navidrome": "error",
            "audiodb": "degraded",
        }




class TestContextVarLifecycle:
    def test_no_context_raises(self):
        clear_degradation_context()
        with pytest.raises(RuntimeError, match="outside a request scope"):
            get_degradation_context()

    def test_try_get_returns_none_outside(self):
        clear_degradation_context()
        assert try_get_degradation_context() is None

    def test_init_and_get(self):
        ctx = init_degradation_context()
        assert get_degradation_context() is ctx
        clear_degradation_context()

    def test_clear_removes_context(self):
        init_degradation_context()
        clear_degradation_context()
        assert try_get_degradation_context() is None

    @pytest.mark.asyncio
    async def test_isolated_across_tasks(self):
        """Context in one asyncio task must not leak into another."""
        results: dict[str, bool] = {}

        async def task_a():
            init_degradation_context()
            ctx = get_degradation_context()
            ctx.record(IntegrationResult.error(source="a", msg="fail"))
            await asyncio.sleep(0.01)
            results["a_has_degradation"] = get_degradation_context().has_degradation()
            clear_degradation_context()

        async def task_b():
            await asyncio.sleep(0.005)
            results["b_is_none"] = try_get_degradation_context() is None

        await asyncio.gather(task_a(), task_b())
        assert results["a_has_degradation"] is True
        assert results["b_is_none"] is True
