# Synthetic MVP Users

These identities are local/test fixtures. Names are borrowed from Scottish
football for memorable synthetic data and make no statement about the real
people. Every seeded account uses password `admin` only when
`ALLOW_DEMO_USERS=true` in a local or test environment. The password is not a
production credential.

Usernames are permanent, sequential account references. Display names, roles,
scopes, memberships and active state can be maintained by a Platform
Administrator. Account removal is reversible deactivation so request and audit
history keep a valid actor reference.

## Shared and routing accounts

| Logon | Display name | Representative role | Scope | Initial state |
| --- | --- | --- | --- | --- |
| `admin1` | Andy Robertson | Platform Administrator | Platform support | Active |
| `admin2` | John McGinn | Customer | Requesting Area A | Active |
| `admin3` | Billy Gilmour | Customer | Requesting Area B | Active |
| `admin4` | Scott McTominay | JIOC Routing User | JIOC | Active |
| `admin5` | Callum McGregor | Command Routing User | DIGOC, SYGOC and MYGOC | Active |
| `admin6` | Kieran Tierney | Ops Routing User | All configured Ops groups | Active |
| `admin7` | Ryan Christie | JIOC Routing User | JIOC | Active |
| `admin10` | Craig Gordon | Ops Routing User | All configured Ops groups | Active |
| `admin15` | Angus Gunn | QC Manager | Shared QC | Active |
| `admin16` | James Forrest | Customer | Requesting Area A | Inactive |

## Team staffing

Every team has at least one active Manager and one active Analyst. OSG Team has
three Managers and seven Analysts because it is the initial operational team.
All sibling teams remain first-class selectable destinations and their own
candidate groups can be exercised through Camunda.

| Command | Ops group | Team | Manager account(s) | Analyst account(s) |
| --- | --- | --- | --- | --- |
| DIGOC | NCGI-A Ops | OSG Team | `admin8` Grant Hanley; `admin9` Kenny McLean; `admin17` Lawrence Shankland | `admin11` Lewis Ferguson; `admin12` Nathan Patterson; `admin13` Ben Doak; `admin14` Che Adams; `admin18` Tommy Conway; `admin19` Steve Clarke; `admin20` Derek McInnes |
| DIGOC | NCGI-A Ops | Cedar Team | `admin21` Kenny Dalglish | `admin22` Denis Law |
| DIGOC | NCGI-A Ops | Quartz Team | `admin23` Graeme Souness | `admin24` Alan Hansen |
| DIGOC | Aurora Ops | Lantern Team | `admin25` Gordon Strachan | `admin26` Ally McCoist |
| DIGOC | Aurora Ops | Mosaic Team | `admin27` Darren Fletcher | `admin28` James McFadden |
| DIGOC | Aurora Ops | Compass Team | `admin29` Barry Ferguson | `admin30` Paul McStay |
| DIGOC | Vertex Ops | Ember Team | `admin31` Gary McAllister | `admin32` John Collins |
| DIGOC | Vertex Ops | Atlas Team | `admin33` Kevin Gallacher | `admin34` Colin Hendry |
| DIGOC | Vertex Ops | Harbour Team | `admin35` Alex McLeish | `admin36` Willie Miller |
| SYGOC | Nimbus Ops | Beacon Team | `admin37` Joe Jordan | `admin38` Archie Gemmill |
| SYGOC | Nimbus Ops | Slate Team | `admin39` Dave Mackay | `admin40` Billy Bremner |
| SYGOC | Nimbus Ops | Orchard Team | `admin41` Jim Baxter | `admin42` Danny McGrain |
| SYGOC | Parallax Ops | Lumen Team | `admin43` Jimmy Johnstone | `admin44` Bobby Lennox |
| SYGOC | Parallax Ops | Northstar Team | `admin45` John Greig | `admin46` Sandy Jardine |
| SYGOC | Parallax Ops | Copper Team | `admin47` Maurice Johnston | `admin48` Gordon Durie |
| SYGOC | Horizon Ops | Rowan Team | `admin49` Stuart McCall | `admin50` Neil McCann |
| SYGOC | Horizon Ops | Vela Team | `admin51` Don Hutchison | `admin52` Christian Dailly |
| SYGOC | Horizon Ops | Keel Team | `admin53` Gary Naysmith | `admin54` Lee McCulloch |
| MYGOC | Meridian Ops | Flint Team | `admin55` Steven Naismith | `admin56` Charlie Adam |
| MYGOC | Meridian Ops | Thistle Team | `admin57` Robert Snodgrass | `admin58` Steven Fletcher |
| MYGOC | Meridian Ops | Granite Team | `admin59` James Morrison | `admin60` Shaun Maloney |
| MYGOC | Solstice Ops | Kestrel Team | `admin61` Barry Bannan | `admin62` David Marshall |
| MYGOC | Solstice Ops | Juniper Team | `admin63` Allan McGregor | `admin64` Stephen O'Donnell |
| MYGOC | Solstice Ops | Vale Team | `admin65` Lyndon Dykes | `admin66` Ryan Porteous |
| MYGOC | Frontier Ops | Tidal Team | `admin67` Jack Hendry | `admin68` Aaron Hickey |
| MYGOC | Frontier Ops | Grove Team | `admin69` Scott McKenna | `admin70` Greg Taylor |
| MYGOC | Frontier Ops | Prism Team | `admin71` Ryan Jack | `admin72` Stuart Armstrong |

If administration leaves a team without an active, role-qualified Manager or
Analyst, the application derives `Awaiting staffing`. The destination stays
selectable and never borrows OSG identities.
