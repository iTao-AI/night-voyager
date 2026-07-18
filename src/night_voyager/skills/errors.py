from __future__ import annotations


class SkillError(Exception):
    """Base for bounded Skill-governance failures."""


class SkillAuthorizationError(SkillError):
    pass


class SkillVersionUnavailableError(SkillError):
    pass


class SkillCandidateStaleError(SkillError):
    pass


class SkillCandidateTerminalError(SkillError):
    pass


class SkillEvaluationFailedError(SkillError):
    pass


class SkillActivationStaleError(SkillError):
    pass


class SkillScopeExpansionError(SkillError):
    pass


class SkillRollbackUnsupportedError(SkillError):
    pass


class SkillPinInvalidError(SkillError):
    pass


class SkillIdempotencyConflictError(SkillError):
    pass


class SkillPersistenceError(SkillError):
    pass


__all__ = [
    "SkillActivationStaleError",
    "SkillAuthorizationError",
    "SkillCandidateStaleError",
    "SkillCandidateTerminalError",
    "SkillError",
    "SkillEvaluationFailedError",
    "SkillIdempotencyConflictError",
    "SkillPersistenceError",
    "SkillPinInvalidError",
    "SkillRollbackUnsupportedError",
    "SkillScopeExpansionError",
    "SkillVersionUnavailableError",
]
