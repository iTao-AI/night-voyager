from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import (
    build_fixture_candidate_import,
    load_live_closure_scenario,
)
from night_voyager.dra.live_fakes import ScenarioDraLiveTransport
from night_voyager.dra.live_models import (
    DraLiveEvidenceEnvelopeV1,
    DraLiveRunEnvelopeV1,
)
from night_voyager.dra.live_projection import (
    DraLiveContractError,
    project_terminal_result,
    select_cited_evidence,
)
from night_voyager.dra.models import (
    DraCanonicalResultProjectionV1,
    DraRunAcceptanceV1,
)
from night_voyager.interfaces.http.dra import DraVerificationDecisionRequest


def acceptance() -> DraRunAcceptanceV1:
    scenario = load_live_closure_scenario()
    return DraRunAcceptanceV1(
        thread_id=scenario.status.thread_id,
        run_id=scenario.status.run_id,
        segment_id=scenario.status.segment_id,
        idempotent_replay=False,
    )


def run_payload() -> dict[str, object]:
    scenario = load_live_closure_scenario()
    return scenario.status.model_dump(mode="json") | {
        "evidence": [item.model_dump(mode="json") for item in scenario.evidence]
    }


def result_payload() -> dict[str, object]:
    scenario = load_live_closure_scenario()
    artifact = build_fixture_candidate_import().artifact
    assert artifact.content_hash == scenario.result.artifact.sha256
    return {
        "run_id": scenario.result.run_id,
        "execution_status": scenario.result.execution_status,
        "delivery_status": scenario.result.delivery_status,
        "artifact": artifact.model_dump(
            mode="json", exclude_computed_fields=True
        ),
    }


def project(
    *,
    acceptance_value: DraRunAcceptanceV1 | None = None,
    run_value: DraLiveRunEnvelopeV1 | None = None,
    result_value: DraCanonicalResultProjectionV1 | None = None,
):
    return project_terminal_result(
        acceptance_value or acceptance(),
        run_value or DraLiveRunEnvelopeV1.model_validate(run_payload()),
        result_value or DraCanonicalResultProjectionV1.model_validate(result_payload()),
    )


