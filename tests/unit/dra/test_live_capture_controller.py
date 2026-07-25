from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pytest

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_controller import (
    CaptureLiveCommand,
    DraLiveCaptureController,
    ReconcileCreateCommand,
    ResumePollCommand,
    SelectAndImportCommand,
)
from night_voyager.dra.live_fakes import (
    ScenarioCandidateGateway,
    ScenarioDraLiveTransport,
)
from night_voyager.dra.live_models import (
    DraCaptureInputV1,
    DraCaptureIntentV1,
    DraCaptureReceiptV1,
    DraControllerStopReceiptV1,
    DraFrozenRequestV1,
    DraInspectionRequiredReceiptV1,
    DraPollRecoveryReceiptV1,
    DraReconciliationRequiredReceiptV1,
    derive_identity_hash,
)
from night_voyager.dra.live_storage import LiveReceiptStore
from night_voyager.identity.models import ActorContext, ActorRole

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
CASE_ID = UUID("40000000-0000-0000-0000-000000000003")
ACTOR_ID = UUID("20000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("30000000-0000-0000-0000-000000000001")
QUERY = b"bounded synthetic query"
SOURCE_URL = "https://example.com/contract-source-1"
SECOND_SOURCE_URL = "https://example.com/contract-source-2"


@dataclass
class FakeTime:
    current: float = 0.0
    sleeps: list[float] = field(default_factory=lambda: list[float]())

    def monotonic(self) -> float:
        return self.current

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


def context(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    return ActorContext(
        organization_id=ORGANIZATION_ID,
        actor_id=ACTOR_ID,
        role=role,
        session_id=SESSION_ID,
    )


def private_root(tmp_path: Path) -> Path:
    root = tmp_path / "receipts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def frozen_intent() -> DraCaptureIntentV1:
    scenario = load_live_closure_scenario()
    return DraCaptureIntentV1.freeze(
        DraCaptureInputV1(
            scenario_id=scenario.scenario_id,
            producer=scenario.producer,
            organization_id=ORGANIZATION_ID,
            case_id=CASE_ID,
            expected_case_revision=1,
            advisor_actor_identity_sha256=derive_identity_hash(
                "actor", str(ACTOR_ID)
            ),
            tenant_identity_sha256=derive_identity_hash(
                "tenant", str(ORGANIZATION_ID)
            ),
            request=DraFrozenRequestV1(
                logical_name="query.txt",
                encoding="utf-8",
                byte_length=len(QUERY),
                sha256=hashlib.sha256(QUERY).hexdigest(),
            ),
            receipt_root_id="dra-live-capture-root",
            one_attempt_authorized=True,
        ),
        attempt_id_factory=lambda: "attempt-0000000000000001",
    )


def timed_intent(
    *, deadline_seconds: int, poll_seconds: float
) -> DraCaptureIntentV1:
    capture = frozen_intent().capture.model_dump(mode="json")
    capture["deadline_seconds"] = deadline_seconds
    capture["poll_seconds"] = poll_seconds
    return DraCaptureIntentV1.freeze(
        DraCaptureInputV1.model_validate(capture),
        attempt_id_factory=lambda: "attempt-0000000000000001",
    )


def query_file(tmp_path: Path) -> Path:
    path = tmp_path / "query.txt"
    path.write_bytes(QUERY)
    path.chmod(0o600)
    return path


@pytest.mark.asyncio
async def test_capture_pauses_for_inspection_then_imports_without_second_run(
    tmp_path: Path,
) -> None:
    scenario = load_live_closure_scenario()
    transport = ScenarioDraLiveTransport(scenario)
    gateway = ScenarioCandidateGateway()
    with LiveReceiptStore.open(private_root(tmp_path)) as store:
        controller = DraLiveCaptureController(transport, gateway, store)
        intent = frozen_intent()
        preflight = controller.preflight(intent)
        assert preflight.environment_values_read is False
        assert preflight.filesystem_primitives_ready is True
        assert "DECISION_RESEARCH_AGENT_API_KEY" in (
            preflight.required_environment_names
        )
        inspection = await controller.capture(
            CaptureLiveCommand(
                intent=intent,
                preflight=preflight,
                query_path=query_file(tmp_path),
            )
        )
        assert isinstance(inspection, DraInspectionRequiredReceiptV1)
        assert inspection.permitted_next_command == "select-and-import"
        assert store.artifact_path() is not None
        assert gateway.import_calls == 0

        final = await controller.select_and_import(
            SelectAndImportCommand(
                intent=intent,
                inspection=inspection,
                declared_raw_url=SOURCE_URL,
                context=context(),
            )
        )
        assert isinstance(final, DraCaptureReceiptV1)
        assert final.candidate_authority == "untrusted_candidate"
        assert final.selected_evidence is not None
        assert final.selected_evidence.source_url == SOURCE_URL
        assert final.cleanup_status == "removed"
        assert store.artifact_path() is None
        assert transport.create_calls == 1
        assert gateway.import_calls == 1
        assert gateway.last_view is not None
        assert gateway.last_view.verification is None


@pytest.mark.asyncio
async def test_request_bytes_are_rechecked_before_any_provider_access(
    tmp_path: Path,
) -> None:
    transport = ScenarioDraLiveTransport(load_live_closure_scenario())
    gateway = ScenarioCandidateGateway()
    path = query_file(tmp_path)
    with LiveReceiptStore.open(private_root(tmp_path)) as store:
        controller = DraLiveCaptureController(transport, gateway, store)
        intent = frozen_intent()
        preflight = controller.preflight(intent)
        path.write_text("mutated", encoding="utf-8")
        result = await controller.capture(
            CaptureLiveCommand(
                intent=intent,
                preflight=preflight,
                query_path=path,
            )
        )
        assert isinstance(result, DraControllerStopReceiptV1)
        assert result.public_code == "request_identity_mismatch"
        assert result.provider_attempt_consumed is False
        assert transport.health_calls == 0
        assert transport.create_calls == 0


@pytest.mark.asyncio
async def test_ambiguous_create_stops_and_only_exact_authorized_replay_resumes(
    tmp_path: Path,
) -> None:
    transport = ScenarioDraLiveTransport(
        load_live_closure_scenario(), ambiguous_create_once=True
    )
    gateway = ScenarioCandidateGateway()
    path = query_file(tmp_path)
    with LiveReceiptStore.open(private_root(tmp_path)) as store:
        controller = DraLiveCaptureController(transport, gateway, store)
        intent = frozen_intent()
        preflight = controller.preflight(intent)
        stopped = await controller.capture(
            CaptureLiveCommand(intent=intent, preflight=preflight, query_path=path)
        )
        assert isinstance(stopped, DraReconciliationRequiredReceiptV1)
        assert stopped.permitted_next_command == "reconcile-create"
        assert transport.create_calls == 1

        with pytest.raises(ValueError, match="reconciliation_authorization_required"):
            await controller.reconcile_create(
                ReconcileCreateCommand(
                    intent=intent,
                    preflight=preflight,
                    prior=stopped,
                    query_path=path,
                    exact_replay_authorized=False,
                )
            )
        assert transport.create_calls == 1

        resumed = await controller.reconcile_create(
            ReconcileCreateCommand(
                intent=intent,
                preflight=preflight,
                prior=stopped,
                query_path=path,
                exact_replay_authorized=True,
            )
        )
        assert isinstance(resumed, DraInspectionRequiredReceiptV1)
        assert transport.create_calls == 2
        assert len(set(transport.create_keys)) == 1
        assert transport.requests[0] == transport.requests[1]


@pytest.mark.asyncio
async def test_poll_timeout_resumes_only_the_same_run(tmp_path: Path) -> None:
    scenario = load_live_closure_scenario()
    transport = ScenarioDraLiveTransport(scenario, in_progress_polls=2)
    gateway = ScenarioCandidateGateway()
    path = query_file(tmp_path)
    with LiveReceiptStore.open(private_root(tmp_path)) as store:
        first_time = FakeTime()
        controller = DraLiveCaptureController(
            transport,
            gateway,
            store,
            clock=first_time,
            sleeper=first_time,
        )
        intent = timed_intent(deadline_seconds=1, poll_seconds=1)
        preflight = controller.preflight(intent)
        stopped = await controller.capture(
            CaptureLiveCommand(intent=intent, preflight=preflight, query_path=path)
        )
        assert isinstance(stopped, DraPollRecoveryReceiptV1)
        assert stopped.permitted_next_command == "resume-poll"
        assert transport.create_calls == 1
        assert first_time.sleeps == [1]

        resumed_time = FakeTime()
        resumed = await DraLiveCaptureController(
            transport,
            gateway,
            store,
            clock=resumed_time,
            sleeper=resumed_time,
        ).resume_poll(
            ResumePollCommand(intent=intent, prior=stopped)
        )
        assert isinstance(resumed, DraInspectionRequiredReceiptV1)
        assert resumed.run_id == stopped.run_id
        assert transport.create_calls == 1
        assert resumed_time.sleeps == []


@pytest.mark.asyncio
async def test_polling_sleeps_at_frozen_interval_until_later_terminal(
    tmp_path: Path,
) -> None:
    transport = ScenarioDraLiveTransport(
        load_live_closure_scenario(), in_progress_polls=2
    )
    gateway = ScenarioCandidateGateway()
    fake_time = FakeTime()
    with LiveReceiptStore.open(private_root(tmp_path)) as store:
        controller = DraLiveCaptureController(
            transport,
            gateway,
            store,
            clock=fake_time,
            sleeper=fake_time,
        )
        intent = timed_intent(deadline_seconds=10, poll_seconds=2)
        result = await controller.capture(
            CaptureLiveCommand(
                intent=intent,
                preflight=controller.preflight(intent),
                query_path=query_file(tmp_path),
            )
        )
    assert isinstance(result, DraInspectionRequiredReceiptV1)
    assert fake_time.sleeps == [2, 2]


@pytest.mark.asyncio
async def test_recovery_rejects_missing_or_forged_durable_prior_without_provider(
    tmp_path: Path,
) -> None:
    path = query_file(tmp_path)
    transport = ScenarioDraLiveTransport(
        load_live_closure_scenario(), ambiguous_create_once=True
    )
    root = private_root(tmp_path)
    with LiveReceiptStore.open(root) as store:
        controller = DraLiveCaptureController(
            transport, ScenarioCandidateGateway(), store
        )
        intent = frozen_intent()
        preflight = controller.preflight(intent)
        prior = await controller.capture(
            CaptureLiveCommand(intent=intent, preflight=preflight, query_path=path)
        )
        assert isinstance(prior, DraReconciliationRequiredReceiptV1)
        forged = prior.model_copy(
            update={
                "intent_receipt": prior.intent_receipt.model_copy(
                    update={"sha256": "f" * 64}
                )
            }
        )
        with pytest.raises(ValueError, match="reconciliation_identity_invalid"):
            await controller.reconcile_create(
                ReconcileCreateCommand(
                    intent=intent,
                    preflight=preflight,
                    prior=forged,
                    query_path=path,
                    exact_replay_authorized=True,
                )
            )
        assert transport.create_calls == 1

        (root / "reconciliation-required.json").unlink()
        with pytest.raises(ValueError, match="reconciliation_identity_invalid"):
            await controller.reconcile_create(
                ReconcileCreateCommand(
                    intent=intent,
                    preflight=preflight,
                    prior=prior,
                    query_path=path,
                    exact_replay_authorized=True,
                )
            )
        assert transport.create_calls == 1


@pytest.mark.asyncio
async def test_resume_rejects_cross_run_prior_before_provider_access(
    tmp_path: Path,
) -> None:
    fake_time = FakeTime()
    transport = ScenarioDraLiveTransport(
        load_live_closure_scenario(), in_progress_polls=10
    )
    root = private_root(tmp_path)
    with LiveReceiptStore.open(root) as store:
        intent = timed_intent(deadline_seconds=1, poll_seconds=1)
        controller = DraLiveCaptureController(
            transport,
            ScenarioCandidateGateway(),
            store,
            clock=fake_time,
            sleeper=fake_time,
        )
        prior = await controller.capture(
            CaptureLiveCommand(
                intent=intent,
                preflight=controller.preflight(intent),
                query_path=query_file(tmp_path),
            )
        )
        assert isinstance(prior, DraPollRecoveryReceiptV1)
        forged = prior.model_copy(
            update={
                "thread_id": "forged-thread",
                "run_id": "forged-run",
                "segment_id": "forged-segment",
            }
        )
        with pytest.raises(ValueError, match="poll_recovery_identity_invalid"):
            await controller.resume_poll(
                ResumePollCommand(intent=intent, prior=forged)
            )
        (root / "poll-recovery.json").unlink()
        with pytest.raises(ValueError, match="poll_recovery_identity_invalid"):
            await controller.resume_poll(
                ResumePollCommand(intent=intent, prior=prior)
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("declared_url", "actor_context", "code"),
    (
        ("https://example.com/not-cited", context(), "source_selection_invalid"),
        (SOURCE_URL, context(ActorRole.STUDENT), "candidate_authority_denied"),
        (
            SOURCE_URL,
            ActorContext(
                organization_id=UUID("99999999-9999-4999-8999-999999999999"),
                actor_id=ACTOR_ID,
                role=ActorRole.ADVISOR,
                session_id=SESSION_ID,
            ),
            "candidate_authority_denied",
        ),
    ),
)
async def test_selection_and_actor_fail_closed_without_second_run(
    tmp_path: Path,
    declared_url: str,
    actor_context: ActorContext,
    code: str,
) -> None:
    transport = ScenarioDraLiveTransport(load_live_closure_scenario())
    gateway = ScenarioCandidateGateway()
    with LiveReceiptStore.open(private_root(tmp_path)) as store:
        controller = DraLiveCaptureController(transport, gateway, store)
        intent = frozen_intent()
        inspection = await controller.capture(
            CaptureLiveCommand(
                intent=intent,
                preflight=controller.preflight(intent),
                query_path=query_file(tmp_path),
            )
        )
        assert isinstance(inspection, DraInspectionRequiredReceiptV1)
        stopped = await controller.select_and_import(
            SelectAndImportCommand(
                intent=intent,
                inspection=inspection,
                declared_raw_url=declared_url,
                context=actor_context,
            )
        )
        assert isinstance(stopped, DraControllerStopReceiptV1)
        assert stopped.public_code == code
        assert transport.create_calls == 1
        assert gateway.import_calls == 0
        assert store.artifact_path() is None


@pytest.mark.asyncio
async def test_multiple_cited_rows_import_only_exact_operator_selection(
    tmp_path: Path,
) -> None:
    scenario = load_live_closure_scenario()
    transport = ScenarioDraLiveTransport(scenario)
    first = transport.run.evidence[0]
    second = first.model_copy(
        update={
            "evidence_id": "evidence-contract-source-2",
            "source_url": SECOND_SOURCE_URL,
            "source_identity": SECOND_SOURCE_URL,
        }
    )
    transport.run = transport.run.model_copy(
        update={"evidence": (first, second)}
    )
    gateway = ScenarioCandidateGateway()
    with LiveReceiptStore.open(private_root(tmp_path)) as store:
        controller = DraLiveCaptureController(transport, gateway, store)
        intent = frozen_intent()
        inspection = await controller.capture(
            CaptureLiveCommand(
                intent=intent,
                preflight=controller.preflight(intent),
                query_path=query_file(tmp_path),
            )
        )
        assert isinstance(inspection, DraInspectionRequiredReceiptV1)
        final = await controller.select_and_import(
            SelectAndImportCommand(
                intent=intent,
                inspection=inspection,
                declared_raw_url=SECOND_SOURCE_URL,
                context=context(),
            )
        )
    assert isinstance(final, DraCaptureReceiptV1)
    assert gateway.last_import is not None
    assert len(gateway.last_import.evidence) == 1
    assert gateway.last_import.evidence[0].source_url == SECOND_SOURCE_URL
