# Synthetic MVP users

This page is a stable locator for the local/test identities. To avoid maintaining
the same 99-row roster in two places, the authoritative human-readable directory
is the [complete synthetic user directory](../architecture/ORGANISATION_AND_ROUTING.md#complete-synthetic-user-directory).
That directory includes every username, name, representative role,
organisational assignment and initial account state.

The machine-readable authority is `DEMO_IDENTITIES` in
`apps/api/src/istari_service/demo_seed.py`. An automated test compares that seed
with the documented directory so additions, removals, renames and active-state
changes cannot silently drift.

## Local access summary

- Usernames run sequentially from `admin1` through `admin99`.
- Initial work emails follow the same sequence at the synthetic-only domain,
  for example `admin1@istari.example.test` through
  `admin99@istari.example.test`. An Administrator may later amend them.
- The shared password is `admin` only when demo users are explicitly enabled in
  a local or test environment.
- `admin16` is intentionally inactive for access-control testing.
- `admin1` is the supporting Platform Administrator.
- `admin73` is the independent configuration-approval Administrator.
- `admin74` to `admin99` provide one named Manager and one named Member for every
  routing workspace, including JIOC, each command and each Ops group.
- `admin4` exercises the JIOC hierarchy view, `admin5` and `admin6` exercise
  shared command and Ops access, `admin8` exercises the OSG Team overview, and
  `admin15` exercises the QC overview.
- The names are memorable synthetic fixtures borrowed from Scottish football and
  make no statement about the real people.

Production identity, authentication and access lifecycle must use the approved
OIDC, MFA and privileged-access design. These fixtures must never be enabled in
that environment.
