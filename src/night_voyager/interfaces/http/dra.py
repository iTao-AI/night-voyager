from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, PositiveInt, StringConstraints, model_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse

from night_voyager.config import Settings
from night_voyager.dra.application import DraCandidateService
from night_voyager.dra.errors import DraAuthorizationError, DraConflictError
from night_voyager.dra.models import (
    DraCandidateImportV1,
    DraCanonicalArtifactInputV1,
    DraEvidenceProjectionV1,
    DraProducerPinV1,
    DraRunAcceptanceV1,
    DraRunProjectionV1,
    DraRunRequestIdentityV1,
    SourceAttestationV1,
)
from night_voyager.dra.ports import VerifyDraCandidateCommand
from night_voyager.dra.postgres import PostgresDraCandidateRepository
from night_voyager.identity.auth import require_origin
from night_voyager.identity.models import ActorContext
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService
from night_voyager.interfaces.http.decision import problem
from night_voyager.interfaces.http.dependencies import (
    resolve_actor_context,
    resolve_mutation_actor_context,
)
from night_voyager.interfaces.http.identity import SESSION_COOKIE


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraCandidateImportRequest(StrictModel):
    schema_version: Literal["night-voyager.dra-candidate-import.v1"]
    expected_case_revision: PositiveInt
    producer: DraProducerPinV1
    request_identity: DraRunRequestIdentityV1
    acceptance: DraRunAcceptanceV1
    run: DraRunProjectionV1
    artifact: DraCanonicalArtifactInputV1
    evidence: tuple[DraEvidenceProjectionV1, ...]


class DraVerificationDecisionRequest(StrictModel):
    schema_version: Literal[1]
    expected_case_revision: PositiveInt
    dra_evidence_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    decision: Literal["approve", "reject"]
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    source_attestation: SourceAttestationV1 | None = None

    @model_validator(mode="after")
    def exact_decision_shape(self) -> Self:
        if (self.decision == "approve") != (self.source_attestation is not None):
            raise ValueError("dra_verification_decision_shape_invalid")
        return self


def create_dra_router(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def enforce_origin(request: Request) -> None:
        try:
            require_origin(request.headers.get("Origin"), settings.allowed_origins)
        except ValueError as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "request rejected") from error

    async def mutation_context(
        session: AsyncSession, raw_session: str | None, csrf: str | None
    ) -> ActorContext:
        return await resolve_mutation_actor_context(
            raw_session,
            csrf,
            IdentityService(IdentityRepository(session), settings.secret_key),
        )

    async def read_context(session: AsyncSession, raw_session: str | None) -> ActorContext:
        return await resolve_actor_context(
            raw_session, IdentityService(IdentityRepository(session), settings.secret_key)
        )

    def key_or_problem(value: str | None) -> str | JSONResponse:
        if value is None or not 16 <= len(value) <= 200:
            return problem(400, "invalid_idempotency_key", "Idempotency-Key is required")
        return value

    @router.post("/cases/{case_id}/dra-candidates", status_code=201, response_model=None)
    async def import_candidate(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        payload: DraCandidateImportRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        key = key_or_problem(idempotency_key)
        if isinstance(key, JSONResponse):
            return key
        async with session_factory() as session, session.begin():
            context = await mutation_context(session, raw_session, csrf)
            command = DraCandidateImportV1(
                organization_id=context.organization_id,
                case_id=case_id,
                **payload.model_dump(exclude_computed_fields=True),
            )
            try:
                result = await DraCandidateService(
                    PostgresDraCandidateRepository(session)
                ).import_candidate(context, command, key)
            except DraAuthorizationError:
                return problem(404, "resource_unavailable", "resource unavailable")
            except DraConflictError as error:
                return problem(409, str(error).lower(), "request conflicts with current state")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result.model_dump(mode="json")}

    @router.get("/cases/{case_id}/dra-candidates/{candidate_id}", response_model=None)
    async def get_candidate(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        candidate_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> dict[str, object] | JSONResponse:
        async with session_factory() as session, session.begin():
            context = await read_context(session, raw_session)
            try:
                result = await DraCandidateService(
                    PostgresDraCandidateRepository(session)
                ).get_candidate(context, case_id, candidate_id)
            except DraAuthorizationError:
                return problem(404, "resource_unavailable", "resource unavailable")
        if result is None:
            return problem(404, "resource_unavailable", "resource unavailable")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result.model_dump(mode="json")}

    @router.post(
        "/cases/{case_id}/dra-candidates/{candidate_id}/verification-decisions",
        status_code=201,
        response_model=None,
    )
    async def verify_candidate(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        candidate_id: UUID,
        payload: DraVerificationDecisionRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        key = key_or_problem(idempotency_key)
        if isinstance(key, JSONResponse):
            return key
        async with session_factory() as session, session.begin():
            context = await mutation_context(session, raw_session, csrf)
            try:
                command = VerifyDraCandidateCommand(
                    case_id=case_id,
                    candidate_id=candidate_id,
                    **payload.model_dump(exclude={"schema_version"}),
                )
                result = await DraCandidateService(
                    PostgresDraCandidateRepository(session)
                ).verify_candidate(context, command, key)
            except DraAuthorizationError:
                return problem(404, "resource_unavailable", "resource unavailable")
            except DraConflictError as error:
                return problem(409, str(error).lower(), "request conflicts with current state")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result.model_dump(mode="json")}

    return router
