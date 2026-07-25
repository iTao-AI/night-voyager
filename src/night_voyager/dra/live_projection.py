from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from night_voyager.dra.live_models import (
    DraLiveRunEnvelopeV1,
    DraSelectedEvidenceV1,
)
from night_voyager.dra.models import (
    BoundedId,
    BoundedText,
    DraCanonicalArtifactInputV1,
    DraCanonicalResultProjectionV1,
    DraRunAcceptanceV1,
    FrozenModel,
    validate_raw_public_https_url,
)


class DraLiveContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DraLiveConsumerEvidenceV1(FrozenModel):
    evidence_id: BoundedId
    source_url: BoundedText | None
    source_identity: BoundedText
    retrieved_at: AwareDatetime
    citation_status: Literal["cited", "uncited"]
    verification_status: Literal["verified", "unverified"]


class DraTerminalProjectionV1(FrozenModel):
    run_id: BoundedId
    segment_id: BoundedId
    state_version: int = Field(gt=0)
    artifact: DraCanonicalArtifactInputV1
    evidence: tuple[DraLiveConsumerEvidenceV1, ...] = Field(
        min_length=1, max_length=100
    )

    @model_validator(mode="after")
    def evidence_ids_are_unique(self) -> DraTerminalProjectionV1:
        identifiers = [row.evidence_id for row in self.evidence]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("dra_evidence_ids_not_unique")
        return self


def _validate_source(row_source_url: str | None, source_identity: str) -> None:
    if row_source_url is None:
        return
    try:
        validate_raw_public_https_url(row_source_url)
    except ValueError as error:
        raise DraLiveContractError("source_url_invalid") from error
    if source_identity != row_source_url:
        raise DraLiveContractError("source_identity_mismatch")


def project_terminal_result(
    acceptance: DraRunAcceptanceV1,
    run: DraLiveRunEnvelopeV1,
    result: DraCanonicalResultProjectionV1,
) -> DraTerminalProjectionV1:
    if run.disposition != "canonical_ready":
        raise DraLiveContractError("terminal_state_invalid")
    if (
        run.thread_id != acceptance.thread_id
        or run.run_id != acceptance.run_id
        or run.segment_id != acceptance.segment_id
    ):
        raise DraLiveContractError("run_ownership_invalid")
    if result.run_id != acceptance.run_id:
        raise DraLiveContractError("result_ownership_invalid")
    if not run.evidence:
        raise DraLiveContractError("evidence_projection_invalid")

    projected: list[DraLiveConsumerEvidenceV1] = []
    for row in run.evidence:
        if (
            row.run_id != acceptance.run_id
            or row.segment_id != acceptance.segment_id
        ):
            raise DraLiveContractError("evidence_ownership_invalid")
        _validate_source(row.source_url, row.source_identity)
        projected.append(
            DraLiveConsumerEvidenceV1.model_validate(
                {
                    field: getattr(row, field)
                    for field in (
                        "evidence_id",
                        "source_url",
                        "source_identity",
                        "retrieved_at",
                        "citation_status",
                        "verification_status",
                    )
                }
            )
        )

    return DraTerminalProjectionV1(
        run_id=run.run_id,
        segment_id=run.segment_id,
        state_version=run.state_version,
        artifact=result.artifact,
        evidence=tuple(projected),
    )


def select_cited_evidence(
    projection: DraTerminalProjectionV1, declared_raw_url: str
) -> DraSelectedEvidenceV1:
    try:
        validate_raw_public_https_url(declared_raw_url)
    except ValueError as error:
        raise DraLiveContractError("source_selection_invalid") from error
    matches = [
        row
        for row in projection.evidence
        if row.citation_status == "cited"
        and row.source_url is not None
        and row.source_identity == row.source_url
        and row.source_url == declared_raw_url
    ]
    if len(matches) != 1:
        raise DraLiveContractError("source_selection_invalid")
    selected = matches[0]
    return DraSelectedEvidenceV1(
        evidence_id=selected.evidence_id,
        run_id=projection.run_id,
        segment_id=projection.segment_id,
        source_url=declared_raw_url,
        source_identity=selected.source_identity,
        retrieved_at=selected.retrieved_at,
        citation_status="cited",
        verification_status=selected.verification_status,
    )
