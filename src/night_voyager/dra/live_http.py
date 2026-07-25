from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.dra.live_models import (
    DraDecisionAuthorityV1,
    DraPlanningTaskProjectionV1,
    DraReviewAuthorityV1,
)
from night_voyager.dra.models import DraCandidateImportV1
from night_voyager.dra.ports import (
    DraCandidateViewV1,
    DraVerificationViewV1,
    VerifyDraCandidateCommand,
)
from night_voyager.dra.postgres import BASELINE_SOURCE_PACK_ID
from night_voyager.identity.models import ActorContext
from night_voyager.skills.models import SkillRuntimePin


class HttpResponsePort(Protocol):
    @property
    def status_code(self) -> int: ...

    def json(self) -> object: ...

    def raise_for_status(self) -> None: ...


class AsyncHttpClientPort(Protocol):
    async def get(self, url: str, *, headers: dict[str, str]) -> HttpResponsePort: ...

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: object,
    ) -> HttpResponsePort: ...


@dataclass(frozen=True, slots=True)
class EphemeralHttpAuthority:
    origin: str
    session_value: str
    csrf_value: str


class NightVoyagerAuthorityGateway:
    """Narrow HTTP adapter; ephemeral authority values never enter receipts."""

    def __init__(
        self,
        client: Any,
        authority: EphemeralHttpAuthority,
    ) -> None:
        self._client = client
        self._authority = authority
        self._tasks: dict[str, DraPlanningTaskProjectionV1] = {}
        self._reviews: dict[UUID, DraReviewAuthorityV1] = {}

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Origin": self._authority.origin,
            "X-CSRF-Token": self._authority.csrf_value,
            "Cookie": (f"night_voyager_session={self._authority.session_value}"),
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    @staticmethod
    def _projection_payload(response: HttpResponsePort) -> dict[str, object]:
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("night_voyager_http_response_invalid")
        payload = cast(dict[str, object], value).copy()
        if payload.get("schema_version") != 1:
            raise ValueError("night_voyager_http_response_invalid")
        payload.pop("schema_version")
        return payload

    async def import_candidate(
        self,
        context: ActorContext,
        candidate_import: DraCandidateImportV1,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        del context
        payload = candidate_import.model_dump(
            mode="json", exclude_computed_fields=True
        )
        payload.pop("organization_id")
        payload.pop("case_id")
        response = await self._client.post(
            f"/api/v1/cases/{candidate_import.case_id}/dra-candidates",
            headers=self._headers(idempotency_key),
            json=payload,
        )
        response.raise_for_status()
        return DraCandidateViewV1.model_validate(self._projection_payload(response))

    async def get_candidate(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> DraCandidateViewV1 | None:
        del context
        response = await self._client.get(
            f"/api/v1/cases/{case_id}/dra-candidates/{candidate_id}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return DraCandidateViewV1.model_validate(self._projection_payload(response))

    async def promote_candidate(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        idempotency_key: str,
    ) -> DraVerificationViewV1:
        del context
        response = await self._client.post(
            (
                f"/api/v1/cases/{command.case_id}/dra-candidates/"
                f"{command.candidate_id}/verification-decisions"
            ),
            headers=self._headers(idempotency_key),
            json={
                "schema_version": 1,
                "expected_case_revision": command.expected_case_revision,
                "dra_evidence_id": command.dra_evidence_id,
                "decision": command.decision,
                "reason": command.reason,
                "source_attestation": (
                    command.source_attestation.model_dump(mode="json")
                    if command.source_attestation is not None
                    else None
                ),
            },
        )
        response.raise_for_status()
        return DraVerificationViewV1.model_validate(
            self._projection_payload(response)
        )

    async def get_promoted_mapping(
        self, context: ActorContext, case_id: UUID, candidate_id: UUID
    ) -> tuple[UUID, int] | None:
        candidate = await self.get_candidate(context, case_id, candidate_id)
        if (
            candidate is None
            or candidate.verification is None
            or candidate.verification.promoted_source_pack_version is None
        ):
            return None
        return (
            BASELINE_SOURCE_PACK_ID,
            candidate.verification.promoted_source_pack_version,
        )

    async def get_task(
        self, context: ActorContext, idempotency_key: str
    ) -> DraPlanningTaskProjectionV1 | None:
        del context
        return self._tasks.get(idempotency_key)

    async def create_task(
        self,
        context: ActorContext,
        case_id: UUID,
        expected_revision: int,
        source_pack_id: UUID,
        source_pack_version: int,
        idempotency_key: str,
    ) -> DraPlanningTaskProjectionV1:
        del context
        request_payload = {
            "case_id": str(case_id),
            "operation": "generate_governed_mixed_planning_run_v1",
            "expected_case_revision": expected_revision,
            "source_pack_id": str(source_pack_id),
            "source_pack_version": source_pack_version,
            "policy_version": "m3a-policy-v1",
        }
        response = await self._client.post(
            f"/api/v1/cases/{case_id}/agent-tasks",
            headers=self._headers(idempotency_key),
            json={
                "schema_version": 1,
                **{
                    key: value
                    for key, value in request_payload.items()
                    if key != "case_id"
                },
            },
        )
        response.raise_for_status()
        raw_value = response.json()
        if not isinstance(raw_value, dict) or "task_id" not in raw_value:
            raise ValueError("planning_task_response_invalid")
        raw = cast(dict[str, object], raw_value)
        task_id = UUID(str(raw["task_id"]))
        for _ in range(60):
            current_response = await self._client.get(
                f"/api/v1/tasks/{task_id}",
                params={"live_authority": "true"},
                headers=self._headers(),
            )
            current_response.raise_for_status()
            current_value = current_response.json()
            if not isinstance(current_value, dict):
                raise ValueError("planning_task_response_invalid")
            current = cast(dict[str, object], current_value)
            if current.get("status") == "needs_advisor_review":
                projection = DraPlanningTaskProjectionV1(
                    task_id=task_id,
                    case_id=UUID(str(current["case_id"])),
                    case_revision=int(str(current["case_revision"])),
                    operation="generate_governed_mixed_planning_run_v1",
                    source_pack_id=UUID(str(current["source_pack_id"])),
                    source_pack_version=int(str(current["source_pack_version"])),
                    status="needs_advisor_review",
                    planning_run_id=UUID(str(current["planning_run_id"])),
                    execution_id=UUID(str(current["execution_id"])),
                    terminal_event_id=int(str(current["terminal_event_id"])),
                    skill_pin=SkillRuntimePin.model_validate_json(
                        json.dumps(
                            current["skill_pin"],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                    request_sha256=str(current["request_sha256"]),
                )
                self._tasks[idempotency_key] = projection
                return projection
            if current.get("status") != "preparing":
                raise ValueError("planning_task_terminal_invalid")
            await asyncio.sleep(1)
        raise ValueError("planning_task_deadline_exceeded")

    async def get_review(
        self, context: ActorContext, case_id: UUID, planning_run_id: UUID
    ) -> DraReviewAuthorityV1 | None:
        del context, case_id
        return self._reviews.get(planning_run_id)

    async def record_review(
        self,
        context: ActorContext,
        case_id: UUID,
        expected_revision: int,
        planning_run_id: UUID,
        eligible_route_ids: tuple[UUID, ...],
        idempotency_key: str,
    ) -> DraReviewAuthorityV1:
        del context
        request_payload = {
            "case_id": str(case_id),
            "planning_run_id": str(planning_run_id),
            "expected_case_revision": expected_revision,
            "action": "approve_for_consultation",
            "eligible_route_ids": [str(item) for item in eligible_route_ids],
            "risk_acceptances": [],
            "reviewer_notes": None,
        }
        response = await self._client.post(
            f"/api/v1/cases/{case_id}/advisor-reviews",
            headers=self._headers(idempotency_key),
            json={
                "schema_version": 1,
                **{
                    key: value
                    for key, value in request_payload.items()
                    if key != "case_id"
                },
            },
        )
        response.raise_for_status()
        raw_value = response.json()
        if not isinstance(raw_value, dict):
            raise ValueError("advisor_review_response_invalid")
        raw = cast(dict[str, object], raw_value)
        projection = DraReviewAuthorityV1(
            review_id=UUID(str(raw["review_id"])),
            case_id=case_id,
            expected_case_revision=expected_revision,
            planning_run_id=planning_run_id,
            brief_id=UUID(str(raw["brief_id"])),
            eligible_route_ids=eligible_route_ids,
            request_sha256=canonical_request_sha256(request_payload),
        )
        self._reviews[planning_run_id] = projection
        return projection

    async def get_decision(
        self, context: ActorContext, brief_id: UUID
    ) -> DraDecisionAuthorityV1 | None:
        del context
        response = await self._client.get(
            f"/api/v1/decision-briefs/{brief_id}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        raw_value = response.json()
        if not isinstance(raw_value, dict):
            raise ValueError("family_decision_response_invalid")
        raw = cast(dict[str, object], raw_value)
        if raw.get("decision_id") is None:
            return None
        receipt_value = raw.get("receipt")
        if not isinstance(receipt_value, dict):
            raise ValueError("family_decision_response_invalid")
        receipt = cast(dict[str, object], receipt_value)
        trade_offs_value = receipt["accepted_trade_offs"]
        if not isinstance(trade_offs_value, list):
            raise ValueError("family_decision_response_invalid")
        trade_offs = cast(list[object], trade_offs_value)
        payload = {
            "brief_id": str(brief_id),
            "expected_brief_version": int(str(raw["brief_version"])),
            "selected_route_id": str(receipt["selected_route_id"]),
            "accepted_budget_min_minor": int(
                str(receipt["accepted_budget_min_minor"])
            ),
            "accepted_budget_max_minor": int(
                str(receipt["accepted_budget_max_minor"])
            ),
            "currency": str(receipt["currency"]),
            "accepted_trade_offs": [str(item) for item in trade_offs],
        }
        return DraDecisionAuthorityV1(
            decision_id=UUID(str(raw["decision_id"])),
            decision_receipt_id=UUID(str(raw["receipt_id"])),
            timeline_plan_id=UUID(str(raw["timeline_id"])),
            brief_id=brief_id,
            selected_route_id=UUID(str(receipt["selected_route_id"])),
            expected_brief_version=int(str(raw["brief_version"])),
            accepted_budget_min_minor=int(
                str(receipt["accepted_budget_min_minor"])
            ),
            accepted_budget_max_minor=int(
                str(receipt["accepted_budget_max_minor"])
            ),
            currency="CNY",
            accepted_trade_offs=tuple(str(item) for item in trade_offs),
            request_sha256=canonical_request_sha256(payload),
        )

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
        del context
        payload = {
            "brief_id": str(brief_id),
            "expected_brief_version": expected_brief_version,
            "selected_route_id": str(selected_route_id),
            "accepted_budget_min_minor": budget_min,
            "accepted_budget_max_minor": budget_max,
            "currency": "CNY",
            "accepted_trade_offs": list(trade_offs),
        }
        response = await self._client.post(
            f"/api/v1/decision-briefs/{brief_id}/family-decisions",
            headers=self._headers(idempotency_key),
            json={
                "schema_version": 1,
                **{
                    key: value
                    for key, value in payload.items()
                    if key != "brief_id"
                },
            },
        )
        response.raise_for_status()
        raw_value = response.json()
        if not isinstance(raw_value, dict):
            raise ValueError("family_decision_response_invalid")
        raw = cast(dict[str, object], raw_value)
        return DraDecisionAuthorityV1(
            decision_id=UUID(str(raw["decision_id"])),
            decision_receipt_id=UUID(str(raw["receipt_id"])),
            timeline_plan_id=UUID(str(raw["timeline_id"])),
            brief_id=brief_id,
            selected_route_id=selected_route_id,
            expected_brief_version=expected_brief_version,
            accepted_budget_min_minor=budget_min,
            accepted_budget_max_minor=budget_max,
            currency="CNY",
            accepted_trade_offs=trade_offs,
            request_sha256=canonical_request_sha256(payload),
        )
