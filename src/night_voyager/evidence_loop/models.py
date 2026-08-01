"""Cross-stage readiness contracts and common closed identities."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Sha1 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
CheckUrl = Annotated[str, StringConstraints(pattern=r"^https://github\.com/.+")]
def validate_safe_relative_path(value: str) -> str:
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or PurePosixPath(value).is_absolute()
        or PurePosixPath(value).as_posix() != value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("path must be a canonical safe relative POSIX path")
    return value


SafeRelativePath = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$"),
    AfterValidator(validate_safe_relative_path),
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

EXPECTED_HOSTED_CHECKS = ("python", "frontend", "compose")
EXPECTED_PREDECESSOR_STAGE = {
    "slice0": None,
    "candidate-authority": "slice0",
    "candidate-journey": "candidate-authority",
    "composition-authority": "candidate-journey",
    "composition-journey": "composition-authority",
}
EXPECTED_PREDECESSOR_DISPOSITION = {
    "slice0": None,
    "candidate-authority": "incremental_value_confirmed",
    "candidate-journey": "authority_verified",
    "composition-authority": "journey_verified",
    "composition-journey": "authority_verified",
}


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
    predecessor_stage: StageName | None
    predecessor_terminal_disposition: TerminalDisposition | None
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

    @model_validator(mode="after")
    def validate_closed_contract(self) -> StageReadinessContractV1:
        if self.required_hosted_checks != EXPECTED_HOSTED_CHECKS:
            raise ValueError("required hosted checks must be python, frontend, compose")
        if self.predecessor_stage != EXPECTED_PREDECESSOR_STAGE[self.stage]:
            raise ValueError("stage predecessor contract mismatch")
        if self.predecessor_terminal_disposition != EXPECTED_PREDECESSOR_DISPOSITION[self.stage]:
            raise ValueError("stage predecessor disposition mismatch")
        return self


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
    predecessor_stage: StageName | None = None
    predecessor_merge_commit: Sha1 | None = None
    predecessor_merge_tree: Sha1 | None = None
    predecessor_receipt_sha256: Sha256 | None = None
    predecessor_terminal_disposition: TerminalDisposition | None = None

    @model_validator(mode="after")
    def validate_closed_body(self) -> StageReadinessBodyV1:
        if self.required_checks != EXPECTED_HOSTED_CHECKS:
            raise ValueError("required checks must be python, frontend, compose")
        expected_stage = EXPECTED_PREDECESSOR_STAGE[self.stage]
        expected_disposition = EXPECTED_PREDECESSOR_DISPOSITION[self.stage]
        if self.predecessor_stage != expected_stage:
            raise ValueError("stage predecessor identity mismatch")
        if self.predecessor_terminal_disposition != expected_disposition:
            raise ValueError("stage predecessor disposition mismatch")
        predecessor_values = (
            self.predecessor_merge_commit,
            self.predecessor_merge_tree,
            self.predecessor_receipt_sha256,
        )
        if expected_stage is None and any(value is not None for value in predecessor_values):
            raise ValueError("slice0 cannot declare a predecessor")
        if expected_stage is not None and any(value is None for value in predecessor_values):
            raise ValueError("later stage must bind a complete predecessor receipt")
        if len(self.check_urls) != len(EXPECTED_HOSTED_CHECKS) or len(set(self.check_urls)) != len(
            self.check_urls
        ):
            raise ValueError("required check URL set invalid")
        return self


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
