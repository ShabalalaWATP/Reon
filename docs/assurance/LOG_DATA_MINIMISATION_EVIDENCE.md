# Log data-minimisation evidence

Recorded on 7 August 2026 against the production API container during browser
journeys and the 50-user load rehearsal.

The last 45 minutes of structured API logs contained 7,818,945 UTF-8 bytes. A
content-free inspection checked for the exact synthetic request title, request
body fragment, clarification question, released-product fragment and feedback
comment used in the completed browser journey. It also checked password, CSRF
and session-cookie field patterns. No prohibited pattern was present.

The inspected log stream SHA-256 was
`7ABE4D521D8D0C1D3F3E55DDBDCB4BA34CF7FAF4393B6E0CE238B00F4D1C18B3`.
The content-free result is retained at
`output/security/log-redaction-report.json`; the raw operational log is not
retained because doing so would increase exposure without improving the proof.

Automated telemetry, audit, analytics-projection and request-security tests
separately verify that those schemas accept identifiers, route templates,
timings, counts and status metadata rather than Customer or product narrative.
Formal security-owner review remains part of the acceptance gate.
