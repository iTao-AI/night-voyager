from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID, uuid5

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.models import SkillKey, SkillRuntimeManifestEntryV1
from night_voyager.skills.registry import (
    SkillRuntimeIncompatibility,
    SkillRuntimeRegistry,
)

DEMO_ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
SKILL_VERSION_NAMESPACE = UUID("9134b732-438f-5a91-950a-7683f773cbf4")


class SkillVersionRegistrationError(RuntimeError):
    """A supported Skill version could not be registered exactly."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _semantic_version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        raise SkillVersionRegistrationError("unsupported Skill semantic version")
    try:
        return cast(tuple[int, int, int], tuple(int(part) for part in parts))
    except ValueError as error:
        raise SkillVersionRegistrationError("unsupported Skill semantic version") from error


def _version_id(organization_id: UUID, skill_key: SkillKey, version: str) -> UUID:
    return uuid5(
        SKILL_VERSION_NAMESPACE,
        f"{organization_id}:{skill_key.value}:{version}",
    )


def _require_exact_row(
    row: Mapping[str, Any],
    *,
    organization_id: UUID,
    definition_id: UUID,
    entry: SkillRuntimeManifestEntryV1,
    registry: SkillRuntimeRegistry,
    supersedes_version_id: UUID,
    expected_evaluation_projection: Mapping[str, Any],
) -> None:
    projection = entry.model_dump(mode="json", exclude_none=True)
    expected = {
        "id": _version_id(organization_id, entry.skill_key, entry.version),
        "definition_id": definition_id,
        "skill_key": entry.skill_key.value,
        "semantic_version": entry.version,
        "binding_kind": entry.binding_kind.value,
        "runtime_manifest_id": registry.manifest.manifest_id,
        "runtime_manifest_version": registry.manifest.manifest_version,
        "runtime_manifest_sha256": registry.manifest.manifest_sha256,
        "manifest_projection": projection,
        "expected_evaluation_projection": dict(expected_evaluation_projection),
        "supersedes_version_id": supersedes_version_id,
        "is_seed": False,
    }
    actual = {field: row[field] for field in expected}
    if actual != expected:
        raise SkillVersionRegistrationError("registered Skill version mismatch")


async def _load_definition(
    connection: AsyncConnection,
    organization_id: UUID,
    entry: SkillRuntimeManifestEntryV1,
) -> Mapping[str, Any]:
    row = (
        (
            await connection.execute(
                text(
                    "SELECT id,binding_kind FROM app.skill_definitions "
                    "WHERE organization_id=:org AND skill_key=:skill_key FOR SHARE"
                ),
                {"org": organization_id, "skill_key": entry.skill_key.value},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["binding_kind"] != entry.binding_kind.value:
        raise SkillVersionRegistrationError("Skill definition unavailable")
    return cast(dict[str, Any], dict(row))


async def _load_superseded_version(
    connection: AsyncConnection,
    organization_id: UUID,
    definition_id: UUID,
    proposed_version: str,
) -> UUID:
    rows = (
        (
            await connection.execute(
                text(
                    "SELECT id,semantic_version FROM app.skill_versions "
                    "WHERE organization_id=:org AND definition_id=:definition"
                ),
                {"org": organization_id, "definition": definition_id},
            )
        )
        .mappings()
        .all()
    )
    proposed = _semantic_version_tuple(proposed_version)
    eligible = [
        row for row in rows if _semantic_version_tuple(str(row["semantic_version"])) < proposed
    ]
    if not eligible:
        raise SkillVersionRegistrationError("superseded Skill version unavailable")
    selected = max(
        eligible,
        key=lambda row: _semantic_version_tuple(str(row["semantic_version"])),
    )
    return UUID(str(selected["id"]))


async def _load_registered_row(
    connection: AsyncConnection,
    organization_id: UUID,
    definition_id: UUID,
    version: str,
) -> Mapping[str, Any] | None:
    row = (
        (
            await connection.execute(
                text(
                    "SELECT id,definition_id,skill_key,semantic_version,binding_kind,"
                    "runtime_manifest_id,runtime_manifest_version,"
                    "runtime_manifest_sha256,manifest_projection,"
                    "expected_evaluation_projection,"
                    "supersedes_version_id,is_seed "
                    "FROM app.skill_versions WHERE organization_id=:org "
                    "AND definition_id=:definition AND semantic_version=:version"
                ),
                {
                    "org": organization_id,
                    "definition": definition_id,
                    "version": version,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    return None if row is None else cast(dict[str, Any], dict(row))


async def _insert_registered_version(
    connection: AsyncConnection,
    organization_id: UUID,
    definition_id: UUID,
    supersedes_version_id: UUID,
    entry: SkillRuntimeManifestEntryV1,
    registry: SkillRuntimeRegistry,
    expected_evaluation_projection: Mapping[str, Any],
) -> None:
    manifest = entry.model_dump(mode="json", exclude_none=True)
    await connection.execute(
        text(
            "INSERT INTO app.skill_versions("
            "organization_id,id,definition_id,skill_key,semantic_version,binding_kind,"
            "executor_id,executor_version,input_contract_id,input_schema_sha256,"
            "output_contract_id,output_schema_sha256,content_sha256,tool_ids,"
            "tool_allowlist_sha256,data_scopes,data_scope_sha256,side_effect_level,"
            "approval_policy,policy_version,policy_sha256,evaluation_dataset_id,"
            "evaluation_dataset_version,evaluation_dataset_sha256,runtime_manifest_id,"
            "expected_evaluation_projection,"
            "runtime_manifest_version,runtime_manifest_sha256,operation_bindings,"
            "runtime_binding_sha256,manifest_projection,supersedes_version_id,is_seed) "
            "VALUES(:org,:version_id,:definition,:skill_key,:semantic_version,"
            ":binding_kind,:executor_id,:executor_version,:input_contract_id,"
            ":input_schema_sha256,:output_contract_id,:output_schema_sha256,"
            ":content_sha256,CAST(:tool_ids AS jsonb),:tool_allowlist_sha256,"
            "CAST(:data_scopes AS jsonb),:data_scope_sha256,:side_effect_level,"
            ":approval_policy,:policy_version,:policy_sha256,:evaluation_dataset_id,"
            ":evaluation_dataset_version,:evaluation_dataset_sha256,"
            ":runtime_manifest_id,CAST(:expected_evaluation_projection AS jsonb),"
            ":runtime_manifest_version,:runtime_manifest_sha256,"
            "CAST(:operation_bindings AS jsonb),:runtime_binding_sha256,"
            "CAST(:manifest_projection AS jsonb),:supersedes_version_id,false) "
            "ON CONFLICT (organization_id,definition_id,semantic_version) DO NOTHING"
        ),
        {
            "org": organization_id,
            "version_id": _version_id(organization_id, entry.skill_key, entry.version),
            "definition": definition_id,
            "skill_key": entry.skill_key.value,
            "semantic_version": entry.version,
            "binding_kind": entry.binding_kind.value,
            "executor_id": entry.executor_id,
            "executor_version": entry.executor_version,
            "input_contract_id": entry.input_contract_id,
            "input_schema_sha256": entry.input_schema_sha256,
            "output_contract_id": entry.output_contract_id,
            "output_schema_sha256": entry.output_schema_sha256,
            "content_sha256": entry.content_sha256,
            "tool_ids": _canonical_json([item.value for item in entry.tool_ids]),
            "tool_allowlist_sha256": entry.tool_allowlist_sha256,
            "data_scopes": _canonical_json([item.value for item in entry.data_scopes]),
            "data_scope_sha256": entry.data_scope_sha256,
            "side_effect_level": entry.side_effect_level.value,
            "approval_policy": entry.approval_policy.value,
            "policy_version": entry.policy_version,
            "policy_sha256": entry.policy_sha256,
            "evaluation_dataset_id": entry.evaluation_dataset_id,
            "evaluation_dataset_version": entry.evaluation_dataset_version,
            "evaluation_dataset_sha256": entry.evaluation_dataset_sha256,
            "runtime_manifest_id": registry.manifest.manifest_id,
            "expected_evaluation_projection": _canonical_json(
                dict(expected_evaluation_projection)
            ),
            "runtime_manifest_version": registry.manifest.manifest_version,
            "runtime_manifest_sha256": registry.manifest.manifest_sha256,
            "operation_bindings": _canonical_json(
                [binding.model_dump(mode="json") for binding in entry.operation_bindings or ()]
            )
            if entry.operation_bindings is not None
            else None,
            "runtime_binding_sha256": entry.runtime_binding_sha256,
            "manifest_projection": _canonical_json(manifest),
            "supersedes_version_id": supersedes_version_id,
        },
    )


async def register_skill_version(
    database_url: str,
    *,
    organization_id: UUID,
    skill_key: SkillKey,
    version: str,
) -> bool:
    registry = SkillRuntimeRegistry.load_packaged()
    evaluator = SkillEvaluator.load_packaged(registry)
    try:
        entry = registry.get(skill_key, version)
    except SkillRuntimeIncompatibility as error:
        raise SkillVersionRegistrationError("unsupported Skill version") from error
    expected_evaluation_projection = evaluator.evaluate(skill_key, version).model_dump(
        mode="json"
    )

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(organization_id)},
            )
            definition = await _load_definition(connection, organization_id, entry)
            definition_id = UUID(str(definition["id"]))
            supersedes_version_id = await _load_superseded_version(
                connection,
                organization_id,
                definition_id,
                entry.version,
            )
            existing = await _load_registered_row(
                connection,
                organization_id,
                definition_id,
                entry.version,
            )
            if existing is not None:
                _require_exact_row(
                    existing,
                    organization_id=organization_id,
                    definition_id=definition_id,
                    entry=entry,
                    registry=registry,
                    supersedes_version_id=supersedes_version_id,
                    expected_evaluation_projection=expected_evaluation_projection,
                )
                return False

            await _insert_registered_version(
                connection,
                organization_id,
                definition_id,
                supersedes_version_id,
                entry,
                registry,
                expected_evaluation_projection,
            )
            registered = await _load_registered_row(
                connection,
                organization_id,
                definition_id,
                entry.version,
            )
            if registered is None:
                raise SkillVersionRegistrationError("Skill version insert failed")
            _require_exact_row(
                registered,
                organization_id=organization_id,
                definition_id=definition_id,
                entry=entry,
                registry=registry,
                supersedes_version_id=supersedes_version_id,
                expected_evaluation_projection=expected_evaluation_projection,
            )
            return True
    except SQLAlchemyError as error:
        raise SkillVersionRegistrationError("Skill version persistence failed") from error
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skill-key",
        required=True,
        choices=tuple(skill_key.value for skill_key in SkillKey),
    )
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--organization-id",
        type=UUID,
        default=DEMO_ORGANIZATION_ID,
    )
    arguments = parser.parse_args(argv)
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if not database_url:
        print("Skill version registration failed closed", file=sys.stderr)
        raise SystemExit(1)
    try:
        created = asyncio.run(
            register_skill_version(
                database_url,
                organization_id=arguments.organization_id,
                skill_key=SkillKey(arguments.skill_key),
                version=arguments.version,
            )
        )
    except (SkillVersionRegistrationError, ValueError):
        print("Skill version registration failed closed", file=sys.stderr)
        raise SystemExit(1) from None
    action = "registered" if created else "already registered"
    print(f"Skill version {action}: {arguments.skill_key}@{arguments.version}")


if __name__ == "__main__":
    main()
