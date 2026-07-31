from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from night_voyager.evidence_loop.canonicalization import (
    CANONICALIZATION_ID,
    canonical_json_bytes,
)
from night_voyager.evidence_loop.dra_baseline import GovernedDraBaselineExportV1
from night_voyager.evidence_loop.receipt import seal_pre_registration_receipt

POST_REVEAL_ALLOWLIST = (
    "tests/fixtures/evidence_loop/holdout-dataset-v1.json",
    "tests/fixtures/evidence_loop/mke-capture-v2.json",
    "tests/fixtures/evidence_loop/slice0-receipt-v2.json",
)

_ROLES = (
    "independent-dataset-author-v3",
    "night-voyager-slice0-evaluator-v1",
    "independent-holdout-custodian-v3",
)

EVALUATOR_PATHS = (
    "src/night_voyager/evidence_loop/canonicalization.py",
    "src/night_voyager/evidence_loop/evaluator.py",
    "src/night_voyager/evidence_loop/freeze.py",
    "src/night_voyager/evidence_loop/mke_capture.py",
    "src/night_voyager/evidence_loop/receipt.py",
)

HARNESS_PATHS = (
    "scripts/evaluate_evidence_loop.py",
    "scripts/freeze_evidence_loop.py",
    "scripts/reveal_evidence_loop_holdouts.py",
    "scripts/verify_evidence_loop.py",
    "scripts/run_mke_lane.sh",
    "tests/unit/evidence_loop/test_canonicalization.py",
    "tests/unit/evidence_loop/test_cli_contracts.py",
    "tests/unit/evidence_loop/test_evaluator.py",
    "tests/unit/evidence_loop/test_freeze.py",
    "tests/unit/evidence_loop/test_mke_capture.py",
    "tests/unit/evidence_loop/test_receipt.py",
    "tests/integration/adapters/test_mke_v2_tagged_wheel.py",
    "tests/integration/evidence_loop/test_frozen_suite.py",
)

THRESHOLDS = {
    "query_count_per_case": 1,
    "max_search_pages": 4,
    "max_search_page_limit": 20,
    "max_evidence_reads": 32,
    "mcp_call_timeout_seconds": 10,
    "case_budget_seconds": 120,
    "combined_output_bytes_max": 1_048_576,
    "accepted_candidate_observations_max": 16,
    "determinism_fresh_process_runs": 3,
}

TERMINAL_MAPPING = {
    "confirmed": "incremental_value_confirmed",
    "exhaustive_miss": "no_incremental_value",
    "bounded_incomplete_or_unavailable": "inconclusive",
    "custody_hash_order_freeze_mutation_or_identity_drift": "evaluation_invalid",
}


@dataclass(frozen=True)
class PublicCommitmentValidation:
    author_revision: int
    roles: tuple[str, str, str]
    source_digests: tuple[str, ...]
    holdout_content_reachable: bool


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return cast(dict[str, object], value)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def _identity(path: Path, *, relative: str | None = None) -> dict[str, object]:
    return {
        "path": relative or path.name,
        "basename": path.name,
        "byte_length": path.stat().st_size,
        "sha256": _digest(path),
        "mode": _mode(path),
    }


def _validate_baseline_export(item: dict[str, Any]) -> None:
    export = GovernedDraBaselineExportV1.model_validate(item)
    advisor = export.advisor_verification.model_dump(mode="json")
    receipt_sha256 = advisor.pop("receipt_sha256")
    if hashlib.sha256(canonical_json_bytes(advisor)).hexdigest() != receipt_sha256:
        raise ValueError("governed baseline hash chain invalid")

    row = export.model_dump(mode="json")
    export_sha256 = row.pop("export_sha256")
    row_sha256 = row.pop("row_sha256")
    if (
        hashlib.sha256(export.typed_value.encode("utf-8")).hexdigest()
        != export.typed_value_sha256
        or hashlib.sha256(canonical_json_bytes(row)).hexdigest() != row_sha256
    ):
        raise ValueError("governed baseline hash chain invalid")
    if (
        hashlib.sha256(
            canonical_json_bytes({**row, "row_sha256": row_sha256})
        ).hexdigest()
        != export_sha256
    ):
        raise ValueError("governed baseline hash chain invalid")


