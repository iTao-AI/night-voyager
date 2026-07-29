class TimelineExecutionProjectionError(ValueError):
    """The authoritative execution projection is contradictory or malformed."""


class TimelineExecutionUnavailableError(LookupError):
    """The requested execution authority is unavailable."""


class TimelineExecutionConflictError(RuntimeError):
    """The requested execution mutation conflicts with durable state."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
