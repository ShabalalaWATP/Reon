# Dependency licence policy

Last reviewed: 18 August 2026

The pilot permits reviewed permissive MIT, BSD, ISC, Apache, PSF, Unlicense,
Zlib, CC0 and MPL 2.0 expressions. The automated gate compares complete reported
licence values against an exact case-insensitive allow-list; a string that merely
contains an approved identifier does not pass. Any other or unidentified licence
fails unless the exact package and reported metadata value have a documented
review.

Four local package-metadata exceptions exist:

- `mist-service-api` 0.1.0 is the private first-party application;
- `camunda-orchestration-sdk` 9.0.1 omits licence metadata from its Python wheel.
  It is retained as the selected workflow client under the Camunda License 1.0
  terms published for the Orchestration Cluster API. Legal and procurement
  acceptance of the wider Camunda deployment remains a stakeholder launch gate;
- `fastembed` 0.8.0 reports `Other/Proprietary License`, but its installed
  Apache-2.0 licence file was reviewed at SHA-256
  `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`; and
- `py-rust-stemmers` 0.1.8 reports `UNKNOWN`, but its installed MIT licence file
  was reviewed at SHA-256
  `9449057776c984e88e29ea1ee135caeba2347756d0c74480f7afc4f16f636f68`.

Every exception is bound to the installed version and reported metadata. The two
third-party incomplete-metadata exceptions are additionally bound to the exact
installed licence-file digest. Version, metadata or licence-file drift reopens
review and fails the gate.

`pnpm licence-check` scans production Node dependencies and every installed
Python dependency. A new unknown, copyleft or otherwise unapproved licence fails
the build rather than silently extending this exception list.