def test_scenario_fake_and_strict_projection_have_exact_field_parity() -> None:
    scenario = load_live_closure_scenario()
    fake = ScenarioDraLiveTransport(scenario)
    assert fake.run.model_dump(mode="json") == run_payload()
    assert fake.result.model_dump(
        mode="json", exclude_computed_fields=True
    ) == result_payload()
    projection = project(run_value=fake.run, result_value=fake.result)
    assert projection.run_id == scenario.status.run_id
    assert projection.segment_id == scenario.status.segment_id
    assert [set(item.model_dump()) for item in projection.evidence] == [
        {
            "evidence_id",
            "source_url",
            "source_identity",
            "retrieved_at",
            "citation_status",
            "verification_status",
        }
    ]
    assert projection.evidence[0].verification_status == "unverified"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("execution_status", "running"),
        ("review_status", "required"),
        ("delivery_status", "review_required"),
        ("failure_cause", {"code": "failed"}),
        ("profile_id", "other"),
    ),
)
def test_terminal_run_contract_rejects_noncanonical_states(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        DraLiveRunEnvelopeV1.model_validate(run_payload() | {field: value})


@pytest.mark.parametrize("evidence", ([], [{}] * 101))
def test_evidence_collection_is_nonempty_and_bounded(
    evidence: list[object],
) -> None:
    with pytest.raises(ValidationError):
        DraLiveRunEnvelopeV1.model_validate(run_payload() | {"evidence": evidence})


def test_duplicate_evidence_and_wrong_ownership_fail_closed() -> None:
    payload = run_payload()
    row = deepcopy(payload["evidence"][0])  # type: ignore[index]
    with pytest.raises(ValidationError, match="dra_evidence_ids_not_unique"):
        DraLiveRunEnvelopeV1.model_validate(
            payload | {"evidence": [row, deepcopy(row)]}
        )

    for field in ("run_id", "segment_id"):
        invalid = DraLiveRunEnvelopeV1.model_validate(payload)
        bad_row = invalid.evidence[0].model_copy(update={field: f"wrong-{field}"})
        bad_run = invalid.model_copy(update={"evidence": (bad_row,)})
        with pytest.raises(
            DraLiveContractError, match="evidence_ownership_invalid"
        ):
            project(run_value=bad_run)


@pytest.mark.parametrize(
    "url",
    (
        "http://example.com/source",
        "https://user@example.com/source",
        "https://localhost/source",
        "https://host.local/source",
        "https://127.0.0.1/source",
        "https://10.0.0.1/source",
        "https://192.0.2.1/source",
        "https://[::1]/source",
    ),
)
def test_projection_rejects_unsafe_source_urls(url: str) -> None:
    run = DraLiveRunEnvelopeV1.model_validate(run_payload())
    row = run.evidence[0].model_copy(
        update={"source_url": url, "source_identity": url}
    )
    with pytest.raises(DraLiveContractError, match="source_url_invalid"):
        project(run_value=run.model_copy(update={"evidence": (row,)}))


@pytest.mark.parametrize(
    "substitution",
    (
        "https://EXAMPLE.com/contract-source-1",
        "https://example.com/contract-source-1/",
        "https://example.com/%63ontract-source-1",
        "https://example.com/contract-source-1?x=1",
        "https://example.com/contract-source-1#x",
        "https://example.com:443/contract-source-1",
        "https://xn--exmple-cua.com/contract-source-1",
    ),
)
def test_selection_requires_byte_exact_raw_url(substitution: str) -> None:
    projection = project()
    with pytest.raises(DraLiveContractError, match="source_selection_invalid"):
        select_cited_evidence(projection, substitution)


def test_selection_requires_exactly_one_cited_match() -> None:
    projection = project()
    raw_url = projection.evidence[0].source_url
    assert raw_url is not None
    selected = select_cited_evidence(projection, raw_url)
    assert selected.source_url == raw_url
    assert selected.run_id == projection.run_id
    assert selected.segment_id == projection.segment_id
    assert selected.verification_status == "unverified"

    duplicate = projection.model_copy(
        update={"evidence": (projection.evidence[0], projection.evidence[0])}
    )
    with pytest.raises(DraLiveContractError, match="source_selection_invalid"):
        select_cited_evidence(duplicate, raw_url)

    uncited = projection.evidence[0].model_copy(update={"citation_status": "uncited"})
    invalid = projection.model_copy(update={"evidence": (uncited,)})
    with pytest.raises(DraLiveContractError, match="source_selection_invalid"):
        select_cited_evidence(invalid, raw_url)


def test_source_identity_mismatch_fails_before_reduction() -> None:
    run = DraLiveRunEnvelopeV1.model_validate(run_payload())
    row = run.evidence[0].model_copy(
        update={"source_identity": f"{run.evidence[0].source_url}/"}
    )
    with pytest.raises(DraLiveContractError, match="source_identity_mismatch"):
        project(run_value=run.model_copy(update={"evidence": (row,)}))


def test_http_attestation_preserves_raw_url_before_exact_selection() -> None:
    projection = project()
    selected_url = projection.evidence[0].source_url
    assert selected_url is not None
    attestation = {
        "canonical_url": selected_url,
        "publisher": "Public Publisher",
        "institution": "Public Institution",
        "snapshot_date": "2026-07-25",
        "freshness_days": 365,
        "redistribution_class": "link_only",
        "evidence_class": "institutional",
        "logical_path": "sources/source.html",
        "snapshot_byte_length": 123,
        "snapshot_sha256": "a" * 64,
        "known_gaps": ["applicant_eligibility", "intake_availability"],
    }
    parsed = DraVerificationDecisionRequest.model_validate(
        {
            "schema_version": 1,
            "expected_case_revision": 1,
            "dra_evidence_id": projection.evidence[0].evidence_id,
            "decision": "approve",
            "reason": "Exact bounded source inspected.",
            "source_attestation": attestation,
        }
    )
    assert parsed.source_attestation is not None
    assert parsed.source_attestation.canonical_url == selected_url

    normalized_substitution = f"{selected_url}/"
    substituted = DraVerificationDecisionRequest.model_validate(
        parsed.model_dump()
        | {
            "source_attestation": attestation
            | {"canonical_url": normalized_substitution}
        }
    )
    assert substituted.source_attestation is not None
    assert substituted.source_attestation.canonical_url == normalized_substitution
    with pytest.raises(DraLiveContractError, match="source_selection_invalid"):
        select_cited_evidence(
            projection, substituted.source_attestation.canonical_url
        )


def test_verified_label_does_not_create_promotion_authority() -> None:
    run = DraLiveRunEnvelopeV1.model_validate(run_payload())
    row = run.evidence[0].model_copy(update={"verification_status": "verified"})
    projection = project(run_value=run.model_copy(update={"evidence": (row,)}))
    selected_url = projection.evidence[0].source_url
    assert selected_url is not None
    selected = select_cited_evidence(projection, selected_url)
    assert selected.verification_status == "verified"
    assert set(selected.model_dump()) == {
        "evidence_id",
        "run_id",
        "segment_id",
        "source_url",
        "source_identity",
        "retrieved_at",
        "citation_status",
        "verification_status",
    }


def test_artifact_and_result_identity_are_strict() -> None:
    payload = result_payload()
    artifact = dict(payload["artifact"])  # type: ignore[arg-type]
    for field, value in (
        ("kind", "other"),
        ("media_type", "application/json"),
        ("content_hash", "0" * 64),
        ("content", ""),
    ):
        with pytest.raises(ValidationError):
            DraCanonicalResultProjectionV1.model_validate(
                payload | {"artifact": artifact | {field: value}}
            )

    result = DraCanonicalResultProjectionV1.model_validate(payload)
    wrong_run = result.model_copy(update={"run_id": "wrong-run"})
    with pytest.raises(DraLiveContractError, match="result_ownership_invalid"):
        project(result_value=wrong_run)


def test_live_evidence_envelope_rejects_unknown_and_wrong_typed_fields() -> None:
    payload = run_payload()["evidence"][0]  # type: ignore[index]
    with pytest.raises(ValidationError):
        DraLiveEvidenceEnvelopeV1.model_validate(
            dict(payload) | {"unknown": "forbidden"}
        )
    with pytest.raises(ValidationError):
        DraLiveEvidenceEnvelopeV1.model_validate(
            dict(payload) | {"run_id": 42}
        )
