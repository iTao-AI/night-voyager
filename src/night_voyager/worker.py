from __future__ import annotations

import asyncio
import os
import socket

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.config import Settings
from night_voyager.database import create_engine, create_session_factory
from night_voyager.tasks.postgres import postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker


async def run() -> None:
    settings = Settings()
    engine = create_engine(settings.database_url)
    worker_id = f"worker-{socket.gethostname()}-{os.getpid()}"
    try:
        worker = TaskWorker(
            postgres_worker_repository_factory(create_session_factory(engine)),
            DeterministicPlanningAdapter(),
            worker_id=worker_id,
        )
        await worker.run_forever()
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
