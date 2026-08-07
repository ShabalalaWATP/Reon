# Accessibility evidence

## Rehearsal record

Recorded on 7 August 2026 against the local React production build, FastAPI,
PostgreSQL 17.9 and Camunda 8.9.14. Browser automation used Playwright with
axe-core 4.10.2.

| Page or workspace | Browser context | Axe result |
| --- | --- | --- |
| Login | Chromium | 0 violations, no incomplete checks |
| Customer request register | Edge, 390 by 844 CSS pixels | 0 violations, no incomplete checks |
| Released request detail | Chromium | 0 violations, no incomplete checks |
| JIOC statistics | Chromium | 0 violations, no incomplete checks |
| Command statistics | Chromium | 0 violations, no incomplete checks |
| OSG Team workspace | Firefox | 0 violations, no incomplete checks |

The tested pages produced 12 applicable axe rule passes in the Customer journey.
No critical, serious, moderate or minor violation was reported in the named
page checks.

## Manual interaction review

- Tab navigation exposed visible focus and reached navigation, request actions,
  forms, workspace tabs and sign-out controls in logical order.
- Enter activated the focused controls without a pointer.
- Required-field failures retained associated labels and error text, and form
  submission moved focus to the first invalid field.
- The Customer register and Team workspace reflowed without horizontal page
  overflow at 390 CSS pixels. This is narrower than a 1280-pixel desktop at
  200 per cent zoom.
- Reduced-motion emulation left zero active animations on the Customer register.
- Statistics charts retained textual summaries and equivalent data tables.
- Board and calendar operations remained available through labelled buttons and
  forms, without requiring drag and drop.

## Artefacts

- `output/playwright/customer-edge-narrow.png`
- `output/playwright/customer-chrome-narrow.png`
- `output/playwright/team-firefox-desktop.png`
- component accessibility and interaction tests under `apps/web/src`

This is technical evidence ready for a named accessibility or product reviewer.
It does not self-approve the human acceptance gate.
