from __future__ import annotations

from importlib import resources

from night_voyager.skills.models import (
    SkillBindingKind,
    SkillKey,
    SkillLeafBindingV1,
    SkillRuntimeManifestEntryV1,
    SkillRuntimeManifestV1,
    SkillRuntimePin,
)


class SkillRuntimeIncompatibility(ValueError):
    """A persisted Skill identity is incompatible with checked-in runtime code."""


class SkillRuntimeRegistry:
    def __init__(self, manifest: SkillRuntimeManifestV1) -> None:
        self.manifest = manifest
        self.entries = manifest.entries
        self._entries = {
            (entry.skill_key, entry.version): entry for entry in manifest.entries
        }

    @classmethod
    def from_json(cls, payload: bytes | str) -> SkillRuntimeRegistry:
        return cls(SkillRuntimeManifestV1.model_validate_json(payload))

    @classmethod
    def load_packaged(cls) -> SkillRuntimeRegistry:
        package = resources.files("night_voyager.skills")
        resource = package.joinpath("data", "runtime-manifest-v1.json")
        return cls.from_json(resource.read_bytes())

    def get(
        self,
        skill_key: SkillKey | str,
        semantic_version: str,
    ) -> SkillRuntimeManifestEntryV1:
        try:
            key = SkillKey(skill_key)
            return self._entries[(key, semantic_version)]
        except (KeyError, ValueError) as error:
            raise SkillRuntimeIncompatibility(
                "unsupported Skill key/version"
            ) from error

    def supported_planning_bindings(self) -> tuple[SkillRuntimeManifestEntryV1, ...]:
        return tuple(
            entry
            for entry in self.entries
            if entry.binding_kind is SkillBindingKind.PLANNING_RUNTIME
        )

    def validate_pin(
        self,
        pin: SkillRuntimePin,
        skill_key: SkillKey | str,
        semantic_version: str,
        operation: str,
        actual_leaf: SkillLeafBindingV1,
    ) -> SkillRuntimeManifestEntryV1:
        entry = self.get(skill_key, semantic_version)
        if entry.binding_kind is not SkillBindingKind.PLANNING_RUNTIME:
            raise SkillRuntimeIncompatibility("catalog-only Skill cannot be task-pinned")
        if entry.runtime_binding_sha256 != pin.runtime_binding_sha256:
            raise SkillRuntimeIncompatibility("runtime binding digest does not match pin")
        expected_leaf = next(
            (
                binding
                for binding in entry.operation_bindings or ()
                if binding.operation == operation
            ),
            None,
        )
        if expected_leaf is None:
            raise SkillRuntimeIncompatibility("task operation is not supported")
        if actual_leaf != expected_leaf:
            raise SkillRuntimeIncompatibility("actual leaf does not match packaged binding")
        return entry
