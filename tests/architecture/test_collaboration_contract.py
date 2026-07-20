from __future__ import annotations

import ast
from pathlib import Path

from night_voyager.collaboration import CollaborationThreadFullError
from night_voyager.collaboration.models import (
    CollaborationThreadV1,
    ConfirmedFactAdvisorV1,
    ConfirmedFactParticipantV1,
    FactKey,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    MessageEventV1,
    MessagePageV1,
    VerificationDecision,
)

ROOT = Path(__file__).resolve().parents[2]
PURE_MODULES = ("models.py", "policy.py", "hashing.py", "errors.py")
MIGRATION = ROOT / "migrations/versions/0007_conversation_and_memory.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_collaboration_pure_contracts_are_framework_independent() -> None:
    forbidden = {"alembic", "asyncpg", "fastapi", "sqlalchemy"}
    for module in PURE_MODULES:
        path = ROOT / "src/night_voyager/collaboration" / module
        assert path.is_file(), module
        assert not (_imports(path) & forbidden), module


def test_collaboration_closed_vocabularies_are_exact() -> None:
    assert CollaborationThreadFullError.__name__ == "CollaborationThreadFullError"
    assert {item.value for item in FactKey} == {
        "student.intended_field",
        "student.preferred_countries",
        "student.intake",
        "family.risk_tolerance",
        "family.japan_risk_accepted",
        "family.budget",
    }
    assert {item.value for item in MemoryCandidateState} == {
        "pending",
        "stale",
        "expired",
        "confirmed",
        "rejected",
    }
    assert {item.value for item in VerificationDecision} == {"confirm", "reject"}


def test_collaboration_role_safe_projection_models_are_distinct() -> None:
    participant_candidate_fields = set(MemoryCandidateParticipantV1.model_fields)
    advisor_candidate_fields = set(MemoryCandidateAdvisorV1.model_fields)
    assert participant_candidate_fields < advisor_candidate_fields
    assert {
        "candidate_id",
        "verification_id",
        "reason",
        "request_sha256",
        "value_sha256",
    }.isdisjoint(participant_candidate_fields)

    participant_fact_fields = set(ConfirmedFactParticipantV1.model_fields)
    advisor_fact_fields = set(ConfirmedFactAdvisorV1.model_fields)
    assert participant_fact_fields < advisor_fact_fields
    assert {
        "confirmed_fact_id",
        "candidate_id",
        "verification_id",
        "source_message_event_id",
        "source_message_sequence_no",
        "source_message_sha256_prefix",
        "confirming_advisor_actor_id",
        "reason",
        "supersedes_fact_id",
    }.isdisjoint(participant_fact_fields)


def test_collaboration_read_models_are_strict_and_versioned() -> None:
    for model in (
        CollaborationThreadV1,
        MessageEventV1,
        MessagePageV1,
        MemoryCandidateParticipantV1,
        MemoryCandidateAdvisorV1,
        ConfirmedFactParticipantV1,
        ConfirmedFactAdvisorV1,
    ):
        assert model.model_config.get("extra") == "forbid"
        assert "schema_version" in model.model_fields


def test_verification_function_freezes_the_approved_resource_lock_order() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    start = migration.index("CREATE FUNCTION app.verify_memory_candidate(")
    function = migration[start : migration.index('END; $$;\n"""', start)]
    ordered_fragments = (
        "SELECT * INTO selected_case FROM app.student_cases selected_case_row",
        "SELECT * INTO candidate FROM app.memory_candidates candidate_row",
        "SELECT * INTO prior_fact FROM app.confirmed_facts AS fact",
        "SELECT * INTO current_run FROM app.planning_runs planning_run",
        "SELECT 1 FROM app.student_case_participants participant",
        "WHERE verification.organization_id=p_org AND verification.candidate_id=p_candidate",
        "IF p_decision='reject' THEN",
        "SELECT 1 FROM app.agent_tasks task",
    )
    positions = tuple(function.index(fragment) for fragment in ordered_fragments)
    assert positions == tuple(sorted(positions))


