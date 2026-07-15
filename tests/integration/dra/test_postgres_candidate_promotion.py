# ruff: noqa: E501
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.dra.fixtures import build_fixture_candidate_import

pytestmark = pytest.mark.database
ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000003")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PACK = UUID("50000000-0000-0000-0000-000000000001")
MANIFEST_SHA = "84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28"
RAW_MANIFEST_SHA = "5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25"
SOURCE_SHA = "87e314e801dca1aeaf9b751c149c53629a4cf23ee04698939fdc87def5a90a13"


def stable_hash(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()

IMPORT_SQL = """
SELECT * FROM app.import_dra_research_candidate(
  :org,:actor,:case,:candidate,1,'v0.1.3',
  '87b2a8e335385eb865086f7a69fe2b190567cfa2','dra.downstream-consumer.v1',
  'cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157',
  'generic',:identity_hash,:run_id,'research-report.md','research_report_markdown',
  'text/markdown',:artifact_bytes,:artifact_sha,CAST(:evidence AS jsonb),
  :request_hash,:key_hash)
"""

VERIFY_SQL = """
SELECT * FROM app.verify_and_promote_dra_candidate(
  :org,:actor,:case,:candidate,1,:dra_evidence_id,:decision,:reason,
  :source_url,:publisher,:institution,:snapshot_date,:freshness_days,
  :redistribution_class,:evidence_class,:declared_path,:source_byte_length,
  :source_sha256,CAST(:known_gaps AS jsonb),:pack,1,:manifest_sha,:raw_manifest_sha,
  :verification,:external_entry,:external_evidence,CAST(:copied_ids AS jsonb),
  :request_hash,:key_hash)
"""


async def set_context(connection: AsyncConnection, actor: UUID, role: str) -> None:
    for key, value in (("organization_id", ORG), ("actor_id", actor), ("role", role)):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def ensure_dra_case(case_id: UUID = CASE) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            exists = await connection.scalar(
                text("SELECT EXISTS(SELECT 1 FROM app.student_cases WHERE organization_id=:org AND id=:case)"),
                {"org": ORG, "case": case_id},
            )
            if not exists:
                await connection.execute(
                    text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"),
                    {"org": ORG, "case": case_id},
                )
                await connection.execute(
                    text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                    {"org": ORG, "case": case_id},
                )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {"org": ORG, "case": case_id, "advisor": ADVISOR, "student": STUDENT, "parent": PARENT},
            )
    finally:
        await engine.dispose()


def import_params(
    candidate: UUID,
    *,
    request_hash: str,
    key_hash: str,
    case_id: UUID = CASE,
) -> dict[str, object]:
    imported = build_fixture_candidate_import()
    return {
        "org": ORG,
        "actor": ADVISOR,
        "case": case_id,
        "candidate": candidate,
        "identity_hash": imported.request_identity.request_sha256,
        "run_id": imported.run.run_id,
        "artifact_bytes": imported.artifact.byte_length,
        "artifact_sha": imported.artifact.content_hash,
        "evidence": json.dumps(
            [
                item.model_dump(mode="json", exclude_computed_fields=True)
                for item in imported.evidence
            ]
        ),
        "request_hash": request_hash,
        "key_hash": key_hash,
    }


