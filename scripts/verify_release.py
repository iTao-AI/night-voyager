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
POSTGRES_IMAGE = (
    "postgres:18.4-alpine@sha256:96d56f7f57c6aacd1fcb908bc83b345ec5f83231ee486dd66a1baadce274db88"
)
M3A_TABLES = {
    "student_cases", "student_case_revisions", "source_packs", "source_pack_entries",
    "evidence_refs", "planning_runs", "planning_routes", "comparison_dimensions",
    "comparison_dimension_evidence_refs", "cost_evidence", "ranking_evidence",
}
IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "node_modules",
}
BINARY_SUFFIXES = {".gif", ".ico", ".jpeg", ".jpg", ".png", ".webp"}

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
            "from night_voyager.api import create_app; assert create_app().version == '0.1.0'",
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
            } | M3A_TABLES or any(
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
            if policy_count != 14:
                raise SystemExit("every app tenant table requires one explicit policy")

            worker_writes = (
                await connection.execute(
                    text("""
                    SELECT count(*) FROM information_schema.role_table_grants
                    WHERE table_schema = 'app' AND table_name = ANY(:tables)
                      AND grantee = 'night_voyager_worker'
                      AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
                    """),
                    {"tables": sorted(M3A_TABLES)},
                )
            ).scalar_one()
            if worker_writes:
                raise SystemExit("worker must not have an M3A write grant")

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
    verify_config()
    verify_wheel()


if __name__ == "__main__":
    main()
