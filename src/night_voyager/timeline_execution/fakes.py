from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from night_voyager.identity.models import ActorContext
from night_voyager.timeline_execution.hashing import canonical_json_bytes
from night_voyager.timeline_execution.models import (
    PlanExecutionContextV1,
    TimelineExecutionViewV1,
    TimelineMutationReceiptV1,
)
from night_voyager.timeline_execution.ports import (
    AttestTimelineCheckpointCommand,
    RequestTimelineReassessmentCommand,
    StartTimelineExecutionCommand,
    VerifyTimelineCheckpointCommand,
)


@dataclass(slots=True)
class FakeTimelineExecutionRepository:
    context_result: PlanExecutionContextV1 | None
    view_result: TimelineExecutionViewV1 | None
    receipts: dict[str, TimelineMutationReceiptV1]
    calls: list[tuple[str, bytes]] = field(
        default_factory=lambda: list[tuple[str, bytes]]()
    )

    async def context(
        self,
        actor: ActorContext,
        scenario: Literal["governed-plan-execution-v1"],
    ) -> PlanExecutionContextV1 | None:
        self.calls.append(("context", canonical_json_bytes({"scenario": scenario})))
        return self.context_result

    async def read(
        self, actor: ActorContext, case_id: UUID
    ) -> TimelineExecutionViewV1 | None:
        self.calls.append(("read", canonical_json_bytes({"case_id": str(case_id)})))
        return self.view_result

    async def start(
        self,
        actor: ActorContext,
        command: StartTimelineExecutionCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        return self._record("start", command)

    async def attest(
        self,
        actor: ActorContext,
        command: AttestTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        return self._record("attest", command)

    async def verify(
        self,
        actor: ActorContext,
        command: VerifyTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        return self._record("verify", command)

    async def reassess(
        self,
        actor: ActorContext,
        command: RequestTimelineReassessmentCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        return self._record("reassess", command)

    def _record(
        self,
        operation: str,
        command: (
            StartTimelineExecutionCommand
            | AttestTimelineCheckpointCommand
            | VerifyTimelineCheckpointCommand
            | RequestTimelineReassessmentCommand
        ),
    ) -> TimelineMutationReceiptV1:
        self.calls.append((operation, canonical_json_bytes(command)))
        return self.receipts[operation]
