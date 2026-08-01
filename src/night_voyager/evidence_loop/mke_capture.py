"""Bounded one-shot MKE capture for the frozen Slice 0 evaluator."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

from night_voyager.evidence_loop.canonicalization import (
    canonical_json_bytes,
    canonical_sha256,
)
from night_voyager.evidence_loop.native_store import (
    NativeStoreValidationError,
    ToolCaller,
    collect_search_pages,
)


def _object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NativeStoreValidationError(code)
    return cast(dict[str, Any], value)


async def _read_complete_text(
    call_tool: ToolCaller,
    descriptor: Mapping[str, Any],
    *,
    authority_snapshot: Mapping[str, Any],
    reads_remaining: list[int],
) -> tuple[str, int]:
    evidence_id = descriptor.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise NativeStoreValidationError("capture_descriptor_invalid")
    request: dict[str, Any] = {"evidence_id": evidence_id, "max_bytes": 16384}
    seen: set[str] = set()
    content = bytearray()
    calls = 0
    while reads_remaining[0] > 0:
        reads_remaining[0] -= 1
        calls += 1
        body = _object(
            await call_tool("read_evidence_v1", {"request": request}),
            "capture_read_invalid",
        )
        if body.get("ok") is not True or body.get("evidence") != descriptor:
            raise NativeStoreValidationError("capture_read_invalid")
        if body.get("authority_snapshot") != authority_snapshot:
            raise NativeStoreValidationError("capture_read_authority_drift")
        chunk = _object(body.get("content"), "capture_read_invalid")
        text = chunk.get("text")
        encoded = text.encode("utf-8") if isinstance(text, str) else None
        if (
            encoded is None
            or chunk.get("content_trust") != "untrusted_evidence"
            or chunk.get("offset_bytes") != len(content)
            or chunk.get("returned_utf8_bytes") != len(encoded)
        ):
            raise NativeStoreValidationError("capture_read_invalid")
        content.extend(encoded)
        if body.get("complete") is True:
            if body.get("next_cursor") is not None:
                raise NativeStoreValidationError("capture_read_cursor_invalid")
            if hashlib.sha256(content).hexdigest() != str(
                descriptor.get("evidence_text_sha256")
            ).removeprefix("sha256:") or len(content) != descriptor.get("original_utf8_bytes"):
                raise NativeStoreValidationError("capture_read_terminal_invalid")
            try:
                return content.decode("utf-8"), calls
            except UnicodeDecodeError as error:
                raise NativeStoreValidationError("capture_read_terminal_invalid") from error
        cursor = body.get("next_cursor")
        if (
            body.get("complete") is not False
            or not isinstance(cursor, str)
            or not cursor
            or cursor in seen
        ):
            raise NativeStoreValidationError("capture_read_cursor_invalid")
        seen.add(cursor)
        request = {"cursor": cursor}
    raise NativeStoreValidationError("capture_read_limit")


def _eligible_sources(
    payload: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    value = payload.get("eligible_mke_sources")
    if not isinstance(value, list):
        raise NativeStoreValidationError("capture_source_set_invalid")
    sources: dict[str, dict[str, Any]] = {}
    for item in cast(list[object], value):
        source = _object(item, "capture_source_set_invalid")
        fingerprint = source.get("expected_content_fingerprint")
        if not isinstance(fingerprint, str) or fingerprint in sources:
            raise NativeStoreValidationError("capture_source_set_invalid")
        sources[fingerprint] = source
    return sources


def verify_capture_artifact(content: bytes) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("capture artifact invalid") from error
    if not isinstance(value, dict):
        raise ValueError("capture artifact invalid")
    artifact = cast(dict[str, Any], value)
    digest = artifact.pop("capture_sha256", None)
    cases = artifact.get("cases")
    if (
        digest != hashlib.sha256(canonical_json_bytes(artifact)).hexdigest()
        or artifact.get("schema_version") != "night-voyager.evidence-loop-mke-capture.v2"
        or artifact.get("canonicalization_id") != "night-voyager.slice0.compact-sorted-utf8-lf.v1"
        or not isinstance(cases, list)
        or len(cast(list[object], cases)) != 4
    ):
        raise ValueError("capture artifact invalid")
    return artifact


def validate_capture_for_dataset(
    capture: Mapping[str, Any],
    dataset: Mapping[str, Any],
    *,
    expected_active_set_fingerprint: str,
    expected_store_tree_sha256: str | None = None,
) -> None:
    cases_value = dataset.get("cases")
    captured_value = capture.get("cases")
    if not isinstance(cases_value, list) or not isinstance(captured_value, list):
        raise ValueError("capture case set invalid")
    cases = cast(list[object], cases_value)
    captured_cases = cast(list[object], captured_value)
    if len(cases) != 4 or len(captured_cases) != 4:
        raise ValueError("capture case set invalid")
    expected_identities: list[dict[str, Any]] = []
    actual_identities: list[dict[str, Any]] = []
    for index, (case_value, captured_value) in enumerate(zip(cases, captured_cases, strict=True)):
        case = _object(case_value, "capture case set invalid")
        payload = _object(case.get("payload"), "capture case set invalid")
        expected_identity = _object(payload.get("identity"), "capture case set invalid")
        captured = _object(captured_value, "capture case set invalid")
        actual_identity = _object(captured.get("identity"), "capture case identity invalid")
        expected_identities.append(expected_identity)
        actual_identities.append(actual_identity)
        if actual_identity != expected_identity:
            raise ValueError(f"capture case identity order invalid at {index}")

        selection = _object(captured.get("selection"), "capture selection invalid")
        if (
            selection.get("status") != "complete"
            or selection.get("authority_state") != "active"
            or selection.get("acquisition_count") != 1
            or selection.get("search_limit") != 20
            or not isinstance(selection.get("search_pages"), int)
            or not 0 <= selection["search_pages"] <= 4
            or not isinstance(selection.get("evidence_reads"), int)
            or not 0 <= selection["evidence_reads"] <= 32
            or selection.get("tool_calls") != ["search_library_v2", "read_evidence_v1"]
            or not isinstance(selection.get("combined_output_bytes"), int)
            or not 0 <= selection["combined_output_bytes"] <= 1_048_576
            or not isinstance(selection.get("mcp_call_seconds_max"), (int, float))
            or selection["mcp_call_seconds_max"] > 10
            or not isinstance(selection.get("case_seconds"), (int, float))
            or selection["case_seconds"] > 120
        ):
            raise ValueError("capture selection invalid")
        if captured.get("active_set_fingerprint") != expected_active_set_fingerprint:
            raise ValueError("capture active set invalid")

        eligible_value = payload.get("eligible_mke_sources")
        observations_value = captured.get("observations")
        if not isinstance(eligible_value, list) or not isinstance(observations_value, list):
            raise ValueError("capture source set invalid")
        eligible_sources = {
            str(_object(item, "capture source set invalid").get("dataset_source_id"))
            for item in cast(list[object], eligible_value)
        }
        observed_sources = [
            str(_object(item, "capture source set invalid").get("dataset_source_id"))
            for item in cast(list[object], observations_value)
        ]
        if (
            len(observed_sources) != len(set(observed_sources))
            or set(observed_sources) != eligible_sources
            or any(
                _object(item, "capture source set invalid").get("content_trust")
                != "untrusted_evidence"
                for item in cast(list[object], observations_value)
            )
        ):
            raise ValueError("capture source set invalid")
        guards = _object(captured.get("guardrails"), "capture guardrails invalid")
        if set(guards) != {
            "night_voyager_business_mutation",
            "filesystem_mutation",
            "database_mutation",
            "instruction_executed",
            "promotion_attempted",
            "human_authority_granted",
        } or any(guards.values()):
            raise ValueError("capture guardrails invalid")
        if expected_store_tree_sha256 is not None:
            proof = _object(
                captured.get("guardrail_proof"),
                "capture guardrail proof invalid",
            )
            if (
                proof.get("immutable_readback_verified") is not True
                or proof.get("runtime_identity_verified_before_capture") is not True
                or proof.get("allowed_read_tools_only") is not True
                or proof.get("store_tree_sha256")
                != expected_store_tree_sha256
            ):
                raise ValueError("capture guardrail proof invalid")
    identity_keys = [
        (
            identity.get("holdout_id"),
            identity.get("case_id"),
            identity.get("case_revision"),
            identity.get("query_id"),
            identity.get("decision_dimension"),
        )
        for identity in expected_identities
    ]
    if len(set(identity_keys)) != 4 or actual_identities != expected_identities:
        raise ValueError("capture case identity set invalid")


async def capture_case(
    payload: Mapping[str, Any],
    *,
    call_tool: ToolCaller,
    source_manifest: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Capture one Case/query without interpreting retrieved instructions."""

    identity = _object(payload.get("identity"), "capture_identity_invalid")
    request = _object(payload.get("mke_request"), "capture_request_invalid")
    query = request.get("query")
    if (
        not isinstance(query, str)
        or not query
        or len(query.encode("utf-8")) > 512
        or request.get("limit") != 20
    ):
        raise NativeStoreValidationError("capture_request_invalid")
    gap = _object(payload.get("pre_registered_gap"), "capture_gap_invalid")
    expected_value = gap.get("expected_value")
    if not isinstance(expected_value, str) or not expected_value:
        raise NativeStoreValidationError("capture_gap_invalid")

    manifest_by_dataset = {
        str(source.get("dataset_source_id")): source for source in source_manifest
    }
    eligible = _eligible_sources(payload)
    search_calls = 0

    async def counted(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        nonlocal search_calls
        if tool == "search_library_v2":
            search_calls += 1
        return await call_tool(tool, arguments)

    search = await collect_search_pages(
        counted,
        query=query,
        limit=20,
        max_pages=4,
    )
    observation = _object(
        search.authority_snapshot.get("observation"),
        "capture_authority_invalid",
    )
    active_set_fingerprint = search.authority_snapshot.get("active_set_fingerprint")
    if (
        observation.get("library_id") != "local"
        or observation.get("state") != "active"
        or not isinstance(active_set_fingerprint, str)
        or not active_set_fingerprint.startswith("sha256:")
    ):
        raise NativeStoreValidationError("capture_authority_invalid")
    reads_remaining = [32]
    units: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for match in search.matches:
        descriptor = _object(match.get("evidence"), "capture_descriptor_invalid")
        fingerprint = descriptor.get("content_fingerprint")
        if not isinstance(fingerprint, str) or fingerprint not in eligible:
            continue
        expected = eligible[fingerprint]
        dataset_source_id = str(expected.get("dataset_source_id"))
        manifest = manifest_by_dataset.get(dataset_source_id)
        if manifest is None or dataset_source_id in seen_sources:
            raise NativeStoreValidationError("capture_source_set_invalid")
        seen_sources.add(dataset_source_id)
        required = {
            "publication_revision": expected.get("expected_publication_revision"),
            "content_fingerprint": expected.get("expected_content_fingerprint"),
            "evidence_text_sha256": expected.get("expected_evidence_text_sha256"),
            "original_utf8_bytes": expected.get("expected_original_utf8_bytes"),
            "locator": expected.get("expected_locator"),
        }
        if any(descriptor.get(key) != value for key, value in required.items()):
            raise NativeStoreValidationError("capture_descriptor_invalid")
        if any(
            not isinstance(descriptor.get(key), str) or not descriptor[key]
            for key in ("source_id", "publication_id", "run_id", "evidence_id")
        ):
            raise NativeStoreValidationError("capture_trace_identity_invalid")

        text, read_calls = await _read_complete_text(
            counted,
            descriptor,
            authority_snapshot=search.authority_snapshot,
            reads_remaining=reads_remaining,
        )
        encoded = text.encode("utf-8")
        selected = expected_value.encode("utf-8")
        start = encoded.find(selected)
        accepted = start >= 0
        evidence_projection = {
            "evaluation_canonical_source_id": expected.get("evaluation_canonical_source_id"),
            "locator": descriptor["locator"],
            "selected_range": {
                "start_utf8_byte": max(start, 0),
                "end_utf8_byte": max(start, 0) + (len(selected) if accepted else 0),
            },
            "selected_bytes_sha256": hashlib.sha256(selected if accepted else b"").hexdigest(),
            "terminal_text_sha256": str(descriptor["evidence_text_sha256"]).removeprefix("sha256:"),
        }
        evidence_id = canonical_sha256(evidence_projection)
        observation = {
            "dataset_source_id": dataset_source_id,
            "evaluation_canonical_source_id": expected.get("evaluation_canonical_source_id"),
            "evaluation_canonical_evidence_id": evidence_id,
            "source_id": descriptor["source_id"],
            "publication_id": descriptor["publication_id"],
            "publication_revision": descriptor["publication_revision"],
            "run_id": descriptor["run_id"],
            "evidence_id": descriptor["evidence_id"],
            "locator": descriptor["locator"],
            "terminal_text_sha256": evidence_projection["terminal_text_sha256"],
            "selected_range": evidence_projection["selected_range"],
            "selected_bytes_sha256": evidence_projection["selected_bytes_sha256"],
            "read_calls": read_calls,
            "content_trust": "untrusted_evidence",
            "accepted": accepted,
        }
        observations.append(observation)
        if accepted:
            units.append(
                {
                    "dataset_source_id": dataset_source_id,
                    "evaluation_canonical_source_id": expected.get(
                        "evaluation_canonical_source_id"
                    ),
                    "evaluation_canonical_evidence_id": evidence_id,
                    "decision_dimension": identity.get("decision_dimension"),
                    "fact_key": gap.get("fact_key"),
                    "value": expected_value,
                    "provenance_paths": [f"mke:{descriptor['evidence_id']}"],
                    "access_kind": (
                        "extraction"
                        if any(
                            entry.get("sha256") == manifest.get("content_sha256")
                            for entry in cast(
                                list[dict[str, Any]],
                                _object(
                                    payload.get("control"),
                                    "capture_control_invalid",
                                ).get("source_pack_entries", []),
                            )
                        )
                        else "source_access"
                    ),
                    "origin_kind": "untrusted_evidence",
                    "content_trust": "untrusted_evidence",
                }
            )
    return {
        "identity": identity,
        "selection": {
            "status": "complete",
            "authority_state": "active",
            "acquisition_count": 1,
            "search_pages": search_calls,
            "search_limit": 20,
            "evidence_reads": 32 - reads_remaining[0],
            "tool_calls": ["search_library_v2", "read_evidence_v1"],
            "combined_output_bytes": 0,
            "mcp_call_seconds_max": 0,
            "case_seconds": 0,
        },
        "mke_units": units,
        "observations": observations,
        "active_set_fingerprint": active_set_fingerprint,
        "guardrail_observations": {
            "allowed_read_tools_only": True,
            "retrieved_content_treated_as_untrusted_data": True,
            "authority_actions_emitted": 0,
        },
    }
