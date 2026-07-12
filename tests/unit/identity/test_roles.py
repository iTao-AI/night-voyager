from __future__ import annotations

from night_voyager.identity.models import ActorRole, Permission, is_allowed


def test_advisor_can_review_and_participants_can_read() -> None:
    assert is_allowed(ActorRole.ADVISOR, Permission.REVIEW)
    assert is_allowed(ActorRole.STUDENT, Permission.READ)
    assert is_allowed(ActorRole.PARENT, Permission.READ)


def test_unknown_roles_and_unlisted_permissions_are_denied() -> None:
    assert not is_allowed("administrator", Permission.REVIEW)
    assert not is_allowed(ActorRole.STUDENT, Permission.REVIEW)
    assert not is_allowed(ActorRole.ADVISOR, "override-policy")
