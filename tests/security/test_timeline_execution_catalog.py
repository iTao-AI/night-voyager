# ruff: noqa: E501
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0014_timeline_execution_authority.py"
pytestmark = pytest.mark.database

TABLES = (
    "timeline_executions",
    "timeline_checkpoints",
    "timeline_checkpoint_attestations",
    "timeline_checkpoint_verifications",
    "timeline_reassessment_requests",
    "timeline_mutation_receipts",
)


def test_0014_declares_only_the_approved_timeline_authority() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0014"' in source
    assert 'down_revision = "0013"' in source
    assert "0015" not in source
    for table_name in TABLES:
        assert f"CREATE TABLE app.{table_name}" in source
        assert f"ALTER TABLE app.{table_name} FORCE ROW LEVEL SECURITY" in source
    assert source.count("CREATE TABLE app.") == len(TABLES)
    assert "night_voyager_worker" in source
    assert "GRANT EXECUTE" in source
    assert "refusing downgrade: timeline execution history exists" in source


def test_0014_function_signatures_are_frozen() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    signatures = (
        "read_plan_execution_context(p_org uuid,p_actor uuid,p_role text,p_scenario text)",
        "read_timeline_execution(p_org uuid,p_actor uuid,p_role text,p_case uuid)",
        "start_timeline_execution(p_org uuid,p_actor uuid,p_role text,p_timeline uuid,p_execution uuid,p_receipt uuid,p_key_hash text,p_request_hash text)",
        "attest_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_execution uuid,p_checkpoint uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_kind text,p_status text,p_attestation_code text,p_reason_code text,p_attestation uuid,p_receipt uuid,p_key_hash text,p_request_hash text)",
        "verify_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_execution uuid,p_checkpoint uuid,p_attestation uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_action text,p_reason_code text,p_verification uuid,p_receipt uuid,p_key_hash text,p_request_hash text)",
        "request_timeline_reassessment(p_org uuid,p_actor uuid,p_role text,p_execution uuid,p_checkpoint uuid,p_trigger_reference uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_trigger text,p_reassessment uuid,p_receipt uuid,p_key_hash text,p_request_hash text)",
    )
    for signature in signatures:
        assert f"CREATE FUNCTION app.{signature}" in source
