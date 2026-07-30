"""Cross-stage readiness contracts and common closed identities."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Sha1 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
CheckUrl = Annotated[str, StringConstraints(pattern=r"^https://github\.com/.+")]
SafeRelativePath = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$"),
]
StageName = Literal[
    "slice0",
    "candidate-authority",
    "candidate-journey",
    "composition-authority",
    "composition-journey",
]
TerminalDisposition = Literal[
    "incremental_value_confirmed",
    "no_incremental_value",
    "inconclusive",
    "evaluation_invalid",
    "authority_verified",
    "journey_verified",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StageReadinessContractV1(FrozenModel):
    schema_version: Literal["night-voyager.stage-readiness-contract.v1"]
    stage: StageName
    proof_path: SafeRelativePath
    allowed_terminal_dispositions: tuple[TerminalDisposition, ...] = Field(
        min_length=1
    )
    required_hosted_checks: tuple[Literal["python", "frontend", "compose"], ...]
    next_stage_unlock: Literal[
        "candidate-authority",
        "candidate-journey",
        "composition-authority",
        "composition-journey",
        "release-preparation",
    ]
    non_claims: tuple[
        Literal[
            "source_truth",
            "provider_quality",
            "statistical_generalization",
            "production_deployment",
            "real_user_outcomes",
            "runtime_multi_agent",
        ],
        ...,
    ]


class StageReadinessBodyV1(FrozenModel):
    stage: StageName
    reviewed_head: Sha1
    reviewed_tree: Sha1
    proof_path: SafeRelativePath
    proof_sha256: Sha256
    terminal_disposition: TerminalDisposition
    required_checks: tuple[Literal["python", "frontend", "compose"], ...]
    check_urls: tuple[CheckUrl, ...]
    next_stage_unlock: str
    non_claims: tuple[str, ...]


class StageReadinessCandidateV1(StageReadinessBodyV1):
    schema_version: Literal["night-voyager.stage-readiness-candidate.v1"]


class StageReadinessReceiptV1(StageReadinessBodyV1):
    schema_version: Literal["night-voyager.stage-readiness-receipt.v1"]
    merge_commit: Sha1
    merge_tree: Sha1
    merged_at: Annotated[str, StringConstraints(min_length=20, max_length=40)]
    reviewed_tree_equals_merge_tree: Literal[True]
    main_sync_commit: Sha1
    cleanup_state: Literal["complete", "retained_by_authority"]
