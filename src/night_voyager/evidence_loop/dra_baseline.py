"""Typed governed DRA baseline export; Markdown is never an input."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    StringConstraints,
    model_validator,
)

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BoundedText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
BoundedId = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GovernedDraProducerV1(FrozenModel):
    release: Literal["v0.1.8"]
    tag_object: Literal["f828606741f636bca7ddbb66244ca60019eaa3c8"]
    commit: Literal["cb1f4660ee4ac7d81b04ffea014362e933487e61"]
    profile_id: Literal["generic-strict-citation"]
    profile_version: Literal["1"]
    run_id: BoundedId
    evidence_id: BoundedId


class AdvisorVerificationReceiptV1(FrozenModel):
    receipt_id: UUID
    assigned_advisor_id: UUID
    decision: Literal["verified_for_baseline"]
    receipt_sha256: Sha256


class GovernedDraBaselineExportV1(FrozenModel):
    schema_version: Literal["night-voyager.governed-dra-baseline-export.v1"]
    case_id: UUID
    case_revision: PositiveInt
    decision_dimension: Literal["program_requirements", "application_timeline"]
    typed_row_id: UUID
    typed_value: BoundedText
    typed_value_sha256: Sha256
    producer: GovernedDraProducerV1
    advisor_verification: AdvisorVerificationReceiptV1
    origin_kind: Literal["night_voyager_typed_governed_row"]
    row_sha256: Sha256
    export_sha256: Sha256

    @model_validator(mode="after")
    def no_rendered_artifact_origin(self) -> Self:
        if "markdown" in self.origin_kind.lower():
            raise ValueError("DRA Markdown cannot originate a typed baseline row")
        return self
