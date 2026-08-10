# ADR 0024: Descendant Statistics and Role Overviews

## Status

Accepted, 9 August 2026.

## Context

Management grants already record a root organisation unit and whether descendants
are included. The statistics API nevertheless resolves only the grant root. The
UI can compare direct children but cannot select an authorised lower node. This
prevents JIOC and intermediate organisations from examining the detail beneath
their own branch. The existing generic statistics composition also appears on
every management role, while My actions and My requests have deliberately narrower
transactional purposes.

## Decision

Statistics queries will carry an active scope identifier and an optional selected
unit identifier. FastAPI resolves the grant, proves the selected unit against the
organisation closure and constructs the dataset using the selected unit's level.
Platform scope uses the same selected-unit rule against the configured root.

The scope response will include a bounded authorised tree. Dashboard responses
will include the selected-node breadcrumb and direct children. React will use
those server-owned records for navigation but will never treat them as authority.

Role-specific overview routes will compose existing bounded endpoints. My actions
continues to contain personal actions and My requests continues to contain
Customer requests. Detailed trends, definitions and exports remain on the
Statistics page.

Staff overviews will greet the authenticated account holder by first name and
present the personal action projection separately from the authorised aggregate
organisation workload. The organisation region must name its scope and state
that its values are not the individual's workload. Primary navigation will be
assembled in operational order from explicit context, with plain-purpose labels
and no positional mutation after assembly.

The Home page will use that same assembled navigation to render explanatory
quick-access tiles, excluding Home itself. Direct child-organisation records and
their drill-down links remain on Operational statistics. The tiles are a second
interaction surface for known destinations, not an independent capability or
authorisation model.

## Consequences

- No schema migration is required because grants and organisation closure already
  express the authority.
- Query and export contracts gain a selected-unit value and caches must include it.
- Independent grants remain separate roots, avoiding accidental sibling traversal.
- The UI gains useful drill-down without exposing a global organisation picker.
- Overview pages may reuse statistics summaries, but must keep a small role-specific
  composition instead of reproducing the full reporting page.
- Presentation becomes easier to interpret without changing role, object or
  action authorisation. Dynamic workspace and statistics links have deterministic
  positions. Home mirrors the authorised sidebar destinations with short purpose
  descriptions, while omitting itself and keeping hierarchy drill-down inside
  Operational statistics.

## Rejected alternatives

- Creating one grant per descendant would duplicate authority and complicate
  revocation.
- Returning the global organisation tree and hiding nodes in React would leak
  topology and rely on presentation as access control.
- Putting all reporting into My actions or My requests would mix action, tracking and
  analysis into one unfocused surface.
