from __future__ import annotations

import ast
from pathlib import Path

from night_voyager.collaboration.models import (
    CollaborationThreadV1,
    ConfirmedFactAdvisorV1,
    ConfirmedFactParticipantV1,
    FactKey,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    MessageEventV1,
    MessagePageV1,
    VerificationDecision,
)

ROOT = Path(__file__).resolve().parents[2]
PURE_MODULES = ("models.py", "policy.py", "hashing.py", "errors.py")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_collaboration_pure_contracts_are_framework_independent() -> None:
    forbidden = {"alembic", "asyncpg", "fastapi", "sqlalchemy"}
    for module in PURE_MODULES:
        path = ROOT / "src/night_voyager/collaboration" / module
        assert path.is_file(), module
        assert not (_imports(path) & forbidden), module


def test_collaboration_closed_vocabularies_are_exact() -> None:
    assert {item.value for item in FactKey} == {
        "student.intended_field",
        "student.preferred_countries",
        "student.intake",
        "family.risk_tolerance",
        "family.japan_risk_accepted",
        "family.budget",
    }
    assert {item.value for item in MemoryCandidateState} == {
        "pending",
        "stale",
        "expired",
        "confirmed",
        "rejected",
    }
    assert {item.value for item in VerificationDecision} == {"confirm", "reject"}


def test_collaboration_role_safe_projection_models_are_distinct() -> None:
    participant_candidate_fields = set(MemoryCandidateParticipantV1.model_fields)
    advisor_candidate_fields = set(MemoryCandidateAdvisorV1.model_fields)
    assert participant_candidate_fields < advisor_candidate_fields
    assert {
        "candidate_id",
        "verification_id",
        "reason",
        "request_sha256",
        "value_sha256",
    }.isdisjoint(participant_candidate_fields)

    participant_fact_fields = set(ConfirmedFactParticipantV1.model_fields)
    advisor_fact_fields = set(ConfirmedFactAdvisorV1.model_fields)
    assert participant_fact_fields < advisor_fact_fields
    assert {
        "confirmed_fact_id",
        "candidate_id",
        "verification_id",
        "source_message_event_id",
        "source_message_sequence_no",
        "source_message_sha256_prefix",
        "confirming_advisor_actor_id",
        "reason",
        "supersedes_fact_id",
    }.isdisjoint(participant_fact_fields)


def test_collaboration_read_models_are_strict_and_versioned() -> None:
    for model in (
        CollaborationThreadV1,
        MessageEventV1,
        MessagePageV1,
        MemoryCandidateParticipantV1,
        MemoryCandidateAdvisorV1,
        ConfirmedFactParticipantV1,
        ConfirmedFactAdvisorV1,
    ):
        assert model.model_config.get("extra") == "forbid"
        assert "schema_version" in model.model_fields
