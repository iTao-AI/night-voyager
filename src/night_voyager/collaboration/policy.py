from __future__ import annotations

from datetime import datetime

from night_voyager.collaboration.models import (
    FactKey,
    FactProposal,
    IntakeProposal,
    IntendedFieldProposal,
    JapanRiskAcceptedProposal,
    MemoryCandidateState,
    PreferredCountriesProposal,
    RiskToleranceProposal,
    VerificationDecision,
    validate_safe_text,
)
from night_voyager.identity.models import ActorRole
from night_voyager.planning.models import (
    FamilyPreferences,
    StudentCaseRevision,
    StudentPreferences,
)

_ROLE_FACTS: dict[ActorRole, frozenset[FactKey]] = {
    ActorRole.ADVISOR: frozenset(),
    ActorRole.STUDENT: frozenset(
        {
            FactKey.STUDENT_INTENDED_FIELD,
            FactKey.STUDENT_PREFERRED_COUNTRIES,
            FactKey.STUDENT_INTAKE,
        }
    ),
    ActorRole.PARENT: frozenset(
        {
            FactKey.FAMILY_RISK_TOLERANCE,
            FactKey.FAMILY_JAPAN_RISK_ACCEPTED,
            FactKey.FAMILY_BUDGET,
        }
    ),
}


def role_allows_fact(role: ActorRole | str, fact_key: FactKey | str) -> bool:
    try:
        parsed_role = ActorRole(role)
        parsed_fact_key = FactKey(fact_key)
    except ValueError:
        return False
    return parsed_fact_key in _ROLE_FACTS[parsed_role]


def validate_message_body(value: str) -> str:
    return validate_safe_text(
        value,
        maximum_bytes=4096,
        label="message body",
        reject_plain_urls=False,
    )


def project_candidate_state(
    *,
    decision: VerificationDecision | None,
    pinned_revision: int,
    current_revision: int,
    expires_at: datetime,
    now: datetime,
) -> MemoryCandidateState:
    if decision is VerificationDecision.CONFIRM:
        return MemoryCandidateState.CONFIRMED
    if decision is VerificationDecision.REJECT:
        return MemoryCandidateState.REJECTED
    if pinned_revision != current_revision:
        return MemoryCandidateState.STALE
    if now >= expires_at:
        return MemoryCandidateState.EXPIRED
    return MemoryCandidateState.PENDING


def apply_confirmed_fact(
    revision: StudentCaseRevision, proposal: FactProposal
) -> StudentCaseRevision:
    student = revision.student
    family = revision.family

    if isinstance(proposal, IntendedFieldProposal):
        student = StudentPreferences(
            schema_version=student.schema_version,
            intended_field=proposal.value,
            preferred_countries=student.preferred_countries,
            intake=student.intake,
        )
    elif isinstance(proposal, PreferredCountriesProposal):
        student = StudentPreferences(
            schema_version=student.schema_version,
            intended_field=student.intended_field,
            preferred_countries=proposal.value,
            intake=student.intake,
        )
    elif isinstance(proposal, IntakeProposal):
        student = StudentPreferences(
            schema_version=student.schema_version,
            intended_field=student.intended_field,
            preferred_countries=student.preferred_countries,
            intake=proposal.value,
        )
    elif isinstance(proposal, RiskToleranceProposal):
        family = FamilyPreferences(
            schema_version=family.schema_version,
            risk_tolerance=proposal.value,
            japan_risk_accepted=family.japan_risk_accepted,
            budget=family.budget,
        )
    elif isinstance(proposal, JapanRiskAcceptedProposal):
        family = FamilyPreferences(
            schema_version=family.schema_version,
            risk_tolerance=family.risk_tolerance,
            japan_risk_accepted=proposal.value,
            budget=family.budget,
        )
    else:
        family = FamilyPreferences(
            schema_version=family.schema_version,
            risk_tolerance=family.risk_tolerance,
            japan_risk_accepted=family.japan_risk_accepted,
            budget=proposal.value,
        )
    return StudentCaseRevision(
        schema_version=revision.schema_version,
        organization_id=revision.organization_id,
        case_id=revision.case_id,
        revision=revision.revision + 1,
        student=student,
        family=family,
    )