def verify_params(
    candidate: UUID,
    verification: UUID,
    *,
    decision: str,
    request_hash: str,
    key_hash: str,
    case_id: UUID = CASE,
) -> dict[str, object]:
    evidence = build_fixture_candidate_import().evidence[0]
    approved = decision == "approve"
    copied = [
        {"claim": claim, "evidence_id": f"62000000-0000-0000-0000-{index:012d}"}
        for index, claim in enumerate(
            (
                "australia_tuition",
                "australia_living_cost",
                "australia_fx",
                "japan_program_fit",
                "australia_ranking",
            ),
            start=int(str(verification)[-4:]) * 10 + 1,
        )
    ]
    suffix = int(str(verification)[-4:])
    return {
        "org": ORG,
        "actor": ADVISOR,
        "case": case_id,
        "candidate": candidate,
        "dra_evidence_id": evidence.evidence_id,
        "decision": decision,
        "reason": "Exact bounded source inspected." if approved else "Source rejected.",
        "source_url": str(evidence.source_url) if approved else None,
        "publisher": "Synthetic Public Source Publisher" if approved else None,
        "institution": "Synthetic Australia Institution" if approved else None,
        "snapshot_date": date(2026, 7, 11) if approved else None,
        "freshness_days": 365 if approved else None,
        "redistribution_class": "link_only" if approved else None,
        "evidence_class": "institutional" if approved else None,
        "declared_path": "sources/australia-program-fit.html" if approved else None,
        "source_byte_length": 375 if approved else None,
        "source_sha256": SOURCE_SHA if approved else None,
        "known_gaps": json.dumps(["applicant_eligibility", "intake_availability"]) if approved else None,
        "pack": PACK,
        "manifest_sha": MANIFEST_SHA,
        "raw_manifest_sha": RAW_MANIFEST_SHA,
        "verification": verification,
        "external_entry": UUID(f"63000000-0000-0000-0000-{suffix:012d}") if approved else None,
        "external_evidence": UUID(f"64000000-0000-0000-0000-{suffix:012d}") if approved else None,
        "copied_ids": json.dumps(copied) if approved else None,
        "request_hash": request_hash,
        "key_hash": key_hash,
    }


