"""Initialise the locked sequence used for immutable synthetic usernames."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.admin_models import AdminIdentitySequence
from mist_service.models import User

ADMIN_USERNAME = re.compile(r"admin([1-9][0-9]*)")


async def initialise_admin_identity_sequence(session: AsyncSession) -> None:
    usernames = await session.scalars(select(User.username))
    numbers = [
        int(match.group(1))
        for username in usernames
        if (match := ADMIN_USERNAME.fullmatch(username))
    ]
    required = max(numbers, default=0) + 1
    sequence = await session.scalar(
        select(AdminIdentitySequence)
        .where(AdminIdentitySequence.id == 1)
        .with_for_update()
    )
    if sequence is None:
        session.add(AdminIdentitySequence(id=1, next_value=required))
    elif sequence.next_value < required:
        sequence.next_value = required
    await session.flush()
