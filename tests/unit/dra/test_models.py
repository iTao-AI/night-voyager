from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

import night_voyager.dra.models as dra_models
from night_voyager.dra.fixtures import build_fixture_candidate_import, load_dra_fixture
from night_voyager.dra.live_models import DraLiveScenarioV2
from night_voyager.dra.models import (
    DRA_LIVE_COMMIT,
    DraCanonicalArtifactInputV1,
    DraObservedProfileManifestV1,
    DraProducerPinV2,
    DraRunProjectionV1,
    DraRunRequestIdentityV2,
    DraStrictConsumerIdentityV2,
)


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


def test_strict_producer_pin_is_exact_commit_identity() -> None:
    pin = DraProducerPinV2()
    assert pin.model_dump(mode="json") == {
        "schema": "night-voyager.dra-producer-pin.v2",
        "repository": "https://github.com/iTao-AI/decision-research-agent",
        "ref_kind": "commit",
        "ref": "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "commit": "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "consumer_contract_schema": "dra.downstream-consumer.v1",
        "consumer_fixture_sha256": (
            "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
        ),
        "profile_id": "generic-strict-citation",
        "profile_version": "1",
        "proof_schema": "dra.strict-citation-profile.v1",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ref_kind", "release"),
        ("ref", "v0.1.6"),
        ("commit", DRA_LIVE_COMMIT),
        ("profile_id", "generic"),
        ("profile_version", "2"),
        ("proof_schema", "dra.downstream-consumer.v1"),
    ],
)
def test_strict_producer_pin_rejects_mixed_identity(
    field: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        DraProducerPinV2.model_validate(
            DraProducerPinV2().model_dump() | {field: value}
        )


def test_request_identity_v2_reconciles_requested_and_observed_profile() -> None:
    identity = DraStrictConsumerIdentityV2(
        schema_version="night-voyager.dra-strict-consumer-identity.v2",
        producer=DraProducerPinV2(),
        request=DraRunRequestIdentityV2(
            schema_version="night-voyager.dra-run-request-identity.v2",
            profile_id="generic-strict-citation",
            request_sha256="a" * 64,
        ),
        observed_profile=DraObservedProfileManifestV1(
            schema_version="night-voyager.dra-observed-profile-manifest.v1",
            profile_id="generic-strict-citation",
            profile_version="1",
        ),
    )
    assert identity.request.profile_id == identity.producer.profile_id
    assert identity.observed_profile.profile_version == identity.producer.profile_version

    payload = identity.model_dump(mode="json")
    payload["observed_profile"]["profile_version"] = "2"
    with pytest.raises(ValidationError):
        DraStrictConsumerIdentityV2.model_validate(payload)


def test_candidate_import_v2_is_closed_and_binds_strict_identity() -> None:
    candidate_type = getattr(dra_models, "DraCandidateImportV2", None)
    assert candidate_type is not None
    scenario = DraLiveScenarioV2.model_validate_json(
        Path("fixtures/dra/live-closure-scenario-v2.json").read_bytes()
    )
    evidence = scenario.evidence[0]
    payload = {
        "schema_version": "night-voyager.dra-candidate-import.v2",
        "organization_id": "10000000-0000-0000-0000-000000000001",
        "case_id": "40000000-0000-0000-0000-000000000003",
        "expected_case_revision": 1,
        "consumer_identity": {
            "schema_version": "night-voyager.dra-strict-consumer-identity.v2",
            "producer": scenario.producer,
            "request": scenario.request_identity,
            "observed_profile": scenario.profile_manifest,
        },
        "acceptance": {
            "thread_id": scenario.status.thread_id,
            "run_id": scenario.status.run_id,
            "segment_id": scenario.status.segment_id,
            "idempotent_replay": False,
        },
        "run": {
            "run_id": scenario.status.run_id,
            "state_version": scenario.status.state_version,
            "execution_status": "completed",
            "review_status": "not_required",
            "delivery_status": "ready",
        },
        "artifact": scenario.canonical_artifact,
        "evidence": [
            {
                "evidence_id": evidence.evidence_id,
                "source_url": evidence.source_url,
                "source_identity": evidence.source_identity,
                "retrieved_at": evidence.retrieved_at,
                "citation_status": evidence.citation_status,
                "verification_status": evidence.verification_status,
            }
        ],
    }
    candidate = candidate_type.model_validate(payload)
    assert candidate.consumer_identity.producer == scenario.producer
    with pytest.raises(ValidationError):
        candidate_type.model_validate(payload | {"producer": scenario.producer})
    with pytest.raises(ValidationError):
        candidate_type.model_validate(payload | {"unknown": True})
