"""Identity and row-security foundation.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the M2 identity boundary (implemented with the database gate)."""


def downgrade() -> None:
    """Remove the M2 identity boundary (implemented with the database gate)."""
