# Workflow runtime reliability remediation

## Status and scope

Status: implemented and locally verified on 14 August 2026.

This remediation covers the intermittent false failure returned by synchronous
human workflow actions, local journey defaults for the hardened Compose topology,
optional managed-product discovery, and content-minimised diagnostics for
unexpected API failures. It does not change workflow stages, routing authority,
role permissions or the durable outbox recovery model.

## Definition of done

1. A newly committed claim or completion has a short synchronous-dispatch grace
   period. The API can dispatch it immediately, while the background worker does
   not compete during that period and still recovers it automatically if the API
   stops before dispatch.
2. If another dispatcher already owns the command, the API reconciles the durable
   outbox result for a bounded period. A command already projected as `SENT`
   returns success; a confirmed support failure remains fail-closed; a genuinely
   pending retry retains the existing recorded-and-retry response.
3. Automated tests reproduce both initial-dispatch priority and the competing
   dispatcher hand-off. They prove one projected result and no duplicate workflow
   effect.
4. Workflow finalisation and locked request-detail authorisation cannot deadlock
   against notification recipient projection over the actor row. PostgreSQL
   command deadlock victims receive one bounded, idempotent retry and no
   concurrent detail read escapes as an unhandled `500`.
5. Maintained local journey and seed scripts default to the only supported host
   entry point, `http://127.0.0.1:5173/api/v1`.
6. Authorised optional managed-product lookups return `200` with `null` when an
   accessible request has no managed package or release. Unknown and unauthorised
   request identifiers remain concealed with the same `404` response.
7. The React product panels treat the nullable result as the legacy-product or
   create-package path without generating failed-resource console noise.
8. Every unexpected API exception produces one content-minimised structured
   request event at error level containing the correlation identifier, matched
   route template, exception type and code location. It never records the URL,
   query string, request body, exception message or credentials.
9. Focused regression tests, full backend and frontend coverage gates, static
   checks, line limits and the rebuilt local stack pass.
10. Both maintained organisational routes complete from Customer submission
   through routing, production, management, QC dissemination and Customer access
   without an unexpected HTTP response or browser-console error.

## Non-functional constraints

- PostgreSQL remains authoritative for the durable intent and projection.
- Camunda remains authoritative for workflow position and task lifecycle.
- Recovery remains idempotent and fenced by the existing lease generation.
- No endpoint may reveal whether another Customer's request or product exists.
- The synchronous priority window must not delay ordinary API actions and must
  bound crash recovery to five seconds before normal maintenance polling.
- All logs remain content-minimised and correlation-safe.

## Verification evidence

- A dispatcher regression test covers a command whose initial recovery time is
  in the future but which is explicitly dispatched by its originating API call.
- A competing-dispatch regression test covers an already-processing command that
  becomes `SENT` and is returned as success to the waiting API call.
- API authorisation tests distinguish accessible legacy requests from unknown and
  cross-Customer identifiers.
- Frontend tests cover nullable package and release responses.
- Telemetry tests inject an unexpected exception and inspect the exact JSON event.
- The primary and alternative journey scripts run against the rebuilt Compose
  stack using their defaults.
- The final rebuilt stack completed five consecutive SYGOC, Nimbus Ops and
  Beacon Team journeys plus two consecutive JIOC, DIGOC, NCGI-A Ops, OSG Team
  and QC journeys, with verified Customer downloads and no 5xx or deadlock log
  entries.
- A clean authenticated Customer browser context opened a completed SSG request,
  loaded its optional release lookup with `200`, and reported zero console errors
  or warnings.
