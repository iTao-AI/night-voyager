from __future__ import annotations

from collections.abc import Mapping

import pytest

from night_voyager.dra.models import DraRunAcceptanceV1
from night_voyager.dra.reconciliation import (
    DraAmbiguousOutcome,
    DraReconciliationRequired,
    DraRunReconciler,
    DraTransportConflict,
)


def accepted(*, replay: bool = False, run_id: str = "run-1") -> DraRunAcceptanceV1:
    return DraRunAcceptanceV1(
        thread_id="thread-1",
        run_id=run_id,
        segment_id="segment-1",
        idempotent_replay=replay,
    )


class FakeTransport:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.create_calls: list[tuple[Mapping[str, object], str]] = []
        self.cancel_calls = 0

    async def create_run(
        self, request: Mapping[str, object], idempotency_key: str
    ) -> DraRunAcceptanceV1:
        self.create_calls.append((request, idempotency_key))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, DraRunAcceptanceV1)
        return outcome


@pytest.mark.asyncio
async def test_lost_ack_replays_once_with_same_key_and_request() -> None:
    request = {"profile_id": "generic", "query": "bounded synthetic query"}
    transport = FakeTransport([DraAmbiguousOutcome(), accepted(replay=True)])
    acceptance = await DraRunReconciler(transport).create(
        request, "key-1234567890123456"
    )
    assert acceptance.idempotent_replay is True
    assert transport.create_calls == [(request, "key-1234567890123456")] * 2
    assert transport.cancel_calls == 0


@pytest.mark.asyncio
async def test_replayed_identity_must_match_original_observation() -> None:
    request = {"profile_id": "generic", "query": "bounded synthetic query"}
    transport = FakeTransport(
        [DraAmbiguousOutcome(observed=accepted()), accepted(replay=True, run_id="run-2")]
    )
    with pytest.raises(DraReconciliationRequired, match="dra_reconciliation_required"):
        await DraRunReconciler(transport).create(request, "key-1234567890123456")
    assert len(transport.create_calls) == 2


@pytest.mark.asyncio
async def test_conflict_is_not_retried() -> None:
    request = {"profile_id": "generic", "query": "bounded synthetic query"}
    transport = FakeTransport([DraTransportConflict()])
    with pytest.raises(DraTransportConflict):
        await DraRunReconciler(transport).create(request, "key-1234567890123456")
    assert len(transport.create_calls) == 1


@pytest.mark.asyncio
async def test_ambiguous_replay_is_attempted_only_once() -> None:
    request = {"profile_id": "generic", "query": "bounded synthetic query"}
    transport = FakeTransport([DraAmbiguousOutcome(), DraAmbiguousOutcome()])
    with pytest.raises(DraReconciliationRequired):
        await DraRunReconciler(transport).create(request, "key-1234567890123456")
    assert len(transport.create_calls) == 2
