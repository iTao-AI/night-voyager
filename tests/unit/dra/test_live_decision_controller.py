from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from night_voyager.dra.live_controller import DecideCommand, DraLiveClosureController
from night_voyager.dra.live_models import (
    DraDecisionInputV1,
    derive_identity_hash,
)
from night_voyager.dra.live_storage import LiveReceiptStore
from night_voyager.identity.models import ActorContext, ActorRole

from .test_live_review_controller import (
    BRIEF,
    ORG,
    PARENT,
    ROUTE,
    SESSION,
    DraReviewInputV1,
    FakeClosureAuthority,
    ReviewCommand,
    advisor_context,
    promotion_receipt,
)
from .test_live_review_controller import (
    CASE as CASE_ID,
)


@pytest.mark.asyncio
async def test_decision_is_distinct_from_capability_completion(
    tmp_path: Path,
) -> None:
    root = tmp_path / "receipts"
    root.mkdir(mode=0o700)
    authority = FakeClosureAuthority()
    promotion = promotion_receipt()
    review_input = DraReviewInputV1(
        intent_sha256=promotion.intent_sha256,
        promotion=promotion,
        organization_id=ORG,
        case_id=CASE_ID,
        expected_case_revision=4,
        candidate_id=promotion.candidate_id,
        promoted_source_pack_id=UUID(
            "10000000-0000-4000-8000-000000000007"
        ),
        promoted_source_pack_version=2,
        advisor_actor_identity_sha256=derive_identity_hash(
            "actor", str(advisor_context().actor_id)
        ),
        tenant_identity_sha256=derive_identity_hash("tenant", str(ORG)),
        eligible_route_ids=(ROUTE,),
    )
    parent_context = ActorContext(
        organization_id=ORG,
        actor_id=PARENT,
        role=ActorRole.PARENT,
        session_id=SESSION,
    )
    with LiveReceiptStore.open(root) as store:
        store.write_receipt("promotion.json", promotion)
        review = await DraLiveClosureController(authority, store).review(
            ReviewCommand(review_input, advisor_context())
        )
        decision = await DraLiveClosureController(authority, store).decide(
            DecideCommand(
                DraDecisionInputV1(
                    intent_sha256=review.intent_sha256,
                    review=review,
                    organization_id=ORG,
                    case_id=CASE_ID,
                    brief_id=BRIEF,
                    expected_brief_version=1,
                    selected_route_id=ROUTE,
                    accepted_budget_min_minor=100,
                    accepted_budget_max_minor=200,
                    accepted_trade_offs=("synthetic proof only",),
                    family_actor_identity_sha256=derive_identity_hash(
                        "actor", str(PARENT)
                    ),
                    tenant_identity_sha256=derive_identity_hash(
                        "tenant", str(ORG)
                    ),
                ),
                parent_context,
            )
        )

    assert decision.acknowledgement == "decision_recorded"
    assert "closure_passed" not in decision.model_dump_json()
    assert decision.decision.brief_id == BRIEF


@pytest.mark.asyncio
async def test_decision_lost_ack_rejects_same_route_with_different_budget_and_tradeoffs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "receipts"
    root.mkdir(mode=0o700)
    authority = FakeClosureAuthority()
    authority.lose_decision_ack = True
    authority.committed_budget = (999, 1000)
    authority.committed_trade_offs = ("conflicting trade-off",)
    promotion = promotion_receipt()
    review_input = DraReviewInputV1(
        intent_sha256=promotion.intent_sha256,
        promotion=promotion,
        organization_id=ORG,
        case_id=CASE_ID,
        expected_case_revision=4,
        candidate_id=promotion.candidate_id,
        promoted_source_pack_id=UUID(
            "10000000-0000-4000-8000-000000000007"
        ),
        promoted_source_pack_version=2,
        advisor_actor_identity_sha256=derive_identity_hash(
            "actor", str(advisor_context().actor_id)
        ),
        tenant_identity_sha256=derive_identity_hash("tenant", str(ORG)),
        eligible_route_ids=(ROUTE,),
    )
    parent_context = ActorContext(
        organization_id=ORG,
        actor_id=PARENT,
        role=ActorRole.PARENT,
        session_id=SESSION,
    )
    with LiveReceiptStore.open(root) as store:
        store.write_receipt("promotion.json", promotion)
        review = await DraLiveClosureController(authority, store).review(
            ReviewCommand(review_input, advisor_context())
        )
        with pytest.raises(ValueError, match="family_decision_projection_invalid"):
            await DraLiveClosureController(authority, store).decide(
                DecideCommand(
                    DraDecisionInputV1(
                        intent_sha256=review.intent_sha256,
                        review=review,
                        organization_id=ORG,
                        case_id=CASE_ID,
                        brief_id=BRIEF,
                        expected_brief_version=1,
                        selected_route_id=ROUTE,
                        accepted_budget_min_minor=100,
                        accepted_budget_max_minor=200,
                        accepted_trade_offs=("synthetic proof only",),
                        family_actor_identity_sha256=derive_identity_hash(
                            "actor", str(PARENT)
                        ),
                        tenant_identity_sha256=derive_identity_hash(
                            "tenant", str(ORG)
                        ),
                    ),
                    parent_context,
                )
            )
        assert "decision-ambiguous.json" in {
            item.logical_name
            for item in store.verify_recovery_bundle().receipts
        }
