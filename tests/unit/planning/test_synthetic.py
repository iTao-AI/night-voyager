from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.adapters.protocols import PlanningAdapterRequest
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.models import Country, StudentPreferences
from night_voyager.planning.policy import evaluate_planning_run
from night_voyager.planning.synthetic import (
    PersistedSyntheticSnapshotV1,
    materialize_persisted_synthetic_input,
)
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
    SyntheticSnapshotLoadError,
)

ALL_COUNTRIES = (Country.AUSTRALIA, Country.JAPAN, Country.MALAYSIA)


def adapter_request() -> PlanningAdapterRequest:
    fixture = validate_planning_fixture().planning_input
    return PlanningAdapterRequest(
        schema_version=1,
        operation="generate_planning_run_v1",
        organization_id=fixture.organization_id,
        case_id=fixture.case.case_id,
        case_revision=fixture.case.revision,
        source_pack_id=fixture.source_pack.pack_id,
        source_pack_version=fixture.source_pack.version,
        policy_version="m3a-policy-v1",
    )


def persisted_snapshot(
    *, countries: tuple[Country, ...] = ALL_COUNTRIES
) -> PersistedSyntheticSnapshotV1:
    baseline = validate_planning_fixture().planning_input
    case = baseline.case.model_copy(
        update={
            "student": baseline.case.student.model_copy(
                update={"preferred_countries": countries}
            )
        }
    )
    return PersistedSyntheticSnapshotV1(
        schema_version=1,
        organization_id=baseline.organization_id,
        case=case,
        source_pack_id=baseline.source_pack.pack_id,
        source_pack_version=baseline.source_pack.version,
        policy_version="m3a-policy-v1",
    )


@pytest.mark.parametrize(
    ("countries", "expected"),
    (
        ((Country.AUSTRALIA,), (Country.AUSTRALIA,)),
        ((Country.JAPAN,), (Country.JAPAN,)),
        (
            (Country.AUSTRALIA, Country.JAPAN),
            (Country.AUSTRALIA, Country.JAPAN),
        ),
        (ALL_COUNTRIES, ALL_COUNTRIES),
    ),
)
def test_persisted_country_subset_filters_product_projection(
    countries: tuple[Country, ...], expected: tuple[Country, ...]
) -> None:
    baseline = validate_planning_fixture().planning_input
    planning_input = materialize_persisted_synthetic_input(
        persisted_snapshot(countries=countries)
    )
    result = evaluate_planning_run(planning_input)

    assert tuple(route.country for route in result.routes) == expected
    assert {row.country for row in planning_input.costs} <= set(expected)
    assert {row.country for row in planning_input.rankings} <= set(expected)
    assert planning_input.evidence == baseline.evidence

    evidence_claims = {item.evidence_id: item.claim for item in planning_input.evidence}
    for route in result.routes:
        linked_claims = {
            evidence_claims[use.evidence_id]
            for dimension in route.dimensions
            for use in dimension.evidence_uses
        }
        assert all(claim.startswith(f"{route.country.value}_") for claim in linked_claims)


def test_all_country_materialization_preserves_canonical_input_and_hashes() -> None:
    fixture = validate_planning_fixture()
    planning_input = materialize_persisted_synthetic_input(persisted_snapshot())
    result = evaluate_planning_run(planning_input)

    assert planning_input == fixture.planning_input
    assert canonical_sha256(planning_input.model_dump(mode="json")) == (
        "eee45c94b44d02237899dd8ec64fc636287a55fa3c2b609fa3c9ded1e5b039dd"
    )
    assert canonical_sha256(
        [item.model_dump(mode="json") for item in planning_input.evidence]
    ) == "a922aa815fd74b8dc3ed2dc7eb3fc80091bbf9d73b3dfb8bea383b83afc5bf36"
    assert canonical_sha256(result.model_dump(mode="json")) == (
        "ab7ed680bdabf6737c87c748501efb4340d85e68aed33c7e6620c1fbe4dc0621"
    )


