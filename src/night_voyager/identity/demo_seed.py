from __future__ import annotations


def ensure_seed_allowed(environment: str, demo_mode: bool) -> None:
    if environment not in {"development", "test"}:
        raise ValueError("demo seed requires development or test environment")
    if not demo_mode:
        raise ValueError("demo seed requires explicit demo mode")