def test_planning_persistence_locks_case_before_replacing_the_current_run() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    legacy_migration = (
        ROOT / "migrations/versions/0002_case_evidence_planning.py"
    ).read_text(encoding="utf-8")

    override_start = migration.index(
        "CREATE OR REPLACE FUNCTION app.persist_planning_result("
    )
    override = migration[
        override_start : migration.index("END; $$;", override_start) + len("END; $$;")
    ]
    case_lock = override.index(
        "SELECT * INTO selected_case FROM app.student_cases selected_case_row"
    )
    superseded_run_update = override.index(
        "IF p_supersedes IS NOT NULL THEN UPDATE app.planning_runs"
    )
    assert case_lock < override.index("FOR UPDATE", case_lock) < superseded_run_update
    assert "selected_case.current_revision IS DISTINCT FROM p_revision" in override
    assert "selected_case.state IS DISTINCT FROM 'planning'" in override
    upgrade = migration[migration.index("def upgrade()") : migration.index("def downgrade()")]
    assert upgrade.index(
        "_execute_statements(PLANNING_PERSISTENCE_LOCK_SQL)"
    ) < upgrade.index("_execute_statements(MUTATION_SQL)")

    legacy_start = legacy_migration.index(
        "CREATE FUNCTION app.persist_planning_result("
    )
    legacy_function = legacy_migration[
        legacy_start : legacy_migration.index("END; $$;", legacy_start) + len("END; $$;")
    ].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    assert legacy_function in migration
    downgrade = migration[migration.index("def downgrade()") :]
    assert downgrade.index(
        "_execute_statements(LEGACY_RUN_GUARD_SQL)"
    ) < downgrade.index("_execute_statements(LEGACY_PLANNING_PERSISTENCE_SQL)")


def test_collaboration_migration_distinguishes_corrupt_replay_from_terminal_state() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "ERRCODE='NV012', MESSAGE='idempotency response unavailable'" not in migration
    assert "ERRCODE='NV012', MESSAGE='memory candidate is terminal'" in migration


def test_collaboration_migration_executes_plpgsql_as_raw_driver_sql() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    helper_start = migration.index("def _execute(sql: str) -> None:")
    helper = migration[helper_start : migration.index("\n\ndef _split_statements", helper_start)]
    assert "op.get_bind().exec_driver_sql(sql.strip())" in helper
    assert "op.execute(sql.strip())" not in helper


def test_collaboration_migration_retires_current_planning_run_only_after_confirmation() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION app.guard_run_transition()" in migration
    assert "app.memory_candidate_verifications verification" in migration
    assert "verification.result_revision=selected_case.current_revision" in migration
    assert "app.case_revision_confirmed_fact_refs fact_ref" in migration


def test_database_runner_proves_empty_round_trips_before_full_collaboration_seed() -> None:
    runner = (ROOT / "scripts/run_db_tests.sh").read_text(encoding="utf-8")
    upgrade_0008 = runner.index("uv run alembic upgrade head")
    skill_empty_downgrade = runner.index(
        "uv run alembic downgrade 0007", upgrade_0008
    )
    empty_downgrade = runner.index(
        "uv run alembic downgrade 0006", skill_empty_downgrade
    )
    reupgrade_0007 = runner.index("uv run alembic upgrade head", empty_downgrade)
    mixed_downgrade = runner.index("uv run alembic downgrade 0005", reupgrade_0007)
    full_graph_downgrade = runner.index("uv run alembic downgrade 0001", mixed_downgrade)
    full_graph_reupgrade = runner.index("uv run alembic upgrade head", full_graph_downgrade)
    seeded_graph_downgrade = runner.index(
        "uv run alembic downgrade 0001", full_graph_reupgrade
    )
    identity_seed = runner.index(
        "uv run python scripts/seed_demo.py --identity-only", seeded_graph_downgrade
    )
    legacy_upgrade = runner.index("uv run alembic upgrade 0007", identity_seed)
    legacy_seed = runner.index(
        "uv run --no-editable python scripts/seed_demo.py --without-skills",
        legacy_upgrade,
    )
    final_upgrade = runner.index("uv run alembic upgrade head", legacy_seed)
    full_seed = runner.index(
        "uv run --no-editable python scripts/seed_demo.py\n", final_upgrade
    )
    refusal = runner.rindex("uv run alembic downgrade 0007")
    assert (
        upgrade_0008
        < skill_empty_downgrade
        < empty_downgrade
        < reupgrade_0007
        < mixed_downgrade
        < full_graph_downgrade
        < full_graph_reupgrade
        < seeded_graph_downgrade
        < identity_seed
        < legacy_upgrade
        < legacy_seed
        < final_upgrade
        < full_seed
        < refusal
    )
    assert "refusing downgrade: Skill governance or runtime pin history exists" in runner