def test_materializer_uses_persisted_case_facts_instead_of_fixture_case() -> None:
    snapshot = persisted_snapshot(countries=(Country.JAPAN,))
    baseline = validate_planning_fixture().planning_input
    persisted_budget = baseline.case.family.budget.model_copy(
        update={
            "preferred_minor": 18000000,
            "hard_ceiling_minor": 22000000,
            "elasticity_bps": 500,
        }
    )
    persisted_case = snapshot.case.model_copy(
        update={
            "revision": 2,
            "student": snapshot.case.student.model_copy(update={"intake": "2028-09"}),
            "family": snapshot.case.family.model_copy(
                update={
                    "risk_tolerance": "low",
                    "japan_risk_accepted": False,
                    "budget": persisted_budget,
                }
            ),
        }
    )
    snapshot = snapshot.model_copy(update={"case": persisted_case})

    planning_input = materialize_persisted_synthetic_input(snapshot)

    assert planning_input.case == persisted_case
    assert planning_input.case != baseline.case
    assert planning_input.case.student.intake == "2028-09"
    assert planning_input.case.student.preferred_countries == (Country.JAPAN,)
    assert planning_input.case.family.japan_risk_accepted is False
    assert planning_input.case.family.budget == persisted_budget


@pytest.mark.parametrize(
    "preferred_countries",
    (
        (),
        (Country.JAPAN, Country.JAPAN),
        (Country.JAPAN, Country.AUSTRALIA),
        ("canada",),
    ),
)
def test_preferred_countries_reject_empty_duplicate_unsorted_or_unsupported(
    preferred_countries: tuple[object, ...],
) -> None:
    baseline = validate_planning_fixture().planning_input.case.student
    with pytest.raises(ValidationError):
        StudentPreferences.model_validate(
            baseline.model_dump(mode="json")
            | {"preferred_countries": preferred_countries}
        )


def test_snapshot_rejects_cross_tenant_case_projection() -> None:
    snapshot = persisted_snapshot()
    with pytest.raises(ValidationError, match="organization"):
        PersistedSyntheticSnapshotV1.model_validate(
            snapshot.model_dump(mode="json")
            | {"organization_id": "10000000-0000-0000-0000-000000000099"}
        )


class _AsyncContext(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeSession(AbstractAsyncContextManager["_FakeSession"]):
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def begin(self) -> _AsyncContext:
        return _AsyncContext()

    async def execute(self, statement: object, parameters: dict[str, object]) -> None:
        self.calls.append((str(statement), parameters))

    async def scalar(self, statement: object, parameters: dict[str, object]) -> object:
        self.calls.append((str(statement), parameters))
        return self.payload


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def __call__(self) -> _FakeSession:
        return self.session


@pytest.mark.asyncio
async def test_postgres_repository_loads_the_exact_worker_snapshot_projection() -> None:
    snapshot = persisted_snapshot()
    session = _FakeSession(snapshot.model_dump(mode="json"))
    factory = cast(
        async_sessionmaker[AsyncSession],
        cast(Any, _FakeSessionFactory(session)),
    )
    request = adapter_request()

    loaded = await PersistedSyntheticSnapshotRepository(factory).load(request)

    assert loaded == snapshot
    assert session.calls == [
        (
            "SELECT set_config('night_voyager.organization_id',:org,true)",
            {"org": str(request.organization_id)},
        ),
        (
            "SELECT app.load_persisted_synthetic_planning_snapshot("
            ":org,:case,:revision,:pack,:pack_version,:policy)",
            {
                "org": request.organization_id,
                "case": request.case_id,
                "revision": request.case_revision,
                "pack": request.source_pack_id,
                "pack_version": request.source_pack_version,
                "policy": request.policy_version,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_postgres_repository_rejects_malformed_snapshot_projection() -> None:
    payload = persisted_snapshot().model_dump(mode="json") | {"unexpected": True}
    session = _FakeSession(payload)
    factory = cast(
        async_sessionmaker[AsyncSession],
        cast(Any, _FakeSessionFactory(session)),
    )

    with pytest.raises(SyntheticSnapshotLoadError) as captured:
        await PersistedSyntheticSnapshotRepository(factory).load(adapter_request())

    assert captured.value.retryable is False
