"""Strict Night Voyager-owned projection of the consumed MKE v1 response contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, StringConstraints, model_validator

StrictId = Annotated[str, StringConstraints(pattern=r"^[a-z]+_[0-9a-f]{32}$")]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
PublicText = Annotated[str, StringConstraints(min_length=1, max_length=1_000_000)]
MachineToken = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,127}$")]
PUBLIC_ERROR_CAUSES = frozenset(
    {
        "PDF cannot be opened",
        "PDF has no extractable text",
        "PDF input exceeds 100 MB limit",
        "argv must contain exactly one {input} placeholder",
        "configured embedding model is not cached",
        "configured embedding model revision is unavailable",
        "configured embedding model snapshot is incomplete",
        "configured embedding model snapshot exceeds size limit",
        "configured language is not supported by the model",
        "configured transcription model is not cached",
        "configured transcription model revision is unavailable",
        "CJK active Evidence scan would exceed configured local budget",
        "CJK candidate pool exceeded the configured cap",
        "demo fixture is missing",
        "demo video fixture is missing",
        "encrypted PDF is not supported",
        "embedding adapter failed",
        "embedding cancelled",
        "embedding input would be truncated",
        "embedding model cache is not readable",
        "embedding model download failed",
        "embedding optional dependency is not installed",
        "embedding output contains non-finite values",
        "embedding output count is invalid",
        "embedding output dimension is invalid",
        "embedding output dtype must be float32",
        "embedding output is not normalized",
        "embedding tokenizer output is invalid",
        "file path cannot be resolved",
        "input file does not exist",
        "input path must be a file",
        "input path must be under allowed root",
        "input path must not be empty",
        "input video is empty",
        "input video is missing",
        "input video must be an MP4 file",
        "input video could not be read",
        "limit must be between 1 and 20",
        "operation failed; details were redacted",
        "query must not be empty",
        "question must be 1000 characters or fewer",
        "question must contain at least one searchable ASCII token",
        "question must not be empty",
        "Query does not contain enough eligible CJK terms",
        "Requested retrieval strategy is not supported by this runtime",
        "stable timestamp locator generation requires increasing ranges",
        "stable timestamp locator generation requires sorted ranges",
        "supported suffixes are .pdf and .mp4",
        "timestamp locators must be integer milliseconds",
        "transcript command executable is missing",
        "transcript command failed",
        "transcript command is required",
        "transcript command produced too much stderr",
        "transcript command produced too much stdout",
        "transcript command stdout is not valid UTF-8",
        "transcript command timed out",
        "transcript schema validation failed",
        "transcription failed",
        "transcription device or compute profile is unsupported",
        "transcription model cache is not readable",
        "transcription model download failed",
        "transcription model resolution failed",
        "transcription optional dependency is not installed",
        "unsupported codec for local video proof",
        "unknown run",
        "vector extension is unavailable or incompatible",
        "vector projection distance is invalid",
        "vector projection identity mismatch",
        "vector projection inventory is incomplete",
        "vector projection replace failed",
        "vector projection search inventory is incomplete",
        "video media exceeds duration limit",
        "video must contain an audio track",
        "video transcript exceeds segment limit",
        "video transcript format is unsupported",
        "video transcript is not valid JSON",
        "video transcript missing media",
        "video transcript must be a JSON object",
        "video transcript must contain at least one segment",
        "video transcript segment exceeds media duration",
        "video transcript segment must be an object",
        "video transcript sidecar format is unsupported",
        "video transcript sidecar is missing",
        "video transcript sidecar is not valid JSON",
        "video transcript sidecar missing media",
        "video transcript sidecar must be a JSON object",
        "video transcript text must not be empty",
        "video input exceeds 100 MiB limit",
        "video ingest initialization failed",
    }
)


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

    @model_validator(mode="after")
    def validate_public_cause(self) -> PublicErrorV1:
        if self.cause not in PUBLIC_ERROR_CAUSES:
            raise ValueError("error cause is not approved for the public boundary")
        return self


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
