from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.collaboration.models import (
    AppendMessageCommand,
    BudgetProposal,
    FactKey,
    IntakeProposal,
    IntendedFieldProposal,
    JapanRiskAcceptedProposal,
    MemoryCandidateState,
    PreferredCountriesProposal,
    RiskToleranceProposal,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.policy import (
    apply_confirmed_fact,
    project_candidate_state,
    role_allows_fact,
    validate_message_body,
)
from night_voyager.identity.models import ActorRole
from night_voyager.planning.models import (
    BudgetEnvelope,
    Country,
    FamilyPreferences,
    StudentCaseRevision,
    StudentPreferences,
)

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
CASE_ID = UUID("20000000-0000-0000-0000-000000000001")
THREAD_ID = UUID("30000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


def case_revision() -> StudentCaseRevision:
    return StudentCaseRevision(
        schema_version=1,
        organization_id=ORG_ID,
        case_id=CASE_ID,
        revision=1,
        student=StudentPreferences(
            schema_version=1,
            intended_field="computing",
            preferred_countries=(Country.AUSTRALIA, Country.JAPAN),
            intake="2027-02",
        ),
        family=FamilyPreferences(
            schema_version=1,
            risk_tolerance="medium",
            japan_risk_accepted=False,
            budget=BudgetEnvelope(
                schema_version=1,
                currency="CNY",
                period="program_total",
                preferred_minor=34_000_000,
                hard_ceiling_minor=40_000_000,
                elasticity_bps=1_000,
            ),
        ),
    )


def test_role_fact_allowlist_is_closed() -> None:
    student = {
        FactKey.STUDENT_INTENDED_FIELD,
        FactKey.STUDENT_PREFERRED_COUNTRIES,
        FactKey.STUDENT_INTAKE,
    }
    parent = {
        FactKey.FAMILY_RISK_TOLERANCE,
        FactKey.FAMILY_JAPAN_RISK_ACCEPTED,
        FactKey.FAMILY_BUDGET,
    }
    for fact_key in FactKey:
        assert role_allows_fact(ActorRole.STUDENT, fact_key) is (fact_key in student)
        assert role_allows_fact(ActorRole.PARENT, fact_key) is (fact_key in parent)
        assert not role_allows_fact(ActorRole.ADVISOR, fact_key)


@pytest.mark.parametrize(
    "body",
    (
        "",
        "a" * 4097,
        "你" * 1366,
        "contains\x00control",
        "password=hunter2",
        "/Users/demo/private.txt",
        "https://user:pass@example.invalid/profile",
        "please run $(whoami)",
        "execute rm -rf cache",
    ),
)
def test_message_body_rejects_out_of_bounds_or_unsafe_content(body: str) -> None:
    with pytest.raises(ValueError):
        validate_message_body(body)


def test_message_body_uses_utf8_bytes_and_allows_ordinary_words() -> None:
    assert validate_message_body("请 ignore 排名，并 approve computing 偏好")
    assert len(validate_message_body("你" * 1365).encode("utf-8")) == 4095


@pytest.mark.parametrize(
    "factory",
    (
        lambda: IntendedFieldProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTENDED_FIELD,
            value="a" * 161,
        ),
        lambda: IntendedFieldProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTENDED_FIELD,
            value="api_key=secret-value",
        ),
        lambda: VerifyMemoryCandidateCommand(
            candidate_id=CASE_ID,
            expected_case_revision=1,
            decision=VerificationDecision.REJECT,
            reason="r" * 513,
        ),
    ),
)
def test_fact_strings_and_reasons_are_bounded_and_safe(factory: object) -> None:
    with pytest.raises(ValidationError):
        factory()  # type: ignore[operator]


