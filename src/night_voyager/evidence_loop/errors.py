"""Bounded public-safe failures for Slice 0 command surfaces."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

SafeText = Annotated[str, StringConstraints(min_length=1, max_length=512)]
EvidenceLoopExitCode = Literal[2, 10, 11, 12, 13, 14]


class EvidenceLoopDiagnosticV1(BaseModel):
    """One closed diagnostic without raw Evidence or physical paths."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["night-voyager.evidence-loop-diagnostic.v1"] = (
        "night-voyager.evidence-loop-diagnostic.v1"
    )
    stage: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,99}$")]
    problem: SafeText
    cause: SafeText
    recovery: SafeText
    exit_code: EvidenceLoopExitCode


class EvidenceLoopError(RuntimeError):
    """Typed failure whose printable value is only its public code."""

    def __init__(self, diagnostic: EvidenceLoopDiagnosticV1) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.code)
