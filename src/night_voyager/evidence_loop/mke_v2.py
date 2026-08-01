"""Night Voyager-owned closed projection of MKE v0.1.5 Search/Read contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    model_validator,
)

Fingerprint = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
MachineToken = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,127}$")
]


def _max_utf8_bytes(limit: int) -> Callable[[str], str]:
    def validate(value: str) -> str:
        if len(value.encode("utf-8")) > limit:
            raise ValueError(f"value exceeds {limit} UTF-8 bytes")
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    return validate


McpQuery = Annotated[str, AfterValidator(_max_utf8_bytes(512))]
DomainQuery = Annotated[str, AfterValidator(_max_utf8_bytes(4096))]
Cursor = Annotated[str, AfterValidator(_max_utf8_bytes(4096))]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class MkeSearchInitialV2(FrozenModel):
    query: McpQuery
    limit: int = Field(default=5, ge=1, le=20)


class MkeSearchContinuationV2(FrozenModel):
    cursor: Cursor


class MkeReadInitialV1(FrozenModel):
    evidence_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    max_bytes: int = Field(default=16384, ge=4, le=16384)


class MkeReadContinuationV1(FrozenModel):
    cursor: Cursor


class ActiveObservationV1(FrozenModel):
    schema_version: Literal["mke.active_publication_observation.v1"]
    library_id: Literal["local"]
    state: Literal["empty", "no_active_publication", "active"]
    source_count: int = Field(ge=0)
    active_publication_count: int = Field(ge=0)
    active_evidence_count: int = Field(ge=0)

    @model_validator(mode="after")
    def state_matches_counts(self) -> Self:
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


class ActiveAuthoritySnapshotV1(FrozenModel):
    schema_version: Literal["mke.active_authority_snapshot.v1"]
    observation: ActiveObservationV1
    active_set_fingerprint: Fingerprint


class PageLocatorV1(FrozenModel):
    kind: Literal["page"]
    start: int = Field(gt=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def single_page(self) -> Self:
        if self.end != self.start:
            raise ValueError("page locator start and end must match")
        return self


class TimestampLocatorV1(FrozenModel):
    kind: Literal["timestamp_ms"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered_interval(self) -> Self:
        if self.end <= self.start:
            raise ValueError("timestamp locator end must follow start")
        return self


LocatorV1 = Annotated[
    PageLocatorV1 | TimestampLocatorV1,
    Field(discriminator="kind"),
]


class EvidenceDescriptorV1(FrozenModel):
    evidence_id: str
    source_id: str
    content_fingerprint: Fingerprint
    publication_id: str
    publication_revision: int = Field(gt=0)
    run_id: str
    locator: LocatorV1
    evidence_text_sha256: Fingerprint
    original_utf8_bytes: int = Field(gt=0)


class EvidenceExcerptV1(FrozenModel):
    kind: Literal["query_window", "prefix_fallback"]
    text: str
    start_utf8_byte: int = Field(ge=0)
    end_utf8_byte: int = Field(gt=0)
    prefix_omitted: bool
    suffix_omitted: bool
    complete: bool
    returned_utf8_bytes: int = Field(gt=0, le=2048)
    content_trust: Literal["untrusted_evidence"]


class EvidenceReadAffordanceV1(FrozenModel):
    tool: Literal["read_evidence_v1"]
    evidence_id: str


class SearchMatchV2(FrozenModel):
    evidence: EvidenceDescriptorV1
    excerpt: EvidenceExcerptV1
    read: EvidenceReadAffordanceV1


class SearchSelectionCompleteV2(FrozenModel):
    schema_version: Literal["mke.search_selection.v2"]
    status: Literal["complete"]
    returned: int = Field(ge=0)


class SearchSelectionMoreV2(FrozenModel):
    schema_version: Literal["mke.search_selection.v2"]
    status: Literal["more_available"]
    returned: int = Field(ge=0)
    next_cursor: Cursor


class SearchSelectionCappedV2(FrozenModel):
    schema_version: Literal["mke.search_selection.v2"]
    status: Literal["capped"]
    returned: int = Field(ge=0)
    limit_reason: Literal["retrieval_strategy_cap"]


class SearchOutputBudgetV1(FrozenModel):
    schema_version: Literal["mke.search_output_budget.v1"]
    incomplete_excerpt_count: int = Field(ge=0)
    content_budget_bytes: Literal[16384]
    envelope_budget_bytes: Literal[32768]


class MkeSearchSuccessV2(FrozenModel):
    schema_version: Literal["mke.search_library_response.v2"]
    ok: Literal[True]
    authority_snapshot: ActiveAuthoritySnapshotV1
    query: DomainQuery
    matches: list[SearchMatchV2] = Field(max_length=20)
    selection: (
        SearchSelectionCompleteV2
        | SearchSelectionMoreV2
        | SearchSelectionCappedV2
    ) = Field(discriminator="status")
    output: SearchOutputBudgetV1

    @property
    def is_exhaustive(self) -> bool:
        return self.selection.status == "complete"

    @model_validator(mode="after")
    def canonical_success_body_cap(self) -> Self:
        encoded = self.model_dump_json().encode("utf-8")
        if len(encoded) > 32_768:
            raise ValueError("canonical success body exceeds 32768 bytes")
        return self


class MkeEvidenceContentV1(FrozenModel):
    text: str
    offset_bytes: int = Field(ge=0)
    returned_utf8_bytes: int = Field(gt=0, le=16384)
    content_trust: Literal["untrusted_evidence"]


class MkeReadSuccessV1(FrozenModel):
    schema_version: Literal["mke.read_evidence_response.v1"]
    ok: Literal[True]
    authority_snapshot: ActiveAuthoritySnapshotV1
    evidence: EvidenceDescriptorV1
    content: MkeEvidenceContentV1
    complete: bool
    next_cursor: Cursor | None = None

    @model_validator(mode="after")
    def terminality_matches_cursor(self) -> Self:
        if self.complete == (self.next_cursor is not None):
            raise ValueError("Read terminality does not match cursor")
        return self


class MkePublicErrorV1(FrozenModel):
    ok: Literal[False]
    problem: MachineToken
    cause: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    active_publication_impact: Literal["unchanged"]
    next_step: MachineToken


class MkeSearchErrorV2(MkePublicErrorV1):
    schema_version: Literal["mke.search_library_response.v2"]


class MkeReadErrorV1(MkePublicErrorV1):
    schema_version: Literal["mke.read_evidence_response.v1"]


class MkeSearchResponseV2(
    RootModel[
        Annotated[
            MkeSearchSuccessV2 | MkeSearchErrorV2,
            Field(discriminator="ok"),
        ]
    ]
):
    pass


class MkeReadResponseV1(
    RootModel[
        Annotated[
            MkeReadSuccessV1 | MkeReadErrorV1,
            Field(discriminator="ok"),
        ]
    ]
):
    pass
