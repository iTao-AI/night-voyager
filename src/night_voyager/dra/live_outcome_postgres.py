from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.dra.live_evaluation import (
    DraDurableCandidateIdentityV2,
    DraLiveOutcomeProjectionV2,
)
from night_voyager.dra.live_outcome import DraLiveOutcomeIntentV1
from night_voyager.dra.models import (
    DraObservedProfileManifestV1,
    DraProducerPinV2,
    DraRunRequestIdentityV2,
)
from night_voyager.identity.models import ActorContext
from night_voyager.identity.repository import IdentityRepository

OUTCOME_PROJECTION_SQL = (
    "SELECT * FROM app.project_dra_live_outcome(:org,:actor,:candidate)"
)


def _identity_hash(value: object) -> str:
    return hashlib.sha256(
        f"night-voyager.dra-live.outcome.v1\0{value}".encode()
    ).hexdigest()


def _strict_candidate_identity(
    row: Mapping[str, object],
) -> DraDurableCandidateIdentityV2 | None:
    ref_kind = row.get("producer_ref_kind")
    profile_id = row.get("profile_id")
    if ref_kind == "release" and profile_id == "generic":
        return None
    if ref_kind != "commit" or profile_id != "generic-strict-citation":
        raise ValueError("dra_strict_candidate_identity_invalid")
    producer = DraProducerPinV2.model_validate(
        {
            "repository": row.get("producer_repository"),
            "ref_kind": ref_kind,
            "ref": row.get("producer_ref"),
            "commit": row.get("producer_commit"),
            "consumer_contract_schema": row.get("contract_schema"),
            "consumer_fixture_sha256": row.get("fixture_sha256"),
            "profile_id": profile_id,
            "profile_version": row.get("profile_version"),
            "proof_schema": row.get("proof_schema"),
        }
    )
    request_identity = DraRunRequestIdentityV2.model_validate(
        {
            "schema_version": (
                "night-voyager.dra-run-request-identity.v2"
            ),
            "profile_id": profile_id,
            "request_sha256": row.get("request_identity_sha256"),
        }
    )
    observed_profile = DraObservedProfileManifestV1.model_validate(
        {
            "schema_version": (
                "night-voyager.dra-observed-profile-manifest.v1"
            ),
            "profile_id": profile_id,
            "profile_version": row.get("profile_version"),
        }
    )
    return DraDurableCandidateIdentityV2(
        schema_version="night-voyager.dra-durable-candidate-identity.v2",
        candidate_id=str(row["candidate_id"]),
        producer=producer,
        request_identity=request_identity,
        observed_profile=observed_profile,
    )


class PostgresLiveOutcomeInspector:
    """Read-only adapter for migration 0011's closed RLS-preserving function."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def inspect(
        self,
        context: ActorContext,
        intent: DraLiveOutcomeIntentV1,
    ) -> DraLiveOutcomeProjectionV2:
        intent.validate_context(context)
        await IdentityRepository(self._session).set_actor_context(context)
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
            return DraLiveOutcomeProjectionV2(
                schema_version=(
                    "night-voyager.dra-live-outcome-projection.v2"
                ),
                durable_candidate=None,
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
                verification_id=None,
                execution_count=0,
                execution_id=None,
                execution_planning_run_id=None,
                terminal_event_count=0,
                terminal_event_id=None,
                terminal_event_planning_run_id=None,
                sse_cursor=None,
                skill_definition_id=None,
                skill_version_id=None,
                skill_activation_event_id=None,
                skill_activation_sequence=None,
                runtime_binding_sha256=None,
                advisor_review_count=0,
                review_id=None,
                brief_id=None,
                family_decision_count=0,
                decision_id=None,
                decision_receipt_count=0,
                decision_receipt_id=None,
                timeline_plan_count=0,
                timeline_plan_id=None,
                tenant_isolated=True,
                partial_row_set_absent=True,
                observed_identity_hashes=(),
            )
        row = cast(Mapping[str, object], raw)
        durable_candidate = _strict_candidate_identity(row)
        identity_fields = (
            "candidate_id",
            "promoted_source_pack_id",
            "promoted_source_entry_id",
            "promoted_evidence_id",
            "task_id",
            "planning_run_id",
            "verification_id",
            "execution_id",
            "review_id",
            "brief_id",
            "decision_id",
            "decision_receipt_id",
            "timeline_plan_id",
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
        return DraLiveOutcomeProjectionV2(
            schema_version="night-voyager.dra-live-outcome-projection.v2",
            durable_candidate=durable_candidate,
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
            verification_id=(
                None if row["verification_id"] is None else str(row["verification_id"])
            ),
            execution_count=int(cast(int, row["execution_count"])),
            execution_id=(
                None if row["execution_id"] is None else str(row["execution_id"])
            ),
            execution_planning_run_id=(
                None
                if row["execution_planning_run_id"] is None
                else str(row["execution_planning_run_id"])
            ),
            terminal_event_count=int(cast(int, row["terminal_event_count"])),
            terminal_event_id=cast(int | None, row["terminal_event_id"]),
            terminal_event_planning_run_id=(
                None
                if row["terminal_event_planning_run_id"] is None
                else str(row["terminal_event_planning_run_id"])
            ),
            sse_cursor=cast(int | None, row["sse_cursor"]),
            skill_definition_id=(
                None
                if row["skill_definition_id"] is None
                else str(row["skill_definition_id"])
            ),
            skill_version_id=(
                None
                if row["skill_version_id"] is None
                else str(row["skill_version_id"])
            ),
            skill_activation_event_id=(
                None
                if row["skill_activation_event_id"] is None
                else str(row["skill_activation_event_id"])
            ),
            skill_activation_sequence=cast(
                int | None, row["skill_activation_sequence"]
            ),
            runtime_binding_sha256=cast(
                str | None, row["runtime_binding_sha256"]
            ),
            advisor_review_count=int(
                cast(int, row["advisor_review_count"])
            ),
            review_id=None if row["review_id"] is None else str(row["review_id"]),
            brief_id=None if row["brief_id"] is None else str(row["brief_id"]),
            family_decision_count=int(
                cast(int, row["family_decision_count"])
            ),
            decision_id=(
                None if row["decision_id"] is None else str(row["decision_id"])
            ),
            decision_receipt_count=int(
                cast(int, row["decision_receipt_count"])
            ),
            decision_receipt_id=(
                None
                if row["decision_receipt_id"] is None
                else str(row["decision_receipt_id"])
            ),
            timeline_plan_count=int(
                cast(int, row["timeline_plan_count"])
            ),
            timeline_plan_id=(
                None
                if row["timeline_plan_id"] is None
                else str(row["timeline_plan_id"])
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
