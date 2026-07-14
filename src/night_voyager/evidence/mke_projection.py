"""Pure projection from strict MKE responses to untrusted Night Voyager candidates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from uuid import UUID, uuid5

from night_voyager.evidence.mke_contract import (
    ActivePublicationObservationV1,
    AskLibrarySuccessV1,
    EvidenceRefV1,
    SearchLibrarySuccessV1,
)
from night_voyager.evidence.mke_models import (
    CandidateEvidence,
    CandidateStoreNoMatch,
    EvidenceQuery,
    M4BManifestV1,
    M4BSourceEntryV1,
    MkeConsumerError,
    MkeTraceV1,
)
from night_voyager.planning.models import EvidenceAuthority, EvidenceRef

M4B_EVIDENCE_NAMESPACE = UUID("bb82fb65-face-585c-90df-ec155d9580f3")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_active(observation: ActivePublicationObservationV1) -> None:
    if observation.state == "empty":
        raise MkeConsumerError("mke_store_empty")
    if observation.state == "no_active_publication":
        raise MkeConsumerError("mke_no_active_publication")


def _require_query_manifest(
    query: EvidenceQuery, manifest: M4BManifestV1
) -> M4BSourceEntryV1:
    if len(manifest.sources) != 1:
        raise MkeConsumerError("mke_manifest_mapping_failed")
    source = manifest.sources[0]
    if (
        query.organization_id != manifest.organization_id
        or query.source_pack_id != manifest.source_pack_id
        or query.source_pack_version != manifest.source_pack_version
        or query.claim != source.claim
    ):
        raise MkeConsumerError("mke_manifest_mapping_failed")
    if query.evidence_role is not source.evidence_role:
        raise MkeConsumerError("mke_evidence_role_mismatch")
    return source


def _store_no_match(query: EvidenceQuery) -> CandidateStoreNoMatch:
    return CandidateStoreNoMatch(
        schema_version="night_voyager.candidate_store_no_match.v1",
        organization_id=query.organization_id,
        source_pack_id=query.source_pack_id,
        source_pack_version=query.source_pack_version,
        claim=query.claim,
        evidence_role=query.evidence_role,
        query_sha256=hashlib.sha256(query.query.encode("utf-8")).hexdigest(),
        observation_state="active",
        projection_status="active_store_no_match",
    )


def _map_source(
    evidence: EvidenceRefV1, manifest: M4BManifestV1
) -> M4BSourceEntryV1:
    fingerprint = evidence.content_fingerprint.removeprefix("sha256:")
    matches = [source for source in manifest.sources if source.sha256 == fingerprint]
    if len(matches) != 1:
        raise MkeConsumerError("mke_manifest_mapping_failed")
    return matches[0]


def _require_locator(
    query: EvidenceQuery, source: M4BSourceEntryV1, evidence: EvidenceRefV1
) -> None:
    if evidence.locator.kind not in query.allowed_locator_kinds:
        raise MkeConsumerError("mke_locator_mismatch")
    if evidence.locator not in source.allowed_locators:
        raise MkeConsumerError("mke_locator_mismatch")


def _project_evidence(
    query: EvidenceQuery,
    manifest: M4BManifestV1,
    evidence: EvidenceRefV1,
) -> CandidateEvidence:
    declared_source = _require_query_manifest(query, manifest)
    mapped_source = _map_source(evidence, manifest)
    if mapped_source.entry_id != declared_source.entry_id:
        raise MkeConsumerError("mke_manifest_mapping_failed")
    _require_locator(query, mapped_source, evidence)
    identity = {
        "organization_id": str(query.organization_id),
        "source_pack_id": str(query.source_pack_id),
        "source_pack_version": query.source_pack_version,
        "source_entry_id": str(mapped_source.entry_id),
        "source_sha256": mapped_source.sha256,
        "claim": query.claim,
        "evidence_role": query.evidence_role.value,
        "locator": evidence.locator.model_dump(mode="json"),
        "selected_text_sha256": hashlib.sha256(evidence.text.encode("utf-8")).hexdigest(),
    }
    evidence_ref = EvidenceRef(
        schema_version=1,
        organization_id=query.organization_id,
        evidence_id=uuid5(M4B_EVIDENCE_NAMESPACE, canonical_json(identity)),
        claim=query.claim,
        source_pack_id=query.source_pack_id,
        source_pack_version=query.source_pack_version,
        source_entry_id=mapped_source.entry_id,
        source_sha256=mapped_source.sha256,
        authority=EvidenceAuthority.UNTRUSTED_CANDIDATE,
    )
    return CandidateEvidence(
        schema_version="night_voyager.candidate_evidence.v1",
        source_pack_id=query.source_pack_id,
        source_pack_version=query.source_pack_version,
        source_entry_id=mapped_source.entry_id,
        claim=query.claim,
        evidence_role=query.evidence_role,
        locator=evidence.locator,
        selected_text=evidence.text,
        trace=MkeTraceV1(
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            publication_id=evidence.publication_id,
            publication_revision=evidence.publication_revision,
            run_id=evidence.run_id,
        ),
        projection_status="manifest_mapped",
        evidence_ref=evidence_ref,
    )


def _project_results(
    query: EvidenceQuery,
    manifest: M4BManifestV1,
    observation: ActivePublicationObservationV1,
    results: Sequence[EvidenceRefV1],
) -> CandidateEvidence | CandidateStoreNoMatch:
    _require_active(observation)
    _require_query_manifest(query, manifest)
    if not results:
        return _store_no_match(query)
    if len(results) != 1:
        raise MkeConsumerError("mke_manifest_mapping_failed")
    return _project_evidence(query, manifest, results[0])


def project_search_candidate(
    query: EvidenceQuery,
    manifest: M4BManifestV1,
    response: SearchLibrarySuccessV1,
) -> CandidateEvidence | CandidateStoreNoMatch:
    return _project_results(query, manifest, response.observation, response.results)


def project_ask_candidate(
    query: EvidenceQuery,
    manifest: M4BManifestV1,
    response: AskLibrarySuccessV1,
) -> CandidateEvidence | CandidateStoreNoMatch:
    return _project_results(query, manifest, response.observation, response.evidence)


def require_paired_candidate(
    search: CandidateEvidence,
    ask: CandidateEvidence,
) -> CandidateEvidence:
    paired = (
        search.evidence_ref.source_sha256 == ask.evidence_ref.source_sha256
        and search.trace.publication_id == ask.trace.publication_id
        and search.trace.publication_revision == ask.trace.publication_revision
        and search.trace.run_id == ask.trace.run_id
        and search.locator == ask.locator
        and search.selected_text == ask.selected_text
    )
    if not paired:
        raise MkeConsumerError("mke_snapshot_pair_mismatch")
    return search
