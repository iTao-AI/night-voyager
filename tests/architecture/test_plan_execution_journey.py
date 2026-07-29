from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "web/e2e/plan-execution.spec.ts"
COMPOSE_PROOF = ROOT / "scripts/verify_compose.sh"
VERIFIER = ROOT / "scripts/verify_timeline_execution.py"
CATALOG = ROOT / "web/lib/presentation/catalog.ts"


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
    for forbidden in ("case_id=",):
        assert forbidden not in source
    assert source.count("sessionStorage.setItem(key, JSON.stringify(envelope));") == 1


def test_browser_database_proof_binds_every_recovery_counterfactual() -> None:
    source = SPEC.read_text(encoding="utf-8")
    verifier = VERIFIER.read_text(encoding="utf-8")
    compose = COMPOSE_PROOF.read_text(encoding="utf-8")

    for marker in (
        "stale second tab",
        "stale_execution_version",
        "shared session rotation while read is in flight",
        "session_changed",
        "cross-Case envelope",
        "activity_total",
        "toHaveLength(64)",
        "64",
        "67",
        "zero_mutation",
        "PLAN_EXECUTION_RECOVERY_PROOF_FILE",
    ):
        assert marker in source
    for marker in (
        "recovery proof",
        "stale_rejection_code",
        "session_changed",
        "cross_case_zero_mutation",
        "activity_total",
        "activity_visible",
        "count(*)=33",
        "count(*)=34",
        "count(*)=67",
        "'night_voyager.actor_id'",
        "'night_voyager.role'",
    ):
        assert marker in verifier
    assert "run_plan_execution_recovery_lane" in compose
    assert "PLAN_EXECUTION_RECOVERY_PROOF_FILE" in compose


def test_english_browser_proof_bootstraps_locale_before_first_navigation() -> None:
    source = SPEC.read_text(encoding="utf-8")
    bootstrap = (
        'if (locale === "en") {\n'
        "    await page.addInitScript(() => {\n"
        '      localStorage.setItem("night-voyager:presentation-locale:v1", "en");\n'
        "    });\n"
        "  }"
    )

    assert source.count(bootstrap) == 1
    assert source.index(bootstrap) < source.index(
        "await page.goto(`/demo/plan?scenario=${scenario}`);"
    )


def test_english_blocked_action_matches_the_product_catalog() -> None:
    source = SPEC.read_text(encoding="utf-8")
    catalog = CATALOG.read_text(encoding="utf-8")
    action = "Record blocker and stop the current checkpoint"

    assert f'planExecutionRecordBlocked: "{action}"' in catalog
    assert source.count(f'blocked: "{action}"') == 1
    assert "Record blocked and stop this checkpoint" not in source


def test_recovery_proof_uses_the_exact_session_changed_catalog_copy() -> None:
    source = SPEC.read_text(encoding="utf-8")
    catalog = CATALOG.read_text(encoding="utf-8")
    message = "角色或执行 authority 已变化，请重新连接。"

    assert f'planExecutionSessionChanged: "{message}"' in catalog
    assert source.count(f'"{message}"') == 2


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
    assert '"SELECT receipt_id FROM app.timeline_mutation_receipts "' in source
