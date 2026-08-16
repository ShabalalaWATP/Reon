"""Keep the authoritative synthetic-user directory aligned with the seed."""

from __future__ import annotations

import re
from pathlib import Path

from mist_service.demo_seed import DEMO_IDENTITIES

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
    assert list(documented) == [f"admin{index}" for index in range(1, 109)]


def test_synthetic_user_directory_has_no_duplicate_reference_document() -> None:
    assert not (ROOT / "docs/reference/MOCK_USERS.md").exists()
