from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from night_voyager.dra.live_controller import (
    DraLiveClosureController,
    ReviewCommand,
)
from night_voyager.dra.live_models import (
    DraDecisionAuthorityV1,
    DraPlanningTaskProjectionV1,
    DraPromotionReceiptV1,
    DraReviewAuthorityV1,
    DraReviewInputV1,
    DraStageStateV1,
    SnapshotIdentityV1,
    derive_identity_hash,
)
from night_voyager.dra.live_storage import LiveReceiptStore
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.skills.models import SkillRuntimePin

ORG = UUID("10000000-0000-4000-8000-000000000001")
ADVISOR = UUID("10000000-0000-4000-8000-000000000002")
PARENT = UUID("10000000-0000-4000-8000-000000000003")
SESSION = UUID("10000000-0000-4000-8000-000000000004")
CASE = UUID("10000000-0000-4000-8000-000000000005")
CANDIDATE = UUID("10000000-0000-4000-8000-000000000006")
PACK = UUID("10000000-0000-4000-8000-000000000007")
TASK = UUID("10000000-0000-4000-8000-000000000008")
RUN = UUID("10000000-0000-4000-8000-000000000009")
REVIEW = UUID("10000000-0000-4000-8000-000000000010")
BRIEF = UUID("10000000-0000-4000-8000-000000000011")
ROUTE = UUID("10000000-0000-4000-8000-000000000012")


def promotion_receipt() -> DraPromotionReceiptV1:
    return DraPromotionReceiptV1(
        intent_sha256="a" * 64,
        attempt_id="attempt-1",
        candidate_id=CANDIDATE,
        dra_evidence_id="evidence-1",
        selected_raw_url="https://example.edu/source",
        promotion_key="b" * 64,
        verification_id=UUID("10000000-0000-4000-8000-000000000013"),
        promoted_source_pack_version=2,
        promoted_source_entry_id=UUID(
            "10000000-0000-4000-8000-000000000014"
        ),
        promoted_evidence_id=UUID(
            "10000000-0000-4000-8000-000000000015"
        ),
        snapshot=SnapshotIdentityV1(
            canonical_url="https://example.edu/source",
            logical_path="source/page.html",
            byte_length=10,
            sha256="c" * 64,
        ),
        stage_states=(
            DraStageStateV1(stage="capture-live", status="completed"),
            DraStageStateV1(stage="promote", status="completed"),
        ),
    )


