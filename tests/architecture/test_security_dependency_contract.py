from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NEXT_VERSION = "16.4.1"
POSTCSS_VERSION = "8.5.23"
NANOID_MINIMUM_VERSION = (3, 3, 18)
REACT_VERSION = "19.2.8"
PROJECT_VERSION = "0.1.6"
SHARP_MINIMUM_VERSION = (0, 35, 5)


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
    assert "httpx2>=2.12,<2.13" in dev_dependencies
    assert not any(dependency.startswith("httpx>=") for dependency in dev_dependencies)

    locked_fastapi = _locked_version(uv_lock["package"], "fastapi")
    locked_starlette = _locked_version(uv_lock["package"], "starlette")
    locked_httpx2 = _locked_version(uv_lock["package"], "httpx2")
    locked_httpcore2 = _locked_version(uv_lock["package"], "httpcore2")
    assert (0, 139, 2) <= locked_fastapi < (0, 140)
    assert (1, 3, 1) <= locked_starlette < (1, 4)
    assert locked_httpx2 == (2, 12, 0)
    assert locked_httpcore2 >= (2, 10, 0)


def test_next_family_stays_on_approved_security_patch() -> None:
    package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads(
        (ROOT / "web/package-lock.json").read_text(encoding="utf-8")
    )

    assert package["version"] == PROJECT_VERSION
    assert package["dependencies"]["next"] == NEXT_VERSION
    assert package["dependencies"]["react"] == REACT_VERSION
    assert package["dependencies"]["react-dom"] == REACT_VERSION
    assert package["devDependencies"]["eslint-config-next"] == NEXT_VERSION
    for dependency in ("postcss", "nanoid", "sharp"):
        assert dependency not in package["dependencies"]
        assert dependency not in package["devDependencies"]
    assert "overrides" not in package

    locked_packages = package_lock["packages"]
    locked_root = locked_packages[""]
    assert locked_root["version"] == PROJECT_VERSION
    for name in ("next", "react", "react-dom"):
        assert locked_root["dependencies"][name] == package["dependencies"][name]
    assert locked_root["devDependencies"]["eslint-config-next"] == NEXT_VERSION
    assert locked_packages["node_modules/next"]["version"] == NEXT_VERSION
    assert locked_packages["node_modules/eslint-config-next"]["version"] == NEXT_VERSION
    assert locked_packages["node_modules/postcss"]["version"] == POSTCSS_VERSION
    nanoid_version = tuple(
        int(part) for part in locked_packages["node_modules/nanoid"]["version"].split(".")
    )
    assert NANOID_MINIMUM_VERSION <= nanoid_version < (3, 4)
    assert "overrides" not in locked_root

    next_family = {
        path: locked["version"]
        for path, locked in locked_packages.items()
        if path.startswith("node_modules/@next/")
    }
    assert next_family
    assert set(next_family.values()) == {NEXT_VERSION}

    locked_next = locked_packages["node_modules/next"]
    assert locked_next["optionalDependencies"]["sharp"] == "^0.35.5"
    locked_sharp = locked_packages["node_modules/sharp"]
    sharp_version = tuple(
        int(part) for part in locked_sharp["version"].split(".")
    )
    assert sharp_version >= SHARP_MINIMUM_VERSION
    assert locked_sharp["optional"] is True


@pytest.mark.parametrize(
    ("nanoid_version", "accepted"),
    [("3.3.20", True), ("3.3.17", False), ("3.4.0", False), ("4.0.0", False)],
)
def test_next_security_contract_checks_nanoid_patch_compatibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    nanoid_version: str,
    accepted: bool,
) -> None:
    manifest = (ROOT / "web/package.json").read_text(encoding="utf-8")
    lock = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
    lock["packages"]["node_modules/nanoid"]["version"] = nanoid_version
    (tmp_path / "web").mkdir()
    (tmp_path / "web/package.json").write_text(manifest, encoding="utf-8")
    (tmp_path / "web/package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setitem(globals(), "ROOT", tmp_path)

    if accepted:
        test_next_family_stays_on_approved_security_patch()
    else:
        with pytest.raises(AssertionError):
            test_next_family_stays_on_approved_security_patch()


def test_locked_web_dependencies_meet_open_security_advisories() -> None:
    web_lock = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
    minimum_versions = {
        "baseline-browser-mapping": (2, 11, 0),
        "browserslist": (4, 28, 7),
        "js-yaml": (4, 3, 2),
        "sharp": SHARP_MINIMUM_VERSION,
        "source-map-js": (1, 2, 2),
        "vite": (8, 1, 6),
        "@vitest/mocker": (4, 1, 12),
        "zod": (4, 6, 6),
    }
    locked_packages = web_lock["packages"]
    for name, minimum in minimum_versions.items():
        version = locked_packages[f"node_modules/{name}"]["version"]
        assert tuple(int(part) for part in version.split(".")) >= minimum, name


def test_vitest_family_stays_on_the_patched_compatible_line() -> None:
    package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
    packages = lock["packages"]

    assert package["devDependencies"]["vitest"] == "4.1.12"
    assert packages[""]["devDependencies"]["vitest"] == "4.1.12"
    assert packages["node_modules/vitest"]["version"] == "4.1.12"
    family = {
        item["version"]
        for path, item in packages.items()
        if path.startswith("node_modules/@vitest/")
    }
    assert family == {"4.1.12"}
