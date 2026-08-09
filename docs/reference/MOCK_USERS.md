# Synthetic MVP users

This page is a stable locator for the local/test identities. To avoid maintaining
the same 73-row roster in two places, the authoritative human-readable directory
is the [complete synthetic user directory](../architecture/ORGANISATION_AND_ROUTING.md#complete-synthetic-user-directory).
That directory includes every username, display name, representative role,
organisational assignment and initial account state.

The machine-readable authority is `DEMO_IDENTITIES` in
`apps/api/src/istari_service/demo_seed.py`. An automated test compares that seed
with the documented directory so additions, removals, renames and active-state
changes cannot silently drift.

## Local access summary

- Usernames run sequentially from `admin1` through `admin73`.
- The shared password is `admin` only when demo users are explicitly enabled in
  a local or test environment.
- `admin16` is intentionally inactive for access-control testing.
- `admin1` is the supporting Platform Administrator.
- `admin73` is the independent configuration-approval Administrator.
- The names are memorable synthetic fixtures borrowed from Scottish football and
  make no statement about the real people.

Production identity, authentication and access lifecycle must use the approved
OIDC, MFA and privileged-access design. These fixtures must never be enabled in
that environment.
