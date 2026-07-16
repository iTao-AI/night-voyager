from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from night_voyager.collaboration.models import (
    AppendMessageCommand,
    BudgetProposal,
    CollaborationThreadV1,
    ConfirmedFactAdvisorV1,
    ConfirmedFactParticipantV1,
    FactKey,
    FactProposal,
    IntakeProposal,
    IntendedFieldProposal,
    JapanRiskAcceptedProposal,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    MessageEventV1,
    MessagePageV1,
    PreferredCountriesProposal,
    ProposeMemoryCandidateCommand,
    RiskToleranceProposal,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.planning.models import BudgetEnvelope, Country

THREAD_ID = UUID("10000000-0000-0000-0000-000000000001")
MESSAGE_ID = UUID("20000000-0000-0000-0000-000000000001")
CANDIDATE_ID = UUID("30000000-0000-0000-0000-000000000001")


def budget() -> BudgetEnvelope:
    return BudgetEnvelope(
        schema_version=1,
        currency="CNY",
        period="program_total",
        preferred_minor=34_000_000,
        hard_ceiling_minor=40_000_000,
        elasticity_bps=1_000,
    )


def test_closed_vocabularies_are_exact() -> None:
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


@pytest.mark.parametrize(
    "proposal",
    (
        IntendedFieldProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTENDED_FIELD,
            value="computing",
        ),
        PreferredCountriesProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_PREFERRED_COUNTRIES,
            value=(Country.AUSTRALIA, Country.JAPAN),
        ),
        IntakeProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTAKE,
            value="2027-02",
        ),
        RiskToleranceProposal(
            schema_version=1,
            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
            value="medium",
        ),
        JapanRiskAcceptedProposal(
            schema_version=1,
            fact_key=FactKey.FAMILY_JAPAN_RISK_ACCEPTED,
            value=True,
        ),
        BudgetProposal(
            schema_version=1,
            fact_key=FactKey.FAMILY_BUDGET,
            value=budget(),
        ),
    ),
)
def test_fact_proposals_are_discriminated_and_strict(proposal: FactProposal) -> None:
    adapter: TypeAdapter[FactProposal] = TypeAdapter(FactProposal)
    parsed = adapter.validate_python(proposal.model_dump())
    assert type(parsed) is type(proposal)
    with pytest.raises(ValidationError):
        type(proposal).model_validate({**proposal.model_dump(), "unexpected": True})


def test_json_country_values_are_controlled_but_not_broadly_coerced() -> None:
    adapter: TypeAdapter[FactProposal] = TypeAdapter(FactProposal)
    parsed = adapter.validate_python(
        {
            "schema_version": 1,
            "fact_key": "student.preferred_countries",
            "value": ["australia", "japan"],
        }
    )
    assert isinstance(parsed, PreferredCountriesProposal)
    assert parsed.value == (Country.AUSTRALIA, Country.JAPAN)
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "schema_version": 1,
                "fact_key": "student.preferred_countries",
                "value": [1],
            }
        )


@pytest.mark.parametrize(
    "value",
    (
        (),
        (Country.JAPAN, Country.AUSTRALIA),
        (Country.AUSTRALIA, Country.AUSTRALIA),
    ),
)
def test_preferred_countries_are_nonempty_sorted_and_unique(value: object) -> None:
    with pytest.raises(ValidationError):
        PreferredCountriesProposal.model_validate(
            {
                "schema_version": 1,
                "fact_key": "student.preferred_countries",
                "value": value,
            }
        )


@pytest.mark.parametrize("value", ("2027-2", "2027-00", "2027-13", "2027-02x"))
def test_intake_is_an_exact_calendar_month(value: str) -> None:
    with pytest.raises(ValidationError):
        IntakeProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTAKE,
            value=value,
        )


def test_boolean_and_budget_values_refuse_coercion() -> None:
    with pytest.raises(ValidationError):
        JapanRiskAcceptedProposal.model_validate(
            {
                "schema_version": 1,
                "fact_key": "family.japan_risk_accepted",
                "value": 1,
            }
        )
    raw_budget = budget().model_dump()
    with pytest.raises(ValidationError):
        BudgetProposal.model_validate(
            {
                "schema_version": 1,
                "fact_key": "family.budget",
                "value": {**raw_budget, "preferred_minor": "34000000"},
            }
        )


def test_commands_are_frozen_strict_and_extra_forbid() -> None:
    append = AppendMessageCommand(thread_id=THREAD_ID, body="Family discussion")
    propose = ProposeMemoryCandidateCommand(
        message_event_id=MESSAGE_ID,
        case_revision=1,
        proposal=IntakeProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTAKE,
            value="2027-02",
        ),
    )
    verify = VerifyMemoryCandidateCommand(
        candidate_id=CANDIDATE_ID,
        expected_case_revision=1,
        decision=VerificationDecision.CONFIRM,
        reason="Confirmed with the family",
    )
    assert append.model_config.get("frozen") is True
    assert propose.model_config.get("strict") is True
    assert verify.model_config.get("extra") == "forbid"
    with pytest.raises(ValidationError):
        AppendMessageCommand.model_validate(
            {"thread_id": THREAD_ID, "body": "ok", "actor_id": MESSAGE_ID}
        )


def test_role_safe_projection_models_are_distinct_strict_supersets() -> None:
    participant_candidate = set(MemoryCandidateParticipantV1.model_fields)
    advisor_candidate = set(MemoryCandidateAdvisorV1.model_fields)
    assert participant_candidate < advisor_candidate
    assert {
        "candidate_id",
        "verification_id",
        "reason",
        "request_sha256",
        "value_sha256",
    }.isdisjoint(participant_candidate)

    participant_fact = set(ConfirmedFactParticipantV1.model_fields)
    advisor_fact = set(ConfirmedFactAdvisorV1.model_fields)
    assert participant_fact < advisor_fact
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
    }.isdisjoint(participant_fact)

    for model in (
        CollaborationThreadV1,
        MessageEventV1,
        MessagePageV1,
        MemoryCandidateParticipantV1,
        MemoryCandidateAdvisorV1,
        ConfirmedFactParticipantV1,
        ConfirmedFactAdvisorV1,
    ):
        assert model.model_config == {"frozen": True, "extra": "forbid", "strict": True}
        assert "schema_version" in model.model_fields


def test_read_projection_fact_key_selects_the_only_legal_value_type() -> None:
    payload = {
        "schema_version": 1,
        "fact_key": FactKey.STUDENT_INTAKE,
        "value": "2027-02",
        "state": MemoryCandidateState.PENDING,
        "created_at": datetime(2026, 7, 17, tzinfo=UTC),
        "expires_at": datetime(2026, 7, 24, tzinfo=UTC),
    }
    assert MemoryCandidateParticipantV1.model_validate(payload).value == "2027-02"
    with pytest.raises(ValidationError):
        MemoryCandidateParticipantV1.model_validate({**payload, "value": True})
