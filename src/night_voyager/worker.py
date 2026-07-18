from __future__ import annotations

import asyncio
import os
import socket

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.config import Settings
from night_voyager.database import create_engine, create_session_factory
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
)
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.postgres import postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker


async def run() -> None:
    settings = Settings()
    engine = create_engine(settings.database_url)
    worker_id = f"worker-{socket.gethostname()}-{os.getpid()}"
    try:
        session_factory = create_session_factory(engine)
        worker = TaskWorker(
            postgres_worker_repository_factory(session_factory),
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(session_factory)
                ),
                mixed=GovernedMixedPlanningAdapter(
                    PostgresMixedPlanningRepository(session_factory)
                ),
            ),
            SkillRuntimeRegistry.load_packaged(),
            worker_id=worker_id,
        )
        await worker.run_forever()
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
