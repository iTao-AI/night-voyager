from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.dra.live_evaluation import DraLiveOutcomeProjectionV1
from night_voyager.dra.live_outcome import DraLiveOutcomeIntentV1
from night_voyager.identity.models import ActorContext

OUTCOME_PROJECTION_SQL = (
    "SELECT * FROM app.project_dra_live_outcome(:org,:actor,:candidate)"
)


def _identity_hash(value: object) -> str:
    return hashlib.sha256(
        f"night-voyager.dra-live.outcome.v1\0{value}".encode()
    ).hexdigest()


class PostgresLiveOutcomeInspector:
    """Read-only adapter for migration 0010's closed RLS-preserving function."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def inspect(
        self,
        context: ActorContext,
        intent: DraLiveOutcomeIntentV1,
    ) -> DraLiveOutcomeProjectionV1:
        intent.validate_context(context)
        result = await self._session.execute(
            text(OUTCOME_PROJECTION_SQL),
            {
                "org": context.organization_id,
                "actor": context.actor_id,
                "candidate": intent.candidate_id,
            },
        )
        raw = result.mappings().one_or_none()
        if raw is None:
            return DraLiveOutcomeProjectionV1(
                candidate_id=None,
                candidate_count=0,
                verification_count=0,
                approved_verification_count=0,
                promoted_source_pack_id=None,
                promoted_source_pack_version=None,
                promoted_source_entry_id=None,
                promoted_evidence_id=None,
                external_claim=None,
                evidence_role=None,
                external_authority=None,
                governed_task_count=0,
                task_id=None,
                task_state=None,
                planning_run_id=None,
                planning_run_state=None,
                advisor_review_count=0,
                family_decision_count=0,
                decision_receipt_count=0,
                timeline_plan_count=0,
                tenant_isolated=True,
                partial_row_set_absent=True,
                observed_identity_hashes=(),
            )
        row = cast(Mapping[str, object], raw)
        identity_fields = (
            "candidate_id",
            "promoted_source_pack_id",
            "promoted_source_entry_id",
            "promoted_evidence_id",
            "task_id",
            "planning_run_id",
        )
        observed = tuple(
            sorted(
                _identity_hash(row[name])
                for name in identity_fields
                if row[name] is not None
            )
        )
        verification_count = int(cast(int, row["verification_count"]))
        governed_task_count = int(cast(int, row["governed_task_count"]))
        required_identity_present = all(
            row[name] is not None for name in identity_fields
        )
        return DraLiveOutcomeProjectionV1(
            candidate_id=str(row["candidate_id"]),
            candidate_count=1,
            verification_count=verification_count,
            approved_verification_count=int(
                cast(int, row["approved_verification_count"])
            ),
            promoted_source_pack_id=(
                None
                if row["promoted_source_pack_id"] is None
                else str(row["promoted_source_pack_id"])
            ),
            promoted_source_pack_version=cast(
                int | None, row["promoted_source_pack_version"]
            ),
            promoted_source_entry_id=(
                None
                if row["promoted_source_entry_id"] is None
                else str(row["promoted_source_entry_id"])
            ),
            promoted_evidence_id=(
                None
                if row["promoted_evidence_id"] is None
                else str(row["promoted_evidence_id"])
            ),
            external_claim=cast(str | None, row["external_claim"]),
            evidence_role=cast(str | None, row["evidence_role"]),
            external_authority=cast(
                str | None, row["external_authority"]
            ),
            governed_task_count=governed_task_count,
            task_id=(
                None if row["task_id"] is None else str(row["task_id"])
            ),
            task_state=cast(str | None, row["task_state"]),
            planning_run_id=(
                None
                if row["planning_run_id"] is None
                else str(row["planning_run_id"])
            ),
            planning_run_state=cast(
                str | None, row["planning_run_state"]
            ),
            advisor_review_count=int(
                cast(int, row["advisor_review_count"])
            ),
            family_decision_count=int(
                cast(int, row["family_decision_count"])
            ),
            decision_receipt_count=int(
                cast(int, row["decision_receipt_count"])
            ),
            timeline_plan_count=int(
                cast(int, row["timeline_plan_count"])
            ),
            tenant_isolated=True,
            partial_row_set_absent=(
                verification_count <= 1
                and governed_task_count <= 1
                and (
                    not required_identity_present
                    or (
                        verification_count == 1
                        and governed_task_count == 1
                    )
                )
            ),
            observed_identity_hashes=observed,
        )
