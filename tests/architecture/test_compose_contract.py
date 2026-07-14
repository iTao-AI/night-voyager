from pathlib import Path


def test_web_healthcheck_uses_ipv4_loopback() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert '"http://127.0.0.1:3000"' in compose


def test_compose_proof_executes_m3b_golden_flow_and_teardown() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    assert "verify_m3b_flow.py" in script
    assert "down --volumes --remove-orphans" in script


def test_worker_service_runs_functional_task_worker_with_non_owner_role() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    entrypoint = Path("src/night_voyager/worker.py").read_text(encoding="utf-8")

    worker = compose.split("  worker:", 1)[1].split("  db-test:", 1)[0]
    assert 'command: ["python", "-m", "night_voyager.worker"]' in worker
    assert "night_voyager_worker" in worker
    assert "night_voyager_migrator" not in worker
    assert "TaskWorker" in entrypoint
    assert "DeterministicPlanningAdapter" in entrypoint


def test_web_uses_only_fixed_m5_bff_origins() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    web = compose.split("  web:", 1)[1].split("volumes:", 1)[0]
    assert "NIGHT_VOYAGER_API_INTERNAL_URL: http://api:8000" in web
    assert "NIGHT_VOYAGER_PUBLIC_ORIGIN: http://127.0.0.1:3000" in web
    assert "API_BASE_URL" not in web
