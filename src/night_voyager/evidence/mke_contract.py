"""Strict Night Voyager-owned projection of the consumed MKE v1 response contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, StringConstraints, model_validator

StrictId = Annotated[str, StringConstraints(pattern=r"^[a-z]+_[0-9a-f]{32}$")]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
PublicText = Annotated[str, StringConstraints(min_length=1, max_length=1_000_000)]
MachineToken = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,127}$")]


class StrictModel(BaseModel):
    """Base for the frozen, fail-closed MKE wire contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PageLocatorV1(StrictModel):
    kind: Literal["page"]
    start: int = Field(gt=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_single_page(self) -> PageLocatorV1:
        if self.end != self.start:
            raise ValueError("page locator start and end must match")
        return self


class TimestampLocatorV1(StrictModel):
    kind: Literal["timestamp_ms"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_interval(self) -> TimestampLocatorV1:
        if self.end <= self.start:
            raise ValueError("timestamp locator end must follow start")
        return self


LocatorV1 = Annotated[PageLocatorV1 | TimestampLocatorV1, Field(discriminator="kind")]


class EvidenceRefV1(StrictModel):
    schema_version: Literal["mke.evidence_ref.v1"] = "mke.evidence_ref.v1"
    evidence_id: Annotated[StrictId, Field(pattern=r"^ev_[0-9a-f]{32}$")]
    source_id: Annotated[StrictId, Field(pattern=r"^src_[0-9a-f]{32}$")]
    content_fingerprint: Fingerprint
    publication_id: Annotated[StrictId, Field(pattern=r"^pub_[0-9a-f]{32}$")]
    publication_revision: int = Field(gt=0)
    run_id: Annotated[StrictId, Field(pattern=r"^run_[0-9a-f]{32}$")]
    locator: LocatorV1
    text: PublicText


class ActivePublicationObservationV1(StrictModel):
    schema_version: Literal["mke.active_publication_observation.v1"] = (
        "mke.active_publication_observation.v1"
    )
    library_id: Literal["local"] = "local"
    state: Literal["empty", "no_active_publication", "active"]
    source_count: int = Field(ge=0)
    active_publication_count: int = Field(ge=0)
    active_evidence_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_state_counts(self) -> ActivePublicationObservationV1:
        counts = (
            self.source_count,
            self.active_publication_count,
            self.active_evidence_count,
        )
        valid = (
            self.state == "empty"
            and counts == (0, 0, 0)
            or self.state == "no_active_publication"
            and self.source_count > 0
            and counts[1:] == (0, 0)
            or self.state == "active"
            and all(value > 0 for value in counts)
            and self.active_publication_count <= self.source_count
            and self.active_publication_count <= self.active_evidence_count
        )
        if not valid:
            raise ValueError("observation state does not match counts")
        return self


class PublicErrorV1(StrictModel):
    ok: Literal[False]
    problem: MachineToken
    cause: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    active_publication_impact: Literal["unchanged"] = "unchanged"
    next_step: MachineToken


class ListLibrariesSuccessV1(StrictModel):
    schema_version: Literal["mke.list_libraries_response.v1"] = (
        "mke.list_libraries_response.v1"
    )
    ok: Literal[True] = True
    observation: ActivePublicationObservationV1


class ListLibrariesErrorV1(PublicErrorV1):
    schema_version: Literal["mke.list_libraries_response.v1"] = (
        "mke.list_libraries_response.v1"
    )


class SearchLibrarySuccessV1(StrictModel):
    schema_version: Literal["mke.search_library_response.v1"] = (
        "mke.search_library_response.v1"
    )
    ok: Literal[True] = True
    query: PublicText
    observation: ActivePublicationObservationV1
    results: list[EvidenceRefV1] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_observation_results(self) -> SearchLibrarySuccessV1:
        if self.observation.state != "active" and self.results:
            raise ValueError("Search results require an active Publication observation")
        if len(self.results) > self.observation.active_evidence_count:
            raise ValueError("Search results exceed observed active Evidence")
        return self


class SearchLibraryErrorV1(PublicErrorV1):
    schema_version: Literal["mke.search_library_response.v1"] = (
        "mke.search_library_response.v1"
    )


class AskLibrarySuccessV1(StrictModel):
    schema_version: Literal["mke.ask_library_response.v1"] = "mke.ask_library_response.v1"
    ok: Literal[True] = True
    question: PublicText
    answer_status: Literal["evidence_found", "insufficient_evidence"]
    summary: PublicText
    observation: ActivePublicationObservationV1
    evidence: list[EvidenceRefV1] = Field(max_length=20)
    limitations: list[PublicText]

    @model_validator(mode="after")
    def validate_observation_evidence(self) -> AskLibrarySuccessV1:
        has_evidence = bool(self.evidence)
        if (self.answer_status == "evidence_found") != has_evidence:
            raise ValueError("Ask answer status does not match Evidence")
        if self.observation.state != "active" and has_evidence:
            raise ValueError("Ask Evidence requires an active Publication observation")
        if len(self.evidence) > self.observation.active_evidence_count:
            raise ValueError("Ask Evidence exceeds observed active Evidence")
        return self


class AskLibraryErrorV1(PublicErrorV1):
    schema_version: Literal["mke.ask_library_response.v1"] = "mke.ask_library_response.v1"


class ListLibrariesResponseV1(
    RootModel[
        Annotated[ListLibrariesSuccessV1 | ListLibrariesErrorV1, Field(discriminator="ok")]
    ]
):
    pass


class SearchLibraryResponseV1(
    RootModel[
        Annotated[SearchLibrarySuccessV1 | SearchLibraryErrorV1, Field(discriminator="ok")]
    ]
):
    pass


class AskLibraryResponseV1(
    RootModel[Annotated[AskLibrarySuccessV1 | AskLibraryErrorV1, Field(discriminator="ok")]]
):
    pass
