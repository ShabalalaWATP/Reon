# Dependency licence policy

The pilot permits permissive MIT, BSD, ISC, Apache, PSF, Unlicense and MPL 2.0
dependencies. Any other or unidentified licence fails the automated gate unless
the exact package has a documented review.

Two local exceptions exist:

- `istari-service-api` is the private first-party application;
- `camunda-orchestration-sdk` 9.0.1 omits licence metadata from its Python wheel.
  It is retained as the selected workflow client under the Camunda License 1.0
  terms published for the Orchestration Cluster API. Legal and procurement
  acceptance of the wider Camunda deployment remains a stakeholder launch gate.

`pnpm licence-check` scans production Node dependencies and every installed
Python dependency. A new unknown, copyleft or otherwise unapproved licence fails
the build rather than silently extending this exception list.
