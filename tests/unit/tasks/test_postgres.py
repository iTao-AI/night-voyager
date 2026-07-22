from __future__ import annotations

import pytest
from sqlalchemy.exc import DBAPIError

from night_voyager.tasks.errors import TaskConflictError
from night_voyager.tasks.postgres import PostgresTaskRepository


class SqlStateOrigin(Exception):
    def __init__(self, sqlstate: str | None) -> None:
        super().__init__("raw database detail must not escape")
        self.sqlstate = sqlstate


def db_error(sqlstate: str | None) -> DBAPIError:
    return DBAPIError(
        "SELECT internal_detail()",
        {},
        SqlStateOrigin(sqlstate),
        connection_invalidated=sqlstate is None,
    )


def test_nv008_maps_to_bounded_idempotency_conflict() -> None:
    with pytest.raises(TaskConflictError) as captured:
        PostgresTaskRepository._raise_mapped(  # pyright: ignore[reportPrivateUsage]
            db_error("NV008")
        )

    assert captured.value.code == "idempotency_conflict"
    assert "NV008" not in str(captured.value)
    assert "raw database detail" not in str(captured.value)


def test_unknown_database_failure_is_not_disguised_as_idempotency_conflict() -> None:
    unknown = db_error("XX999")

    with pytest.raises(DBAPIError) as captured:
        PostgresTaskRepository._raise_mapped(  # pyright: ignore[reportPrivateUsage]
            unknown
        )

    assert captured.value is unknown
