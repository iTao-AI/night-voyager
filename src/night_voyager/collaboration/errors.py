from __future__ import annotations


class CollaborationError(Exception):
    """Base for bounded collaboration failures."""


class CollaborationAuthorizationError(CollaborationError):
    pass


class InvalidCollaborationMessageError(CollaborationError):
    pass


class UnsupportedFactKeyError(CollaborationError):
    pass


class UnsafeFactValueError(CollaborationError):
    pass


class CaseRevisionStaleError(CollaborationError):
    pass


class MemoryCandidateStaleError(CollaborationError):
    pass


class MemoryCandidateExpiredError(CollaborationError):
    pass


class MemoryCandidateTerminalError(CollaborationError):
    pass


class ActiveTaskBlocksRevisionError(CollaborationError):
    pass


class IdempotencyConflictError(CollaborationError):
    pass


class CollaborationPersistenceError(CollaborationError):
    pass


class CollaborationThreadFullError(CollaborationError):
    pass
