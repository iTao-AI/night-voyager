from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from night_voyager.dra.models import (
    DRA_COMMIT,
    DRA_CONTRACT_SCHEMA,
    DRA_RELEASE,
    DraCanonicalArtifactInputV1,
    DraEvidenceProjectionV1,
    DraResearchCandidateV1,
)


def evidence_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_id": "ev-1",
        "source_url": "https://example.com/contract-source-1",
        "source_identity": "https://example.com/contract-source-1",
        "retrieved_at": datetime(2026, 7, 11, tzinfo=UTC),
        "citation_status": "cited",
        "verification_status": "unverified",
    }
    payload.update(changes)
    return payload


def test_exact_producer_pins_are_public_constants() -> None:
    assert DRA_RELEASE == "v0.1.3"
    assert DRA_COMMIT == "87b2a8e335385eb865086f7a69fe2b190567cfa2"
    assert DRA_CONTRACT_SCHEMA == "dra.downstream-consumer.v1"


def test_canonical_artifact_hashes_exact_utf8_bytes() -> None:
    content = "# Synthetic Research Report\n\nPublic-safe contract proof."
    artifact = DraCanonicalArtifactInputV1(
        artifact_id="research-report.md",
        kind="research_report_markdown",
        media_type="text/markdown",
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    assert artifact.byte_length == len(content.encode("utf-8"))


@pytest.mark.parametrize(
    "changes,error",
    (
        ({"source_url": "http://example.com/x"}, "dra_source_url_invalid"),
        ({"source_url": "https://user@example.com/x"}, "dra_source_url_invalid"),
        ({"source_url": "https://localhost/x"}, "dra_source_url_invalid"),
        ({"source_url": "https://127.0.0.1/x"}, "dra_source_url_invalid"),
        ({"source_url": "https://10.0.0.1/x"}, "dra_source_url_invalid"),
        ({"source_url": "https://169.254.1.1/x"}, "dra_source_url_invalid"),
        ({"source_url": "https://0.0.0.0/x"}, "dra_source_url_invalid"),
        ({"source_identity": "https://example.com/other"}, "dra_source_identity_mismatch"),
    ),
)
def test_evidence_requires_exact_public_https_identity(
    changes: dict[str, object], error: str
) -> None:
    with pytest.raises(ValidationError, match=error):
        DraEvidenceProjectionV1.model_validate(evidence_payload(**changes))


def test_nullable_upstream_source_is_valid_but_not_promotable() -> None:
    evidence = DraEvidenceProjectionV1.model_validate(
        evidence_payload(source_url=None, source_identity="upstream-source-without-url")
    )
    assert evidence.source_url is None
    assert evidence.is_promotable is False


def test_external_authority_is_not_a_candidate_input() -> None:
    with pytest.raises(ValidationError):
        DraResearchCandidateV1.model_validate(
            {
                "schema_version": "night-voyager.dra-candidate.v1",
                "candidate_id": "90000000-0000-0000-0000-000000000001",
                "organization_id": "10000000-0000-0000-0000-000000000001",
                "case_id": "40000000-0000-0000-0000-000000000001",
                "expected_case_revision": 1,
                "producer": {
                    "name": "decision-research-agent",
                    "release": DRA_RELEASE,
                    "commit": DRA_COMMIT,
                    "contract_schema": DRA_CONTRACT_SCHEMA,
                    "fixture_sha256": "c" * 64,
                },
                "request_identity": {
                    "profile_id": "generic",
                    "request_sha256": "a" * 64,
                },
                "run_id": "run_00000000000000000000000000000003",
                "artifact_id": "research-report.md",
                "artifact_kind": "research_report_markdown",
                "artifact_media_type": "text/markdown",
                "artifact_byte_length": 10,
                "artifact_sha256": "b" * 64,
                "evidence": [evidence_payload()],
                "import_request_sha256": "d" * 64,
                "authority": "externally_verified",
                "created_at": datetime(2026, 7, 15, tzinfo=UTC),
            }
        )