def _validate_provider_peers(
    setup: Mapping[str, object],
    provider_locks: Mapping[str, object],
    *,
    source_manifest_sha256: str,
) -> None:
    producer_value = setup.get("producer")
    mke_lock_value = provider_locks.get("mke")
    dra_lock_value = provider_locks.get("dra")
    if not all(
        isinstance(value, dict)
        for value in (producer_value, mke_lock_value, dra_lock_value)
    ):
        raise ValueError("provider lock peer mismatch")
    producer = cast(dict[str, Any], producer_value)
    mke_lock = cast(dict[str, Any], mke_lock_value)
    dra_lock = cast(dict[str, Any], dra_lock_value)
    if not isinstance(producer.get("source_archive"), dict) or not isinstance(
        producer.get("dra_admission"), dict
    ):
        raise ValueError("provider lock peer mismatch")
    mke_archive = cast(dict[str, Any], producer.get("source_archive"))
    dra_admission = cast(dict[str, Any], producer.get("dra_admission"))
    if not isinstance(dra_admission.get("source_archive"), dict):
        raise ValueError("provider lock peer mismatch")
    dra_archive = cast(dict[str, Any], dra_admission.get("source_archive"))
    if (
        setup.get("source_manifest_sha256") != source_manifest_sha256
        or producer.get("tag_object") != mke_lock.get("tag_object")
        or producer.get("peeled_commit") != mke_lock.get("commit")
        or producer.get("wheel_sha256") != mke_lock.get("wheel_sha256")
        or mke_archive.get("basename")
        != mke_lock.get("a3_source_tree_archive_basename")
        or mke_archive.get("sha256")
        != mke_lock.get("a3_source_tree_archive_sha256")
        or dra_admission.get("tag_object") != dra_lock.get("tag_object")
        or dra_admission.get("peeled_commit") != dra_lock.get("commit")
        or dra_admission.get("profile_id") != dra_lock.get("profile_id")
        or dra_admission.get("profile_version") != dra_lock.get("profile_version")
        or dra_archive.get("basename")
        != dra_lock.get("source_archive_basename")
        or dra_archive.get("sha256") != dra_lock.get("source_archive_sha256")
    ):
        raise ValueError("provider lock peer mismatch")


def _matches_identity(path: Path, identity: Mapping[str, object]) -> bool:
    return bool(
        path.is_file()
        and path.stat().st_size == identity.get("byte_length")
        and _digest(path) == identity.get("sha256")
        and _mode(path) == identity.get("mode")
    )


def validate_frozen_checkout(
    receipt: Mapping[str, object],
    *,
    repo_root: Path,
    store_root: Path | None,
    current_head: str,
    current_tree: str,
    status_paths: Sequence[str],
    allowed_generated_paths: Sequence[str] = (),
) -> None:
    git_value = receipt.get("git")
    if not isinstance(git_value, dict):
        raise ValueError("frozen git identity invalid")
    git_identity = cast(dict[str, object], git_value)
    if git_identity != {
        "head": current_head,
        "tree": current_tree,
        "clean": True,
    }:
        raise ValueError("frozen git identity drift")
    if not set(status_paths).issubset(set(allowed_generated_paths)):
        raise ValueError("post-freeze write set invalid")

    for group_name in ("evaluator_paths", "harness_paths"):
        group_value = receipt.get(group_name)
        if not isinstance(group_value, list):
            raise ValueError("frozen path inventory invalid")
        for item in cast(list[object], group_value):
            if not isinstance(item, dict):
                raise ValueError("frozen path inventory invalid")
            identity = cast(dict[str, object], item)
            relative = identity.get("path")
            if (
                not isinstance(relative, str)
                or not _matches_identity(repo_root / relative, identity)
            ):
                raise ValueError("frozen path drift")

    for identity_name in (
        "provider_locks_identity",
        "source_manifest",
        "development_dataset",
        "governed_dra_baseline",
        "holdout_manifest",
    ):
        identity_value = receipt.get(identity_name)
        if identity_value is None:
            continue
        if not isinstance(identity_value, dict):
            raise ValueError("frozen input identity invalid")
        identity = cast(dict[str, object], identity_value)
        relative = identity.get("path")
        if (
            not isinstance(relative, str)
            or not _matches_identity(repo_root / relative, identity)
        ):
            raise ValueError("frozen input drift")

    if store_root is not None:
        sealed_store_value = receipt.get("sealed_store")
        if not isinstance(sealed_store_value, dict):
            raise ValueError("sealed store identity invalid")
        artifact_value = cast(dict[str, object], sealed_store_value).get("artifact")
        if not isinstance(artifact_value, dict):
            raise ValueError("sealed store identity invalid")
        artifact = cast(dict[str, object], artifact_value)
        basename = artifact.get("basename")
        if (
            not isinstance(basename, str)
            or not _matches_identity(store_root / basename, artifact)
        ):
            raise ValueError("sealed store artifact drift")


