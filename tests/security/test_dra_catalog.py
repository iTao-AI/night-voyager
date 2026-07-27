from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "migrations/versions/0005_dra_candidate_promotion.py"
LIVE_MIGRATION_PATH = ROOT / "migrations/versions/0010_dra_v0_1_6_live_consumer.py"
STRICT_MIGRATION_PATH = ROOT / "migrations/versions/0011_dra_strict_consumer_identity.py"
TABLES = ("dra_research_candidates", "external_evidence_verifications")


def migration_source() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_0005_extends_0004_with_exact_storage() -> None:
    source = migration_source()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
        and isinstance(node.value, ast.Constant)
    }
    assert assignments == {"revision": "0005", "down_revision": "0004"}
    assert source.count("CREATE TABLE app.") == 2
    for table in TABLES:
        assert f"CREATE TABLE app.{table}" in source
        assert f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY" in source
        assert f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY" in source
        assert f"CREATE POLICY {table}_tenant_isolation" in source
    assert "external_evidence_promotions" not in source


def test_candidate_storage_excludes_provider_payload_and_authority_side_effects() -> None:
    source = migration_source()
    candidate = source.split("CREATE TABLE app.dra_research_candidates", 1)[1].split(
        "CREATE TABLE app.external_evidence_verifications", 1
    )[0]
    for forbidden in (
        "artifact_content",
        "snippet",
        "credential",
        "checkpoint",
        "provider_payload",
        "token_count",
        "cost_minor",
    ):
        assert forbidden not in candidate
    assert "ordered_evidence jsonb" in candidate
    assert "artifact_sha256" in candidate


def test_0005_has_narrow_import_and_one_atomic_promotion_function() -> None:
    source = migration_source()
    for function in ("import_dra_research_candidate", "verify_and_promote_dra_candidate"):
        assert source.count(f"CREATE FUNCTION app.{function}") == 1
        assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in source
        assert f"REVOKE ALL ON FUNCTION app.{function}" in source
    assert "GRANT EXECUTE ON FUNCTION app.import_dra_research_candidate" in source
    assert "GRANT EXECUTE ON FUNCTION app.verify_and_promote_dra_candidate" in source
    assert "TO night_voyager_api" in source
    assert "TO night_voyager_worker" not in source
    assert "GRANT INSERT ON app." not in source
    assert "GRANT UPDATE ON app." not in source
    assert "GRANT DELETE ON app." not in source


def test_atomic_authority_fixes_mapping_shapes_and_conflicts() -> None:
    source = migration_source()
    for contract in (
        "CHECK (claim = 'australia_program_fit')",
        "CHECK (evidence_role = 'program_fit')",
        "CHECK (authority = 'externally_verified')",
        "redistribution_class IS NULL OR redistribution_class = 'link_only'",
        "evidence_class IS NULL OR evidence_class IN ('institutional','government')",
        "WHERE decision='approve'",
        "ERRCODE='NV011'",
        "ERRCODE='NV012'",
    ):
        assert contract in source
    assert "UNIQUE (organization_id, candidate_id)" in source
    assert "IF promotable_count<>1" in source
    authority_values = (
        "authority IN "
        "('untrusted_candidate','accepted_synthetic_demo','externally_verified')"
    )
    assert authority_values in source


def test_authority_rows_are_immutable_and_runtime_roles_are_read_only() -> None:
    source = migration_source()
    for table in TABLES:
        assert f"CREATE TRIGGER {table}_immutable" in source
    assert "REVOKE ALL ON TABLE app.dra_research_candidates FROM PUBLIC" in source
    assert "REVOKE ALL ON TABLE app.external_evidence_verifications FROM PUBLIC" in source
    expected_grant = (
        "GRANT SELECT ON app.dra_research_candidates,"
        "app.external_evidence_verifications TO night_voyager_api"
    )
    assert expected_grant in source


