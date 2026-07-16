from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.adapters.protocols import PlanningAdapterRequest
from night_voyager.planning.trusted import GovernedMixedSnapshotV1


@dataclass(frozen=True, slots=True)
class MixedSnapshotLoadError(RuntimeError):
    retryable: bool


class PostgresMixedPlanningRepository:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def load(
        self, request: PlanningAdapterRequest
    ) -> GovernedMixedSnapshotV1:
        try:
            async with self._session_factory() as session, session.begin():
                await session.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(request.organization_id)},
                )
                payload = await session.scalar(
                    text(
                        "SELECT app.load_governed_mixed_planning_snapshot("
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
            raise MixedSnapshotLoadError(retryable=retryable) from error
        if not isinstance(payload, dict):
            raise MixedSnapshotLoadError(retryable=False)
        try:
            return GovernedMixedSnapshotV1.model_validate_json(json.dumps(payload))
        except ValueError as error:
            raise MixedSnapshotLoadError(retryable=False) from error
