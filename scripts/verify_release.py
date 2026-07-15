from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
DESCRIPTION = "Evidence-grounded advisor-to-family decision workflow with durable Agent tasks"
POSTGRES_IMAGE = (
    "postgres:18.4-alpine@sha256:96d56f7f57c6aacd1fcb908bc83b345ec5f83231ee486dd66a1baadce274db88"
)
M3A_TABLES = {
    "student_cases",
    "student_case_revisions",
    "source_packs",
    "source_pack_entries",
    "evidence_refs",
    "planning_runs",
    "planning_routes",
    "comparison_dimensions",
    "comparison_dimension_evidence_refs",
    "cost_evidence",
    "ranking_evidence",
}
M3B_TABLES = {
    "student_case_participants",
    "advisor_reviews",
    "evidence_risk_acceptances",
    "decision_briefs",
    "family_decisions",
    "timeline_plans",
    "audit_events",
    "idempotency_records",
}
M4A_TABLES = {"agent_tasks", "agent_executions", "agent_task_events"}
DRA_TABLES = {"dra_research_candidates", "external_evidence_verifications"}
IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "node_modules",
}
BINARY_SUFFIXES = {".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".webp"}
M5_SCREENSHOTS = (
    "docs/assets/m5-advisor-ledger.png",
    "docs/assets/m5-family-receipt-timeline.png",
)
RELEASE_DOCUMENTS = (
    "docs/releases/v0.1.0.md",
    "docs/how-to/verify-v0.1.0-release.md",
)
RELEASE_HEADINGS = (
    "## Summary",
    "## Completion",
    "## Verification",
    "## Scope",
    "## Risk / Impact",
    "## Documentation impact",
)
RELEASE_NOTE_TOKENS = (
    "local synthetic portfolio release",
    "GitHub-generated source archive",
    "UNTRUSTED_CANDIDATE",
    "production tenancy",
    "真实学生",
    "SLA",
    "业务收益",
)
RELEASE_HOW_TO_TOKENS = (
    "git fetch origin --tags --prune",
    "git status --short --branch",
    "git rev-parse HEAD",
    "git rev-parse origin/main",
    "git describe --tags --exact-match HEAD",
    "git cat-file -t v0.1.0",
    "git rev-parse v0.1.0^{tag}",
    "git rev-parse v0.1.0^{commit}",
    'curl --fail --location --output "$archive"',
    "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.0.tar.gz",
    'wc -c "$archive"',
    'shasum -a 256 "$archive"',
    'tar -xzf "$archive" -C "$tmp_dir"',
    'cd "$tmp_dir/night-voyager-0.1.0"',
    "make doctor",
    "make proof",
    "make compose-proof",
    "make down",
    "docker compose ps --all",
    "object type `tag`",
    "Never move the tag after publication",
    "Use the extracted source archive",
    "normal pull request",
    "Do not force-move `v0.1.0`",
    "bypass the `main` ruleset",
)
DRA_SURFACE = (
    "scripts/verify_dra_consumer.py",
    "scripts/run_dra_lane.sh",
    "scripts/seed_dra_proof.py",
    "docs/decisions/0007-dra-governed-mixed-evidence-boundary.md",
    "docs/reference/dra-governed-evidence.md",
    "docs/operations/dra-consumer-proof.md",
)

os.environ.setdefault("UV_BUILD_CONSTRAINT", "build-constraints.txt")
os.environ.setdefault("UV_REQUIRE_HASHES", "1")


def run(*command: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def git_available() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def source_files() -> list[Path]:
    if git_available():
        output = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        return [ROOT / item.decode() for item in output.split(b"\0") if item]

    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in IGNORED_DIRECTORIES for part in path.parts)
    ]


def verify_tree_mode(mode: str) -> None:
    if mode == "snapshot":
        if git_available():
            raise SystemExit("snapshot proof must run from a Git-free Docker build context")
        print("proof tree: Docker snapshot context confirmed")
        return

    if not git_available():
        raise SystemExit(f"{mode} proof requires a Git checkout")
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
    )
    if mode == "release" and status:
        raise SystemExit("release proof requires a clean Git tree")
    state = "clean" if not status else "development tree with pending changes"
    print(f"proof tree: {state} ({mode} mode)")


