from __future__ import annotations


class DraAuthorizationError(Exception):
    """Raised when an actor attempts a DRA authority operation they do not own."""


class DraConflictError(Exception):
    """Raised when candidate state or an idempotency key conflicts."""


class DraNotFoundError(Exception):
    """Raised with a non-enumerating candidate-unavailable response."""
