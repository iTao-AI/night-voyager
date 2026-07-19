from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.adapters.protocols import PlanningAdapterRequest
from night_voyager.planning.synthetic import PersistedSyntheticSnapshotV1


@dataclass(frozen=True, slots=True)
class SyntheticSnapshotLoadError(RuntimeError):
    retryable: bool


class PersistedSyntheticSnapshotRepository:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def load(
        self, request: PlanningAdapterRequest
    ) -> PersistedSyntheticSnapshotV1:
        if request.operation != "generate_planning_run_v1":
            raise SyntheticSnapshotLoadError(retryable=False)
        try:
            async with self._session_factory() as session, session.begin():
                await session.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(request.organization_id)},
                )
                payload = await session.scalar(
                    text(
                        "SELECT app.load_persisted_synthetic_planning_snapshot("
                        ":org,:case,:revision,:pack,:pack_version,:policy)"
                    ),
                    {
                        "org": request.organization_id,
                        "case": request.case_id,
                        "revision": request.case_revision,
                        "pack": request.source_pack_id,
                        "pack_version": request.source_pack_version,
                        "policy": request.policy_version,
                    },
                )
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            retryable = (
                isinstance(error, OperationalError)
                or error.connection_invalidated
                or (isinstance(sqlstate, str) and sqlstate.startswith("08"))
                or sqlstate in {"40001", "40P01"}
            )
            raise SyntheticSnapshotLoadError(retryable=retryable) from error
        if not isinstance(payload, dict):
            raise SyntheticSnapshotLoadError(retryable=False)
        try:
            snapshot = PersistedSyntheticSnapshotV1.model_validate_json(
                json.dumps(payload), strict=True
            )
        except ValueError as error:
            raise SyntheticSnapshotLoadError(retryable=False) from error
        if (
            snapshot.organization_id != request.organization_id
            or snapshot.case.case_id != request.case_id
            or snapshot.case.revision != request.case_revision
            or snapshot.source_pack_id != request.source_pack_id
            or snapshot.source_pack_version != request.source_pack_version
            or snapshot.policy_version != request.policy_version
        ):
            raise SyntheticSnapshotLoadError(retryable=False)
        return snapshot
