from __future__ import annotations

from typing import Protocol

from night_voyager.adapters.protocols import PlanningAdapter


class PlanningAdapterPort(PlanningAdapter, Protocol):
    """Task-layer alias for the product-owned adapter boundary."""