def scan_pre_reveal(
    repo_root: Path, *, environment: Mapping[str, str] | None = None
) -> dict[str, object]:
    visible_environment = environment if environment is not None else os.environ
    if any(
        "CUSTODY" in key.upper() and value
        for key, value in visible_environment.items()
    ):
        raise ValueError("custody environment reachable")
    present = [
        relative
        for relative in POST_REVEAL_ALLOWLIST
        if (repo_root / relative).exists()
    ]
    if present:
        raise ValueError("post-reveal generated file reachable before freeze")
    return {
        "passed": True,
        "custody_environment_reachable": False,
        "custody_root_mounted": False,
        "custody_root_indexed": False,
        "holdout_payload_reachable": False,
        "holdout_oracle_reachable": False,
        "answer_key_reachable": False,
        "generated_paths_present": [],
        "permitted_public_commitments_only": True,
    }


def validate_public_commitments(root: Path) -> PublicCommitmentValidation:
    manifest = _load_object(root / "holdout-manifest-v1.json")
    fragment = _load_object(root / "source-manifest-fragment-v1.json")
    roles = (
        manifest.get("dataset_author_id"),
        manifest.get("evaluator_id"),
        manifest.get("proposed_holdout_custodian_id"),
    )
    if manifest.get("author_revision") != 3 or roles != _ROLES:
        raise ValueError("revision three role identity mismatch")
    if manifest.get("rejected_pre_admission_revisions") != [
        {"author_revision": 1, "status": "rejected_pre_admission"},
        {"author_revision": 2, "status": "rejected_pre_admission"},
    ]:
        raise ValueError("rejected revision identity mismatch")
    if (
        manifest.get("holdout_content_included") is not False
        or manifest.get("oracle_content_included") is not False
    ):
        raise ValueError("holdout content must remain unreachable")

    sources_raw = fragment.get("sources")
    if not isinstance(sources_raw, list):
        raise ValueError("source identity mismatch")
    sources = cast(list[object], sources_raw)
    if len(sources) != 4:
        raise ValueError("source identity mismatch")
    digests: list[str] = []
    identities: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("source identity mismatch")
        typed_source = cast(dict[str, Any], source)
        relative = typed_source.get("relative_path")
        if not isinstance(relative, str):
            raise ValueError("source identity mismatch")
        posix = PurePosixPath(relative)
        if posix.is_absolute() or ".." in posix.parts:
            raise ValueError("source identity mismatch")
        path = root.joinpath(*posix.parts)
        digest = _digest(path)
        if (
            typed_source.get("media_type") != "application/pdf"
            or path.stat().st_size != typed_source.get("byte_length")
            or digest != typed_source.get("content_sha256")
        ):
            raise ValueError("source identity mismatch")
        identity = typed_source.get("evaluation_canonical_source_id")
        if not isinstance(identity, str) or identity in identities:
            raise ValueError("source identity mismatch")
        identities.add(identity)
        digests.append(digest)
    return PublicCommitmentValidation(
        author_revision=3,
        roles=_ROLES,
        source_digests=tuple(digests),
        holdout_content_reachable=False,
    )


