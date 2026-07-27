from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

import night_voyager.dra.live_projection as live_projection
from night_voyager.dra.fixtures import (
    build_fixture_candidate_import,
    load_live_closure_scenario,
)
from night_voyager.dra.live_fakes import ScenarioDraLiveTransport
from night_voyager.dra.live_models import (
    DraLiveEvidenceEnvelopeV1,
    DraLiveRunEnvelopeV1,
    DraLiveScenarioV2,
)
from night_voyager.dra.live_projection import (
    DraLiveContractError,
    DraStrictLiveRunEnvelopeV2,
    project_terminal_result,
    select_cited_evidence,
)
from night_voyager.dra.models import (
    DraCanonicalArtifactInputV1,
    DraCanonicalResultProjectionV1,
    DraObservedProfileManifestV1,
    DraProducerPinV2,
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
    payload = cast(dict[str, object], scenario.status.model_dump(mode="json"))
    payload["evidence"] = [
        cast(dict[str, object], item.model_dump(mode="json"))
        for item in scenario.evidence
    ]
    return payload


def evidence_payload() -> dict[str, object]:
    value = run_payload()["evidence"]
    assert isinstance(value, list)
    rows = cast(list[object], value)
    first = rows[0]
    assert isinstance(first, dict)
    return cast(dict[str, object], first)


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
    assert isinstance(fake.run, DraLiveRunEnvelopeV1)
    assert fake.run.model_dump(
        mode="json", exclude_computed_fields=True
    ) == run_payload()
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


def test_strict_terminal_projection_binds_profile_manifest_and_local_pin() -> None:
    project_strict = getattr(
        live_projection, "project_strict_terminal_result", None
    )
    assert project_strict is not None
    scenario = DraLiveScenarioV2.model_validate_json(
        Path("fixtures/dra/live-closure-scenario-v2.json").read_bytes()
    )
    fake = ScenarioDraLiveTransport(scenario)
    assert isinstance(fake.run, DraStrictLiveRunEnvelopeV2)
    strict = project_strict(
        DraRunAcceptanceV1(
            thread_id=scenario.status.thread_id,
            run_id=scenario.status.run_id,
            segment_id=scenario.status.segment_id,
            idempotent_replay=False,
        ),
        fake.run,
        fake.result,
        scenario.producer,
        scenario.request_identity,
        scenario.profile_manifest,
    )
    assert strict.consumer_identity.producer == scenario.producer
    assert strict.consumer_identity.request == scenario.request_identity
    assert strict.consumer_identity.observed_profile == scenario.profile_manifest


@pytest.mark.parametrize(
    "failure",
    (
        "returned_profile",
        "manifest_version",
        "proof_schema",
        "status_run",
        "result_run",
    ),
)
def test_strict_terminal_projection_rejects_identity_counterfactuals(
    failure: str,
) -> None:
    scenario = DraLiveScenarioV2.model_validate_json(
        Path("fixtures/dra/live-closure-scenario-v2.json").read_bytes()
    )
    fake = ScenarioDraLiveTransport(scenario)
    assert isinstance(fake.run, DraStrictLiveRunEnvelopeV2)
    run = fake.run
    result = fake.result
    producer = scenario.producer
    observed = scenario.profile_manifest
    if failure == "returned_profile":
        run = run.model_copy(update={"profile_id": "generic"})
    elif failure == "manifest_version":
        observed = DraObservedProfileManifestV1.model_construct(
            schema_version=(
                "night-voyager.dra-observed-profile-manifest.v1"
            ),
            profile_id="generic-strict-citation",
            profile_version="2",
        )
    elif failure == "proof_schema":
        producer_payload = scenario.producer.model_dump(by_alias=False)
        producer_payload["proof_schema"] = "wrong-proof-schema"
        producer = DraProducerPinV2.model_construct(**producer_payload)
    elif failure == "status_run":
        run = run.model_copy(update={"run_id": "wrong-run"})
    else:
        result = result.model_copy(update={"run_id": "wrong-run"})
    with pytest.raises(DraLiveContractError):
        live_projection.project_strict_terminal_result(
            DraRunAcceptanceV1(
                thread_id=scenario.status.thread_id,
                run_id=scenario.status.run_id,
                segment_id=scenario.status.segment_id,
                idempotent_replay=False,
            ),
            run,
            result,
            producer,
            scenario.request_identity,
            observed,
        )


@pytest.mark.parametrize("failure", ("missing_url", "zero_cited"))
def test_strict_selection_requires_one_cited_url_in_canonical_artifact(
    failure: str,
) -> None:
    scenario = DraLiveScenarioV2.model_validate_json(
        Path("fixtures/dra/live-closure-scenario-v2.json").read_bytes()
    )
    fake = ScenarioDraLiveTransport(scenario)
    assert isinstance(fake.run, DraStrictLiveRunEnvelopeV2)
    projection = live_projection.project_strict_terminal_result(
        DraRunAcceptanceV1(
            thread_id=scenario.status.thread_id,
            run_id=scenario.status.run_id,
            segment_id=scenario.status.segment_id,
            idempotent_replay=False,
        ),
        fake.run,
        fake.result,
        scenario.producer,
        scenario.request_identity,
        scenario.profile_manifest,
    )
    if failure == "missing_url":
        content = "# Synthetic Strict Research Report\n\nSource omitted."
        projection = projection.model_copy(
            update={
                "artifact": DraCanonicalArtifactInputV1(
                    artifact_id="research-report.md",
                    kind="research_report_markdown",
                    media_type="text/markdown",
                    content=content,
                    content_hash=hashlib.sha256(
                        content.encode()
                    ).hexdigest(),
                )
            }
        )
    else:
        projection = projection.model_copy(
            update={
                "evidence": (
                    projection.evidence[0].model_copy(
                        update={"citation_status": "uncited"}
                    ),
                )
            }
        )
    with pytest.raises(
        DraLiveContractError, match="source_selection_invalid"
    ):
        live_projection.select_strict_cited_evidence(
            projection, "https://example.com/contract-source-1"
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("execution_status", "running"),
        ("review_status", "required"),
        ("delivery_status", "review_required"),
        (
            "failure_cause",
            {
                "schema_version": "dra.run-failure-cause.v1",
                "observation_status": "observed",
                "phase": "execution",
                "code": "execution_error",
                "recorded_at": "2026-07-25T00:00:00Z",
            },
        ),
    ),
)
def test_terminal_run_contract_rejects_noncanonical_states(
    field: str, value: object
) -> None:
    run = DraLiveRunEnvelopeV1.model_validate(run_payload() | {field: value})
    with pytest.raises(DraLiveContractError, match="terminal_state_invalid"):
        project(run_value=run)