def verify_public_hygiene() -> None:
    forbidden = (
        "/" + "Users/",
        "." + "sessions/",
        "." + "gstack/",
        "Developer/" + "Career",
        "BEGIN " + "PRIVATE KEY",
    )
    credential = re.compile(r"(?i)(api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]+['\"]")
    scanned: list[str] = []
    violations: list[str] = []
    for path in source_files():
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        relative = str(path.relative_to(ROOT))
        scanned.append(relative)
        if any(value in text for value in forbidden) or credential.search(text):
            violations.append(relative)
    if violations:
        raise SystemExit(f"public-hygiene violations: {', '.join(violations)}")
    if "uv.lock" not in scanned or "web/package-lock.json" not in scanned:
        raise SystemExit("public-hygiene must scan both lockfiles")
    print(f"proof hygiene: {len(scanned)} readable source files scanned, including both lockfiles")


def verify_m5_public_evidence() -> None:
    public_entries = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("README.md", "README_CN.md")
    }
    for relative in M5_SCREENSHOTS:
        if not (ROOT / relative).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise SystemExit(f"missing or invalid M5 screenshot: {relative}")
        if any(source.count(relative) != 1 for source in public_entries.values()):
            raise SystemExit(f"each README must reference the M5 screenshot once: {relative}")
    print("proof M5 evidence: connected runbook and two PNG screenshots present")


def verify_dra_surface() -> None:
    if any(not (ROOT / relative).is_file() for relative in DRA_SURFACE):
        raise SystemExit("governed DRA proof surface incomplete")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    reference = (ROOT / "docs/reference/dra-governed-evidence.md").read_text(
        encoding="utf-8"
    )
    if (
        "dra-check:" not in makefile
        or "dra-consumer-proof:" not in makefile
        or "make dra-check" not in workflow
        or "dra-consumer-proof" in workflow
        or "governed mixed PlanningRun is not implemented" not in reference
    ):
        raise SystemExit("governed DRA command or status contract drift")
    print("proof DRA surface: offline candidate and atomic promotion lane confirmed")


def verify_release_surface() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject["project"]["description"] != DESCRIPTION:
        raise SystemExit("v0.1.0 project description drift")

    readme_contracts = (
        (
            "README.md",
            "Night Voyager turns a synthetic study-abroad comparison",
            "## Engineering proof",
            "## Evaluate the release",
            "## Synthetic and local limits",
            "## Milestones and history",
        ),
        (
            "README_CN.md",
            "Night Voyager 将一组三国留学比较",
            "## 工程证据",
            "## 验证 release",
            "## 合成与本地边界",
            "## Milestone 与历史",
        ),
    )
    for relative, outcome, proof, evaluator, limits, history in readme_contracts:
        source = (ROOT / relative).read_text(encoding="utf-8")
        required = (outcome, *M5_SCREENSHOTS, proof, evaluator, limits, history)
        try:
            positions = [source.index(value) for value in required]
        except ValueError as error:
            raise SystemExit(f"missing v0.1.0 README contract: {relative}") from error
        if positions != sorted(positions):
            raise SystemExit(f"v0.1.0 README outcome order drift: {relative}")
        if any(document not in source for document in RELEASE_DOCUMENTS):
            raise SystemExit(f"v0.1.0 README release links drift: {relative}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README_CN.md").read_text(encoding="utf-8")

    for relative in RELEASE_DOCUMENTS:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"missing v0.1.0 release document: {relative}")
    release = (ROOT / RELEASE_DOCUMENTS[0]).read_text(encoding="utf-8")
    try:
        heading_positions = [release.index(heading) for heading in RELEASE_HEADINGS]
    except ValueError as error:
        raise SystemExit("release notes contract missing required heading") from error
    if heading_positions != sorted(heading_positions):
        raise SystemExit("release notes contract heading order drift")
    for index, position in enumerate(heading_positions):
        end = (
            heading_positions[index + 1]
            if index + 1 < len(heading_positions)
            else len(release)
        )
        if re.search(r"[\u4e00-\u9fff]", release[position:end]) is None:
            raise SystemExit("release notes contract requires Simplified Chinese body")
    if any(token not in release for token in RELEASE_NOTE_TOKENS):
        raise SystemExit("release notes contract boundary drift")

    how_to = (ROOT / RELEASE_DOCUMENTS[1]).read_text(encoding="utf-8")
    if any(token not in how_to for token in RELEASE_HOW_TO_TOKENS):
        raise SystemExit("release how-to contract boundary drift")

    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    if any(
        "release/source-archive verification" not in source
        for source in (readme, readme_cn)
    ):
        raise SystemExit("README release/source-archive verification wording drift")
    if "source-archive verification" not in docs_index:
        raise SystemExit("documentation index source-archive verification wording drift")

    stale = ("bootstrap stage", "local bootstrap phase", "no released production version")
    for relative in ("SECURITY.md", "CONTRIBUTING.md", "docs/README.md"):
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        if any(phrase in source for phrase in stale):
            raise SystemExit(f"stale bootstrap release wording: {relative}")
    print("proof release surface: v0.1.0 local synthetic portfolio contract confirmed")


