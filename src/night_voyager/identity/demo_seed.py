from __future__ import annotations

from uuid import UUID

from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.models import SkillKey, canonical_sha256
from night_voyager.skills.registry import SkillRuntimeRegistry

CONNECTED_DEMO_CASE_ID = UUID("40000000-0000-0000-0000-000000000002")
DRA_PROOF_CASE_ID = UUID("40000000-0000-0000-0000-000000000003")
COLLABORATION_CASE_ID = UUID("41000000-0000-0000-0000-000000000001")
COLLABORATION_ACTIVE_CASE_ID = UUID("41000000-0000-0000-0000-000000000002")
COLLABORATION_STALE_CASE_ID = UUID("41000000-0000-0000-0000-000000000003")
COLLABORATION_EXPIRED_CASE_ID = UUID("41000000-0000-0000-0000-000000000004")
COLLABORATION_THREAD_IDS = {
    "primary": UUID("42000000-0000-0000-0000-000000000001"),
    "active_task": UUID("42000000-0000-0000-0000-000000000002"),
    "stale": UUID("42000000-0000-0000-0000-000000000003"),
    "expired": UUID("42000000-0000-0000-0000-000000000004"),
}
COLLABORATION_STALE_MESSAGE_ID = UUID("43000000-0000-0000-0000-000000000003")
COLLABORATION_EXPIRED_MESSAGE_ID = UUID("43000000-0000-0000-0000-000000000004")
COLLABORATION_STALE_CANDIDATE_ID = UUID("45000000-0000-0000-0000-000000000003")
COLLABORATION_EXPIRED_CANDIDATE_ID = UUID("45000000-0000-0000-0000-000000000004")
COLLABORATION_ACTIVE_TASK_ID = UUID("48000000-0000-0000-0000-000000000002")

_SKILL_KEYS = (
    SkillKey.STUDENT_PROFILE_INTAKE,
    SkillKey.STUDY_DESTINATION_COMPARE,
    SkillKey.EVIDENCE_RESEARCH,
    SkillKey.DOCUMENT_EVIDENCE_RETRIEVAL,
    SkillKey.FAMILY_DECISION_BRIEF,
    SkillKey.APPLICATION_TIMELINE_GUARD,
)
SKILL_DEFINITION_IDS = {
    key: UUID(f"81000000-0000-0000-0000-{index:012d}")
    for index, key in enumerate(_SKILL_KEYS, start=1)
}
SKILL_VERSION_IDS = {
    key: UUID(f"82000000-0000-0000-0000-{index:012d}")
    for index, key in enumerate(_SKILL_KEYS, start=1)
}
SKILL_EVALUATION_IDS = {
    key: UUID(f"83000000-0000-0000-0000-{index:012d}")
    for index, key in enumerate(_SKILL_KEYS, start=1)
}
SKILL_ACTIVATION_EVENT_ID = UUID("84000000-0000-0000-0000-000000000001")


def build_demo_skill_seed(
    registry: SkillRuntimeRegistry,
    evaluator: SkillEvaluator,
) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for key in _SKILL_KEYS:
        manifest_entry = registry.get(key, "1.0.0")
        evaluation = evaluator.evaluate(key, "1.0.0")
        envelope: dict[str, object] = {
            "definition_id": str(SKILL_DEFINITION_IDS[key]),
            "version_id": str(SKILL_VERSION_IDS[key]),
            "evaluation_id": str(SKILL_EVALUATION_IDS[key]),
            "is_seed": True,
            "manifest": manifest_entry.model_dump(mode="json", exclude_none=True),
            "evaluation": evaluation.model_dump(mode="json"),
            "request_sha256": canonical_sha256(
                {
                    "seed": "night-voyager-demo-skill-registry-v1",
                    "skill_key": key.value,
                    "version": "1.0.0",
                }
            ),
        }
        if key is SkillKey.STUDY_DESTINATION_COMPARE:
            envelope["activation_event_id"] = str(SKILL_ACTIVATION_EVENT_ID)
        entries.append(envelope)
    return {
        "schema_version": 1,
        "runtime_manifest_id": registry.manifest.manifest_id,
        "runtime_manifest_version": registry.manifest.manifest_version,
        "runtime_manifest_sha256": registry.manifest.manifest_sha256,
        "evaluation_manifest_id": evaluator.manifest.manifest_id,
        "evaluation_manifest_version": evaluator.manifest.manifest_version,
        "evaluation_manifest_sha256": evaluator.manifest.manifest_sha256,
        "entries": entries,
    }


def build_demo_active_task_pin(
    registry: SkillRuntimeRegistry,
) -> dict[str, object]:
    key = SkillKey.STUDY_DESTINATION_COMPARE
    manifest_entry = registry.get(key, "1.0.0")
    if manifest_entry.runtime_binding_sha256 is None:
        raise ValueError("planning runtime seed omitted its binding hash")
    return {
        "skill_definition_id": str(SKILL_DEFINITION_IDS[key]),
        "skill_version_id": str(SKILL_VERSION_IDS[key]),
        "skill_activation_event_id": str(SKILL_ACTIVATION_EVENT_ID),
        "skill_activation_sequence": 1,
        "runtime_binding_sha256": manifest_entry.runtime_binding_sha256,
    }


def ensure_seed_allowed(environment: str, demo_mode: bool) -> None:
    if environment not in {"development", "test"}:
        raise ValueError("demo seed requires development or test environment")
    if not demo_mode:
        raise ValueError("demo seed requires explicit demo mode")
