from __future__ import annotations

import inspect
import json
from pathlib import Path

from night_voyager.skills.models import SkillBindingKind, SkillRuntimeManifestV1
from night_voyager.skills.registry import SkillRuntimeRegistry

RUNTIME_MANIFEST = Path("fixtures/skills/runtime-manifest-v1.json")


def test_checked_in_manifest_has_exact_runtime_and_catalog_boundaries() -> None:
    payload = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    manifest = SkillRuntimeManifestV1.model_validate_json(json.dumps(payload))
    runtime = [
        entry
        for entry in manifest.entries
        if entry.binding_kind is SkillBindingKind.PLANNING_RUNTIME
    ]
    catalog = [
        entry for entry in manifest.entries if entry.binding_kind is SkillBindingKind.CATALOG_ONLY
    ]
    assert len(runtime) == 2
    assert len(catalog) == 5
    assert {entry.version for entry in runtime} == {"1.0.0", "1.0.1"}
    assert all(entry.skill_key.value == "study-destination-compare" for entry in runtime)
    assert all(entry.executor_id is None for entry in catalog)
    assert all(entry.executor_version is None for entry in catalog)
    assert all(entry.operation_bindings is None for entry in catalog)
    assert all(entry.runtime_binding_sha256 is None for entry in catalog)


def test_registry_production_loader_uses_only_importlib_resources() -> None:
    module = inspect.getmodule(SkillRuntimeRegistry)
    assert module is not None
    source = inspect.getsource(module)
    loader = inspect.getsource(SkillRuntimeRegistry.load_packaged)
    assert "from importlib import resources" in source
    assert 'resources.files("night_voyager.skills")' in loader
    assert 'package.joinpath("data", "runtime-manifest-v1.json")' in loader
    assert "from pathlib" not in source
    assert "fixtures/skills" not in source
    assert "cwd" not in loader.lower()


def test_source_tree_does_not_duplicate_packaged_manifest() -> None:
    assert not Path("src/night_voyager/skills/data/runtime-manifest-v1.json").exists()