def test_database_runner_isolates_legacy_mixed_downgrade_from_collaboration_history() -> None:
    runner = (ROOT / "scripts/run_db_tests.sh").read_text(encoding="utf-8")
    seed = (ROOT / "scripts/seed_demo.py").read_text(encoding="utf-8")

    main_lane = runner[runner.index('if [ "${1:-}" = "inside" ]'):]
    isolated_lane = runner[
        runner.index('if [ "${1:-}" = "inside-mixed-downgrade" ]') :
    ]

    assert "--ignore=tests/integration/tasks/test_mixed_downgrade.py" in main_lane
    assert (
        "uv run --no-editable python scripts/seed_demo.py --without-collaboration"
        in isolated_lane
    )
    assert "tests/integration/tasks/test_mixed_downgrade.py" in isolated_lane
    assert 'run_lane "${BASE_PROJECT_NAME}-main" inside' in runner
    assert (
        'run_lane "${BASE_PROJECT_NAME}-mixed-downgrade" inside-mixed-downgrade'
        in runner
    )
    assert "include_collaboration: bool = True" in seed
    assert 'parser.add_argument("--without-collaboration", action="store_true")' in seed


def test_http_suite_crosses_the_real_identity_postgres_and_rls_boundary() -> None:
    http_test = (ROOT / "tests/integration/collaboration/test_http_collaboration.py").read_text(
        encoding="utf-8"
    )
    runner = (ROOT / "scripts/run_collaboration_db_tests.sh").read_text(encoding="utf-8")
    assert "create_app" in http_test
    assert "NIGHT_VOYAGER_API_DATABASE_URL" in http_test
    assert "NIGHT_VOYAGER_MIGRATION_DATABASE_URL" in http_test
    assert "IdentityService(" in http_test
    assert "IdentityRepository(session)" in http_test
    assert "current_setting('night_voyager.actor_id',true)" in http_test
    assert "SELECT * FROM app.collaboration_threads" in http_test
    http_suite = runner[runner.index("        http)") : runner.index("        authority)")]
    legacy_downgrade = http_suite.index("uv run alembic downgrade 0007")
    legacy_seed = http_suite.index(
        "uv run --no-editable python scripts/seed_demo.py --without-skills",
        legacy_downgrade,
    )
    head = http_suite.index("uv run alembic upgrade head", legacy_seed)
    full_seed = http_suite.index(
        "uv run --no-editable python scripts/seed_demo.py\n", head
    )
    assert legacy_downgrade < legacy_seed < head < full_seed
    assert http_suite.count(
        "uv run --no-editable python scripts/seed_demo.py\n"
    ) == 2
    assert "NIGHT_VOYAGER_DEMO_SEED_READY=1" in http_suite


def test_database_authority_proof_covers_every_composite_fk_and_forced_rls() -> None:
    repository_test = (
        ROOT
        / "tests/integration/collaboration/test_postgres_collaboration.py"
    ).read_text(encoding="utf-8")
    for fragment in (
        "EXPECTED_COLLABORATION_FOREIGN_KEYS",
        "candidate revision",
        "candidate subject participant",
        "verification advisor participant",
        "verification result fact",
        "verification result revision",
        "fact confirming advisor participant",
        "fact supersession",
        "revision source",
        "SET CONSTRAINTS ALL IMMEDIATE",
        "forced_rls_visible",
        "wrong_tenant_insert",
    ):
        assert fragment in repository_test