def test_0010_closes_live_producer_and_outcome_projection_authority() -> None:
    source = LIVE_MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
        and isinstance(node.value, ast.Constant)
    }
    assert assignments == {"revision": "0010", "down_revision": "0009"}
    for identity_fragment in (
        "(producer_release='v0.1.3' AND ",
        "producer_commit='87b2a8e335385eb865086f7a69fe2b190567cfa2') OR ",
        "(producer_release='v0.1.6' AND ",
        "producer_commit='7d43324b469cb5e445c2e8be83af3be4d841cf1c'))",
    ):
        assert identity_fragment in source
    assert "p_producer_release<>'v0.1.6'" in source
    assert "p_producer_commit<>'7d43324b469cb5e445c2e8be83af3be4d841cf1c'" in source
    assert "CREATE FUNCTION app.project_dra_live_outcome" in source
    assert "CREATE FUNCTION app.project_agent_task_live_authority" in source
    assert "CREATE FUNCTION app.project_agent_task_by_idempotency" in source
    assert "CREATE FUNCTION app.project_advisor_review_by_idempotency" in source
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in source
    assert "PERFORM app.assert_m3b_context(p_org,p_actor,'advisor')" in source
    assert "REVOKE ALL ON FUNCTION {OUTCOME_SIGNATURE} FROM PUBLIC" in source
    assert "GRANT EXECUTE ON FUNCTION {OUTCOME_SIGNATURE} TO night_voyager_api" in source
    assert (
        "GRANT EXECUTE ON FUNCTION {TASK_AUTHORITY_SIGNATURE} "
        "TO night_voyager_api"
    ) in source
    assert (
        "GRANT EXECUTE ON FUNCTION {TASK_RECOVERY_SIGNATURE} "
        "TO night_voyager_api"
    ) in source
    assert (
        "GRANT EXECUTE ON FUNCTION {REVIEW_RECOVERY_SIGNATURE} "
        "TO night_voyager_api"
    ) in source
    assert "TO night_voyager_worker" not in source
    assert "GRANT SELECT ON" not in source
    assert "GRANT INSERT ON" not in source
    assert "GRANT UPDATE ON" not in source
    assert "GRANT DELETE ON" not in source
    assert (
        source.count(
            "ALTER TABLE app.dra_research_candidates NO FORCE ROW LEVEL SECURITY"
        )
        == 1
    )
    assert (
        source.count(
            "ALTER TABLE app.dra_research_candidates FORCE ROW LEVEL SECURITY"
        )
        == 1
    )
    assert "refusing downgrade: DRA v0.1.6 candidate history exists" in source


def test_live_storage_uses_descriptor_relative_no_follow_operations() -> None:
    source = (
        ROOT / "src/night_voyager/dra/live_storage.py"
    ).read_text(encoding="utf-8")
    assert "O_NOFOLLOW" in source
    assert "dir_fd=" in source
    assert "os.fsync" in source
    assert "os.link" in source
    assert "resolve(" not in source


def test_live_outcome_adapter_uses_only_closed_0010_projection() -> None:
    source = (
        ROOT / "src/night_voyager/dra/live_outcome_postgres.py"
    ).read_text(encoding="utf-8")
    assert source.count("app.project_dra_live_outcome") == 1
    for forbidden in (
        "dra_research_candidates",
        "external_evidence_verifications",
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "SELECT * FROM app.",
    ):
        if forbidden == "SELECT * FROM app.":
            assert source.count(forbidden) == 1
        else:
            assert forbidden not in source


def test_0011_closes_strict_identity_and_preserves_runtime_authority() -> None:
    source = STRICT_MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
        and isinstance(node.value, ast.Constant)
    }
    assert assignments == {"revision": "0011", "down_revision": "0010"}
    for fragment in (
        "LOCK TABLE app.dra_research_candidates IN ACCESS EXCLUSIVE MODE",
        "ALTER TABLE app.dra_research_candidates NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE app.dra_research_candidates DISABLE TRIGGER "
        "dra_research_candidates_immutable",
        "producer_repository",
        "producer_ref_kind",
        "producer_ref",
        "profile_version",
        "proof_schema",
        "generic-strict-citation",
        "dra.strict-citation-profile.v1",
        "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "ALTER TABLE app.dra_research_candidates ENABLE TRIGGER "
        "dra_research_candidates_immutable",
        "ALTER TABLE app.dra_research_candidates FORCE ROW LEVEL SECURITY",
    ):
        assert fragment in source
    assert "TO night_voyager_worker" not in source
    assert "GRANT EXECUTE" in source
    assert "REVOKE ALL" in source