def package_version(packages: list[dict[str, object]], name: str) -> str:
    for package in packages:
        if package.get("name") == name:
            version = package.get("version")
            if isinstance(version, str):
                return version
    raise SystemExit(f"missing locked package: {name}")


def verify_config() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    web_package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    npm_lock = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    constraint = (ROOT / "build-constraints.txt").read_text(encoding="utf-8").strip()

    versions = {
        "pyproject": pyproject["project"]["version"],
        "uv.lock": package_version(uv_lock["package"], "night-voyager"),
        "web/package.json": web_package["version"],
        "web/package-lock.json": npm_lock["packages"][""]["version"],
    }
    if set(versions.values()) != {VERSION}:
        raise SystemExit(f"identity version mismatch: {versions}")
    runtime_dependencies = pyproject["project"]["dependencies"]
    optional_dependencies = pyproject["project"].get("optional-dependencies", {})
    if optional_dependencies.get("dra") != ["httpx2>=2.5,<2.6"]:
        raise SystemExit("DRA must remain an exact optional dependency range")
    if package_version(uv_lock["package"], "httpx2") != "2.5.0":
        raise SystemExit("httpx2 optional lock must remain at the reviewed 2.5.0 version")
    if optional_dependencies.get("mke") != ["mcp>=1.28.1,<2"]:
        raise SystemExit("MKE must remain an exact optional dependency range")
    if package_version(uv_lock["package"], "mcp") != "1.28.1":
        raise SystemExit("MCP optional lock must remain at the reviewed 1.28.1 version")
    if "fastapi>=0.139,<0.140" not in runtime_dependencies:
        raise SystemExit("FastAPI runtime dependency must remain on approved 0.139.x")
    if "starlette>=1.3.1,<1.4" not in runtime_dependencies:
        raise SystemExit(
            "Starlette runtime dependency must enforce the approved 1.3.1 security floor"
        )
    if package_version(uv_lock["package"], "fastapi").split(".")[:2] != ["0", "139"]:
        raise SystemExit("FastAPI lock must remain on approved 0.139.x")
    locked_starlette = tuple(
        int(part) for part in package_version(uv_lock["package"], "starlette").split(".")
    )
    if not (locked_starlette >= (1, 3, 1) and locked_starlette < (1, 4)):
        raise SystemExit("Starlette lock must remain within the approved >=1.3.1,<1.4 range")
    if pyproject["build-system"]["requires"] != ["hatchling==1.31.0"]:
        raise SystemExit("build backend must be exactly pinned")
    if not constraint.startswith("hatchling==1.31.0 --hash=sha256:"):
        raise SystemExit("build backend constraint must include a SHA-256 hash")
    if constraint.count("--hash=sha256:") != 5:
        raise SystemExit("all build backend dependencies must be hash constrained")
    if POSTGRES_IMAGE not in compose:
        raise SystemExit("Compose PostgreSQL image must use the approved exact tag and digest")
    if re.search(r"(?m)^\s{2}mke:\s*$", compose):
        raise SystemExit("MKE must not become a Compose service")
    post_m4a = list((ROOT / "migrations" / "versions").glob("0005_*.py"))
    if [path.name for path in post_m4a] != ["0005_dra_candidate_promotion.py"]:
        raise SystemExit("post-M4A migration surface must be the governed DRA boundary")
    if "mke" in post_m4a[0].read_text(encoding="utf-8").lower():
        raise SystemExit("M4B must not add a database migration")
    for required in (
        ROOT / "fixtures/m4b/candidate-artifact-lock.json",
        ROOT / "fixtures/m4b/manifest.json",
    ):
        if not required.is_file():
            raise SystemExit(f"missing M4B public contract: {required.name}")
    for pure_file in (ROOT / "src/night_voyager/evidence").glob("*.py"):
        pure_content = pure_file.read_text(encoding="utf-8")
        if "import mcp" in pure_content or "from mcp" in pure_content:
            raise SystemExit("pure M4B boundary must not import the optional MCP SDK")
    local_bindings = (
        '"127.0.0.1:${POSTGRES_PORT:-55432}:5432"',
        '"127.0.0.1:${API_PORT:-8000}:8000"',
        '"127.0.0.1:${WEB_PORT:-3000}:3000"',
    )
    if not all(binding in compose for binding in local_bindings):
        raise SystemExit("Compose host ports must bind to IPv4 loopback")
    if (ROOT / ".python-version").read_text(encoding="utf-8").strip() != "3.12.13":
        raise SystemExit("Python patch version drift")
    if (ROOT / ".node-version").read_text(encoding="utf-8").strip() != "24.18.0":
        raise SystemExit("Node.js patch version drift")
    print(f"proof identity: Night Voyager package surfaces agree on version {VERSION}")
    print(
        "proof dependencies: FastAPI 0.139.x, Starlette >=1.3.1,<1.4, "
        "and hashed Hatchling 1.31.0 constraints confirmed"
    )
    print(f"proof compose: exact PostgreSQL reference confirmed ({POSTGRES_IMAGE})")
    print("proof config: Python/Node pins and IPv4-loopback host bindings confirmed")


