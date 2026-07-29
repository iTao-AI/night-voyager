from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "web/e2e/plan-execution.spec.ts"
COMPOSE_PROOF = ROOT / "scripts/verify_compose.sh"
VERIFIER = ROOT / "scripts/verify_timeline_execution.py"


def test_browser_proof_closes_bilingual_happy_blocked_and_recovery_contract() -> None:
    source = SPEC.read_text(encoding="utf-8")
    for marker in (
        '"zh-CN"',
        '"en"',
        '"happy"',
        '"blocked"',
        "lostReceipt",
        'route.abort("failed")',
        "accepted_receipt_ids",
        "reassessment_request_id",
        "checkpointIds",
        "page.reload()",
        "responseOrder",
    ):
        assert marker in source
    for forbidden in ("case_id=", "localStorage", "sessionStorage.setItem"):
        assert forbidden not in source


def test_compose_runs_four_isolated_browser_database_lanes_and_cleans_proofs() -> None:
    source = COMPOSE_PROOF.read_text(encoding="utf-8")
    assert 'run_plan_execution_lane "zh-CN" "happy"' in source
    assert 'run_plan_execution_lane "zh-CN" "blocked"' in source
    assert 'run_plan_execution_lane "en" "happy"' in source
    assert 'run_plan_execution_lane "en" "blocked"' in source
    assert "PLAN_EXECUTION_PROOF_FILE" in source
    assert "verify_timeline_execution.py" in source
    assert "--proof-file /tmp/plan-execution-proof.json" in source
    assert "PLAN_EXECUTION_SCENARIO" in source
    assert "plan-execution.spec.ts" in source


def test_database_verifier_accepts_only_the_closed_private_proof_schema() -> None:
    source = VERIFIER.read_text(encoding="utf-8")
    for key in (
        "schema_version",
        "locale",
        "scenario",
        "case_id",
        "timeline_plan_id",
        "execution_id",
        "accepted_receipt_ids",
        "checkpoint_ids",
        "reassessment_request_id",
    ):
        assert key in source
    for forbidden in ("csrf_token", "session_token", "idempotency_key", "database_url"):
        assert forbidden not in source
