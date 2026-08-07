"""Synthetic user helpers shared by repository tests."""

from uuid import uuid4

from istari_service.domain import Actor
from istari_service.models import User, UserRole


def make_user(role: UserRole, *, scope: str = "Area A") -> User:
    suffix = uuid4().hex
    return User(
        username=f"user.{suffix}@example.test",
        display_name=f"Synthetic {role.value.title()}",
        password_hash="$argon2id$synthetic",
        role=role,
        scope=scope,
    )


def actor_from(user: User) -> Actor:
    return Actor(user.id, user.username, user.display_name, user.role, user.scope)
