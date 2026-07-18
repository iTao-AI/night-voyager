from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _locked_version(packages: list[dict[str, object]], name: str) -> tuple[int, ...]:
    for package in packages:
        if package.get("name") == name:
            version = package.get("version")
            assert isinstance(version, str)
            return tuple(int(part) for part in version.split("."))
    raise AssertionError(f"missing locked package: {name}")


def test_fastapi_and_starlette_stay_on_approved_security_lines() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    runtime_dependencies = pyproject["project"]["dependencies"]
    dev_dependencies = pyproject["dependency-groups"]["dev"]

    fastapi_dependencies = [
        dependency for dependency in runtime_dependencies if dependency.startswith("fastapi")
    ]
    assert fastapi_dependencies == ["fastapi>=0.139,<0.140"]
    assert "starlette>=1.3.1,<1.4" in runtime_dependencies
    assert "httpx2>=2,<3" in dev_dependencies
    assert not any(dependency.startswith("httpx>=") for dependency in dev_dependencies)

    locked_fastapi = _locked_version(uv_lock["package"], "fastapi")
    locked_starlette = _locked_version(uv_lock["package"], "starlette")
    assert (0, 139, 2) <= locked_fastapi < (0, 140)
    assert (1, 3, 1) <= locked_starlette < (1, 4)
