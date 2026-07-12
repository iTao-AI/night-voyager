from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ActorRole(StrEnum):
    ADVISOR = "advisor"
    STUDENT = "student"
    PARENT = "parent"


class DemoActorChoice(StrEnum):
    ADVISOR = "advisor"
    STUDENT = "student"
    PARENT = "parent"


class Permission(StrEnum):
    READ = "read"
    DRAFT = "draft"
    REVIEW = "review"
    DECIDE = "decide"


PERMISSIONS: dict[ActorRole, frozenset[Permission]] = {
    ActorRole.ADVISOR: frozenset({Permission.READ, Permission.DRAFT, Permission.REVIEW}),
    ActorRole.STUDENT: frozenset({Permission.READ, Permission.DECIDE}),
    ActorRole.PARENT: frozenset({Permission.READ, Permission.DECIDE}),
}


def is_allowed(role: ActorRole | str, permission: Permission | str) -> bool:
    try:
        parsed_role = ActorRole(role)
        parsed_permission = Permission(permission)
    except ValueError:
        return False
    return parsed_permission in PERMISSIONS.get(parsed_role, frozenset())


@dataclass(frozen=True, slots=True)
class ActorContext:
    organization_id: UUID
    actor_id: UUID
    role: ActorRole
    session_id: UUID
