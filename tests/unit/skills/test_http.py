from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.config import Environment, Settings
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.interfaces.http.identity import SESSION_COOKIE
from night_voyager.interfaces.http.skills import (
    ActivateSkillCandidateRequest,
    CreateSkillCandidateRequest,
    EvaluateSkillCandidateRequest,
    RollbackSkillRequest,
    create_skills_router,
    skills_request_validation_problem,
)
from night_voyager.skills.errors import (
    SkillActivationStaleError,
    SkillAuthorizationError,
    SkillCandidateStaleError,
    SkillCandidateTerminalError,
    SkillEvaluationFailedError,
    SkillIdempotencyConflictError,
    SkillPersistenceError,
    SkillPinInvalidError,
    SkillRollbackUnsupportedError,
    SkillScopeExpansionError,
    SkillVersionUnavailableError,
)
from night_voyager.skills.models import (
    SkillBindingKind,
    SkillEvaluationStatus,
    SkillKey,
)
from night_voyager.skills.ports import (
    ActivateSkillCandidateCommand,
    CreateSkillCandidateCommand,
    EvaluateSkillCandidateCommand,
    PlanningSkillInspectorV1,
    RollbackSkillCommand,
    SkillActivationRecordedV1,
    SkillCandidateCreatedV1,
    SkillCatalogSummaryV1,
    SkillCatalogV1,
    SkillEvaluationRecordedV1,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
SESSION = UUID("30000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000001")
DEFINITION = UUID("70000000-0000-0000-0000-000000000001")
CANDIDATE = UUID("72000000-0000-0000-0000-000000000001")
EVALUATION = UUID("73000000-0000-0000-0000-000000000001")
ACTIVATION = UUID("74000000-0000-0000-0000-000000000001")
ORIGIN = "http://127.0.0.1:3000"
IDEMPOTENCY_KEY = "http-skill-lifecycle-key"
OPAQUE_SESSION = "opaque-session-token"
CSRF = "opaque-csrf-token"


def context() -> ActorContext:
    return ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, SESSION)


