from pathlib import Path


def test_seed_declares_separate_task_ready_case_without_resetting_golden_case() -> None:
    source = Path("scripts/seed_demo.py").read_text(encoding="utf-8")

    assert "CONNECTED_DEMO_CASE_ID" in source
    assert "_seed_task_case" in source
    assert "ON CONFLICT DO NOTHING" in source
    assert "UPDATE app.student_cases SET state='planning'" not in source


def test_m4a_compose_proof_is_bounded_and_retains_m3b_and_restart_probes() -> None:
    proof = Path("scripts/verify_m4a_flow.py")
    assert proof.is_file()
    source = proof.read_text(encoding="utf-8")
    for required in (
        "needs_advisor_review",
        "review_required",
        "Last-Event-ID",
        "--verify-existing",
        "range(30)",
        "agent_task_events",
    ):
        assert required in source

    compose = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    assert compose.index("verify_m3b_flow.py") < compose.index("verify_m4a_flow.py")
    assert "restart api worker" in compose
    assert "verify_m4a_flow.py --verify-existing" in compose
    assert "down --volumes --remove-orphans" in compose


def test_m4a_reference_and_operations_documents_are_public_and_linked() -> None:
    expected = (
        Path("docs/reference/agent-tasks-and-events.md"),
        Path("docs/operations/worker-and-sse.md"),
    )
    for path in expected:
        assert path.is_file(), path
        source = path.read_text(encoding="utf-8")
        assert "/" + "Users/" not in source
        assert "Car" + "eer" not in source
    index = Path("docs/README.md").read_text(encoding="utf-8")
    assert "reference/agent-tasks-and-events.md" in index
    assert "operations/worker-and-sse.md" in index
