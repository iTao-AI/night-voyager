from __future__ import annotations


class StaleRevisionError(RuntimeError):
    def __init__(self, expected: int | None, actual: int | None) -> None:
        super().__init__(f"stale case revision: expected {expected}, actual {actual}")
        self.expected = expected
        self.actual = actual
