"""Keep the authoritative synthetic-user directory aligned with the seed."""

from __future__ import annotations

import re
from pathlib import Path

from istari_service.demo_seed import DEMO_IDENTITIES

ROOT = Path(__file__).parents[3]
DIRECTORY = ROOT / "docs/architecture/ORGANISATION_AND_ROUTING.md"
ROW = re.compile(
    r"^\| `(?P<username>admin\d+)` \| (?P<name>[^|]+) \| [^|]+ \| [^|]+ \| "
    r"(?P<state>Active|Inactive) \|$"
)


def test_documented_user_directory_matches_every_seeded_identity() -> None:
    contents = DIRECTORY.read_text(encoding="utf-8")
    section = contents.split("## Complete synthetic user directory", maxsplit=1)[1]
    section = section.split("\n## ", maxsplit=1)[0]
    documented = {}
    for line in section.splitlines():
        match = ROW.fullmatch(line)
        if match is not None:
            documented[match["username"]] = (
                match["name"].strip(),
                match["state"] == "Active",
            )

    expected = {
        identity.username: (identity.display_name, identity.active)
        for identity in DEMO_IDENTITIES
    }
    assert documented == expected
    assert list(documented) == [f"admin{index}" for index in range(1, 74)]


def test_mock_user_reference_is_a_locator_not_a_duplicate_roster() -> None:
    reference = (ROOT / "docs/reference/MOCK_USERS.md").read_text(encoding="utf-8")
    assert "ORGANISATION_AND_ROUTING.md#complete-synthetic-user-directory" in reference
    assert reference.count("| `admin") == 0