def build_pre_registration_receipt(
    *,
    repo_root: Path,
    exact_head: str,
    exact_tree: str,
    store_receipt: Path,
    source_manifest: Path,
    development_dataset: Path,
    holdout_manifest: Path,
    dra_baseline: Path,
    environment: Mapping[str, str] | None = None,
) -> bytes:
    if len(exact_head) != 40 or len(exact_tree) != 40:
        raise ValueError("git identity invalid")
    public_validation = validate_public_commitments(source_manifest.parent)
    setup = _load_object(store_receipt)
    source = _load_object(source_manifest)
    development = _load_object(development_dataset)
    holdouts = _load_object(holdout_manifest)
    baseline = _load_object(dra_baseline)
    provider_locks_path = (
        repo_root / "tests/fixtures/evidence_loop/provider-locks-v1.json"
    )
    provider_locks = _load_object(provider_locks_path)
    _validate_provider_peers(
        setup,
        provider_locks,
        source_manifest_sha256=_digest(source_manifest),
    )

    if (
        setup.get("mutation_capability") != "closed_after_preparation"
        or setup.get("read_only_reopen_verified") is not True
        or _mode(store_receipt) != "0600"
    ):
        raise ValueError("sealed store receipt invalid")
    store_seal_value = setup.get("store_seal")
    if not isinstance(store_seal_value, dict):
        raise ValueError("sealed store receipt invalid")
    store_seal = cast(dict[str, Any], store_seal_value)
    if store_seal.get("lifecycle_state") != "sealed_read_only":
        raise ValueError("sealed store receipt invalid")
    store_path = store_receipt.parents[1] / "store" / "store.sqlite"
    store_files_value = store_seal.get("files")
    if not isinstance(store_files_value, list):
        raise ValueError("sealed store receipt invalid")
    store_files = cast(list[dict[str, Any]], store_files_value)
    if (
        len(store_files) != 1
        or not store_path.is_file()
        or _digest(store_path) != store_files[0].get("sha256")
        or store_path.stat().st_size != store_files[0].get("byte_length")
        or _mode(store_path) != "0400"
    ):
        raise ValueError("sealed store artifact drift")

    development_cases_value = development.get("cases")
    holdout_cases_value = holdouts.get("holdouts")
    if (
        not isinstance(development_cases_value, list)
        or not isinstance(holdout_cases_value, list)
    ):
        raise ValueError("case identity set invalid")
    development_cases = cast(list[object], development_cases_value)
    holdout_cases = cast(list[object], holdout_cases_value)
    if len(development_cases) != 4 or len(holdout_cases) != 4:
        raise ValueError("case identity set invalid")
    baseline_exports_value = baseline.get("exports")
    baseline_exports = (
        cast(list[object], baseline_exports_value)
        if isinstance(baseline_exports_value, list)
        else []
    )
    typed_baseline_exports = [
        cast(dict[str, Any], item)
        for item in baseline_exports
        if isinstance(item, dict)
    ]
    if (
        baseline.get("fixture_boundary")
        != {
            "nature": "deterministic_public_safe_synthetic_governed_fixture",
            "production_or_historical_user_receipt_claimed": False,
            "a2_projection_and_hash_contract_required": True,
        }
        or baseline.get("producer")
        != {
            "release": "v0.1.8",
            "tag_object": "f828606741f636bca7ddbb66244ca60019eaa3c8",
            "commit": "cb1f4660ee4ac7d81b04ffea014362e933487e61",
            "profile_id": "generic-strict-citation",
            "profile_version": "1",
        }
        or len(typed_baseline_exports) != 4
        or any(
            item.get("origin_kind") != "night_voyager_typed_governed_row"
            for item in typed_baseline_exports
        )
    ):
        raise ValueError("governed baseline invalid")
    for item in typed_baseline_exports:
        _validate_baseline_export(item)

    evaluator_paths = [
        _identity(repo_root / relative, relative=relative)
        for relative in EVALUATOR_PATHS
    ]
    harness_paths = [
        _identity(repo_root / relative, relative=relative)
        for relative in HARNESS_PATHS
    ]
    development_identities = [
        cast(dict[str, Any], item).get("identity") for item in development_cases
    ]
    holdout_identities = [
        {
            key: cast(dict[str, Any], item)[key]
            for key in (
                "holdout_id",
                "case_id",
                "case_revision",
                "query_id",
                "decision_dimension",
            )
        }
        for item in holdout_cases
    ]
    holdout_commitments = [
        {
            key: cast(dict[str, Any], item)[key]
            for key in (
                "holdout_id",
                "case_id",
                "case_revision",
                "query_id",
                "decision_dimension",
                "payload_byte_length",
                "payload_sha256",
                "oracle_byte_length",
                "oracle_sha256",
                "full_case_byte_length",
                "full_case_sha256",
            )
        }
        for item in holdout_cases
    ]
    source_rows_value = source.get("sources")
    if not isinstance(source_rows_value, list):
        raise ValueError("eligible source matrix invalid")
    source_rows = cast(list[object], source_rows_value)
    if len(source_rows) != 4:
        raise ValueError("eligible source matrix invalid")

    body: dict[str, Any] = {
        "schema_version": "night-voyager.evidence-loop-pre-registration.v2",
        "canonicalization_id": CANONICALIZATION_ID,
        "git": {"head": exact_head, "tree": exact_tree, "clean": True},
        "roles": {
            "dataset_author_id": public_validation.roles[0],
            "evaluator_implementer_id": public_validation.roles[1],
            "holdout_custodian_id": public_validation.roles[2],
        },
        "rejected_pre_admission_author_revisions": [1, 2],
        "provider_locks": provider_locks,
        "provider_locks_identity": _identity(
            provider_locks_path,
            relative="tests/fixtures/evidence_loop/provider-locks-v1.json",
        ),
        "setup_receipt": _identity(store_receipt),
        "sealed_store": {
            "artifact": _identity(store_path),
            "tree_sha256": store_seal["tree_sha256"],
            "active_set_fingerprint": setup["active_set_fingerprint"],
            "mutation_capability": setup["mutation_capability"],
            "read_only_reopen_verified": True,
            "sealed_evaluation_window_started": True,
        },
        "source_manifest": _identity(
            source_manifest,
            relative="tests/fixtures/evidence_loop/source-manifest-v1.json",
        ),
        "eligible_source_matrix": source_rows,
        "development_dataset": _identity(
            development_dataset,
            relative="tests/fixtures/evidence_loop/development-dataset-v1.json",
        ),
        "governed_dra_baseline": _identity(
            dra_baseline,
            relative="tests/fixtures/evidence_loop/dra-governed-baseline-v1.json",
        ),
        "holdout_manifest": _identity(
            holdout_manifest,
            relative="tests/fixtures/evidence_loop/holdout-manifest-v1.json",
        ),
        "case_query_identities": [
            *development_identities,
            *holdout_identities,
        ],
        "holdout_commitments": holdout_commitments,
        "evaluator_paths": evaluator_paths,
        "harness_paths": harness_paths,
        "environment": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "python_executable_basename": Path(sys.executable).name,
            "uv_lock_sha256": _digest(repo_root / "uv.lock"),
        },
        "thresholds": THRESHOLDS,
        "metric_families": {
            "mechanism": [
                "producer_identity_closure",
                "retrieval_completeness",
                "evidence_byte_reconstruction",
                "canonical_deduplication",
                "explicit_conflict_retention",
                "fresh_process_determinism",
            ],
            "target": [
                "novel_source_bound_units",
                "source_access_gain",
                "extraction_gain",
                "pre_registered_gap_closure",
                "decision_dimension_coverage",
                "advisor_rubric_relevance",
            ],
            "guardrail_veto": [
                "zero_business_mutation",
                "zero_instruction_execution",
                "zero_private_or_moving_source",
                "zero_freeze_violation",
                "zero_generalization_claim",
                "zero_decoy_novelty",
                "explicit_conflict_retention",
            ],
        },
        "terminal_mapping": TERMINAL_MAPPING,
        "pre_reveal_scan": scan_pre_reveal(
            repo_root, environment=environment
        ),
        "reveal_procedure_id": "nv.slice0.one-way-reveal.v1",
        "post_reveal_generated_file_allowlist": list(POST_REVEAL_ALLOWLIST),
    }
    return seal_pre_registration_receipt(body)
