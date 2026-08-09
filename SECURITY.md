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
storage and local Compose are evaluation-only. Review the production gates and
threat models before considering any connected deployment.
