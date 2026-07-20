from __future__ import annotations

import json
import tomllib
from pathlib import Path

from fastapi import FastAPI

from night_voyager.api import create_app

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.2"
POSTGRES_IMAGE = (
    "postgres:18.4-alpine3.24@sha256:9a8afca54e7861fd90fab5fdf4c42477a6b1cb7d293595148e674e0a3181de15"
)


def test_canonical_versions_are_consistent() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    web_package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    app: FastAPI = create_app()

    assert pyproject["project"]["version"] == VERSION
    assert web_package["version"] == VERSION
    assert app.version == VERSION


def test_evaluator_and_contributor_make_contracts_are_separate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    doctor_target = makefile.split("doctor: ##", 1)[1].split("\n\n", 1)[0]
    proof_target = makefile.split("proof: ##", 1)[1].split("\n\n", 1)[0]
    assert "scripts/doctor.sh" in doctor_target
    assert "docker build" in proof_target
    assert 'test "$(MODE)"' not in doctor_target
    doctor_script = (ROOT / "scripts/doctor.sh").read_text(encoding="utf-8")
    assert 'if [ "$mode" = "dev" ]' in doctor_script
    assert "uv python find" in doctor_script
    assert "observed_node=$(node --version)" in doctor_script


def test_compose_uses_local_bindings_and_exact_postgres_image() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert POSTGRES_IMAGE in compose
    assert '"127.0.0.1:${POSTGRES_PORT:-55432}:5432"' in compose
    assert '"127.0.0.1:${API_PORT:-8000}:8000"' in compose
    assert '"127.0.0.1:${WEB_PORT:-3000}:3000"' in compose


def test_ci_compose_lane_runs_health_proof_and_always_tears_down() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "make compose-proof" in workflow
    assert "if: always()" in workflow
    assert "make down" in workflow
    assert "scripts/verify_release.py --tree-mode release" in workflow
    compose_proof = (ROOT / "scripts/verify_compose.sh").read_text(encoding="utf-8")
    assert "COMPOSE_PROJECT_NAME" in compose_proof
    assert "down --volumes" in compose_proof
    for evidence in (
        "State.Health.Status",
        "State.Status",
        "State.ExitCode",
        "API probe",
        "Web probe",
    ):
        assert evidence in compose_proof


def test_docker_proof_and_hygiene_cover_release_contracts() -> None:
    dockerfile = (ROOT / "Dockerfile.proof").read_text(encoding="utf-8")
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")

    assert "--tree-mode snapshot" in dockerfile
    assert 'if "uv.lock" not in scanned' in verifier
    assert "path.suffix.lower() in BINARY_SUFFIXES" in verifier
    assert '".lock"' not in verifier


def test_build_backend_is_exactly_pinned() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["build-system"]["requires"] == ["hatchling==1.31.0"]
    constraints = (ROOT / "build-constraints.txt").read_text(encoding="utf-8")
    assert constraints.startswith("hatchling==1.31.0 --hash=")
    assert constraints.count("--hash=sha256:") == 5
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    assert (
        "uv build --wheel --build-constraints build-constraints.txt --require-hashes" in dockerfile
    )


def test_every_uv_build_path_enforces_hashed_constraints() -> None:
    surfaces = {
        "Makefile": (ROOT / "Makefile").read_text(encoding="utf-8"),
        "Dockerfile.proof": (ROOT / "Dockerfile.proof").read_text(encoding="utf-8"),
        "Dockerfile.api": (ROOT / "Dockerfile.api").read_text(encoding="utf-8"),
        "ci.yml": (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        "verify_release.py": (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8"),
    }

    for name, content in surfaces.items():
        assert "UV_BUILD_CONSTRAINT" in content, name
    for name in ("Makefile", "Dockerfile.proof", "ci.yml"):
        assert "UV_REQUIRE_HASHES" in surfaces[name], name
    for name in ("Makefile", "Dockerfile.api", "ci.yml", "verify_release.py"):
        assert "--require-hashes" in surfaces[name], name
    assert (
        'wheel_install_environment.pop("UV_REQUIRE_HASHES", None)' in surfaces["verify_release.py"]
    )


def test_dependabot_covers_approved_ecosystems() -> None:
    config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")

    for ecosystem in ("uv", "npm", "github-actions", "docker", "docker-compose"):
        assert f"package-ecosystem: {ecosystem}" in config


def _dependabot_block(config: str, ecosystem: str) -> str:
    marker = f"  - package-ecosystem: {ecosystem}\n"
    block = config.split(marker, 1)[1]
    return block.split("  - package-ecosystem:", 1)[0]


def test_dependabot_groups_only_routine_patch_updates() -> None:
    config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")

    for ecosystem in ("uv", "npm", "github-actions", "docker", "docker-compose"):
        assert "    schedule:\n      interval: weekly\n" in _dependabot_block(
            config, ecosystem
        )

    for ecosystem in ("uv", "npm"):
        block = _dependabot_block(config, ecosystem)
        assert "    versioning-strategy: increase-if-necessary\n" in block
        assert "    open-pull-requests-limit: 1\n" in block
        assert '        patterns: ["*"]\n' in block
        assert '        update-types: ["patch"]\n' in block

    actions = _dependabot_block(config, "github-actions")
    assert "    open-pull-requests-limit: 1\n" in actions
    assert '        patterns: ["*"]\n' in actions
    assert '        update-types: ["patch"]\n' in actions


def test_dependabot_suppresses_routine_major_and_minor_updates() -> None:
    config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    ignored_routine_lines = (
        '      - dependency-name: "*"\n'
        "        update-types:\n"
        "          - version-update:semver-major\n"
        "          - version-update:semver-minor\n"
    )

    for ecosystem in ("uv", "npm", "github-actions"):
        assert ignored_routine_lines in _dependabot_block(config, ecosystem)


def test_dependabot_fails_closed_for_coordinated_patch_surfaces() -> None:
    config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    uv_updates = _dependabot_block(config, "uv")
    npm_updates = _dependabot_block(config, "npm")
    patch_ignore = (
        "        update-types:\n"
        "          - version-update:semver-patch\n"
    )

    for dependency in ("httpx2", "mcp"):
        assert f"      - dependency-name: {dependency}\n{patch_ignore}" in uv_updates
    assert f"      - dependency-name: \"@playwright/test\"\n{patch_ignore}" in npm_updates


def test_dependabot_disables_docker_version_updates_without_disabling_security_updates() -> None:
    config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")

    for ecosystem in ("docker", "docker-compose"):
        block = _dependabot_block(config, ecosystem)
        assert "    open-pull-requests-limit: 0\n" in block
        assert "    ignore:\n" not in block

    assert "applies-to: security-updates" not in config
    assert "cooldown:" not in config
