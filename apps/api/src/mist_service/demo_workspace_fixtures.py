"""Public-safe Scottish-football workspace identity fixtures."""

from __future__ import annotations

from dataclasses import dataclass

from mist_service.models import UserRole


@dataclass(frozen=True, slots=True)
class WorkspaceIdentityFixture:
    display_name: str
    role: UserRole
    scope: str
    unit_code: str
    manager: bool


_DELIVERY_STAFF = (
    ("CEDAR_TEAM", "Cedar Team", "Kenny Dalglish", "Denis Law"),
    ("QUARTZ_TEAM", "Quartz Team", "Graeme Souness", "Alan Hansen"),
    ("LANTERN_TEAM", "Lantern Team", "Gordon Strachan", "Ally McCoist"),
    ("MOSAIC_TEAM", "Mosaic Team", "Darren Fletcher", "James McFadden"),
    ("COMPASS_TEAM", "Compass Team", "Barry Ferguson", "Paul McStay"),
    ("EMBER_TEAM", "Ember Team", "Gary McAllister", "John Collins"),
    ("ATLAS_TEAM", "Atlas Team", "Kevin Gallacher", "Colin Hendry"),
    ("HARBOUR_TEAM", "Harbour Team", "Alex McLeish", "Willie Miller"),
    ("BEACON_TEAM", "Beacon Team", "Joe Jordan", "Archie Gemmill"),
    ("SLATE_TEAM", "Slate Team", "Dave Mackay", "Billy Bremner"),
    ("ORCHARD_TEAM", "Orchard Team", "Jim Baxter", "Danny McGrain"),
    ("LUMEN_TEAM", "Lumen Team", "Jimmy Johnstone", "Bobby Lennox"),
    ("NORTHSTAR_TEAM", "Northstar Team", "John Greig", "Sandy Jardine"),
    ("COPPER_TEAM", "Copper Team", "Maurice Johnston", "Gordon Durie"),
    ("ROWAN_TEAM", "Rowan Team", "Stuart McCall", "Neil McCann"),
    ("VELA_TEAM", "Vela Team", "Don Hutchison", "Christian Dailly"),
    ("KEEL_TEAM", "Keel Team", "Gary Naysmith", "Lee McCulloch"),
    ("FLINT_TEAM", "Flint Team", "Steven Naismith", "Charlie Adam"),
    ("THISTLE_TEAM", "Thistle Team", "Robert Snodgrass", "Steven Fletcher"),
    ("GRANITE_TEAM", "Granite Team", "James Morrison", "Shaun Maloney"),
    ("KESTREL_TEAM", "Kestrel Team", "Barry Bannan", "David Marshall"),
    ("JUNIPER_TEAM", "Juniper Team", "Allan McGregor", "Stephen O'Donnell"),
    ("VALE_TEAM", "Vale Team", "Lyndon Dykes", "Ryan Porteous"),
    ("TIDAL_TEAM", "Tidal Team", "Jack Hendry", "Aaron Hickey"),
    ("GROVE_TEAM", "Grove Team", "Scott McKenna", "Greg Taylor"),
    ("PRISM_TEAM", "Prism Team", "Ryan Jack", "Stuart Armstrong"),
)

SSG_IDENTITY_FIXTURES = (
    WorkspaceIdentityFixture(
        "Lawrence Shankland",
        UserRole.DELIVERY_TEAM_LEAD,
        "SSG Team",
        "SSG_TEAM",
        True,
    ),
    WorkspaceIdentityFixture(
        "Tommy Conway", UserRole.DELIVERY_SPECIALIST, "SSG Team", "SSG_TEAM", False
    ),
    WorkspaceIdentityFixture(
        "Steve Clarke", UserRole.DELIVERY_SPECIALIST, "SSG Team", "SSG_TEAM", False
    ),
    WorkspaceIdentityFixture(
        "Derek McInnes", UserRole.DELIVERY_SPECIALIST, "SSG Team", "SSG_TEAM", False
    ),
)

_ROUTING_STAFF = (
    ("CRIOC", "CRIOC", UserRole.INTAKE_TRIAGE, "Alan Rough", "Willie Ormond"),
    ("JOCK", "JOCK", UserRole.SERVICE_COORDINATION, "Craig Levein", "Walter Smith"),
    ("SYGOC", "SYGOC", UserRole.SERVICE_COORDINATION, "Alex Ferguson", "Tommy Burns"),
    ("MYGOC", "MYGOC", UserRole.SERVICE_COORDINATION, "Jock Stein", "Bill Shankly"),
    (
        "ACSA_B_OPS",
        "ACSA-B Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Willie Johnston",
        "Asa Hartford",
    ),
    (
        "AURORA_OPS",
        "Aurora Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Craig Burley",
        "Kevin Thomson",
    ),
    (
        "VERTEX_OPS",
        "Vertex Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Scott Brown",
        "Kris Boyd",
    ),
    (
        "NIMBUS_OPS",
        "Nimbus Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Kenny Miller",
        "Garry O'Connor",
    ),
    (
        "PARALLAX_OPS",
        "Parallax Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "David Weir",
        "Russell Anderson",
    ),
    (
        "HORIZON_OPS",
        "Horizon Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Gary Caldwell",
        "Steven Caldwell",
    ),
    (
        "MERIDIAN_OPS",
        "Meridian Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Lee Wallace",
        "Ross McCormack",
    ),
    (
        "SOLSTICE_OPS",
        "Solstice Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Mark Burchill",
        "Nigel Quashie",
    ),
    (
        "FRONTIER_OPS",
        "Frontier Ops",
        UserRole.OPERATIONS_ALLOCATION,
        "Matt Ritchie",
        "Oliver Burke",
    ),
)

DELIVERY_IDENTITY_FIXTURES = tuple(
    fixture
    for code, scope, manager, member in _DELIVERY_STAFF
    for fixture in (
        WorkspaceIdentityFixture(
            manager, UserRole.DELIVERY_TEAM_LEAD, scope, code, True
        ),
        WorkspaceIdentityFixture(
            member, UserRole.DELIVERY_SPECIALIST, scope, code, False
        ),
    )
)

ROUTING_IDENTITY_FIXTURES = tuple(
    fixture
    for code, scope, role, manager, member in _ROUTING_STAFF
    for fixture in (
        WorkspaceIdentityFixture(manager, role, scope, code, True),
        WorkspaceIdentityFixture(member, role, scope, code, False),
    )
)

# The combined QC workspace mirrors a delivery team: QC Managers hold release
# accountability, QC Users perform quality review. Angus Gunn and Neil Alexander
# are seeded earlier in the base directory; these fixtures complete the roster.
_QC_SCOPE = "Combined QC Team"
QC_IDENTITY_FIXTURES = (
    WorkspaceIdentityFixture(
        "Zander Clark", UserRole.QUALITY_RELEASE, _QC_SCOPE, "QC_TEAM", True
    ),
    *(
        WorkspaceIdentityFixture(
            name, UserRole.QUALITY_RELEASE, _QC_SCOPE, "QC_TEAM", False
        )
        for name in (
            "Liam Kelly",
            "Anthony Ralston",
            "John Souttar",
            "Lewis Morgan",
            "Ryan Fraser",
            "Kevin Nisbet",
            "Josh Doig",
        )
    ),
)