def test_database_authority_proof_hits_terminal_precedence_and_replay_cardinality() -> None:
    repository_test = (
        ROOT
        / "tests/integration/collaboration/test_postgres_collaboration.py"
    ).read_text(encoding="utf-8")
    for fragment in (
        "REJECT_CASE_ID",
        "test_terminal_projection_precedes_stale_and_expired",
        "stale_and_expired",
        "advisor_terminal_projection",
        "participant_terminal_projection",
        "verification_count",
        "audit_count",
        "idempotency_count",
        "fact_count",
        "revision_ref_count",
    ):
        assert fragment in repository_test


def test_authority_runner_isolates_every_downgrade_scenario() -> None:
    runner = (ROOT / "scripts/run_collaboration_db_tests.sh").read_text(encoding="utf-8")
    authority_suite = runner[
        runner.index("        authority)") : runner.index(
            "    esac", runner.index("        authority)")
        )
    ]
    assert "test_collaboration_downgrade.py" not in authority_suite
    assert "NIGHT_VOYAGER_DEMO_SEED_READY=1" in authority_suite
    assert (
        "for scenario in empty unrelated table-history audit-history idempotency-history" in runner
    )
    assert '--env "NIGHT_VOYAGER_COLLABORATION_DOWNGRADE_SCENARIO=$scenario"' in runner
    assert 'run_project "${base_project}-${scenario}"' in runner


def test_collaboration_proof_and_documentation_surface_is_registered() -> None:
    required = (
        "docs/decisions/0008-governed-collaboration-and-memory-authority.md",
        "docs/reference/collaboration-and-confirmed-facts.md",
        "docs/operations/collaboration-authority.md",
        "scripts/verify_collaboration_flow.py",
    )
    assert all((ROOT / relative).is_file() for relative in required)
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    compose_proof = (ROOT / "scripts/verify_compose.sh").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "collaboration-check:" in makefile
    assert "make collaboration-check" in workflow
    assert "python scripts/verify_collaboration_flow.py" in compose_proof
    collaboration_proof = (ROOT / "scripts/verify_collaboration_flow.py").read_text(
        encoding="utf-8"
    )
    assert "def one_current_fact(" in collaboration_proof
    assert 'page.get("current")' in collaboration_proof
    assert 'page.get("history")' in collaboration_proof
    assert "collaboration-and-confirmed-facts.md" in docs_index
    assert "collaboration-authority.md" in docs_index
    assert "0008-governed-collaboration-and-memory-authority.md" in docs_index


def test_collaboration_walkthrough_documents_browser_authority_boundaries() -> None:
    walkthrough_path = ROOT / "docs/operations/collaboration-walkthrough.md"
    assert walkthrough_path.is_file()

    walkthrough = walkthrough_path.read_text(encoding="utf-8")
    for token in (
        "/demo/collaboration",
        "parent proposal",
        "advisor confirmation",
        "confirmed fact",
        "Case revision",
        "role switch",
        "synthetic",
        "non-production",
        "AgentTask",
        "EventSource",
        "polling",
        "collaboration-confirmed-fact.png",
    ):
        assert token in walkthrough
    assert "does not create" in walkthrough


def test_public_contract_documents_freeze_capacity_and_fact_paging() -> None:
    documents = (
        "docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md",
        "docs/superpowers/plans/2026-07-16-governed-conversation-memory-authority.md",
        "docs/decisions/0008-governed-collaboration-and-memory-authority.md",
        "docs/reference/collaboration-and-confirmed-facts.md",
    )
    for relative in documents:
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "collaboration_thread_full" in content, relative
        assert "NV012" in content, relative
        assert "current" in content and "history" in content, relative


def test_collaboration_offline_lane_runs_only_fake_http_contracts() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    lane = makefile[
        makefile.index("collaboration-check:") : makefile.index("mke-doctor:")
    ]
    assert '-m "not database"' in lane
    assert "-m database" not in lane
    assert 'not real_http_surface' not in lane
