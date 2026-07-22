import os
import stat
import subprocess
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


def test_browser_proof_runs_real_connected_playwright_before_teardown() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    assert "  browser-proof:" in compose
    assert "profiles: [browser-proof]" in compose
    assert "web/Dockerfile.e2e" in compose
    assert "connected-demo.spec.ts" in Path("web/e2e/connected-demo.spec.ts").read_text()
    assert script.count("docker compose --profile browser-proof run --rm --no-deps") == 3


def test_compose_proof_builds_once_and_reuses_images_across_fresh_stacks() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert script.count("docker compose --profile browser-proof build") == 1
    assert script.count("docker compose up --no-build --wait") == 4
    assert "docker compose up --build --wait" not in script
    assert "run --rm --build" not in script


def test_compose_proof_cleans_task_owned_images_and_ignores_local_build_state() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    cleanup = script.split("cleanup() {", 1)[1].split("}", 1)[0]

    assert "down --volumes --remove-orphans --rmi local" in cleanup
    for relative in (".dockerignore", "web/.dockerignore"):
        ignored = Path(relative).read_text(encoding="utf-8").splitlines()
        assert "**/*.tsbuildinfo" in ignored, relative


def test_root_browser_proof_context_ignores_local_playwright_artifacts() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    browser_proof = compose.split("  browser-proof:", 1)[1].split("volumes:", 1)[0]
    ignored = Path(".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "context: ." in browser_proof
    assert "dockerfile: web/Dockerfile.e2e" in browser_proof
    assert "**/playwright-report" in ignored
    assert "**/test-results" in ignored


def test_browser_proof_installs_one_owned_playwright_browser_tree() -> None:
    dockerfile = Path("web/Dockerfile.e2e").read_text(encoding="utf-8")
    normalized = " ".join(dockerfile.replace("\\", "").split())

    browser_path = dockerfile.index("ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright")
    install = dockerfile.index("playwright install --with-deps chromium")
    assert browser_path < install
    assert "cp -R /root/.cache/ms-playwright" not in dockerfile
    assert "chown -R browser:browser /workspace" not in dockerfile
    assert "mkdir -p /workspace/docs/assets /workspace/web/test-results" in normalized
    assert (
        "chown browser:browser /workspace/docs/assets /workspace/web /workspace/web/test-results"
        in normalized
    )
    assert "COPY --chown=browser:browser web ./" in dockerfile


def test_dockerfiles_keep_dependency_work_ahead_of_frequently_changed_source() -> None:
    api = Path("Dockerfile.api").read_text(encoding="utf-8")
    proof = Path("Dockerfile.proof").read_text(encoding="utf-8")
    web = Path("web/Dockerfile").read_text(encoding="utf-8")

    dependency_wheels = api.index("pip wheel")
    assert dependency_wheels < api.index("COPY src ./src")
    assert dependency_wheels < api.index("COPY fixtures/skills ./fixtures/skills")
    assert "/wheels/dependencies" in api
    assert "/wheels/project" in api
    assert "--mount=type=cache,target=/root/.cache/uv" in api
    assert "pip install --no-cache-dir uv==0.11.7" in api
    assert "pip wheel --no-cache-dir --wheel-dir /wheels/dependencies" in api

    dependency_sync = proof.index("uv sync --locked --no-install-project")
    assert dependency_sync < proof.index("COPY . .")
    assert proof.count("--mount=type=cache,target=/root/.cache/uv") == 2

    assert "--mount=type=cache,target=/root/.npm" in web

    for content in (api, proof, web):
        assert not content.startswith("# syntax=docker/dockerfile:1\n")


def test_browser_proof_includes_governed_collaboration_and_screenshot_capture() -> None:
    config = Path("web/playwright.compose.config.ts").read_text(encoding="utf-8")
    proof = Path("web/e2e/collaboration-demo.spec.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert '"collaboration-demo.spec.ts"' in config
    assert "UPDATE_COLLABORATION_SCREENSHOT" in proof
    assert "memory_candidate_stale" in proof
    assert "memory_candidate_expired" in proof
    assert "active_task_blocks_revision" in proof
    assert "UPDATE_COLLABORATION_SCREENSHOT=${UPDATE_COLLABORATION_SCREENSHOT:-0}" in script


def test_browser_proof_runs_isolated_fact_to_plan_and_database_verifier() -> None:
    config = Path("web/playwright.compose.config.ts").read_text(encoding="utf-8")
    browser = Path("web/e2e/fact-to-plan.spec.ts").read_text(encoding="utf-8")
    verifier = Path("scripts/verify_fact_to_plan_flow.py")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert '"fact-to-plan.spec.ts"' in config
    assert "FACT_TO_PLAN_PROOF_FILE" in browser
    assert "Continue to governed planning" in browser
    assert "events?after=0" in browser
    assert verifier.is_file()
    assert "verify_fact_to_plan_flow.py" in script
    assert "fact-to-plan.spec.ts" in script
    assert "docker compose pause worker" in script
    assert "docker compose unpause worker" in script
    assert "--no-build" in script


def test_fact_to_plan_proof_gates_task_creation_worker_start_and_responsive_content() -> None:
    browser = Path("web/e2e/fact-to-plan.spec.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert "taskPostsForCase(caseId)).toHaveLength(0)" in browser
    assert "taskPostsForCase(caseId)).toHaveLength(1)" in browser
    assert "FACT_TO_PLAN_WORKER_READY_FILE" in browser
    assert "await firstStream" in browser
    assert browser.index("await firstStream") < browser.index("writeFile(workerReadyFile")
    assert "requiredVisible: readonly Locator[]" in browser
    assert "for (const required of requiredVisible)" in browser
    for content in (
        'replan: "Re-plan required"',
        'replan: "需要重新规划"',
        'receipt: "Family Decision Receipt"',
        'receipt: "家庭决定回执"',
        'timeline: "Action timeline"',
        'timeline: "行动时间线"',
        'page.getByRole("heading", { name: presentationCopy.replan })',
        'page.getByText("Fact version 1")',
        'page.getByText("Case revision 2")',
        'page.getByRole("heading", { name: presentationCopy.receipt })',
        'page.getByRole("heading", { name: presentationCopy.timeline })',
    ):
        assert content in browser

    assert "FACT_TO_PLAN_WORKER_READY_FILE=docs/assets/.fact-to-plan-worker-ready" in script
    assert "sleep 15" not in script
    assert "seq 1 120" in script


def test_fact_to_plan_ipc_prepares_exact_writable_files_and_requires_content(
    tmp_path: Path,
) -> None:
    browser = Path("web/e2e/fact-to-plan.spec.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    reset_prepare = (
        'rm -f "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"\n'
        ': > "$FACT_TO_PLAN_PROOF_FILE"\n'
        ': > "$FACT_TO_PLAN_WORKER_READY_FILE"'
    )
    permission = 'chmod 0666 "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"'
    sentinel = 'FACT_TO_PLAN_WORKER_READY_SENTINEL="task accepted and initial SSE observed"'
    watcher = 'grep -Fqx "$FACT_TO_PLAN_WORKER_READY_SENTINEL" "$FACT_TO_PLAN_WORKER_READY_FILE"'
    browser_run = "browser-proof npx playwright test"

    assert reset_prepare in script
    assert permission in script
    assert sentinel in script
    assert watcher in script
    assert 'test -f "$FACT_TO_PLAN_WORKER_READY_FILE"' not in script
    assert 'test -s "$FACT_TO_PLAN_PROOF_FILE"' in script
    assert script.index(reset_prepare) < script.index(permission) < script.index(watcher)
    assert script.index(watcher) < script.index(browser_run)
    assert 'chmod 0666 docs/assets' not in script

    proof_target = tmp_path / "proof-target"
    ready_target = tmp_path / "ready-target"
    proof_target.write_text("preserve proof target\n", encoding="utf-8")
    ready_target.write_text("preserve ready target\n", encoding="utf-8")
    proof_target.chmod(0o640)
    ready_target.chmod(0o640)
    proof_file = tmp_path / ".fact-to-plan-proof.json"
    ready_file = tmp_path / ".fact-to-plan-worker-ready"
    proof_file.symlink_to(proof_target)
    ready_file.symlink_to(ready_target)
    environment = os.environ.copy()
    environment.update(
        FACT_TO_PLAN_PROOF_FILE=str(proof_file),
        FACT_TO_PLAN_WORKER_READY_FILE=str(ready_file),
    )
    subprocess.run(
        ["sh", "-eu", "-c", f"{reset_prepare}\n{permission}"],
        check=True,
        env=environment,
    )

    assert not proof_file.is_symlink()
    assert not ready_file.is_symlink()
    assert proof_file.read_bytes() == b""
    assert ready_file.read_bytes() == b""
    assert stat.S_IMODE(proof_file.stat().st_mode) == 0o666
    assert stat.S_IMODE(ready_file.stat().st_mode) == 0o666
    assert proof_target.read_text(encoding="utf-8") == "preserve proof target\n"
    assert ready_target.read_text(encoding="utf-8") == "preserve ready target\n"
    assert stat.S_IMODE(proof_target.stat().st_mode) == 0o640
    assert stat.S_IMODE(ready_target.stat().st_mode) == 0o640

    cleanup = script.split("cleanup() {", 1)[1].split("}", 1)[0]
    assert 'rm -f "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"' in cleanup
    assert "FACT_TO_PLAN_WORKER_READY_SENTINEL" in browser
    assert '`${workerReadySentinel}\\n`' in browser
