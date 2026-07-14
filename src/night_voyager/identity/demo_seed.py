from __future__ import annotations

from uuid import UUID

CONNECTED_DEMO_CASE_ID = UUID("40000000-0000-0000-0000-000000000002")


def ensure_seed_allowed(environment: str, demo_mode: bool) -> None:
    if environment not in {"development", "test"}:
        raise ValueError("demo seed requires development or test environment")
    if not demo_mode:
        raise ValueError("demo seed requires explicit demo mode")
