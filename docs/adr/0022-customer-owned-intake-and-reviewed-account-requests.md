# ADR 0022: Customer-owned intake and reviewed account requests

## Status

Accepted, 9 August 2026.

## Decision

The public request contract contains only information a Customer can reasonably provide. It does not contain an internal business area, destination team, analyst discipline or dissemination recipient. The authenticated requester is the eventual Customer recipient, while CRIOC and later routing users make internal routing choices through the existing human-led workflow.

Account requests are separate pending records. They contain identity and access-need metadata, never a password or requested privilege. In the local MVP, a stepped-up Platform Administrator may approve a record into a Customer account. The existing identity sequence allocates its account ID and the configured demo credential policy supplies the temporary shared password.

Private drafts use the same field vocabulary but allow null values. Workflow submission always validates the complete non-null contract.

Previously activated workflow-configuration snapshots remain immutable and keep their historical form metadata. The current allow-list applies to newly proposed configuration versions. Runtime request validation is defined by the versioned FastAPI contract, not by mutating a sealed historical snapshot.

## Consequences

- Customer input is stable if the organisation tree changes.
- Internal topology and staffing are not disclosed or coupled to public forms.
- Administrators retain explicit control of account creation and cannot grant elevated roles through an access request.
- Account notification remains an operational hand-off in this local MVP because no email service is configured.
- Migrating away from shared MVP credentials remains required before production authentication can be enabled.