class FakeSkillService:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.failure: Exception | None = None

    def _fail(self) -> None:
        if self.failure is not None:
            raise self.failure

    async def list_catalog(self, context: ActorContext) -> SkillCatalogV1:
        self.calls.append(("list_catalog", context))
        self._fail()
        return SkillCatalogV1(
            schema_version=1,
            items=(
                SkillCatalogSummaryV1(
                    schema_version=1,
                    skill_key=SkillKey.STUDY_DESTINATION_COMPARE,
                    definition_id=DEFINITION,
                    owner_actor_id=ADVISOR,
                    binding_kind=SkillBindingKind.PLANNING_RUNTIME,
                    latest_version="1.0.1",
                    active_version="1.0.0",
                    activation_sequence=1,
                ),
            ),
        )

    async def get_catalog_item(
        self, context: ActorContext, skill_key: SkillKey
    ) -> Any:
        self.calls.append(("get_catalog_item", context, skill_key))
        self._fail()
        # The exact strict detail model is covered by the service/repository tests.
        return None

    async def create_candidate(
        self,
        context: ActorContext,
        command: CreateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillCandidateCreatedV1:
        self.calls.append(("create_candidate", context, command, idempotency_key))
        self._fail()
        return SkillCandidateCreatedV1(
            schema_version=1, candidate_id=CANDIDATE, replayed=False
        )

    async def evaluate_candidate(
        self,
        context: ActorContext,
        command: EvaluateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillEvaluationRecordedV1:
        self.calls.append(("evaluate_candidate", context, command, idempotency_key))
        self._fail()
        return SkillEvaluationRecordedV1(
            schema_version=1,
            evaluation_id=EVALUATION,
            status=SkillEvaluationStatus.PASSED,
            replayed=False,
        )

    async def activate_candidate(
        self,
        context: ActorContext,
        command: ActivateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        self.calls.append(("activate_candidate", context, command, idempotency_key))
        self._fail()
        return SkillActivationRecordedV1(
            schema_version=1,
            activation_event_id=ACTIVATION,
            activation_sequence=2,
            replayed=False,
        )

    async def rollback_skill(
        self,
        context: ActorContext,
        command: RollbackSkillCommand,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        self.calls.append(("rollback_skill", context, command, idempotency_key))
        self._fail()
        return SkillActivationRecordedV1(
            schema_version=1,
            activation_event_id=ACTIVATION,
            activation_sequence=3,
            replayed=False,
        )

    async def inspect_planning_skill(
        self, context: ActorContext, case_id: UUID
    ) -> PlanningSkillInspectorV1:
        self.calls.append(("inspect_planning_skill", context, case_id))
        self._fail()
        return PlanningSkillInspectorV1(
            schema_version=1,
            case_id=case_id,
            operation=None,
            active_skill_key=SkillKey.STUDY_DESTINATION_COMPARE,
            active_version="1.0.0",
            activation_sequence=1,
            evaluator_id="night-voyager.deterministic-skill-evaluator",
            evaluator_version="v1",
            evaluation_dataset_id="night-voyager.study-destination-compare.eval",
            evaluation_dataset_version="1.0.0",
            task_request_sha256_prefix=None,
            version_content_sha256_prefix="111111111111",
            runtime_binding_sha256_prefix="cd897b22d034",
            adapter_id=None,
            adapter_version=None,
            pin_status="not_created",
        )


class DummySession:
    async def __aenter__(self) -> DummySession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def begin(self) -> DummySession:
        return self


def dummy_session_factory() -> DummySession:
    return DummySession()


def build_client(
    monkeypatch: pytest.MonkeyPatch,
    service: FakeSkillService,
) -> TestClient:
    from night_voyager.interfaces.http import skills as skill_http

    class FakeIdentityService:
        def __init__(self, *_args: object) -> None:
            pass

        async def resolve(self, raw_session: str) -> ActorContext | None:
            return context() if raw_session == OPAQUE_SESSION else None

    async def resolve_read(
        raw_session: str | None, _identity: object
    ) -> ActorContext:
        if raw_session != OPAQUE_SESSION:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
        return context()

    async def resolve_mutation(
        raw_session: str | None,
        csrf: str | None,
        _identity: object,
    ) -> ActorContext:
        if raw_session != OPAQUE_SESSION or csrf != CSRF:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
        return context()

    monkeypatch.setattr(skill_http, "resolve_actor_context", resolve_read)
    monkeypatch.setattr(skill_http, "resolve_mutation_actor_context", resolve_mutation)
    monkeypatch.setattr(skill_http, "IdentityService", FakeIdentityService)
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def validation_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, error: RequestValidationError
    ) -> Any:
        bounded = skills_request_validation_problem(request, error)
        if bounded is not None:
            return bounded
        raise error

    settings = Settings(
        environment=Environment.TEST,
        allowed_origins=(ORIGIN,),
    )
    app.include_router(
        create_skills_router(
            settings,
            cast(async_sessionmaker[AsyncSession], dummy_session_factory),
            service_factory=lambda _session: service,
        )
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, OPAQUE_SESSION)
    return client


def auth_headers(*, mutation: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if mutation:
        headers.update(
            {
                "Origin": ORIGIN,
                "X-CSRF-Token": CSRF,
                "Idempotency-Key": IDEMPOTENCY_KEY,
            }
        )
    return headers


def replace_session(client: TestClient, raw_session: str | None) -> None:
    client.cookies.clear()
    if raw_session is not None:
        client.cookies.set(SESSION_COOKIE, raw_session)


def test_router_freezes_exact_seven_path_method_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = cast(FastAPI, build_client(monkeypatch, FakeSkillService()).app)
    paths = cast(dict[str, dict[str, object]], app.openapi()["paths"])
    expected = {
        "/api/v1/skills": {"get"},
        "/api/v1/skills/{skill_key}": {"get"},
        "/api/v1/skills/{skill_key}/change-candidates": {"post"},
        "/api/v1/skill-change-candidates/{candidate_id}/evaluations": {"post"},
        "/api/v1/skill-change-candidates/{candidate_id}/activations": {"post"},
        "/api/v1/skills/{skill_key}/rollbacks": {"post"},
        "/api/v1/cases/{case_id}/planning-skill-inspector": {"get"},
    }
    assert {path: set(paths[path]) & {"get", "post"} for path in expected} == expected


def test_openapi_preserves_exact_mutation_request_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = cast(FastAPI, build_client(monkeypatch, FakeSkillService()).app)
    openapi = app.openapi()
    paths = cast(dict[str, dict[str, Any]], openapi["paths"])
    components = cast(
        dict[str, object], openapi["components"]["schemas"]
    )
    expected = {
        "/api/v1/skills/{skill_key}/change-candidates": (
            CreateSkillCandidateRequest
        ),
        "/api/v1/skill-change-candidates/{candidate_id}/evaluations": (
            EvaluateSkillCandidateRequest
        ),
        "/api/v1/skill-change-candidates/{candidate_id}/activations": (
            ActivateSkillCandidateRequest
        ),
        "/api/v1/skills/{skill_key}/rollbacks": RollbackSkillRequest,
    }

    def dereference(
        value: object,
        definitions: dict[str, object],
        prefix: str,
    ) -> object:
        if isinstance(value, dict):
            mapping = cast(dict[str, object], value)
            reference = mapping.get("$ref")
            if isinstance(reference, str) and reference.startswith(prefix):
                return dereference(
                    definitions[reference.removeprefix(prefix)], definitions, prefix
                )
            return {
                key: dereference(item, definitions, prefix)
                for key, item in mapping.items()
                if key != "$defs" and not (key == "default" and item is None)
            }
        if isinstance(value, list):
            return [
                dereference(item, definitions, prefix)
                for item in cast(list[object], value)
            ]
        return value

    for path, model in expected.items():
        operation = paths[path]["post"]
        actual = operation["requestBody"]["content"]["application/json"]["schema"]
        expected_schema = model.model_json_schema()
        expected_definitions = cast(
            dict[str, object], expected_schema.get("$defs", {})
        )
        assert dereference(actual, components, "#/components/schemas/") == dereference(
            expected_schema, expected_definitions, "#/$defs/"
        )


@pytest.mark.parametrize(
    ("path", "method", "parameter_name"),
    [
        (
            "/api/v1/skill-change-candidates/{candidate_id}/evaluations",
            "post",
            "candidate_id",
        ),
        (
            "/api/v1/skill-change-candidates/{candidate_id}/activations",
            "post",
            "candidate_id",
        ),
        (
            "/api/v1/cases/{case_id}/planning-skill-inspector",
            "get",
            "case_id",
        ),
    ],
)
def test_openapi_preserves_uuid_resource_path_contracts(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    method: str,
    parameter_name: str,
) -> None:
    app = cast(FastAPI, build_client(monkeypatch, FakeSkillService()).app)
    operation = cast(dict[str, Any], app.openapi()["paths"][path][method])
    parameters = cast(list[dict[str, Any]], operation["parameters"])
    parameter = next(item for item in parameters if item["name"] == parameter_name)
    assert parameter["schema"]["type"] == "string"
    assert parameter["schema"]["format"] == "uuid"


def test_catalog_and_inspector_are_session_bound_and_no_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeSkillService()
    client = build_client(monkeypatch, service)

    catalog = client.get("/api/v1/skills")
    inspector = client.get(
        f"/api/v1/cases/{CASE}/planning-skill-inspector"
    )
    assert catalog.status_code == 200
    assert catalog.headers["cache-control"] == "no-store"
    assert catalog.json()["items"][0]["binding_kind"] == "planning_runtime"
    assert inspector.status_code == 200
    assert inspector.headers["cache-control"] == "no-store"
    assert inspector.json()["pin_status"] == "not_created"
    assert "skill_definition_id" not in inspector.json()
    assert "runtime_binding_sha256" not in inspector.json()

    client.cookies.clear()
    unauthenticated = client.get("/api/v1/skills")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert unauthenticated.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("path", "body", "expected_call"),
    [
        (
            "/api/v1/skills/study-destination-compare/change-candidates",
            {
                "schema_version": 1,
                "proposed_version": "1.0.1",
                "provenance": "maintainer_proposal",
                "reason": "Add deterministic negative compatibility coverage.",
                "reference": "public-safe-test-reference",
            },
            "create_candidate",
        ),
        (
            f"/api/v1/skill-change-candidates/{CANDIDATE}/evaluations",
            {"schema_version": 1},
            "evaluate_candidate",
        ),
        (
            f"/api/v1/skill-change-candidates/{CANDIDATE}/activations",
            {
                "schema_version": 1,
                "expected_active_version": "1.0.0",
                "expected_activation_sequence": 1,
                "reason": "Promote the evaluated compatibility revision.",
            },
            "activate_candidate",
        ),
        (
            "/api/v1/skills/study-destination-compare/rollbacks",
            {
                "schema_version": 1,
                "target_version": "1.0.0",
                "expected_active_version": "1.0.1",
                "expected_activation_sequence": 2,
                "reason": "Restore the prior supported version.",
            },
            "rollback_skill",
        ),
    ],
)
def test_mutations_require_exact_origin_csrf_session_and_idempotency(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    body: dict[str, object],
    expected_call: str,
) -> None:
    service = FakeSkillService()
    client = build_client(monkeypatch, service)

    response = client.post(
        path, json=body, headers=auth_headers(mutation=True)
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert service.calls[-1][0] == expected_call
    assert service.calls[-1][-1] == IDEMPOTENCY_KEY

    no_origin = client.post(
        path,
        json=body,
        headers={
            "X-CSRF-Token": CSRF,
            "Idempotency-Key": IDEMPOTENCY_KEY,
        },
    )
    assert no_origin.status_code == 403
    assert no_origin.json()["code"] == "request_rejected"

    no_csrf = client.post(
        path,
        json=body,
        headers={"Origin": ORIGIN, "Idempotency-Key": IDEMPOTENCY_KEY},
    )
    assert no_csrf.status_code == 401
    assert no_csrf.json()["code"] == "authentication_failed"

    no_key = client.post(
        path,
        json=body,
        headers={"Origin": ORIGIN, "X-CSRF-Token": CSRF},
    )
    assert no_key.status_code == 400
    assert no_key.json()["code"] == "invalid_idempotency_key"


def test_browser_cannot_submit_manifest_or_evaluation_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = build_client(monkeypatch, FakeSkillService())
    requests = (
        (
            "/api/v1/skills/study-destination-compare/change-candidates",
            {
                "schema_version": 1,
                "proposed_version": "1.0.1",
                "provenance": "maintainer_proposal",
                "reason": "Attempt to smuggle runtime authority.",
                "executor_id": "browser-controlled",
            },
        ),
        (
            f"/api/v1/skill-change-candidates/{CANDIDATE}/evaluations",
            {"schema_version": 1, "status": "passed"},
        ),
        (
            f"/api/v1/skill-change-candidates/{CANDIDATE}/activations",
            {
                "schema_version": 1,
                "expected_active_version": "1.0.0",
                "expected_activation_sequence": 1,
                "reason": "Malformed activation.",
                "status": "passed",
            },
        ),
        (
            "/api/v1/skills/study-destination-compare/rollbacks",
            {
                "schema_version": 1,
                "target_version": "1.0.0",
                "expected_active_version": "1.0.1",
                "expected_activation_sequence": 2,
                "reason": "Malformed rollback.",
                "runtime_binding_sha256": "f" * 64,
            },
        ),
    )
    for path, body in requests:
        response = client.post(
            path,
            json=body,
            headers=auth_headers(mutation=True),
        )
        assert response.status_code == 422
        assert response.headers["content-type"].startswith(
            "application/problem+json"
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["code"] == "request_validation_failed"


@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        (SkillAuthorizationError(), 404, "resource_unavailable"),
        (SkillVersionUnavailableError(), 409, "skill_version_unavailable"),
        (SkillCandidateStaleError(), 409, "skill_candidate_stale"),
        (SkillCandidateTerminalError(), 409, "skill_candidate_terminal"),
        (SkillEvaluationFailedError(), 409, "skill_evaluation_failed"),
        (SkillActivationStaleError(), 409, "skill_activation_stale"),
        (SkillScopeExpansionError(), 409, "skill_scope_expansion"),
        (SkillRollbackUnsupportedError(), 409, "skill_rollback_unsupported"),
        (SkillPinInvalidError(), 409, "skill_pin_invalid"),
        (SkillIdempotencyConflictError(), 409, "idempotency_conflict"),
        (SkillPersistenceError(), 503, "persistence_unavailable"),
        (RuntimeError("raw internal detail"), 503, "persistence_unavailable"),
    ],
)
def test_failures_map_to_closed_bounded_rfc9457_problems(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    status_code: int,
    code: str,
) -> None:
    service = FakeSkillService()
    service.failure = failure
    response = build_client(monkeypatch, service).get(
        "/api/v1/skills"
    )

    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["code"] == code
    assert "raw internal detail" not in response.text


def test_invalid_skill_path_is_non_enumerating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = build_client(monkeypatch, FakeSkillService())
    response: Response = client.get(
        "/api/v1/skills/not-a-skill"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "resource_unavailable"

    client.cookies.clear()
    unauthenticated = client.get("/api/v1/skills/not-a-skill")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "authentication_failed"


@pytest.mark.parametrize("raw_session", [None, "wrong-session-token"])
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        (
            "post",
            "/api/v1/skill-change-candidates/not-a-uuid/evaluations",
            {"schema_version": 1},
        ),
        (
            "post",
            "/api/v1/skill-change-candidates/not-a-uuid/activations",
            {
                "schema_version": 1,
                "expected_active_version": "1.0.0",
                "expected_activation_sequence": 1,
                "reason": "Bounded review input.",
            },
        ),
        (
            "get",
            "/api/v1/cases/not-a-uuid/planning-skill-inspector",
            None,
        ),
    ],
)
def test_authentication_precedes_malformed_resource_uuid(
    monkeypatch: pytest.MonkeyPatch,
    raw_session: str | None,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    client = build_client(monkeypatch, FakeSkillService())
    replace_session(client, raw_session)
    response = client.request(
        method,
        path,
        json=body,
        headers=auth_headers(mutation=method == "post"),
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["code"] == "authentication_failed"


@pytest.mark.parametrize("raw_session", [None, "wrong-session-token"])
@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/api/v1/skills/study-destination-compare/change-candidates",
            {
                "schema_version": 1,
                "proposed_version": "1.0.1",
                "provenance": "maintainer_proposal",
                "reason": "Malformed authority attempt.",
                "executor_id": "browser-controlled",
            },
        ),
        (
            f"/api/v1/skill-change-candidates/{CANDIDATE}/evaluations",
            {"schema_version": 1, "status": "passed"},
        ),
        (
            f"/api/v1/skill-change-candidates/{CANDIDATE}/activations",
            {
                "schema_version": 1,
                "expected_active_version": "1.0.0",
                "expected_activation_sequence": 1,
            },
        ),
        (
            "/api/v1/skills/study-destination-compare/rollbacks",
            {
                "schema_version": 2,
                "target_version": "1.0.0",
                "expected_active_version": "1.0.1",
                "expected_activation_sequence": 2,
                "reason": "Malformed schema version.",
            },
        ),
    ],
)
def test_authentication_precedes_strict_mutation_body_validation(
    monkeypatch: pytest.MonkeyPatch,
    raw_session: str | None,
    path: str,
    body: dict[str, object],
) -> None:
    client = build_client(monkeypatch, FakeSkillService())
    replace_session(client, raw_session)
    response = client.post(
        path,
        json=body,
        headers=auth_headers(mutation=True),
    )
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["code"] == "authentication_failed"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        (
            "post",
            "/api/v1/skill-change-candidates/not-a-uuid/evaluations",
            {"schema_version": 1},
        ),
        (
            "post",
            "/api/v1/skill-change-candidates/not-a-uuid/activations",
            {
                "schema_version": 1,
                "expected_active_version": "1.0.0",
                "expected_activation_sequence": 1,
                "reason": "Bounded review input.",
            },
        ),
        (
            "get",
            "/api/v1/cases/not-a-uuid/planning-skill-inspector",
            None,
        ),
    ],
)
def test_authenticated_malformed_resource_uuid_is_non_enumerating(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    response = build_client(monkeypatch, FakeSkillService()).request(
        method,
        path,
        json=body,
        headers=auth_headers(mutation=method == "post"),
    )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["code"] == "resource_unavailable"
