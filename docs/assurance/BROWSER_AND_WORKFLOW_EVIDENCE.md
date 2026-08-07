# Browser and workflow evidence

## Environment

Recorded on 7 August 2026 against the production React image, FastAPI,
PostgreSQL 17.9 and Camunda 8.9.14. Installed browser versions were Chrome
151.0.7922.75, Edge 151.0.4129.59 and Firefox 153.0.

## Complete Customer and delivery journey

Request `SR-2026-A5660D8D` completed through the real application and workflow:

1. Customer `admin2` proved mandatory-field rejection, then submitted a complete
   request and saw it in the tracking register.
2. JIOC `admin4` recorded related records and selected DIGOC.
3. Command user `admin5` selected NCGI-A Ops, then Ops user `admin6` selected
   OSG Team.
4. OSG Manager `admin8` assigned Lewis Ferguson (`admin11`).
5. The Analyst requested additional information. The Customer response was
   retained in the dashboard and returned to the same Analyst assignment.
6. The Analyst submitted a product. OSG Manager approved it and QC user
   `admin15` separately approved and disseminated it to a required recipient.
7. The Customer saw `Completed`, the full activity and clarification history,
   downloaded the authenticated product link and submitted one-time mandatory
   rating and comments.

No JIOC, command or Ops approval was inserted into the return path.

## Alternative route proof

`scripts/run-local-app-journey.py` completed request `SR-2026-4D12E2BA` through
SYGOC, Nimbus Ops and Beacon Team. Archie Gemmill produced the product and the
Customer download was verified. The content-free result is retained at
`output/playwright/alternative-app-journey.json`.

`scripts/smoke-camunda.ps1` separately completed both the OSG route with two
clarification loops and an alternative staffed route. Candidate groups remained
distinct and no alternative route fell back to OSG.

## Team and management journeys

- OSG Team showed three Managers and seven Analysts.
- A Manager ended and re-added Ben Doak using mandatory reasons. Current and
  historical membership remained visible.
- Board, accessible table, WIP limits, saved filters and required work-package
  fields rendered from workflow and team planning records.
- Calendar month, week and agenda views, privacy, recurrence and capacity
  controls were exercised.
- Statistics showed OSG only to the OSG Manager, JIOC and child commands to the
  JIOC Manager, and only explicit DIGOC, SYGOC and MYGOC scopes to the shared
  command account.

## Compatibility result

Critical pages rendered and remained navigable in current Chrome, Edge and
Firefox at desktop and narrow widths. Screenshots are retained in
`output/playwright`. Customer authentication, tracking, released-product,
clarification, feedback and mandatory-form validation passed in all three
browsers and are retained as Playwright CLI traces:

- `chrome-customer-acceptance.trace`;
- `edge-customer-acceptance.trace`;
- `firefox-customer-acceptance.trace`.

Additional Chrome traces cover the Team Manager queue, roster, calendar, board
and exact-team statistics; JIOC metadata tracking and JIOC-only statistics; and
the 72-account Administrator register, step-up and create-user form. Trace names,
browser versions, scenarios and SHA-256 values are recorded in
`output/playwright/browser-acceptance.json`.

The complete end-to-end state-changing delivery journey was repeated in Edge
151.0.4129.59 as request `SR-2026-0D8A4A96` on the OSG route and Firefox 153.0
as request `SR-2026-79C5D79F` on the SYGOC, Nimbus Ops and Beacon Team route.
Both journeys included named claims and routing decisions, Team Manager
assignment, Analyst clarification, Customer response, Analyst product
submission, Manager review, separate QC approval, dissemination, authenticated
download and required feedback. PostgreSQL reconciliation found both requests,
products and Camunda workflow instances completed, one clarification thread
with two messages in each, and ratings of five and four respectively.

The raw traces, network logs, completion screenshots and downloaded products are
retained in `output/playwright`. Their hashes are recorded in
`output/playwright/browser-acceptance.json`. The validated final reports are:

- `output/playwright/cross-browser-staff-acceptance.html`;
- `output/playwright/cross-browser-staff-acceptance.junit.xml`.

The final report SHA-256 values are
`F035EEE71CEBACB3345CBC52A80164BF5013AF2D0CF837C605A41CA52B6EF080` for
the HTML report and
`F5B727A85E40C97C85F23539B17818D2EC23A3162A90CCC7A8E154B25B9ACA6A`
for the JUnit report. The manifest SHA-256 is
`548B8D2D2BE0DD06D48D61904FBD6DC21E81427124B8D6BBF870182A01908E96`.

Run `uv run --directory apps/api python
../../scripts/render-browser-acceptance.py` to verify every evidence hash and
regenerate both reports. DOD-31 and DOD-44 are evidence-ready. Product-owner and
representative-user acceptance remain separate human decisions.
