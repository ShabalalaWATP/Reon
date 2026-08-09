"""Active configuration restoration does not rewrite an unchanged projection."""

from sqlalchemy import select

from conftest import ApiHarness
from istari_service.configuration_seed import restore_active_configuration_projection
from istari_service.management_models import OrganisationClosure
from istari_service.organisation_models import OrganisationUnit


async def test_unchanged_configuration_restore_preserves_versions_and_closure(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session, session.begin():
        versions_before = {
            unit.id: unit.version
            for unit in await session.scalars(select(OrganisationUnit))
        }
        closure_before = set(
            (
                await session.execute(
                    select(
                        OrganisationClosure.ancestor_id,
                        OrganisationClosure.descendant_id,
                        OrganisationClosure.depth,
                    )
                )
            )
            .tuples()
            .all()
        )

        assert await restore_active_configuration_projection(session) is True
        await session.flush()

        versions_after = {
            unit.id: unit.version
            for unit in await session.scalars(select(OrganisationUnit))
        }
        closure_after = set(
            (
                await session.execute(
                    select(
                        OrganisationClosure.ancestor_id,
                        OrganisationClosure.descendant_id,
                        OrganisationClosure.depth,
                    )
                )
            )
            .tuples()
            .all()
        )

    assert versions_after == versions_before
    assert closure_after == closure_before