@pytest.mark.asyncio
async def test_import_is_candidate_only_and_idempotent() -> None:
    await ensure_dra_case()
    candidate = UUID("90000000-0000-0000-0000-000000000101")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            params = import_params(candidate, request_hash="a" * 64, key_hash="b" * 64)
            first = (await connection.execute(text(IMPORT_SQL), params)).mappings().one()
            replay = (await connection.execute(text(IMPORT_SQL), {**params, "candidate": UUID(int=999)})).mappings().one()
            assert first["candidate_id"] == candidate and first["replayed"] is False
            assert replay["candidate_id"] == candidate and replay["replayed"] is True
            assert await connection.scalar(text("SELECT count(*) FROM app.dra_research_candidates WHERE id=:id"), {"id": candidate}) == 1
            assert await connection.scalar(text("SELECT count(*) FROM app.external_evidence_verifications WHERE candidate_id=:id"), {"id": candidate}) == 0
            assert await connection.scalar(text("SELECT count(*) FROM app.planning_runs WHERE case_id=:case"), {"case": CASE}) == 0
            assert await connection.scalar(text("SELECT state FROM app.student_cases WHERE id=:case"), {"case": CASE}) == "planning"
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(text(IMPORT_SQL), {**params, "request_hash": "c" * 64})
            assert getattr(raised.value.orig, "sqlstate", None) == "NV008"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reject_is_one_terminal_audit_row_without_promotion() -> None:
    await ensure_dra_case()
    candidate = UUID("90000000-0000-0000-0000-000000000102")
    verification = UUID("91000000-0000-0000-0000-000000000102")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(text(IMPORT_SQL), import_params(candidate, request_hash="d" * 64, key_hash="e" * 64))
            before = await connection.scalar(text("SELECT count(*) FROM app.source_packs WHERE id=:pack"), {"pack": PACK})
            result = (await connection.execute(text(VERIFY_SQL), verify_params(candidate, verification, decision="reject", request_hash="f" * 64, key_hash="1" * 64))).mappings().one()
            assert result["terminal_decision"] == "reject"
            assert result["promoted_source_pack_version"] is None
            replay = (await connection.execute(text(VERIFY_SQL), verify_params(candidate, UUID("91000000-0000-0000-0000-000000000999"), decision="reject", request_hash="f" * 64, key_hash="1" * 64))).mappings().one()
            assert replay["verification_id"] == verification and replay["replayed"] is True
            assert await connection.scalar(text("SELECT count(*) FROM app.source_packs WHERE id=:pack"), {"pack": PACK}) == before
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(text(VERIFY_SQL), verify_params(candidate, UUID("91000000-0000-0000-0000-000000000998"), decision="reject", request_hash="0" * 64, key_hash="1" * 64))
            assert getattr(raised.value.orig, "sqlstate", None) == "NV008"
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(text(VERIFY_SQL), verify_params(candidate, UUID("91000000-0000-0000-0000-000000000997"), decision="reject", request_hash="9" * 64, key_hash="8" * 64))
            assert getattr(raised.value.orig, "sqlstate", None) == "NV012"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_any_verification_makes_the_whole_candidate_terminal_and_readable() -> None:
    await ensure_dra_case()
    candidate = UUID("90000000-0000-0000-0000-000000000109")
    verification = UUID("91000000-0000-0000-0000-000000000109")
    params = import_params(
        candidate,
        request_hash=stable_hash("terminal-import-request"),
        key_hash=stable_hash("terminal-import-key"),
    )
    evidence = json.loads(str(params["evidence"]))
    evidence.append(
        {
            **evidence[0],
            "evidence_id": "bounded-non-promotable-context",
            "source_url": None,
            "source_identity": "bounded-non-promotable-context",
        }
    )
    params["evidence"] = json.dumps(evidence)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(text(IMPORT_SQL), params)
            await connection.execute(
                text(VERIFY_SQL),
                verify_params(
                    candidate,
                    verification,
                    decision="reject",
                    request_hash=stable_hash("terminal-reject-request"),
                    key_hash=stable_hash("terminal-reject-key"),
                ),
            )
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    second = verify_params(
                        candidate,
                        UUID("91000000-0000-0000-0000-000000000110"),
                        decision="reject",
                        request_hash=stable_hash("terminal-second-request"),
                        key_hash=stable_hash("terminal-second-key"),
                    )
                    second["dra_evidence_id"] = "bounded-non-promotable-context"
                    await connection.execute(text(VERIFY_SQL), second)
            assert getattr(raised.value.orig, "sqlstate", None) == "NV012"
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            row = (
                await connection.execute(
                    text(
                        "SELECT c.id,v.id FROM app.dra_research_candidates c "
                        "LEFT JOIN app.external_evidence_verifications v "
                        "ON v.organization_id=c.organization_id AND v.candidate_id=c.id "
                        "WHERE c.organization_id=:org AND c.id=:candidate"
                    ),
                    {"org": ORG, "candidate": candidate},
                )
            ).one_or_none()
            assert row == (candidate, verification)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_approve_atomically_creates_exact_mixed_evidence_revision() -> None:
    await ensure_dra_case()
    candidate = UUID("90000000-0000-0000-0000-000000000103")
    verification = UUID("91000000-0000-0000-0000-000000000103")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(text(IMPORT_SQL), import_params(candidate, request_hash="2" * 64, key_hash="3" * 64))
            result = (await connection.execute(text(VERIFY_SQL), verify_params(candidate, verification, decision="approve", request_hash="4" * 64, key_hash="5" * 64))).mappings().one()
            version = result["promoted_source_pack_version"]
            rows = (await connection.execute(text("SELECT claim,authority FROM app.evidence_refs WHERE source_pack_id=:pack AND source_pack_version=:version ORDER BY claim"), {"pack": PACK, "version": version})).all()
            assert len(rows) == 6
            assert rows.count(("australia_program_fit", "externally_verified")) == 1
            assert all(authority == "accepted_synthetic_demo" for claim, authority in rows if claim != "australia_program_fit")
            coverage = await connection.scalar(text("SELECT coverage FROM app.source_pack_entries WHERE source_pack_id=:pack AND source_pack_version=:version AND id=:entry"), {"pack": PACK, "version": version, "entry": result["promoted_source_entry_id"]})
            assert coverage == ["australia_program_fit"]
            assert await connection.scalar(text("SELECT count(*) FROM app.agent_tasks WHERE case_id=:case"), {"case": CASE}) == 0
            assert await connection.scalar(text("SELECT count(*) FROM app.planning_runs WHERE case_id=:case"), {"case": CASE}) == 0
            replay = (
                await connection.execute(
                    text(VERIFY_SQL),
                    verify_params(
                        candidate,
                        UUID("91000000-0000-0000-0000-000000000999"),
                        decision="approve",
                        request_hash="4" * 64,
                        key_hash="5" * 64,
                    ),
                )
            ).mappings().one()
            assert replay["verification_id"] == verification
            assert replay["replayed"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_roles_cannot_directly_mutate_authority_tables() -> None:
    for variable in ("NIGHT_VOYAGER_API_DATABASE_URL", "NIGHT_VOYAGER_WORKER_DATABASE_URL"):
        engine = create_async_engine(os.environ[variable])
        try:
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    async with connection.begin():
                        await set_context(connection, ADVISOR, "advisor")
                        await connection.execute(text("INSERT INTO app.evidence_refs(organization_id,id,source_pack_id,source_pack_version,source_entry_id,claim,authority,source_sha256) VALUES(:org,gen_random_uuid(),:pack,1,'51000000-0000-0000-0000-000000000001','australia_program_fit','externally_verified',repeat('a',64))"), {"org": ORG, "pack": PACK})
                for table in ("dra_research_candidates", "external_evidence_verifications"):
                    with pytest.raises(DBAPIError):
                        async with connection.begin():
                            await set_context(connection, ADVISOR, "advisor")
                            await connection.execute(text(f"DELETE FROM app.{table}"))
        finally:
            await engine.dispose()

    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with worker.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(
                        text(IMPORT_SQL),
                        import_params(
                            UUID("90000000-0000-0000-0000-000000000111"),
                            request_hash="7" * 64,
                            key_hash="8" * 64,
                        ),
                    )
            assert getattr(raised.value.orig, "sqlstate", None) == "42501"
    finally:
        await worker.dispose()

    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await connection.execute(
                        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                        {"org": str(ORG)},
                    )
                    await connection.execute(
                        text("UPDATE app.dra_research_candidates SET run_id='rewritten' WHERE id='90000000-0000-0000-0000-000000000101'")
                    )
            assert getattr(raised.value.orig, "sqlstate", None) == "NV006"
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_missing_or_wrong_actor_context_is_non_enumerating() -> None:
    await ensure_dra_case()
    candidate = UUID("90000000-0000-0000-0000-000000000104")
    params = import_params(candidate, request_hash="6" * 64, key_hash="7" * 64)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await connection.execute(text(IMPORT_SQL), params)
            assert getattr(raised.value.orig, "sqlstate", None) == "NV007"
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, STUDENT, "advisor")
                    await connection.execute(text(IMPORT_SQL), params)
            assert getattr(raised.value.orig, "sqlstate", None) == "NV007"
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await connection.execute(
                        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                        {"org": str(UUID("10000000-0000-0000-0000-000000000099"))},
                    )
                    await connection.execute(
                        text("SELECT set_config('night_voyager.actor_id',:actor,true)"),
                        {"actor": str(ADVISOR)},
                    )
                    await connection.execute(
                        text("SELECT set_config('night_voyager.role','advisor',true)")
                    )
                    await connection.execute(text(IMPORT_SQL), params)
            assert getattr(raised.value.orig, "sqlstate", None) == "NV007"
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "student")
                    await connection.execute(text(IMPORT_SQL), params)
            assert getattr(raised.value.orig, "sqlstate", None) == "NV007"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_failed_promotion_rolls_back_every_authority_write() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000004")
    candidate = UUID("90000000-0000-0000-0000-000000000105")
    verification = UUID("91000000-0000-0000-0000-000000000105")
    await ensure_dra_case(case_id)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(text(IMPORT_SQL), import_params(candidate, request_hash="a" * 64, key_hash="c" * 64, case_id=case_id))
            before = await connection.scalar(text("SELECT count(*) FROM app.source_packs WHERE id=:pack"), {"pack": PACK})
        params = verify_params(candidate, verification, decision="approve", request_hash="b" * 64, key_hash="d" * 64, case_id=case_id)
        copied = json.loads(str(params["copied_ids"]))
        params["external_evidence"] = UUID(copied[0]["evidence_id"])
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(text(VERIFY_SQL), params)
            assert getattr(raised.value.orig, "sqlstate", None) == "NV012"
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            assert await connection.scalar(text("SELECT count(*) FROM app.source_packs WHERE id=:pack"), {"pack": PACK}) == before
            assert await connection.scalar(text("SELECT count(*) FROM app.external_evidence_verifications WHERE candidate_id=:candidate"), {"candidate": candidate}) == 0
            assert await connection.scalar(text("SELECT state FROM app.student_cases WHERE id=:case"), {"case": case_id}) == "planning"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_url", "https://example.org/source"),
        ("source_sha256", "not-a-sha256"),
        ("declared_path", "../private/source.html"),
        ("publisher", " "),
        ("known_gaps", json.dumps(["applicant_eligibility"])),
        ("manifest_sha", "0" * 64),
    ],
)
async def test_source_attestation_and_baseline_mismatches_fail_without_side_effects(
    field: str, value: object
) -> None:
    await ensure_dra_case()
    suffix = {
        "source_url": 112,
        "source_sha256": 113,
        "declared_path": 114,
        "publisher": 115,
        "known_gaps": 116,
        "manifest_sha": 117,
    }[field]
    candidate = UUID(f"90000000-0000-0000-0000-{suffix:012d}")
    verification = UUID(f"91000000-0000-0000-0000-{suffix:012d}")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(
                text(IMPORT_SQL),
                import_params(
                    candidate,
                    request_hash=stable_hash(f"source-import-request-{suffix}"),
                    key_hash=stable_hash(f"source-import-key-{suffix}"),
                ),
            )
            before = await connection.scalar(
                text("SELECT count(*) FROM app.source_packs WHERE id=:pack"),
                {"pack": PACK},
            )
        params = verify_params(
            candidate,
            verification,
            decision="approve",
            request_hash=stable_hash(f"source-verify-request-{suffix}"),
            key_hash=stable_hash(f"source-verify-key-{suffix}"),
        )
        params[field] = value
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(text(VERIFY_SQL), params)
            assert getattr(raised.value.orig, "sqlstate", None) == "NV011"
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            assert await connection.scalar(
                text("SELECT count(*) FROM app.source_packs WHERE id=:pack"),
                {"pack": PACK},
            ) == before
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM app.external_evidence_verifications "
                    "WHERE candidate_id=:candidate"
                ),
                {"candidate": candidate},
            ) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_same_candidate_concurrent_approvals_yield_one_result_and_one_conflict() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000007")
    await ensure_dra_case(case_id)
    candidate = UUID("90000000-0000-0000-0000-000000000118")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(
                text(IMPORT_SQL),
                import_params(
                    candidate,
                    request_hash=stable_hash("concurrent-import-request"),
                    key_hash=stable_hash("concurrent-import-key"),
                    case_id=case_id,
                ),
            )

        async def approve() -> object:
            try:
                async with engine.begin() as connection:
                    await set_context(connection, ADVISOR, "advisor")
                    return await connection.execute(
                        text(VERIFY_SQL),
                        verify_params(
                            candidate,
                            UUID("91000000-0000-0000-0000-000000009001"),
                            decision="approve",
                            request_hash=stable_hash("concurrent-approval-request"),
                            key_hash=stable_hash("concurrent-approval-key"),
                            case_id=case_id,
                        ),
                    )
            except DBAPIError as error:
                return str(getattr(error.orig, "sqlstate", ""))

        initial = await approve()
        assert initial != "NV012", initial

        async def conflicting_approve() -> object:
            try:
                async with engine.begin() as connection:
                    await set_context(connection, ADVISOR, "advisor")
                    return await connection.execute(
                        text(VERIFY_SQL),
                        verify_params(
                            candidate,
                            UUID("91000000-0000-0000-0000-000000009002"),
                            decision="approve",
                            request_hash=stable_hash("concurrent-conflict-request"),
                            key_hash=stable_hash("concurrent-conflict-key"),
                            case_id=case_id,
                        ),
                    )
            except DBAPIError as error:
                return str(getattr(error.orig, "sqlstate", ""))

        results = await asyncio.gather(approve(), conflicting_approve())
        conflicts = [result for result in results if result == "NV012"]
        assert len(conflicts) == 1, results
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM app.external_evidence_verifications "
                    "WHERE candidate_id=:candidate"
                ),
                {"candidate": candidate},
            ) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_failed_transaction_does_not_leak_actor_context_through_pool() -> None:
    await ensure_dra_case()
    engine = create_async_engine(
        os.environ["NIGHT_VOYAGER_API_DATABASE_URL"], pool_size=1, max_overflow=0
    )
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError):
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    params = import_params(
                        UUID("90000000-0000-0000-0000-000000000120"),
                        request_hash="bad",
                        key_hash=stable_hash("pool-import-key"),
                    )
                    await connection.execute(text(IMPORT_SQL), params)
        async with engine.connect() as connection:
            assert await connection.scalar(
                text("SELECT current_setting('night_voyager.actor_id',true)")
            ) in (None, "")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table", "mode"),
    [
        ("source_packs", "all"),
        ("source_pack_entries", "synthetic_entry"),
        ("evidence_refs", "synthetic_evidence"),
        ("source_pack_entries", "external_entry"),
        ("evidence_refs", "external_evidence"),
        ("external_evidence_verifications", "all"),
        ("idempotency_records", "verification_idempotency"),
    ],
)
async def test_each_promotion_write_boundary_rolls_back_atomically(
    table: str, mode: str
) -> None:
    await ensure_dra_case()
    boundaries = {
        ("source_packs", "all"): 130,
        ("source_pack_entries", "synthetic_entry"): 131,
        ("evidence_refs", "synthetic_evidence"): 132,
        ("source_pack_entries", "external_entry"): 133,
        ("evidence_refs", "external_evidence"): 134,
        ("external_evidence_verifications", "all"): 135,
        ("idempotency_records", "verification_idempotency"): 136,
    }
    suffix = boundaries[(table, mode)]
    candidate = UUID(f"90000000-0000-0000-0000-{suffix:012d}")
    verification = UUID(f"91000000-0000-0000-0000-{suffix:012d}")
    trigger_name = f"test_dra_fail_{suffix}"
    function_name = f"app.{trigger_name}"
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(
                text(IMPORT_SQL),
                import_params(
                    candidate,
                    request_hash=stable_hash(f"rollback-import-request-{suffix}"),
                    key_hash=stable_hash(f"rollback-import-key-{suffix}"),
                ),
            )
            before = await connection.scalar(
                text("SELECT count(*) FROM app.source_packs WHERE id=:pack"),
                {"pack": PACK},
            )
        condition = {
            "all": "TRUE",
            "synthetic_entry": "NEW.coverage ? 'australia_tuition'",
            "synthetic_evidence": "NEW.authority = 'accepted_synthetic_demo'",
            "external_entry": "NEW.coverage ? 'australia_program_fit'",
            "external_evidence": "NEW.authority = 'externally_verified'",
            "verification_idempotency": "NEW.operation = 'dra_candidate_verify'",
        }[mode]
        async with migrator.begin() as connection:
            await connection.execute(
                text(
                    f"CREATE FUNCTION {function_name}() RETURNS trigger LANGUAGE plpgsql "
                    f"AS $$ BEGIN IF {condition} THEN RAISE EXCEPTION USING "
                    "ERRCODE='NV012', MESSAGE='injected promotion failure'; END IF; "
                    "RETURN NEW; END $$"
                )
            )
            await connection.execute(
                text(
                    f"CREATE TRIGGER {trigger_name} BEFORE INSERT ON app.{table} "
                    f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
                )
            )
        try:
            async with api.connect() as connection:
                with pytest.raises(DBAPIError) as raised:
                    async with connection.begin():
                        await set_context(connection, ADVISOR, "advisor")
                        await connection.execute(
                            text(VERIFY_SQL),
                            verify_params(
                                candidate,
                                verification,
                                decision="approve",
                                request_hash=stable_hash(f"rollback-verify-request-{suffix}"),
                                key_hash=stable_hash(f"rollback-verify-key-{suffix}"),
                            ),
                        )
                assert getattr(raised.value.orig, "sqlstate", None) == "NV012"
        finally:
            async with migrator.begin() as connection:
                await connection.execute(
                    text(f"DROP TRIGGER {trigger_name} ON app.{table}")
                )
                await connection.execute(text(f"DROP FUNCTION {function_name}()"))
        async with api.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            assert await connection.scalar(
                text("SELECT count(*) FROM app.source_packs WHERE id=:pack"),
                {"pack": PACK},
            ) == before
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM app.external_evidence_verifications "
                    "WHERE candidate_id=:candidate"
                ),
                {"candidate": candidate},
            ) == 0
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_sql_import_rejects_malformed_or_multiple_promotable_evidence_without_side_effects() -> None:
    await ensure_dra_case()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    candidates = tuple(
        UUID(f"90000000-0000-0000-0000-{suffix:012d}")
        for suffix in range(140, 148)
    )
    base = import_params(
        candidates[0],
        request_hash=stable_hash("malformed-import-base-request"),
        key_hash=stable_hash("malformed-import-base-key"),
    )
    malformed = [{"evidence_id": "raw-only", "source_url": "https://example.com/raw"}]
    valid = json.loads(str(base["evidence"]))
    second = {**valid[0], "evidence_id": "second-public-evidence"}
    additive = {**valid[0], "raw_provider_value": "not-persistable"}
    private_url = {
        **valid[0],
        "source_url": "https://127.0.0.1/private",
        "source_identity": "https://127.0.0.1/private",
    }
    identity_mismatch = {**valid[0], "source_identity": "https://example.org/other"}
    bad_timestamp = {**valid[0], "retrieved_at": "not-a-timestamp"}
    no_promotable = {
        **valid[0],
        "source_url": None,
        "source_identity": "bounded-context",
    }
    duplicate = [valid[0], {**no_promotable, "evidence_id": valid[0]["evidence_id"]}]
    try:
        invalid_projections = (
            malformed,
            [valid[0], second],
            [additive],
            [private_url],
            [identity_mismatch],
            [bad_timestamp],
            [no_promotable],
            duplicate,
        )
        for index, evidence in enumerate(invalid_projections):
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError) as raised:
                    async with connection.begin():
                        await set_context(connection, ADVISOR, "advisor")
                        await connection.execute(
                            text(IMPORT_SQL),
                            {
                                **base,
                                "candidate": candidates[index],
                                "evidence": json.dumps(evidence),
                                "request_hash": stable_hash(
                                    f"malformed-import-request-{index}"
                                ),
                                "key_hash": stable_hash(f"malformed-import-key-{index}"),
                            },
                        )
                assert getattr(raised.value.orig, "sqlstate", None) == "NV011"
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            assert await connection.scalar(
                text("SELECT count(*) FROM app.dra_research_candidates WHERE id=ANY(:ids)"),
                {"ids": list(candidates)},
            ) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_import_holds_case_lock_until_candidate_and_idempotency_commit() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000006")
    candidate = UUID("90000000-0000-0000-0000-000000000108")
    run_id = UUID("70000000-0000-0000-0000-000000000106")
    await ensure_dra_case(case_id)
    migration_engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    import_connection: AsyncConnection | None = None
    publication: asyncio.Task[None] | None = None
    try:
        async with migration_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text("INSERT INTO app.planning_runs(organization_id,id,case_id,case_revision,source_pack_id,source_pack_version,policy_version,evidence_projection_sha256,state,is_current) VALUES(:org,:run,:case,1,:pack,1,'m3a-policy-v1',repeat('a',64),'synthesizing',true)"),
                {"org": ORG, "run": run_id, "case": case_id, "pack": PACK},
            )
        import_connection = await api_engine.connect()
        import_transaction = await import_connection.begin()
        await set_context(import_connection, ADVISOR, "advisor")
        await import_connection.execute(
            text(IMPORT_SQL),
            import_params(
                candidate,
                request_hash=stable_hash("race-import-request"),
                key_hash=stable_hash("race-import-key"),
                case_id=case_id,
            ),
        )

        async def publish_review_required() -> None:
            async with migration_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                await connection.execute(
                    text("UPDATE app.planning_runs SET state='review_required',reason_code='ready',output_sha256=repeat('b',64) WHERE organization_id=:org AND id=:run"),
                    {"org": ORG, "run": run_id},
                )

        publication = asyncio.create_task(publish_review_required())
        await asyncio.sleep(0.2)
        assert not publication.done(), "Case transition crossed candidate import before commit"
        await import_transaction.commit()
        await import_connection.close()
        await asyncio.wait_for(publication, timeout=2)
        async with migration_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            assert await connection.scalar(
                text("SELECT state FROM app.student_cases WHERE organization_id=:org AND id=:case"),
                {"org": ORG, "case": case_id},
            ) == "advisor_review"
        async with api_engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(
                        text(IMPORT_SQL),
                        import_params(
                            UUID("90000000-0000-0000-0000-000000000121"),
                            request_hash=stable_hash("stale-import-request"),
                            key_hash=stable_hash("stale-import-key"),
                            case_id=case_id,
                        ),
                    )
            assert getattr(raised.value.orig, "sqlstate", None) == "NV003"
    finally:
        if publication is not None and not publication.done():
            publication.cancel()
            await asyncio.gather(publication, return_exceptions=True)
        if import_connection is not None and not import_connection.closed:
            await import_connection.close()
        await api_engine.dispose()
        await migration_engine.dispose()