@pytest.mark.parametrize(
    ("decision", "current_revision", "expires_at", "expected"),
    (
        (VerificationDecision.CONFIRM, 2, NOW - timedelta(days=1), MemoryCandidateState.CONFIRMED),
        (VerificationDecision.REJECT, 2, NOW - timedelta(days=1), MemoryCandidateState.REJECTED),
        (None, 2, NOW - timedelta(days=1), MemoryCandidateState.STALE),
        (None, 1, NOW, MemoryCandidateState.EXPIRED),
        (None, 1, NOW + timedelta(seconds=1), MemoryCandidateState.PENDING),
    ),
)
def test_candidate_state_precedence(
    decision: VerificationDecision | None,
    current_revision: int,
    expires_at: datetime,
    expected: MemoryCandidateState,
) -> None:
    assert (
        project_candidate_state(
            decision=decision,
            pinned_revision=1,
            current_revision=current_revision,
            expires_at=expires_at,
            now=NOW,
        )
        is expected
    )


def test_canonical_hash_ignores_mapping_order_and_binds_value() -> None:
    assert canonical_sha256({"fact": "student.intake", "value": "2027-02"}) == (
        canonical_sha256({"value": "2027-02", "fact": "student.intake"})
    )
    assert canonical_sha256({"value": "2027-02"}) != canonical_sha256({"value": "2028-02"})


@pytest.mark.parametrize(
    ("proposal", "section", "field", "value"),
    (
        (
            IntendedFieldProposal(
                schema_version=1,
                fact_key=FactKey.STUDENT_INTENDED_FIELD,
                value="data science",
            ),
            "student",
            "intended_field",
            "data science",
        ),
        (
            PreferredCountriesProposal(
                schema_version=1,
                fact_key=FactKey.STUDENT_PREFERRED_COUNTRIES,
                value=(Country.AUSTRALIA, Country.MALAYSIA),
            ),
            "student",
            "preferred_countries",
            ["australia", "malaysia"],
        ),
        (
            IntakeProposal(
                schema_version=1,
                fact_key=FactKey.STUDENT_INTAKE,
                value="2028-07",
            ),
            "student",
            "intake",
            "2028-07",
        ),
        (
            RiskToleranceProposal(
                schema_version=1,
                fact_key=FactKey.FAMILY_RISK_TOLERANCE,
                value="high",
            ),
            "family",
            "risk_tolerance",
            "high",
        ),
        (
            JapanRiskAcceptedProposal(
                schema_version=1,
                fact_key=FactKey.FAMILY_JAPAN_RISK_ACCEPTED,
                value=True,
            ),
            "family",
            "japan_risk_accepted",
            True,
        ),
        (
            BudgetProposal(
                schema_version=1,
                fact_key=FactKey.FAMILY_BUDGET,
                value=BudgetEnvelope(
                    schema_version=1,
                    currency="CNY",
                    period="program_total",
                    preferred_minor=30_000_000,
                    hard_ceiling_minor=36_000_000,
                    elasticity_bps=500,
                ),
            ),
            "family",
            "budget",
            {
                "schema_version": 1,
                "currency": "CNY",
                "period": "program_total",
                "preferred_minor": 30_000_000,
                "hard_ceiling_minor": 36_000_000,
                "elasticity_bps": 500,
                "refused": False,
            },
        ),
    ),
)
def test_apply_confirmed_fact_changes_one_leaf_and_increments_revision(
    proposal: object,
    section: str,
    field: str,
    value: object,
) -> None:
    before = case_revision().model_dump(mode="json")
    after = apply_confirmed_fact(case_revision(), proposal).model_dump(mode="json")  # type: ignore[arg-type]
    assert after["revision"] == 2
    assert after[section][field] == value  # type: ignore[index]

    expected = deepcopy(before)
    expected["revision"] = 2
    expected_section = cast(dict[str, object], expected[section])
    expected_section[field] = value
    expected[section] = expected_section
    assert canonical_sha256(after) == canonical_sha256(expected)


def test_commands_apply_message_and_reason_validation() -> None:
    assert AppendMessageCommand(thread_id=THREAD_ID, body="https://example.invalid/info").body
    with pytest.raises(ValidationError):
        AppendMessageCommand(
            thread_id=THREAD_ID,
            body="https://user:pass@example.invalid/info",
        )