def verify_wheel() -> None:
    run(
        "uv",
        "build",
        "--wheel",
        "--build-constraints",
        "build-constraints.txt",
        "--require-hashes",
    )
    wheel = max((ROOT / "dist").glob("*.whl"), key=lambda path: path.stat().st_mtime)
    with tempfile.TemporaryDirectory(prefix="night-voyager-wheel-") as temp:
        venv = str(Path(temp) / ".venv")
        run("uv", "venv", venv, "--python", "3.12.13")
        python = f"{venv}/bin/python"
        wheel_install_environment = os.environ.copy()
        wheel_install_environment.pop("UV_REQUIRE_HASHES", None)
        run(
            "uv",
            "pip",
            "install",
            "--python",
            python,
            str(wheel),
            env=wheel_install_environment,
        )
        run(
            python,
            "-c",
            "import sys; from night_voyager.api import create_app; "
            "assert create_app().version == '0.1.0'; assert \"httpx2\" not in sys.modules",
        )
    print(f"proof wheel: isolated installed-wheel import and app factory passed ({wheel.name})")


async def verify_database_catalog(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            roles = (
                (
                    await connection.execute(
                        text(
                            """
            SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolbypassrls
            FROM pg_roles
            WHERE rolname IN (
              'night_voyager_migrator', 'night_voyager_api', 'night_voyager_worker'
            )
            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            if len(roles) != 3 or any(
                row["rolsuper"]
                or row["rolcreatedb"]
                or row["rolcreaterole"]
                or row["rolinherit"]
                or row["rolbypassrls"]
                for row in roles
            ):
                raise SystemExit("database roles violate least-privilege attributes")

            tenant_tables = (
                (
                    await connection.execute(
                        text(
                            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, r.rolname AS owner
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            JOIN pg_roles AS r ON r.oid = c.relowner
            WHERE n.nspname = 'app' AND c.relkind = 'r'
            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            if {row["relname"] for row in tenant_tables} != {
                "organizations",
                "actors",
                "memberships",
            } | M3A_TABLES | M3B_TABLES | M4A_TABLES | DRA_TABLES or any(
                not row["relrowsecurity"]
                or not row["relforcerowsecurity"]
                or row["owner"] != "night_voyager_migrator"
                for row in tenant_tables
            ):
                raise SystemExit("app tenant tables must be migrator-owned with forced RLS")

            policy_count = (
                await connection.execute(
                    text("SELECT count(*) FROM pg_policies WHERE schemaname = 'app'")
                )
            ).scalar_one()
            if policy_count != 27:
                raise SystemExit("every app tenant table requires one explicit policy")

            runtime_writes = (
                await connection.execute(
                    text("""
                    SELECT count(*) FROM information_schema.role_table_grants
                    WHERE table_schema = 'app' AND table_name = ANY(:tables)
                      AND grantee IN ('night_voyager_api','night_voyager_worker')
                      AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
                    """),
                    {"tables": sorted(M3A_TABLES | M3B_TABLES | M4A_TABLES | DRA_TABLES)},
                )
            ).scalar_one()
            if runtime_writes:
                raise SystemExit("runtime roles must not have direct M3A write grants")

            app_functions = (
                (
                    await connection.execute(
                        text("""
                        SELECT p.proname,p.prosecdef,p.proconfig,
                          oidvectortypes(p.proargtypes) AS identity_arguments,
                          has_function_privilege('public',p.oid,'EXECUTE') AS public_execute,
                          has_function_privilege(
                            'night_voyager_api',p.oid,'EXECUTE'
                          ) AS api_execute,
                          has_function_privilege(
                            'night_voyager_worker',p.oid,'EXECUTE'
                          ) AS worker_execute
                        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                        WHERE n.nspname='app' AND (p.proname IN
                          ('publish_case_revision','transition_case','persist_source_pack',
                           'persist_evidence_ref','persist_planning_result','review_planning_run',
                           'decide_family_brief','create_agent_task','cancel_agent_task',
                           'claim_agent_task','start_agent_task','heartbeat_agent_task',
                           'fail_agent_task','finalize_agent_task_result')
                           OR p.proname IN
                          ('import_dra_research_candidate','verify_and_promote_dra_candidate'))
                        """)
                    )
                )
                .mappings()
                .all()
            )
            if {row["proname"] for row in app_functions} != {
                "publish_case_revision",
                "transition_case",
                "persist_source_pack",
                "persist_evidence_ref",
                "persist_planning_result",
                "review_planning_run",
                "decide_family_brief",
                "create_agent_task",
                "cancel_agent_task",
                "claim_agent_task",
                "start_agent_task",
                "heartbeat_agent_task",
                "fail_agent_task",
                "finalize_agent_task_result",
                "import_dra_research_candidate",
                "verify_and_promote_dra_candidate",
            } or any(
                not row["prosecdef"]
                or row["proconfig"] != ["search_path=pg_catalog, pg_temp"]
                or row["public_execute"]
                for row in app_functions
            ):
                raise SystemExit("app functions violate narrow SECURITY DEFINER contract")
            api_functions = {
                "publish_case_revision",
                "transition_case",
                "persist_source_pack",
                "persist_evidence_ref",
                "persist_planning_result",
                "review_planning_run",
                "decide_family_brief",
                "create_agent_task",
                "cancel_agent_task",
                "import_dra_research_candidate",
                "verify_and_promote_dra_candidate",
            }
            worker_functions = {
                "claim_agent_task",
                "start_agent_task",
                "heartbeat_agent_task",
                "fail_agent_task",
                "finalize_agent_task_result",
            }
            worker_signatures = {
                row["proname"]: row["identity_arguments"]
                for row in app_functions
                if row["proname"] in worker_functions
            }
            if worker_signatures["start_agent_task"] != "uuid, uuid, text, bigint, text":
                raise SystemExit("start_agent_task audit signature drift")
            if worker_signatures["fail_agent_task"] != (
                "uuid, uuid, text, bigint, text, boolean, boolean"
            ):
                raise SystemExit("fail_agent_task audit signature drift")
            if any(
                (row["proname"] in api_functions) != row["api_execute"]
                or (row["proname"] in worker_functions) != row["worker_execute"]
                for row in app_functions
            ):
                raise SystemExit("app function grants violate API/worker separation")

            internal_columns = (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='internal' AND table_name='agent_task_dispatch' "
                        "ORDER BY ordinal_position"
                    )
                )
            ).scalars().all()
            if internal_columns != ["task_id", "organization_id", "available_at"]:
                raise SystemExit("internal dispatch column allowlist drift")
            internal_ownership = (
                await connection.execute(
                    text(
                        "SELECT pg_get_userbyid(c.relowner) AS table_owner, "
                        "pg_get_userbyid(n.nspowner) AS schema_owner "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='internal' AND c.relname='agent_task_dispatch'"
                    )
                )
            ).mappings().one()
            if dict(internal_ownership) != {
                "table_owner": "night_voyager_migrator",
                "schema_owner": "night_voyager_migrator",
            }:
                raise SystemExit("internal dispatch ownership drift")
            internal_grants = (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.role_table_grants "
                        "WHERE table_schema='internal' AND table_name='agent_task_dispatch' "
                        "AND grantee IN ('PUBLIC','night_voyager_api','night_voyager_worker')"
                    )
                )
            ).scalar_one()
            if internal_grants:
                raise SystemExit("runtime roles must not access internal dispatch storage")
            internal_schema_access = (
                await connection.execute(
                    text(
                        "SELECT has_schema_privilege('night_voyager_api','internal','USAGE') "
                        "OR has_schema_privilege('night_voyager_worker','internal','USAGE')"
                    )
                )
            ).scalar_one()
            if internal_schema_access:
                raise SystemExit("runtime roles must not use the internal schema")

            auth_grants = (
                await connection.execute(
                    text(
                        """
            SELECT count(*) FROM information_schema.role_table_grants
            WHERE table_schema = 'auth'
              AND grantee IN ('night_voyager_api', 'night_voyager_worker')
            """
                    )
                )
            ).scalar_one()
            if auth_grants:
                raise SystemExit("runtime roles must not have direct auth table grants")

            functions = (
                (
                    await connection.execute(
                        text(
                            """
            SELECT p.oid, p.proname, p.prosecdef, p.proconfig,
                   has_function_privilege('public', p.oid, 'EXECUTE') AS public_execute,
                   has_function_privilege('night_voyager_api', p.oid, 'EXECUTE') AS api_execute,
                   has_function_privilege(
                       'night_voyager_worker', p.oid, 'EXECUTE'
                   ) AS worker_execute
            FROM pg_proc AS p
            JOIN pg_namespace AS n ON n.oid = p.pronamespace
            WHERE n.nspname = 'auth'
            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            expected = {
                "mint_demo_session",
                "resolve_demo_session",
                "rotate_demo_session",
                "revoke_demo_session",
                "resolve_demo_session_with_csrf",
            }
            if {row["proname"] for row in functions} != expected or any(
                not row["prosecdef"]
                or row["proconfig"] != ["search_path=pg_catalog, pg_temp"]
                or row["public_execute"]
                or not row["api_execute"]
                or row["worker_execute"]
                for row in functions
            ):
                raise SystemExit("auth functions violate SECURITY DEFINER privilege contract")
    finally:
        await engine.dispose()
    print("proof database: role, forced-RLS, policy, auth grant, and function catalog passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tree-mode", choices=("development", "release", "snapshot"), default="development"
    )
    parser.add_argument("--check-db-roles", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.check_db_roles:
        database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
        if not database_url:
            raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
        asyncio.run(verify_database_catalog(database_url))
        return
    verify_tree_mode(args.tree_mode)
    verify_public_hygiene()
    verify_m5_public_evidence()
    verify_dra_surface()
    verify_release_surface()
    verify_config()
    verify_wheel()


if __name__ == "__main__":
    main()
