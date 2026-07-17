from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from night_voyager.identity.models import ActorRole
from night_voyager.planning.models import BudgetEnvelope, Country


class _StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class FactKey(StrEnum):
    STUDENT_INTENDED_FIELD = "student.intended_field"
    STUDENT_PREFERRED_COUNTRIES = "student.preferred_countries"
    STUDENT_INTAKE = "student.intake"
    FAMILY_RISK_TOLERANCE = "family.risk_tolerance"
    FAMILY_JAPAN_RISK_ACCEPTED = "family.japan_risk_accepted"
    FAMILY_BUDGET = "family.budget"


class MemoryCandidateState(StrEnum):
    PENDING = "pending"
    STALE = "stale"
    EXPIRED = "expired"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class VerificationDecision(StrEnum):
    CONFIRM = "confirm"
    REJECT = "reject"


_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|password|passwd|secret|access[_-]?token|bearer)\s*[:=]"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)
_URL_PATTERN = re.compile(r"(?i)\b(?:https?|file|ftp|ssh)://\S+")
_FILE_URL_PATTERN = re.compile(r"(?i)\bfile://\S+")
_URL_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b(?:https?|ftp|ssh)://[^\s/:@]+:[^\s/@]+@[^\s/]+"
)
_LOCAL_PATH_PATTERN = re.compile(
    r"(?:^|\s)(?:/(?:Users|home|etc|private|var|tmp)/\S+|[A-Za-z]:\\\S+)"
)
_SHELL_PATTERN = re.compile(
    r"`|\$\(|&&|\|\||(?:^|\s)(?:sudo|rm|bash|sh|zsh|curl|wget|python)\s+"
)


def validate_safe_text(
    value: str,
    *,
    maximum_bytes: int,
    label: str,
    reject_plain_urls: bool = True,
) -> str:
    byte_length = len(value.encode("utf-8"))
    if not 1 <= byte_length <= maximum_bytes:
        raise ValueError(f"{label} must be 1..{maximum_bytes} UTF-8 bytes")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{label} contains a control character")
    if _SECRET_PATTERN.search(value):
        raise ValueError(f"{label} contains credential material")
    if (
        (reject_plain_urls and _URL_PATTERN.search(value))
        or _FILE_URL_PATTERN.search(value)
        or _URL_CREDENTIAL_PATTERN.search(value)
    ):
        raise ValueError(f"{label} contains a URL")
    if _LOCAL_PATH_PATTERN.search(value):
        raise ValueError(f"{label} contains a local path")
    if _SHELL_PATTERN.search(value):
        raise ValueError(f"{label} contains executable structure")
    return value


class IntendedFieldProposal(_StrictModel):
    schema_version: Literal[1]
    fact_key: Literal[FactKey.STUDENT_INTENDED_FIELD]
    value: str

    @field_validator("value")
    @classmethod
    def safe_value(cls, value: str) -> str:
        return validate_safe_text(value, maximum_bytes=160, label="fact value")


