from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEXT_VERSION = "16.2.11"
REACT_VERSION = "19.2.7"


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


def test_next_family_stays_on_approved_security_patch() -> None:
    package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads(
        (ROOT / "web/package-lock.json").read_text(encoding="utf-8")
    )

    assert package["dependencies"]["next"] == NEXT_VERSION
    assert package["dependencies"]["react"] == REACT_VERSION
    assert package["dependencies"]["react-dom"] == REACT_VERSION
    assert package["devDependencies"]["eslint-config-next"] == NEXT_VERSION

    locked_packages = package_lock["packages"]
    locked_root = locked_packages[""]
    for name in ("next", "react", "react-dom"):
        assert locked_root["dependencies"][name] == package["dependencies"][name]
    assert locked_root["devDependencies"]["eslint-config-next"] == NEXT_VERSION
    assert locked_packages["node_modules/next"]["version"] == NEXT_VERSION
    assert locked_packages["node_modules/eslint-config-next"]["version"] == NEXT_VERSION

    next_family = {
        path: locked["version"]
        for path, locked in locked_packages.items()
        if path.startswith("node_modules/@next/")
    }
    assert next_family
    assert set(next_family.values()) == {NEXT_VERSION}
