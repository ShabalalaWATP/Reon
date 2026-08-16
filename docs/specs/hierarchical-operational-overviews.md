# Hierarchical Operational Overviews

## Status

Approved implementation specification, 9 August 2026.

## Outcome

Mist provides a restrained role-specific landing experience for immediate
orientation and a separate statistics workspace for detailed reporting. A
statistics grant authorises its root organisation unit and, when configured,
every descendant beneath that root. It never authorises a parent or sibling.

`My actions` remains the place for personal and explicitly shared actions. `My requests` remains the
Customer request register. Team and operational overviews answer what is
happening now. The Statistics workspace answers why performance is changing and
supports hierarchy navigation, comparisons and definitions.

## Visual thesis

A calm graphite operational surface using one cyan accent, strong type hierarchy
and unboxed information bands. Landing views show only the measures needed to
orient and act, while detailed evidence remains in the Statistics workspace.

## Content plan

1. State the signed-in role and authorised organisation context.
2. Show a small set of immediate measures and actions.
3. Show one operational comparison or priority register.
4. Link to the established work, tracking, team and statistics workspaces.

## Interaction thesis

- Preserve date filters while moving down or back up the authorised hierarchy.
- Use fast colour and underline transitions to make drill-down affordances clear.
- Respect reduced-motion preferences and retain a complete keyboard path.

## Information architecture

| User | Default landing | Detailed reporting |
| --- | --- | --- |
| Customer | My requests | No organisation statistics |
| Team Analyst | My actions | No management statistics without an explicit grant |
| Team Manager | Team overview | Exact-team statistics |
| JIOC, Command and Ops routing users | Operational overview | Granted root and descendants |
| QC Manager | Quality and release overview | Explicitly granted quality scope |
| Platform Administrator | Administration overview | Whole-platform aggregate and health |

Profile remains in the account menu. An incomplete personal profile may produce
one discreet completion prompt, but profile fields never influence access.

## Hierarchical statistics authority

A non-platform query names both an active management grant and a selected unit.
The selected unit is authorised only when it is the grant root, or it is a
configured descendant and `include_descendants` is true. Platform Administrators
use the platform scope and may select any configured unit, while the default
platform selection remains the root.

The server returns the selected node, its authorised breadcrumb and its direct
configured children. It returns neither names nor counts for parents above the
grant root or sibling branches outside the root.

Examples:

- JIOC may select JIOC, any Command, any Ops group or any Team;
- DIGOC may select DIGOC and its descendants, never JIOC, SYGOC or MYGOC;
- NCGI-A Ops may select that Ops group and SSG, Cedar or Quartz, never an Ops
  sibling or DIGOC aggregate; and
- OSG Team may select only OSG Team.

An independently granted second root is presented as another scope. It does not
turn the roots into siblings that can be traversed from one another.

## Statistics experience

The selected-node breadcrumb and direct children form the primary scope control.
The grant selector is separate and appears only when a user holds multiple roots.
Child comparisons are actionable links that select that authorised child.

The default period is 30 days. Presets provide 7, 30, 90 and 365 days. Throughput
is daily up to 31 days, weekly up to 120 days and monthly beyond that. Charts show
labels and values, and their data tables are available through an expanded
`View data` disclosure rather than permanently duplicating every visual.

Empty advanced measures are omitted. Suppressed measures are grouped into a
single privacy explanation. Terminal workflow states never appear as active
bottlenecks; completed interval durations remain available separately.

## Landing composition

Operational routing users are greeted by first name. Their personal assigned,
waiting and due-soon action counts appear in a **Your workload** region. Active
demand, due risk, completions and direct child comparison appear separately in a
named organisation workload region which states that it is not personal workload.
Team Managers use the Team overview, extended with statistics and links to the
Service Request board, Work Package board, Calendar and People.
Team Analysts retain My actions as their default. Platform Administrators receive a
separate administration overview with account, configuration and projection
health links rather than a generic operational card grid. Staff overview pages do
not repeat the complete sidebar as a second destination list.

## Security and privacy

- React never derives authority from a breadcrumb or cached tree.
- Every dashboard, evolution and export request repeats grant and selected-unit
  authorisation.
- Non-authorised unit identifiers produce a non-disclosing not-found response.
- Query caches include actor, grant, selected unit, range and time zone.
- Analytics remain content-free and never rank individual Analysts.
- Cohort suppression applies at the selected unit and cannot be bypassed by
  navigating between ancestors and descendants.
- Disabled units disappear from new reads without granting access through old
  links.

## Acceptance

1. JIOC can select and report on every configured descendant.
2. Command and Ops users cannot read a parent or sibling by URL, API or export.
3. A Team Manager sees only the exact granted team.
4. Multiple independent grants remain separately bounded.
5. Landing pages preserve the distinct purposes of My actions and My requests.
6. Charts have readable values, accessible table parity and useful empty states.
7. Terminal states are excluded from active bottleneck measures.
8. Backend and frontend retain at least 95 per cent line and branch coverage.
