import json
import os
import re
import stat
import subprocess
import textwrap
from pathlib import Path

import yaml

APPROVED_PRESENTATION_ASSETS = (
    "night-voyager-portfolio-entry.png",
    "collaboration-confirmed-fact.png",
    "m5-advisor-ledger.png",
    "m5-family-receipt-timeline.png",
    "night-voyager-planning-revision.png",
    "plan-execution-current-action.png",
    "plan-execution-advisor-review.png",
    "plan-execution-reassessment-mobile.png",
    "plan-execution-recovery-mobile.png",
)


def _run_compose_cleanup_harness(
    tmp_path: Path,
    *,
    initial_status: int = 0,
    down_status: int = 0,
    residue: str = "",
    signal_name: str | None = None,
) -> subprocess.CompletedProcess[str]:
    source = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    cleanup = source.split("cleanup() {", 1)[1].split(
        "\n}\n\nstart_planning_revision_barrier", 1
    )[0]
    trap_contract = "\n".join(
        line for line in source.splitlines() if line.startswith("trap ")
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    docker_stub = bin_dir / "docker"
    docker_stub.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            printf '%s|%s\n' "$COMPOSE_PROJECT_NAME" "$*" >> "$STUB_LOG"
            case "$*" in
                "compose down"*) exit "$STUB_DOWN_STATUS" ;;
                "compose ps --all --quiet") printf '%s' "$STUB_RESIDUE" ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    docker_stub.chmod(0o755)
    harness = tmp_path / "cleanup-harness.sh"
    harness.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            set -eu
            COMPOSE_PROJECT_NAME=night-voyager-cleanup-contract
            export COMPOSE_PROJECT_NAME
            planning_revision_browser_pid=
            worker_start_pid=
            barrier_fd_open=0
            barrier_pid=
            FACT_TO_PLAN_ZH_PROOF_FILE=fact-zh
            FACT_TO_PLAN_ZH_WORKER_READY_FILE=fact-zh-ready
            FACT_TO_PLAN_EN_PROOF_FILE=fact-en
            FACT_TO_PLAN_EN_WORKER_READY_FILE=fact-en-ready
            PLANNING_REVISION_ZH_PROOF_FILE=revision-zh
            PLANNING_REVISION_ZH_WORKER_READY_FILE=revision-zh-ready
            PLANNING_REVISION_EN_PROOF_FILE=revision-en
            PLANNING_REVISION_EN_WORKER_READY_FILE=revision-en-ready
            PLANNING_REVISION_BARRIER_FIFO=barrier-fifo
            PLANNING_REVISION_BARRIER_OUTPUT=barrier-output
            PLANNING_REVISION_BARRIER_STATE=barrier-state
            PLANNING_REVISION_PREDECESSOR_STDOUT=predecessor-out
            PLANNING_REVISION_PREDECESSOR_STDERR=predecessor-err
            PLAN_EXECUTION_RECOVERY_PROOF_FILE=recovery-proof
            cleanup() {{{cleanup}
            }}
            {trap_contract}
            {f'kill -{signal_name} $$' if signal_name else f'exit {initial_status}'}
            exit 99
            """
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.update(
        PATH=f"{bin_dir}:/usr/bin:/bin",
        STUB_LOG=str(tmp_path / "docker.log"),
        STUB_DOWN_STATUS=str(down_status),
        STUB_RESIDUE=residue,
    )
    return subprocess.run(
        ["sh", str(harness)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_compose_interruptions_preserve_signal_status_and_cleanup_once(
    tmp_path: Path,
) -> None:
    for signal_name, expected_status in (("INT", 130), ("TERM", 143)):
        result = _run_compose_cleanup_harness(
            tmp_path / signal_name.lower(), signal_name=signal_name
        )

        assert result.returncode == expected_status
        log = (tmp_path / signal_name.lower() / "docker.log").read_text(
            encoding="utf-8"
        )
        assert log.count("night-voyager-cleanup-contract|") == 2
        assert "compose down --volumes --remove-orphans --rmi local" in log
        assert "compose ps --all --quiet" in log


def test_compose_cleanup_preserves_main_failure_and_fails_on_teardown_or_residue(
    tmp_path: Path,
) -> None:
    original_failure = _run_compose_cleanup_harness(tmp_path / "original", initial_status=7)
    teardown_failure = _run_compose_cleanup_harness(tmp_path / "down", down_status=9)
    residue_failure = _run_compose_cleanup_harness(tmp_path / "residue", residue="container-id")

    assert original_failure.returncode == 7
    assert teardown_failure.returncode != 0
    assert residue_failure.returncode != 0
    for case in ("original", "down", "residue"):
        log = (tmp_path / case / "docker.log").read_text(encoding="utf-8")
        assert log.count("night-voyager-cleanup-contract|") == 2
        assert "compose down --volumes --remove-orphans --rmi local" in log
        assert "compose ps --all --quiet" in log


def test_web_healthcheck_uses_ipv4_loopback() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert '"http://127.0.0.1:3000"' in compose


def test_hosted_compose_heavy_gates_are_independent_and_exact() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    heavy_commands = {
        "compose_db": "make db-check",
        "compose_collaboration_authority": (
            "make collaboration-db-check SUITE=authority"
        ),
        "compose_proof": "make compose-proof",
    }
    project_names: set[str] = set()

    assert set(jobs) == {
        "python",
        "frontend",
        *heavy_commands,
        "compose",
    }
    for lane_id, command in heavy_commands.items():
        lane = jobs[lane_id]
        steps = lane["steps"]
        uses = [step["uses"] for step in steps if "uses" in step]
        runs = [step["run"] for step in steps if "run" in step]
        project_name = lane["env"]["COMPOSE_PROJECT_NAME"]

        assert "needs" not in lane
        assert lane["timeout-minutes"] == 30
        assert any(use.startswith("actions/checkout@") for use in uses)
        assert any(use.startswith("docker/setup-buildx-action@") for use in uses)
        assert runs == [command, "make down"]
        assert steps[-1] == {"if": "always()", "run": "make down"}
        assert "continue-on-error" not in lane
        assert all("continue-on-error" not in step for step in steps)
        assert "${{ github.run_id }}" in project_name
        assert "${{ github.run_attempt }}" in project_name
        assert lane_id.replace("_", "-") in project_name
        project_names.add(project_name)

    assert len(project_names) == len(heavy_commands)


def test_hosted_compose_aggregator_is_stable_and_fail_closed() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    compose_job = workflow["jobs"]["compose"]
    expected_needs = [
        "compose_db",
        "compose_collaboration_authority",
        "compose_proof",
    ]
    success_checks = compose_job["steps"][0]["run"].splitlines()

    assert compose_job["name"] == "compose"
    assert compose_job["needs"] == expected_needs
    assert compose_job["if"] == "always()"
    assert "timeout-minutes" not in compose_job
    assert len(compose_job["steps"]) == 1
    assert all("uses" not in step for step in compose_job["steps"])
    assert success_checks == [
        f'test "${{{{ needs.{lane_id}.result }}}}" = success'
        for lane_id in expected_needs
    ]
    assert "continue-on-error" not in compose_job


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
    assert script.count("docker compose --profile browser-proof run --rm --no-deps") == 8
    assert "PRESENTATION_AUDIT=1" in script
    assert "PRESENTATION_AUDIT_OUTPUT_DIR" in script
    assert "presentation.spec.ts" in script


def test_presentation_audit_lane_runs_the_exact_browser_specs_and_fail_closed_root() -> None:
    config = Path("web/playwright.compose.config.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    lane = script.split("run_presentation_audit_lane() {", 1)[1].split(
        "\n}\n\nrun_plan_execution_lane", 1
    )[0]

    for spec in (
        "bootstrap.spec.ts",
        "portfolio-design-review.spec.ts",
        "presentation.spec.ts",
    ):
        assert spec in config
        assert spec in lane
    assert "PRESENTATION_PUBLIC_EVIDENCE_ROOT=${PRESENTATION_PUBLIC_EVIDENCE_ROOT:-}" in script
    assert (
        lane.count('-e PRESENTATION_PUBLIC_EVIDENCE_ROOT="$PRESENTATION_PUBLIC_EVIDENCE_ROOT"')
        == 1
    )
    assert (
        script.count('-e PRESENTATION_PUBLIC_EVIDENCE_ROOT="$PRESENTATION_PUBLIC_EVIDENCE_ROOT"')
        == 1
    )
    assert "presentation.spec.ts" in lane


def test_presentation_audit_success_marker_is_count_neutral() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert "compose-proof: presentation audit passed" in script
    assert "58-cell" not in script


def test_presentation_evidence_contract_has_exactly_the_approved_public_assets() -> None:
    presentation = Path("web/e2e/presentation.spec.ts").read_text(encoding="utf-8")
    browser_sources = "\n".join(
        Path(relative).read_text(encoding="utf-8")
        for relative in (
            "web/e2e/fact-to-plan.spec.ts",
            "web/e2e/collaboration-demo.spec.ts",
            "web/e2e/connected-demo.spec.ts",
            "web/e2e/planning-revision.spec.ts",
            "web/e2e/presentation.spec.ts",
        )
    )

    assert "APPROVED_PUBLIC_EVIDENCE_FILENAMES" in presentation
    assert "PUBLIC_EVIDENCE_ROOT && publicFilename" in presentation
    declared_filenames = set(re.findall(r'"([a-z0-9-]+\.png)"', browser_sources))
    assert declared_filenames == set(APPROVED_PRESENTATION_ASSETS)
    for filename in APPROVED_PRESENTATION_ASSETS:
        assert filename in browser_sources
    assert "PRESENTATION_PUBLIC_EVIDENCE_ROOT" not in "\n".join(
        Path(relative).read_text(encoding="utf-8")
        for relative in (
            "web/e2e/fact-to-plan.spec.ts",
            "web/e2e/collaboration-demo.spec.ts",
            "web/e2e/connected-demo.spec.ts",
            "web/e2e/planning-revision.spec.ts",
        )
    )


def test_current_public_navigation_explains_the_advisor_workspace_and_two_proof_segments() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_cn = Path("README_CN.md").read_text(encoding="utf-8")
    docs_index = Path("docs/README.md").read_text(encoding="utf-8")

    assert "AI collaboration platform for study-abroad advisors" in readme
    assert "connected same-Case proof ends at the receipt and TimelinePlan" in readme
    assert "independent deterministic execution scenario" in readme
    assert "Screenshots are review evidence, not functional authority" in readme
    assert "面向留学顾问的 AI 协作平台" in readme_cn
    assert "同一 Case" in readme_cn
    assert "独立播种" in readme_cn
    assert "截图是评审证据，不是功能权威" in readme_cn
    assert "reference-driven AI collaboration platform for study-abroad advisors" in docs_index
    assert "independent deterministic execution scenario" in docs_index


def test_compose_proof_builds_once_and_reuses_images_across_fresh_stacks() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert script.count("docker compose --profile browser-proof build") == 1
    assert script.count("docker compose up --no-build --wait") == 9
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


def test_root_proof_context_excludes_only_root_task_local_tmp() -> None:
    ignored = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    proof = Path("Dockerfile.proof").read_text(encoding="utf-8")

    assert "tmp" in ignored
    assert "**/tmp" not in ignored
    assert "COPY . ." in proof
    assert "--tree-mode snapshot" in proof


def test_compose_proof_runs_governed_dra_closure_and_closed_outcome_inspector() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    governed = Path("scripts/verify_dra_governed_flow.py").read_text(
        encoding="utf-8"
    )
    assert "verify_dra_governed_flow.py --fixture" in script
    assert "PostgresLiveOutcomeInspector" in governed
    assert "app.evidence_refs" not in governed


def test_local_playwright_uses_the_exact_ipv4_next_origin() -> None:
    config = Path("web/playwright.config.ts").read_text(encoding="utf-8")

    assert 'command: "npm run dev -- --hostname 127.0.0.1"' in config
    assert 'url: "http://127.0.0.1:3000"' in config


def test_browser_proof_installs_one_owned_playwright_browser_tree() -> None:
    dockerfile = Path("web/Dockerfile.e2e").read_text(encoding="utf-8")
    normalized = " ".join(dockerfile.replace("\\", "").split())

    browser_path = dockerfile.index("ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright")
    install = dockerfile.index(
        "./node_modules/.bin/playwright install --with-deps chromium"
    )
    assert browser_path < install
    assert "cp -R /root/.cache/ms-playwright" not in dockerfile
    assert "chown -R browser:browser /workspace" not in dockerfile
    assert "mkdir -p /workspace/docs/assets /workspace/web/test-results" in normalized
    assert (
        "chown browser:browser /workspace/docs/assets /workspace/web /workspace/web/test-results"
        in normalized
    )
    assert "COPY --chown=browser:browser web ./" in dockerfile


def test_browser_proof_installer_uses_checked_in_lockfile_integrity_authority() -> None:
    dockerfile = Path("web/Dockerfile.e2e").read_text(encoding="utf-8")
    package = json.loads(Path("web/package.json").read_text(encoding="utf-8"))
    lock = json.loads(Path("web/package-lock.json").read_text(encoding="utf-8"))
    installer_package_path = Path("web/docker/browser-installer/package.json")
    installer_lock_path = Path("web/docker/browser-installer/package-lock.json")

    expected = package["devDependencies"]["@playwright/test"]
    assert expected == "1.58.2"
    assert lock["packages"]["node_modules/@playwright/test"]["version"] == expected
    assert lock["packages"]["node_modules/playwright"]["version"] == expected
    assert lock["packages"]["node_modules/playwright-core"]["version"] == expected
    assert installer_package_path.is_file()
    assert installer_lock_path.is_file()

    installer_package = json.loads(installer_package_path.read_text(encoding="utf-8"))
    installer_lock = json.loads(installer_lock_path.read_text(encoding="utf-8"))
    assert installer_package["private"] is True
    assert installer_package["dependencies"] == {"playwright": expected}
    assert installer_lock["packages"][""]["dependencies"] == {"playwright": expected}
    for dependency in ("playwright", "playwright-core"):
        root_entry = lock["packages"][f"node_modules/{dependency}"]
        installer_entry = installer_lock["packages"][f"node_modules/{dependency}"]
        assert installer_entry["version"] == expected
        assert installer_entry["resolved"] == root_entry["resolved"]
        assert installer_entry["integrity"] == root_entry["integrity"]
        assert installer_entry["resolved"].endswith(f"{dependency}-{expected}.tgz")
        assert installer_entry["integrity"].startswith("sha512-")

    assert f"ARG PLAYWRIGHT_VERSION={expected}" in dockerfile
    assert (
        "COPY web/docker/browser-installer/package.json "
        "web/docker/browser-installer/package-lock.json ./"
    ) in dockerfile
    normalized = " ".join(dockerfile.replace("\\\n", " ").split())
    assert "RUN --mount=type=cache,target=/root/.npm npm ci" in normalized
    assert "./node_modules/.bin/playwright install --with-deps chromium" in dockerfile
    assert "npx --yes playwright@" not in dockerfile
    assert "npm exec --package playwright@" not in dockerfile


def test_browser_proof_keeps_stable_browser_and_os_layers_ahead_of_version_copy() -> None:
    dockerfile = Path("web/Dockerfile.e2e").read_text(encoding="utf-8")

    installer_copy = dockerfile.index(
        "COPY web/docker/browser-installer/package.json "
        "web/docker/browser-installer/package-lock.json ./"
    )
    package_copy = dockerfile.index(
        "COPY web/package.json web/package-lock.json ./"
    )
    browser_install = dockerfile.index(
        "./node_modules/.bin/playwright install --with-deps chromium"
    )
    socat_install = dockerfile.index(
        "apt-get install --yes --no-install-recommends socat"
    )
    installer_install = dockerfile.index("npm ci", installer_copy)
    project_install = dockerfile.index("npm ci", installer_install + 1)

    assert installer_copy < installer_install
    assert installer_install < browser_install
    assert browser_install < package_copy
    assert socat_install < package_copy
    assert package_copy < project_install
    stable_prefix = dockerfile[:package_copy]
    assert "COPY web/package.json" not in stable_prefix
    assert "COPY web/package-lock.json" not in stable_prefix
    assert "npm ci &&" not in dockerfile


def test_browser_proof_dependency_cache_preserves_non_root_runtime_contract() -> None:
    dockerfile = Path("web/Dockerfile.e2e").read_text(encoding="utf-8")

    assert "ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright" in dockerfile
    assert "useradd --create-home --uid 10001 browser" in dockerfile
    assert "COPY --chown=browser:browser web ./" in dockerfile
    assert dockerfile.index("COPY --chown=browser:browser web ./") < dockerfile.index(
        "USER browser"
    )
    assert 'ENTRYPOINT ["sh", "-c", "socat TCP-LISTEN:3000' in dockerfile


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


def test_web_docker_installs_use_locked_retrying_registry_reads() -> None:
    web = Path("web/Dockerfile").read_text(encoding="utf-8")
    browser = Path("web/Dockerfile.e2e").read_text(encoding="utf-8")
    install = (
        "npm ci --prefer-offline --fetch-retries=5 "
        "--fetch-retry-mintimeout=10000 --fetch-retry-maxtimeout=60000"
    )

    normalized_web = " ".join(web.replace("\\\n", " ").split())
    normalized_browser = " ".join(browser.replace("\\\n", " ").split())
    assert normalized_web.count(
        f"RUN --mount=type=cache,target=/root/.npm {install}"
    ) == 1
    assert normalized_browser.count(
        f"RUN --mount=type=cache,target=/root/.npm {install}"
    ) == 2

    assert "COPY package.json package-lock.json ./" in web
    assert browser.count(
        "COPY web/docker/browser-installer/package.json "
        "web/docker/browser-installer/package-lock.json ./"
    ) == 1
    assert browser.count("COPY web/package.json web/package-lock.json ./") == 1
    for content in (web, browser):
        assert " --offline" not in content
        assert ".npmrc" not in content
        assert "registry=" not in content
        assert "HTTP_PROXY" not in content
        assert "HTTPS_PROXY" not in content
        assert "host.docker.internal" not in content


def test_web_standalone_image_includes_public_portfolio_assets() -> None:
    dockerfile = Path("web/Dockerfile").read_text(encoding="utf-8")

    public_copy = (
        "COPY --from=builder --chown=nextjs:nodejs /app/public ./public"
    )
    assert public_copy in dockerfile
    assert dockerfile.index(public_copy) < dockerfile.index("USER nextjs")


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
    assert "Continue to planning" in browser
    assert "events?after=0" in browser
    assert verifier.is_file()
    assert "verify_fact_to_plan_flow.py" in script
    assert "fact-to-plan.spec.ts" in script
    assert "docker compose pause worker" in script
    assert "docker compose unpause worker" in script
    assert "--no-build" in script
    assert 'run_fact_to_plan_lane "zh-CN"' in script
    assert 'run_fact_to_plan_lane "en"' in script
    assert "-e PRESENTATION_LOCALE=en" in script
    assert "UPDATE_PORTFOLIO_SCREENSHOTS=${UPDATE_PORTFOLIO_SCREENSHOTS:-0}" in script
    assert (
        '-e UPDATE_PORTFOLIO_SCREENSHOTS="$UPDATE_PORTFOLIO_SCREENSHOTS"'
        in script
    )


def test_required_compose_gate_runs_both_locales_from_fresh_baselines() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    lane = script.split("run_fact_to_plan_lane() {", 1)[1].split("\n}", 1)[0]

    assert 'case "$lane_locale" in' in lane
    assert (
        'zh-CN) set -- -e UPDATE_PORTFOLIO_SCREENSHOTS="$UPDATE_PORTFOLIO_SCREENSHOTS" ;;'
        in lane
    )
    assert 'en) set -- -e PRESENTATION_LOCALE=en ;;' in lane
    assert "docker compose down --volumes --remove-orphans" in lane
    assert "docker compose up --no-build --wait" in lane
    assert "browser-proof npx playwright test" in lane
    assert "verify_fact_to_plan_flow.py" in lane
    assert "governed fact-to-plan browser and database proof passed locale=%s" in lane
    assert script.count('run_fact_to_plan_lane "zh-CN"') == 1
    assert script.count('run_fact_to_plan_lane "en"') == 1
    zh_lane = script.index('run_fact_to_plan_lane "zh-CN"')
    en_lane = script.index('run_fact_to_plan_lane "en"')
    assert zh_lane < en_lane


def test_fact_to_plan_root_proof_locks_the_high_end_portfolio_contract() -> None:
    browser = Path("web/e2e/fact-to-plan.spec.ts").read_text(encoding="utf-8")
    bootstrap = Path("web/e2e/bootstrap.spec.ts").read_text(encoding="utf-8")

    for token in (
        "Move complex study-abroad planning forward with clarity.",
        "让复杂的留学规划，清晰地向前。",
        '"/demo/collaboration"',
        '"#route-atlas .portfolio-preview-route-description"',
        "{ width: 1440, height: 1000 }",
        "{ width: 768, height: 1024 }",
        "{ width: 390, height: 844 }",
        "{ width: 320, height: 720 }",
        'page.emulateMedia({ reducedMotion: "reduce" })',
        "rootApiRequests",
        "storageReplacements",
        ".portfolio-primary-action:visible",
        "document.documentElement.scrollWidth",
        "night-voyager-portfolio-entry.png",
    ):
        assert token in browser
    for token in (
        "apiRequests",
        "eventRequests",
        "sessionStorage.getItem",
        "English",
        "{ width: 320, height: 720 }",
    ):
        assert token in bootstrap


def test_fact_to_plan_proof_gates_task_creation_worker_start_and_responsive_content() -> None:
    browser = Path("web/e2e/fact-to-plan.spec.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert "taskPostsForCase(caseId)).toHaveLength(0)" in browser
    assert "taskPostsForCase(caseId)).toHaveLength(1)" in browser
    assert "FACT_TO_PLAN_WORKER_READY_FILE" in browser
    assert "await firstStream" in browser
    assert browser.index("await firstStream") < browser.index("writeFile(workerReadyFile")
    assert "waitForFactToPlanReviewAuthority" in browser
    assert "`/api/demo/cases/${caseId}/journey-status`" in browser
    assert "`/api/demo/tasks/${taskId}`" in browser
    assert "`/api/demo/cases/${caseId}/advisor-ledger`" in browser
    assert 'phase: journey.phase' in browser
    assert 'taskStatus: task.status' in browser
    assert 'ledgerPhase: ledger.phase' in browser
    assert 'problemCode: payload.code' in browser
    assert "timeout: 120_000" in browser
    assert "fact-to-plan approval convergence diagnostic" in browser
    cursor_wait = browser.index(
        'Number(JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").cursor) > 0'
    )
    authority_wait = browser.index("await waitForFactToPlanReviewAuthority")
    approval_wait = browser.index(
        'page.getByRole("button", { name: presentationCopy.approve })'
    )
    assert cursor_wait < authority_wait < approval_wait
    assert "waitForTimeout" not in browser
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
        'page.locator("[data-confirmed-record]")',
        'toHaveAttribute("data-fact-version", "1")',
        'toHaveAttribute("data-case-revision", "2")',
        'getByText(presentationCopy.factVersion, { exact: true })',
        'getByText(presentationCopy.caseRevision, { exact: true })',
        'page.getByRole("heading", { name: presentationCopy.receipt })',
        'page.getByRole("heading", { name: presentationCopy.timeline })',
    ):
        assert content in browser

    assert "FACT_TO_PLAN_ZH_PROOF_FILE=docs/assets/.fact-to-plan-zh-CN-proof.json" in script
    assert (
        "FACT_TO_PLAN_ZH_WORKER_READY_FILE="
        "docs/assets/.fact-to-plan-zh-CN-worker-ready"
    ) in script
    assert "FACT_TO_PLAN_EN_PROOF_FILE=docs/assets/.fact-to-plan-en-proof.json" in script
    assert "FACT_TO_PLAN_EN_WORKER_READY_FILE=docs/assets/.fact-to-plan-en-worker-ready" in script
    assert "sleep 15" not in script
    assert "seq 1 120" in script


def test_fact_to_plan_ipc_prepares_exact_writable_files_and_requires_content(
    tmp_path: Path,
) -> None:
    browser = Path("web/e2e/fact-to-plan.spec.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    reset_prepare = (
        '    rm -f "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"\n'
        '    : > "$FACT_TO_PLAN_PROOF_FILE"\n'
        '    : > "$FACT_TO_PLAN_WORKER_READY_FILE"'
    )
    permission = 'chmod 0666 "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"'
    sentinel = 'FACT_TO_PLAN_WORKER_READY_SENTINEL="task accepted and initial SSE observed"'
    watcher = 'grep -Fqx "$FACT_TO_PLAN_WORKER_READY_SENTINEL" "$FACT_TO_PLAN_WORKER_READY_FILE"'
    browser_run = "browser-proof npx playwright test"
    lane = script.split("run_fact_to_plan_lane() {", 1)[1].split("\n}", 1)[0]

    assert reset_prepare in script
    assert permission in script
    assert sentinel in script
    assert watcher in script
    assert 'test -f "$FACT_TO_PLAN_WORKER_READY_FILE"' not in script
    assert 'test -s "$FACT_TO_PLAN_PROOF_FILE"' in script
    assert script.index(reset_prepare) < script.index(permission) < script.index(watcher)
    assert lane.index(watcher) < lane.index(browser_run)
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
    for path_variable in (
        "FACT_TO_PLAN_ZH_PROOF_FILE",
        "FACT_TO_PLAN_ZH_WORKER_READY_FILE",
        "FACT_TO_PLAN_EN_PROOF_FILE",
        "FACT_TO_PLAN_EN_WORKER_READY_FILE",
    ):
        assert f'"${path_variable}"' in cleanup
    assert "FACT_TO_PLAN_WORKER_READY_SENTINEL" in browser
    assert '`${workerReadySentinel}\\n`' in browser


def test_planning_revision_compose_lane_is_closed_and_runs_both_locales() -> None:
    config = Path("web/playwright.compose.config.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert '"planning-revision.spec.ts"' in config
    assert "UPDATE_PLANNING_REVISION_SCREENSHOT=${UPDATE_PLANNING_REVISION_SCREENSHOT:-0}" in script
    assert (
        "PLANNING_REVISION_REVIEW_DIR="
        "${PLANNING_REVISION_REVIEW_DIR:-tmp/planning-revision-review}"
        in script
    )
    assert "run_planning_revision_lane() {" in script
    lane = script.split("run_planning_revision_lane() {", 1)[1].split("\n}", 1)[0]
    assert 'case "$lane_locale" in' in lane
    assert (
        'zh-CN) set -- -e UPDATE_PLANNING_REVISION_SCREENSHOT='
        '"$UPDATE_PLANNING_REVISION_SCREENSHOT" ;;'
        in lane
    )
    assert (
        "en) set -- -e PRESENTATION_LOCALE=en "
        "-e UPDATE_PLANNING_REVISION_SCREENSHOT=0 ;;"
        in lane
    )
    assert "docker compose down --volumes --remove-orphans" in lane
    assert "docker compose up --no-build --wait" in lane
    assert "docker compose pause worker" in lane
    assert "docker compose unpause worker" in lane
    assert "docker compose restart worker" in lane
    assert "planning-revision.spec.ts" in lane
    assert "verify_planning_revision_flow.py" in lane
    assert '-v "$PWD/$PLANNING_REVISION_REVIEW_DIR:/workspace/tmp/planning-revision-review"' in lane
    assert script.count('run_planning_revision_lane "zh-CN"') == 1
    assert script.count('run_planning_revision_lane "en"') == 1

    mode = script.split("case \"$mode\" in", 1)[1].split("esac", 1)[0]
    assert "planning-revision)" in mode
    assert "full)" in mode
    assert "unsupported mode" in mode
    assert script.index('case "$mode" in') < script.index("docker compose config --quiet")
    for forbidden in ("HTTP_PROXY", "HTTPS_PROXY", "API_BASE_URL", "host.docker.internal"):
        assert forbidden not in lane


def test_planning_revision_restart_uses_a_deterministic_postgres_barrier() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    lane = script.split("run_planning_revision_lane() {", 1)[1].split("\n}", 1)[0]
    cleanup = script.split("cleanup() {", 1)[1].split("\n}", 1)[0]

    assert "sleep 0.01" not in lane
    assert "mkfifo \"$PLANNING_REVISION_BARRIER_FIFO\"" in script
    assert "FROM app.planning_runs" in script
    assert "FOR UPDATE;" in script
    assert "$PLANNING_REVISION_BARRIER_READY:$predecessor_id" in script
    assert "pg_stat_activity" in script
    assert "wait_event_type='Lock'" in script
    assert "task.attempt_count=1" in script
    assert "task.lease_generation=1" in script
    assert "execution.attempt_no=1" in script
    assert "execution.lease_generation=1" in script
    assert "execution.status='running'" in script
    assert lane.count("docker compose unpause worker") == 1
    assert lane.index("docker compose restart worker") < lane.index(
        "release_planning_revision_barrier"
    )
    assert "PLANNING_REVISION_BARRIER_FIFO" in cleanup
    assert "PLANNING_REVISION_BARRIER_OUTPUT" in cleanup
    assert "PLANNING_REVISION_BARRIER_STATE" in cleanup
    assert "barrier_pid" in cleanup


def test_planning_revision_predecessor_selector_is_cardinality_closed() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    barrier = script.split("start_planning_revision_barrier() {", 1)[1].split(
        "\n}", 1
    )[0]
    cleanup = script.split("cleanup() {", 1)[1].split("\n}", 1)[0]

    assert "min(id)" not in barrier
    assert "max(id)" not in barrier
    assert "count(*)::text || ':'" not in barrier
    assert "SELECT selected.id::text FROM (" in barrier
    assert "SELECT predecessor.id, count(*) OVER () AS match_count" in barrier
    assert "FROM app.student_cases case_row" in barrier
    assert "JOIN app.student_case_revisions revision_row" in barrier
    assert "revision_row.organization_id=case_row.organization_id" in barrier
    assert "revision_row.case_id=case_row.id" in barrier
    assert "revision_row.revision=case_row.current_revision" in barrier
    assert "JOIN app.agent_tasks task" in barrier
    assert "task.organization_id=revision_row.organization_id" in barrier
    assert "task.case_id=revision_row.case_id" in barrier
    assert "task.case_revision=revision_row.revision" in barrier
    assert "JOIN app.planning_runs predecessor" in barrier
    assert "predecessor.organization_id=revision_row.organization_id" in barrier
    assert "predecessor.case_id=revision_row.case_id" in barrier
    assert "predecessor.id=revision_row.superseded_planning_run_id" in barrier
    assert (
        "case_row.organization_id='10000000-0000-0000-0000-000000000001'"
        in barrier
    )
    assert "case_row.id='49000000-0000-0000-0000-000000000001'" in barrier
    assert "case_row.current_revision=2" in barrier
    assert "case_row.state='planning'" in barrier
    assert "task.state='queued'" in barrier
    assert "task.attempt_count=0" in barrier
    assert "task.result_planning_run_id IS NULL" in barrier
    assert (
        "task.predecessor_planning_run_id="
        "revision_row.superseded_planning_run_id"
        in barrier
    )
    assert "predecessor.id=task.predecessor_planning_run_id" in barrier
    assert "predecessor.case_revision=revision_row.revision - 1" in barrier
    assert "NOT predecessor.is_current" in barrier
    assert "case_revision=1 AND is_current" not in barrier
    assert ") AS selected WHERE selected.match_count = 1" in barrier
    assert "PLANNING_REVISION_PREDECESSOR_STDOUT" in barrier
    assert "PLANNING_REVISION_PREDECESSOR_STDERR" in barrier
    assert 'chmod 0600 "$PLANNING_REVISION_PREDECESSOR_STDOUT"' in barrier
    assert 'grep -Eq "^[0-9a-f]{8}-' in barrier
    assert barrier.index('grep -Eq "^[0-9a-f]{8}-') < barrier.index("mkfifo")
    assert "planning revision predecessor selector failed" in barrier
    assert "planning revision predecessor selector was not one UUID" in barrier
    assert "PLANNING_REVISION_PREDECESSOR_STDOUT" in cleanup
    assert "PLANNING_REVISION_PREDECESSOR_STDERR" in cleanup


def test_planning_revision_ipc_resets_symlinks_and_prepares_only_owned_files(
    tmp_path: Path,
) -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    reset_prepare = (
        '    rm -f "$PLANNING_REVISION_PROOF_FILE" "$PLANNING_REVISION_WORKER_READY_FILE"\n'
        '    : > "$PLANNING_REVISION_PROOF_FILE"\n'
        '    : > "$PLANNING_REVISION_WORKER_READY_FILE"'
    )
    permission = (
        'chmod 0666 "$PLANNING_REVISION_PROOF_FILE" '
        '"$PLANNING_REVISION_WORKER_READY_FILE"'
    )
    assert reset_prepare in script
    assert permission in script
    assert 'chmod 0666 "$PLANNING_REVISION_REVIEW_DIR"' not in script
    assert 'grep -Fqx "$PLANNING_REVISION_INITIAL_SENTINEL"' in script
    assert 'grep -Fqx "$PLANNING_REVISION_RESTART_SENTINEL"' in script
    assert 'test -s "$PLANNING_REVISION_PROOF_FILE"' in script

    proof_target = tmp_path / "proof-target"
    ready_target = tmp_path / "ready-target"
    proof_target.write_text("preserve proof\n", encoding="utf-8")
    ready_target.write_text("preserve ready\n", encoding="utf-8")
    proof_target.chmod(0o640)
    ready_target.chmod(0o640)
    proof_file = tmp_path / "proof.json"
    ready_file = tmp_path / "worker-ready"
    proof_file.symlink_to(proof_target)
    ready_file.symlink_to(ready_target)
    environment = os.environ.copy()
    environment.update(
        PLANNING_REVISION_PROOF_FILE=str(proof_file),
        PLANNING_REVISION_WORKER_READY_FILE=str(ready_file),
    )
    subprocess.run(
        ["sh", "-eu", "-c", f"{reset_prepare}\n    {permission}"],
        check=True,
        env=environment,
    )
    assert not proof_file.is_symlink()
    assert not ready_file.is_symlink()
    assert proof_file.read_bytes() == b""
    assert ready_file.read_bytes() == b""
    assert stat.S_IMODE(proof_file.stat().st_mode) == 0o666
    assert stat.S_IMODE(ready_file.stat().st_mode) == 0o666
    assert proof_target.read_text(encoding="utf-8") == "preserve proof\n"
    assert ready_target.read_text(encoding="utf-8") == "preserve ready\n"

    for locale in ("zh-CN", "en"):
        for viewport in ("1440", "390"):
            for state in ("happy", "blocked"):
                assert f"planning-revision-{locale}-{viewport}-{state}.png" in script


def test_full_compose_proof_runs_one_minimal_plan_execution_lane() -> None:
    config = Path("web/playwright.compose.config.ts").read_text(encoding="utf-8")
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    browser_path = Path("web/e2e/plan-execution-minimal.spec.ts")

    assert browser_path.is_file()
    browser = browser_path.read_text(encoding="utf-8")
    assert config.count('"plan-execution-minimal.spec.ts"') == 1
    assert script.count("run_plan_execution_minimal_lane") == 2
    lane = script.split("run_plan_execution_minimal_lane() {", 1)[1].split(
        "\n}", 1
    )[0]
    assert "docker compose down --volumes --remove-orphans" in lane
    assert "docker compose up --no-build --wait" in lane
    assert "plan-execution-minimal.spec.ts" in lane
    assert "verify_timeline_execution.py --expect completed" in lane
    assert "governed plan execution minimal browser and database proof passed" in lane
    assert "governed-plan-execution-v1" in browser
    assert "当前行动" in browser
    assert "Start the action plan" in browser
    assert "开始执行行动计划" in browser
    assert "The action plan is complete." in browser
    assert 'getByRole("button", { name: "English"' in browser
    assert "request_update" not in browser
    for forbidden in (
        "reassess",
        "blocked",
        "EventSource",
        "worker",
        "restart",
        "reload",
        "stale",
        "lost-ack",
    ):
        assert forbidden not in lane
        assert forbidden not in browser


def test_full_compose_proof_includes_the_governed_plan_execution_suite() -> None:
    config = Path("web/playwright.compose.config.ts").read_text(encoding="utf-8")

    assert config.count('"plan-execution.spec.ts"') == 1


def test_timeline_execution_verifier_has_closed_seed_and_completed_modes() -> None:
    verifier = Path("scripts/verify_timeline_execution.py").read_text(
        encoding="utf-8"
    )

    assert 'choices=("seed", "completed")' in verifier
    assert 'default="seed"' in verifier
    assert 'if expectation == "completed":' in verifier
    assert "timeline execution seed verified" in verifier
    assert "timeline execution completed verified" in verifier
    for required in (
        "execution AS (SELECT e.* FROM app.timeline_executions e",
        "count(*)=1 FROM execution",
        "state='completed'",
        "count(*)=4 FROM app.timeline_checkpoints",
        "count(*)=4 FROM app.timeline_checkpoint_attestations",
        "a.attestation_kind<>'completion'",
        "count(*)=4 FROM app.timeline_checkpoint_verifications",
        "v.action<>'verify'",
        "count(*)=0 FROM app.timeline_reassessment_requests r",
        "operation='start'",
        "operation='attest'",
        "operation='verify'",
    ):
        assert required in verifier