def test_run_envelope_rejects_non_generic_profile() -> None:
    with pytest.raises(ValidationError):
        DraLiveRunEnvelopeV1.model_validate(
            run_payload() | {"profile_id": "other"}
        )


def test_evidence_collection_is_nonempty_and_bounded() -> None:
    evidence: list[object] = [{} for _ in range(101)]
    with pytest.raises(ValidationError):
        DraLiveRunEnvelopeV1.model_validate(run_payload() | {"evidence": evidence})


def test_empty_terminal_evidence_fails_projection() -> None:
    run = DraLiveRunEnvelopeV1.model_validate(run_payload() | {"evidence": []})
    with pytest.raises(DraLiveContractError, match="evidence_projection_invalid"):
        project(run_value=run)


def test_duplicate_evidence_and_wrong_ownership_fail_closed() -> None:
    payload = run_payload()
    row = deepcopy(evidence_payload())
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
    artifact_value = payload["artifact"]
    assert isinstance(artifact_value, dict)
    artifact = cast(dict[str, object], artifact_value)
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
    payload = evidence_payload()
    with pytest.raises(ValidationError):
        DraLiveEvidenceEnvelopeV1.model_validate(
            payload | {"unknown": "forbidden"}
        )
    with pytest.raises(ValidationError):
        DraLiveEvidenceEnvelopeV1.model_validate(
            payload | {"run_id": 42}
        )
