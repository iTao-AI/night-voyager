from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import build_fixture_candidate_import, load_dra_fixture
from night_voyager.dra.models import DraCanonicalArtifactInputV1, DraRunProjectionV1


def test_fixture_exposes_only_strict_canonical_projection() -> None:
    fixture = load_dra_fixture()
    candidate = build_fixture_candidate_import()
    assert fixture.schema_version == "dra.downstream-consumer.v1"
    assert fixture.health.status == "ok"
    assert fixture.health.service == "decision-research-agent"
    assert fixture.dispositions["canonical_ready"] == "accept_draft"
    assert candidate.artifact.content.startswith("# Synthetic Research Report")
    assert len(candidate.evidence) == 1
    assert set(candidate.evidence[0].model_dump()) == {
        "evidence_id",
        "source_url",
        "source_identity",
        "retrieved_at",
        "citation_status",
        "verification_status",
        "is_promotable",
    }


@pytest.mark.parametrize(
    ("execution", "review", "delivery"),
    (
        ("completed_with_fallback", "not_required", "ready"),
        ("completed", "required", "review_required"),
        ("completed", "resolved", "blocked"),
        ("failed", "not_required", "failed"),
    ),
)
def test_noncanonical_run_states_fail_closed(
    execution: str, review: str, delivery: str
) -> None:
    with pytest.raises(ValidationError, match="dra_run_not_canonical_ready"):
        DraRunProjectionV1.model_validate(
            {
                "run_id": "run_00000000000000000000000000000001",
                "state_version": 1,
                "execution_status": execution,
                "review_status": review,
                "delivery_status": delivery,
            }
        )


def test_artifact_rejects_wrong_hash_empty_and_oversize() -> None:
    content = "safe"
    with pytest.raises(ValidationError, match="dra_artifact_hash_mismatch"):
        DraCanonicalArtifactInputV1(
            artifact_id="research-report.md",
            kind="research_report_markdown",
            media_type="text/markdown",
            content=content,
            content_hash="0" * 64,
        )
    with pytest.raises(ValidationError):
        DraCanonicalArtifactInputV1(
            artifact_id="research-report.md",
            kind="research_report_markdown",
            media_type="text/markdown",
            content="",
            content_hash=hashlib.sha256(b"").hexdigest(),
        )
    oversized = "x" * (1024 * 1024 + 1)
    with pytest.raises(ValidationError, match="dra_artifact_oversize"):
        DraCanonicalArtifactInputV1(
            artifact_id="research-report.md",
            kind="research_report_markdown",
            media_type="text/markdown",
            content=oversized,
            content_hash=hashlib.sha256(oversized.encode()).hexdigest(),
        )


def test_candidate_requires_unique_ordered_evidence_ids() -> None:
    candidate = build_fixture_candidate_import()
    duplicate = candidate.model_copy(update={"evidence": candidate.evidence * 2})
    with pytest.raises(ValidationError, match="dra_evidence_ids_not_unique"):
        type(candidate).model_validate(duplicate.model_dump(exclude_computed_fields=True))


def test_candidate_requires_exactly_one_promotable_public_evidence() -> None:
    candidate = build_fixture_candidate_import()
    second = candidate.evidence[0].model_copy(update={"evidence_id": "second-public-evidence"})
    payload = candidate.model_copy(update={"evidence": (*candidate.evidence, second)})
    with pytest.raises(ValidationError, match="dra_promotable_evidence_cardinality"):
        type(candidate).model_validate(payload.model_dump(exclude_computed_fields=True))