class FakeClosureAuthority:
    def __init__(self) -> None:
        self.task: DraPlanningTaskProjectionV1 | None = None
        self.review: DraReviewAuthorityV1 | None = None
        self.decision: DraDecisionAuthorityV1 | None = None
        self.task_calls = 0

    async def get_promoted_mapping(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> tuple[UUID, int] | None:
        return (PACK, 2)

    async def get_task(
        self, context: ActorContext, idempotency_key: str
    ) -> DraPlanningTaskProjectionV1 | None:
        return self.task

    async def create_task(
        self,
        context: ActorContext,
        case_id: UUID,
        expected_revision: int,
        source_pack_id: UUID,
        source_pack_version: int,
        idempotency_key: str,
    ) -> DraPlanningTaskProjectionV1:
        self.task_calls += 1
        self.task = DraPlanningTaskProjectionV1(
            task_id=TASK,
            operation="generate_governed_mixed_planning_run_v1",
            source_pack_id=PACK,
            source_pack_version=2,
            status="ready",
            planning_run_id=RUN,
            terminal_event_id=9,
            skill_pin=SkillRuntimePin(
                skill_definition_id=UUID(
                    "10000000-0000-4000-8000-000000000020"
                ),
                skill_version_id=UUID(
                    "10000000-0000-4000-8000-000000000021"
                ),
                skill_activation_event_id=UUID(
                    "10000000-0000-4000-8000-000000000022"
                ),
                skill_activation_sequence=1,
                runtime_binding_sha256="d" * 64,
            ),
        )
        return self.task

    async def get_review(
        self,
        context: ActorContext,
        case_id: UUID,
        planning_run_id: UUID,
    ) -> DraReviewAuthorityV1 | None:
        return self.review

    async def record_review(
        self,
        context: ActorContext,
        case_id: UUID,
        expected_revision: int,
        planning_run_id: UUID,
        eligible_route_ids: tuple[UUID, ...],
        idempotency_key: str,
    ) -> DraReviewAuthorityV1:
        self.review = DraReviewAuthorityV1(
            review_id=REVIEW,
            planning_run_id=RUN,
            brief_id=BRIEF,
            eligible_route_ids=(ROUTE,),
        )
        return self.review

    async def get_decision(
        self, context: ActorContext, brief_id: UUID
    ) -> DraDecisionAuthorityV1 | None:
        return self.decision

    async def record_decision(
        self,
        context: ActorContext,
        brief_id: UUID,
        expected_brief_version: int,
        selected_route_id: UUID,
        budget_min: int,
        budget_max: int,
        trade_offs: tuple[str, ...],
        idempotency_key: str,
    ) -> DraDecisionAuthorityV1:
        self.decision = DraDecisionAuthorityV1(
            decision_id=UUID("10000000-0000-4000-8000-000000000030"),
            decision_receipt_id=UUID(
                "10000000-0000-4000-8000-000000000031"
            ),
            timeline_plan_id=UUID(
                "10000000-0000-4000-8000-000000000032"
            ),
            brief_id=BRIEF,
            selected_route_id=ROUTE,
        )
        return self.decision


def advisor_context() -> ActorContext:
    return ActorContext(
        organization_id=ORG,
        actor_id=ADVISOR,
        role=ActorRole.ADVISOR,
        session_id=SESSION,
    )


@pytest.mark.asyncio
async def test_review_reuses_governed_task_and_records_distinct_ack(
    tmp_path: Path,
) -> None:
    root = tmp_path / "receipts"
    root.mkdir(mode=0o700)
    promotion = promotion_receipt()
    authority = FakeClosureAuthority()
    review_input = DraReviewInputV1(
        intent_sha256=promotion.intent_sha256,
        promotion=promotion,
        organization_id=ORG,
        case_id=CASE,
        expected_case_revision=4,
        candidate_id=CANDIDATE,
        promoted_source_pack_id=PACK,
        promoted_source_pack_version=2,
        advisor_actor_identity_sha256=derive_identity_hash(
            "actor", str(ADVISOR)
        ),
        tenant_identity_sha256=derive_identity_hash("tenant", str(ORG)),
        eligible_route_ids=(ROUTE,),
    )
    with LiveReceiptStore.open(root) as store:
        store.write_receipt("promotion.json", promotion)
        receipt = await DraLiveClosureController(authority, store).review(
            ReviewCommand(review_input, advisor_context())
        )

    assert receipt.acknowledgement == "review_recorded"
    assert receipt.task.operation == "generate_governed_mixed_planning_run_v1"
    assert receipt.task.skill_pin.runtime_binding_sha256 == "d" * 64
    assert receipt.review.brief_id == BRIEF
    assert authority.task_calls == 1


@pytest.mark.asyncio
async def test_review_rejects_wrong_promoted_pack_before_task(
    tmp_path: Path,
) -> None:
    root = tmp_path / "receipts"
    root.mkdir(mode=0o700)
    promotion = promotion_receipt()
    authority = FakeClosureAuthority()
    command = DraReviewInputV1(
        intent_sha256=promotion.intent_sha256,
        promotion=promotion,
        organization_id=ORG,
        case_id=CASE,
        expected_case_revision=4,
        candidate_id=CANDIDATE,
        promoted_source_pack_id=UUID(
            "10000000-0000-4000-8000-000000000099"
        ),
        promoted_source_pack_version=2,
        advisor_actor_identity_sha256=derive_identity_hash(
            "actor", str(ADVISOR)
        ),
        tenant_identity_sha256=derive_identity_hash("tenant", str(ORG)),
        eligible_route_ids=(ROUTE,),
    )
    with LiveReceiptStore.open(root) as store:
        store.write_receipt("promotion.json", promotion)
        with pytest.raises(ValueError, match="promoted_mapping_invalid"):
            await DraLiveClosureController(authority, store).review(
                ReviewCommand(command, advisor_context())
            )
    assert authority.task_calls == 0
