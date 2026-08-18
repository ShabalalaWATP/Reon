# Security policy

## Supported code

Security fixes are applied to the current default branch. This public-safe
repository contains synthetic demonstration data only and is not an approved
production deployment.

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, personal
data or sensitive service content. Use GitHub's enabled private vulnerability
reporting facility for this repository. If GitHub is unavailable, contact the
repository owner through a previously agreed private channel and ask for a
secure reporting route before sharing details.

Include the affected revision, component, reproducible steps, impact and any
suggested mitigation. Do not test against systems or data you do not own or have
explicit permission to assess.

## Response expectations

The maintainer will acknowledge receipt, establish a private coordination route,
triage severity and agree disclosure timing. No fixed service-level commitment
is made by this demonstration project. Confirmed exposed credentials must be
revoked or rotated outside the repository before a code fix is considered
complete.

## Production boundary

Local passwords, unauthenticated local Camunda access, filesystem product
storage and local Compose are evaluation-only. Local step-up authentication
rotates the opaque bearer and CSRF credentials together, but it is not approved
OIDC, MFA, privileged-access management or enterprise account recovery.

The local product inspectors and ClamAV composition are bounded detection
controls, not semantic content disarm and reconstruction. Their concurrency
limit is per process, not deployment-wide. Connected use therefore remains
blocked pending approved private object storage, semantic CDR, shared scanner
capacity, authenticated TLS Camunda access, independent security monitoring,
joined recovery evidence and authorised staging security assessment.

Review the production gates, threat models and current assurance matrices before
considering any connected deployment. Internal review and local automated
evidence do not constitute production accreditation or named security-owner
acceptance.
