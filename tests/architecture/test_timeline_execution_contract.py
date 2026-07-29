from pathlib import Path

from night_voyager.api import create_app

ROOT = Path(__file__).resolve().parents[2]

PATHS = {
    "/api/v1/plan-execution-context",
    "/api/v1/timeline-plans/{timeline_plan_id}/executions",
    "/api/v1/cases/{case_id}/timeline-execution",
    "/api/v1/timeline-executions/{execution_id}/checkpoint-attestations",
    "/api/v1/timeline-executions/{execution_id}/checkpoint-verifications",
    "/api/v1/timeline-executions/{execution_id}/reassessments",
}


def test_timeline_execution_routes_are_exact_and_have_no_task_or_sse_surface() -> None:
    schema = create_app().openapi()
    paths = set(schema["paths"])
    assert paths >= PATHS
    timeline_paths = {path for path in paths if "timeline-execution" in path}
    assert timeline_paths == PATHS - {
        "/api/v1/plan-execution-context",
        "/api/v1/timeline-plans/{timeline_plan_id}/executions",
    }
    assert not any(
        "task" in path or "event" in path
        for path in PATHS
    )


def test_router_uses_strict_models_server_ids_and_existing_identity_helpers() -> None:
    source = (
        ROOT / "src/night_voyager/interfaces/http/timeline_execution.py"
    ).read_text(encoding="utf-8")
    assert 'ConfigDict(extra="forbid")' in source
    assert "resolve_actor_context" in source
    assert "resolve_mutation_actor_context" in source
    assert "require_origin" in source
    assert source.count("uuid4()") == 8
    assert "AgentTask" not in source
    assert "EventSource" not in source
    assert "provider" not in source.lower()


def test_api_classifier_and_wiring_include_timeline_execution() -> None:
    source = (ROOT / "src/night_voyager/api.py").read_text(encoding="utf-8")
    assert "is_timeline_execution_http_path(path)" in source
    assert "create_timeline_execution_router" in source