class PreferredCountriesProposal(_StrictModel):
    schema_version: Literal[1]
    fact_key: Literal[FactKey.STUDENT_PREFERRED_COUNTRIES]
    value: tuple[Country, ...]

    @field_validator("value", mode="before")
    @classmethod
    def parse_json_countries(cls, value: object) -> tuple[Country, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("preferred countries must be an array")
        countries: list[Country] = []
        for item in cast(list[object] | tuple[object, ...], value):
            if isinstance(item, Country):
                countries.append(item)
            elif type(item) is str:
                countries.append(Country(item))
            else:
                raise ValueError("preferred countries contain an unsupported value")
        return tuple(countries)

    @field_validator("value")
    @classmethod
    def validate_countries(cls, value: tuple[Country, ...]) -> tuple[Country, ...]:
        if not value:
            raise ValueError("preferred countries must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("preferred countries must be unique")
        if value != tuple(sorted(value, key=lambda item: item.value)):
            raise ValueError("preferred countries must be sorted")
        return value


class IntakeProposal(_StrictModel):
    schema_version: Literal[1]
    fact_key: Literal[FactKey.STUDENT_INTAKE]
    value: str

    @field_validator("value")
    @classmethod
    def validate_intake(cls, value: str) -> str:
        value = validate_safe_text(value, maximum_bytes=160, label="fact value")
        if re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", value) is None:
            raise ValueError("intake must be a valid calendar month in YYYY-MM")
        return value


class RiskToleranceProposal(_StrictModel):
    schema_version: Literal[1]
    fact_key: Literal[FactKey.FAMILY_RISK_TOLERANCE]
    value: Literal["low", "medium", "high"]


class JapanRiskAcceptedProposal(_StrictModel):
    schema_version: Literal[1]
    fact_key: Literal[FactKey.FAMILY_JAPAN_RISK_ACCEPTED]
    value: bool


class BudgetProposal(_StrictModel):
    schema_version: Literal[1]
    fact_key: Literal[FactKey.FAMILY_BUDGET]
    value: BudgetEnvelope

    @field_validator("value", mode="before")
    @classmethod
    def strict_budget(cls, value: object) -> BudgetEnvelope:
        if isinstance(value, BudgetEnvelope):
            return value
        return BudgetEnvelope.model_validate(value, strict=True)


type FactProposal = Annotated[
    IntendedFieldProposal
    | PreferredCountriesProposal
    | IntakeProposal
    | RiskToleranceProposal
    | JapanRiskAcceptedProposal
    | BudgetProposal,
    Field(discriminator="fact_key"),
]

type FactValue = str | tuple[Country, ...] | bool | BudgetEnvelope
_FACT_PROPOSAL_ADAPTER: TypeAdapter[FactProposal] = TypeAdapter(FactProposal)


class AppendMessageCommand(_StrictModel):
    thread_id: UUID
    body: str

    @field_validator("body")
    @classmethod
    def safe_body(cls, value: str) -> str:
        return validate_safe_text(
            value,
            maximum_bytes=4096,
            label="message body",
            reject_plain_urls=False,
        )


class ProposeMemoryCandidateCommand(_StrictModel):
    message_event_id: UUID
    case_revision: PositiveInt
    proposal: FactProposal


class VerifyMemoryCandidateCommand(_StrictModel):
    candidate_id: UUID
    expected_case_revision: PositiveInt
    decision: VerificationDecision
    reason: str

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value: str) -> str:
        return validate_safe_text(value, maximum_bytes=512, label="verification reason")


class CollaborationThreadV1(_StrictModel):
    schema_version: Literal[1]
    thread_id: UUID
    case_id: UUID
    created_by_actor_id: UUID
    created_at: datetime


class MessageEventV1(_StrictModel):
    schema_version: Literal[1]
    message_event_id: UUID
    thread_id: UUID
    case_id: UUID
    sequence_no: PositiveInt
    actor_id: UUID
    actor_role: ActorRole
    body: str
    content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    created_at: datetime


class MessagePageV1(_StrictModel):
    schema_version: Literal[1]
    items: tuple[MessageEventV1, ...]
    next_after_sequence: PositiveInt | None


class _FactProjection(_StrictModel):
    schema_version: Literal[1]
    fact_key: FactKey
    value: FactValue

    @model_validator(mode="before")
    @classmethod
    def bind_fact_value(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        mapping = cast(Mapping[str, object], value)
        if not {"schema_version", "fact_key", "value"} <= mapping.keys():
            return mapping
        proposal = _FACT_PROPOSAL_ADAPTER.validate_python(
            {
                "schema_version": mapping["schema_version"],
                "fact_key": mapping["fact_key"],
                "value": mapping["value"],
            }
        )
        normalized = dict(mapping)
        normalized["fact_key"] = proposal.fact_key
        normalized["value"] = proposal.value
        return normalized


class MemoryCandidateParticipantV1(_FactProjection):
    state: MemoryCandidateState
    created_at: datetime
    expires_at: datetime


class MemoryCandidateAdvisorV1(MemoryCandidateParticipantV1):
    candidate_id: UUID
    message_event_id: UUID
    source_message_sequence_no: PositiveInt
    subject_actor_id: UUID
    subject_role: ActorRole
    case_revision: PositiveInt
    verification_id: UUID | None
    decision: VerificationDecision | None
    reason: str | None
    request_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    value_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ConfirmedFactParticipantV1(_FactProjection):
    fact_version: PositiveInt
    confirmed_at: datetime
    subject_role: ActorRole
    confirming_advisor_role: Literal[ActorRole.ADVISOR]


class ConfirmedFactAdvisorV1(ConfirmedFactParticipantV1):
    confirmed_fact_id: UUID
    candidate_id: UUID
    verification_id: UUID
    source_message_event_id: UUID
    source_message_sequence_no: PositiveInt
    source_message_sha256_prefix: Annotated[str, Field(pattern=r"^[0-9a-f]{12}$")]
    confirming_advisor_actor_id: UUID
    reason: str
    supersedes_fact_id: UUID | None


class ConfirmedFactHistoryCursorV1(_StrictModel):
    schema_version: Literal[1]
    snapshot: datetime
    fact_key: FactKey
    fact_version: PositiveInt

    @field_validator("snapshot")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("confirmed fact cursor snapshot requires a timezone")
        return value

    def encode(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @classmethod
    def decode(cls, value: str) -> ConfirmedFactHistoryCursorV1:
        if not 1 <= len(value) <= 512 or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
            raise ValueError("invalid confirmed fact cursor")
        try:
            payload = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
            return cls.model_validate_json(payload)
        except (binascii.Error, UnicodeDecodeError, ValidationError) as error:
            raise ValueError("invalid confirmed fact cursor") from error


class ConfirmedFactParticipantPageV1(_StrictModel):
    schema_version: Literal[1]
    current: tuple[ConfirmedFactParticipantV1, ...]


class ConfirmedFactAdvisorPageV1(_StrictModel):
    schema_version: Literal[1]
    current: tuple[ConfirmedFactAdvisorV1, ...]
    history: tuple[ConfirmedFactAdvisorV1, ...]
    next_cursor: str | None
