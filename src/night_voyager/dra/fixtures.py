from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from night_voyager.dra.models import (
    DRA_FIXTURE_SHA256,
    DraCandidateImportV1,
    DraCanonicalArtifactInputV1,
    DraEvidenceProjectionV1,
    DraFixtureProjectionV1,
    DraHealthProjectionV1,
    DraProducerPinV1,
    DraRunAcceptanceV1,
    DraRunProjectionV1,
    DraRunRequestIdentityV1,
)
from night_voyager.planning.hashing import canonical_sha256

DRA_ROOT = Path("fixtures/dra")
DRA_FIXTURE = DRA_ROOT / "downstream-consumer-contract-v1.json"
DRA_MANIFEST = DRA_ROOT / "manifest.json"


def _as_object(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(code)
    return cast(dict[str, object], value)


def _as_list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(code)
    return cast(list[object], value)


def _as_str(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise ValueError(code)
    return value


def _read_json(path: Path) -> dict[str, object]:
    return _as_object(json.loads(path.read_text(encoding="utf-8")), "dra_fixture_object_required")


def _project_evidence(payload: object) -> DraEvidenceProjectionV1:
    if not isinstance(payload, dict):
        raise ValueError("dra_evidence_object_required")
    value = cast(dict[str, object], payload)
    return DraEvidenceProjectionV1.model_validate(
        {
            field: value.get(field)
            for field in (
                "evidence_id",
                "source_url",
                "source_identity",
                "retrieved_at",
                "citation_status",
                "verification_status",
            )
        }
    )


def load_dra_fixture() -> DraFixtureProjectionV1:
    raw = DRA_FIXTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DRA_FIXTURE_SHA256:
        raise ValueError("dra_fixture_hash_mismatch")
    fixture = _as_object(json.loads(raw), "dra_fixture_object_required")
    manifest = _read_json(DRA_MANIFEST)
    producer = _as_object(manifest.get("producer"), "dra_manifest_producer_invalid")
    if fixture.get("schema_version") != producer.get("fixture_schema"):
        raise ValueError("dra_fixture_schema_mismatch")

    cases = [_as_object(item, "dra_fixture_case_invalid") for item in _as_list(
        fixture.get("cases"), "dra_fixture_cases_invalid"
    )]
    dispositions = {
        _as_str(case.get("case_id"), "dra_fixture_case_id_invalid"): _as_str(
            _as_object(case.get("expected"), "dra_fixture_expected_invalid").get(
                "disposition"
            ),
            "dra_fixture_disposition_invalid",
        )
        for case in cases
    }
    if dispositions != _as_object(
        manifest.get("dispositions"), "dra_manifest_dispositions_invalid"
    ):
        raise ValueError("dra_fixture_dispositions_mismatch")
    accepted_case = _as_str(manifest.get("accepted_case"), "dra_manifest_accepted_case_invalid")
    canonical = next(
        case
        for case in cases
        if case.get("case_id") == accepted_case
    )
    run_payload = _as_object(canonical.get("run"), "dra_fixture_run_invalid")
    result = _as_object(canonical.get("result"), "dra_fixture_result_invalid")
    result_body = _as_object(result.get("body"), "dra_fixture_result_body_invalid")
    artifact_payload = _as_object(
        result_body.get("artifact"), "dra_fixture_artifact_invalid"
    )
    run = DraRunProjectionV1.model_validate(
        {
            field: run_payload.get(field)
            for field in (
                "run_id",
                "state_version",
                "execution_status",
                "review_status",
                "delivery_status",
            )
        }
    )
    evidence = tuple(
        _project_evidence(item)
        for item in _as_list(canonical.get("evidence"), "dra_fixture_evidence_invalid")
    )
    candidate_manifest = _as_object(manifest.get("candidate"), "dra_manifest_candidate_invalid")
    request = _as_object(candidate_manifest.get("request"), "dra_manifest_request_invalid")
    request_identity = DraRunRequestIdentityV1.model_validate(
        {
            "profile_id": request.get("profile_id"),
            "request_sha256": canonical_sha256(request),
        }
    )
    candidate_import = DraCandidateImportV1.model_validate(
        {
            "schema_version": "night-voyager.dra-candidate-import.v1",
            "organization_id": candidate_manifest.get("organization_id"),
            "case_id": candidate_manifest.get("case_id"),
            "expected_case_revision": candidate_manifest.get("expected_case_revision"),
            "producer": DraProducerPinV1(),
            "request_identity": request_identity,
            "acceptance": DraRunAcceptanceV1(
                thread_id="thread_00000000000000000000000000000003",
                run_id=run.run_id,
                segment_id="segment_00000000000000000000000000000003",
                idempotent_replay=False,
            ),
            "run": run,
            "artifact": DraCanonicalArtifactInputV1.model_validate(
                {
                    field: artifact_payload.get(field)
                    for field in (
                        "artifact_id",
                        "kind",
                        "media_type",
                        "content",
                        "content_hash",
                    )
                }
            ),
            "evidence": evidence,
        }
    )
    service = _as_object(fixture.get("service"), "dra_fixture_service_invalid")
    return DraFixtureProjectionV1.model_validate(
        {
            "schema_version": fixture.get("schema_version"),
            "health": DraHealthProjectionV1.model_validate(
                _as_object(service.get("health"), "dra_fixture_health_invalid")
            ),
            "dispositions": dispositions,
            "canonical_import": candidate_import,
        }
    )


def build_fixture_candidate_import() -> DraCandidateImportV1:
    fixture = load_dra_fixture()
    promotable = [item for item in fixture.canonical_import.evidence if item.is_promotable]
    if len(promotable) != 1:
        raise ValueError("dra_promotable_evidence_count_invalid")
    return fixture.canonical_import
