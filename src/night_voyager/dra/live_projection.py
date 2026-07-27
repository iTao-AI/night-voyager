from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, Field, computed_field, model_validator

from night_voyager.dra.live_models import (
    DraLiveEvidenceEnvelopeV1,
    DraLiveFailureCauseEnvelopeV1,
    DraLiveRunEnvelopeV1,
    DraSelectedEvidenceV1,
)
from night_voyager.dra.models import (
    BoundedId,
    BoundedText,
    DraCanonicalArtifactInputV1,
    DraCanonicalResultProjectionV1,
    DraObservedProfileManifestV1,
    DraProducerPinV2,
    DraRunAcceptanceV1,
    DraRunRequestIdentityV2,
    DraStrictConsumerIdentityV2,
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


class DraStrictLiveRunEnvelopeV2(FrozenModel):
    run_id: BoundedId
    thread_id: BoundedId
    segment_id: BoundedId
    profile_id: Literal["generic-strict-citation"]
    state_version: int
    execution_status: Literal[
        "pending", "running", "completed", "completed_with_fallback", "failed"
    ]
    review_status: Literal["not_required", "required", "resolved"]
    delivery_status: Literal[
        "pending", "ready", "review_required", "blocked", "failed"
    ]
    failure_cause: DraLiveFailureCauseEnvelopeV1 | None
    evidence: tuple[DraLiveEvidenceEnvelopeV1, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def exact_segment_and_unique_evidence(self) -> DraStrictLiveRunEnvelopeV2:
        identifiers = [row.evidence_id for row in self.evidence]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("dra_evidence_ids_not_unique")
        return self

    @computed_field
    @property
    def disposition(
        self,
    ) -> Literal["in_progress", "canonical_ready", "terminal_invalid"]:
        state = (
            self.execution_status,
            self.review_status,
            self.delivery_status,
        )
        if (
            state
            in {
                ("pending", "not_required", "pending"),
                ("running", "not_required", "pending"),
            }
            and self.failure_cause is None
        ):
            return "in_progress"
        if (
            state == ("completed", "not_required", "ready")
            and self.state_version > 0
            and self.failure_cause is None
        ):
            return "canonical_ready"
        return "terminal_invalid"


class DraStrictTerminalProjectionV2(DraTerminalProjectionV1):
    consumer_identity: DraStrictConsumerIdentityV2


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


def project_strict_terminal_result(
    acceptance: DraRunAcceptanceV1,
    run: DraStrictLiveRunEnvelopeV2,
    result: DraCanonicalResultProjectionV1,
    producer: DraProducerPinV2,
    request_identity: DraRunRequestIdentityV2,
    observed_profile: DraObservedProfileManifestV1,
) -> DraStrictTerminalProjectionV2:
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
    try:
        consumer_identity = DraStrictConsumerIdentityV2(
            schema_version="night-voyager.dra-strict-consumer-identity.v2",
            producer=DraProducerPinV2.model_validate(
                producer.model_dump(mode="json")
            ),
            request=DraRunRequestIdentityV2.model_validate(
                request_identity.model_dump(mode="json")
            ),
            observed_profile=DraObservedProfileManifestV1.model_validate(
                observed_profile.model_dump(mode="json")
            ),
        )
    except ValueError as error:
        raise DraLiveContractError("strict_identity_invalid") from error
    if run.profile_id != consumer_identity.request.profile_id:
        raise DraLiveContractError("terminal_profile_invalid")

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
    return DraStrictTerminalProjectionV2(
        run_id=run.run_id,
        segment_id=run.segment_id,
        state_version=run.state_version,
        artifact=result.artifact,
        evidence=tuple(projected),
        consumer_identity=consumer_identity,
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


def select_strict_cited_evidence(
    projection: DraStrictTerminalProjectionV2,
    declared_raw_url: str,
) -> DraSelectedEvidenceV1:
    selected = select_cited_evidence(projection, declared_raw_url)
    cited = [
        row
        for row in projection.evidence
        if row.citation_status == "cited" and row.source_url is not None
    ]
    if (
        len(cited) != 1
        or selected.source_url not in projection.artifact.content
    ):
        raise DraLiveContractError("source_selection_invalid")
    return selected
