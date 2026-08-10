# Accessibility and WCAG 2.2 evidence

## Position

ISTARI is designed towards the [Web Content Accessibility Guidelines (WCAG)
2.2](https://www.w3.org/TR/WCAG22/) Level AA. The evidence below supports the
current technical position. It is not a claim of formal conformance or a
replacement for an accessibility audit by disabled users and a named reviewer.

Related authorities:

- [master accessibility plan](../MASTER_IMPLEMENTATION_PLAN.md#accessibility-plan-and-evidence-11-august-2026);
- [accessibility completion gates](DEFINITION_OF_DONE_MATRIX.md#accessibility-compatibility-and-performance-gates);
- [production gates](../deployment/PRODUCTION_GATES.md); and
- [representative-user acceptance record](ACCEPTANCE_RECORD.md).

The latest review was completed on 10 August 2026 against the local production
React build. The stack was healthy and served from Docker at
`http://localhost:5173`.

## Current accessibility controls

- A keyboard-visible `Skip to main content` link is the first focusable control
  on authenticated pages. Its destination is programmatically
  focusable, supporting [WCAG 2.4.1 Bypass
  Blocks](https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks).
- The document has no fixed minimum body width, and a production-browser check
  at a strict 320 CSS-pixel viewport found no horizontal overflow.
- Mobile primary navigation uses a wrapping two-column grid. A
  production-browser check at 320 CSS pixels found
  no document or navigation overflow, supporting [WCAG 1.4.10
  Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).
- Form-control and theme boundary colours are guarded by automated tests that
  require at least 3:1 contrast for strong boundaries against every core surface.
- All semantic text colours and all four classification banners must provide at
  least 4.5:1 contrast against their supported light and dark backgrounds.
- The skip link and primary interactive controls retain a minimum 40-pixel
  height. Small checkbox inputs remain enclosed by larger labelled targets,
  supporting the intent of [WCAG 2.5.8 Target Size
  (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum).

## WCAG 2.2 Level AA evidence matrix

| Success criterion | Current evidence | Position |
| --- | --- | --- |
| 1.3.1 Info and Relationships | Semantic landmarks, headings, lists, tables, labels, fieldsets and descriptions are exercised by component tests and representative live DOM inspection. | Technical evidence present |
| 1.3.2 Meaningful Sequence | The skip link is first in DOM and focus order, followed by identity, navigation and page content. Representative page order was inspected at desktop and mobile sizes. | Technical evidence present |
| 1.3.5 Identify Input Purpose | Authentication and profile fields use semantic input types and appropriate autocomplete metadata where the purpose is known. | Component evidence present |
| 1.4.3 Contrast (Minimum) | Automated token tests require 4.5:1 for semantic text and classification text across supported light and dark surfaces. | Automated guard present |
| 1.4.10 Reflow | Production-browser validation at 320 CSS pixels found a 305-pixel layout viewport, a 305-pixel document width and no horizontal overflow. The 273-pixel primary navigation had equal client and scroll widths. | Production evidence present |
| 1.4.11 Non-text Contrast | Strong control boundaries are tested at 3:1 against every core surface. Visible focus styling is shared across links and controls. | Automated guard present |
| 1.4.12 Text Spacing | Layouts use flexible sizing and wrapping, but the prescribed text-spacing overrides have not yet been manually exercised across every critical journey. | Human validation required |
| 1.4.13 Content on Hover or Focus | Account menus, drawers and contextual content have interaction tests, including keyboard dismissal where applicable. A full hover/focus persistence review remains part of acceptance. | Partial technical evidence |
| 2.1.1 Keyboard | Navigation, forms, board and calendar actions use native links, buttons and form controls. No workflow requires pointer-only drag and drop. | Automated and representative manual evidence |
| 2.1.2 No Keyboard Trap | Dialog and menu tests cover keyboard dismissal and focus behaviour. Assistive-technology confirmation remains required. | Partial technical evidence |
| 2.4.1 Bypass Blocks | Authenticated pages provide a focus-revealed skip link to `#main-content`, followed by named navigation and main landmarks. | Automated and production evidence |
| 2.4.2 Page Titled | The application has a descriptive ISTARI Service document title. Route-specific titles should be reviewed before production acceptance. | Partial technical evidence |
| 2.4.3 Focus Order | Native DOM order follows the visual sequence, and the skip link precedes repeated navigation. Representative keyboard order has been reviewed. | Technical evidence present |
| 2.4.6 Headings and Labels | Pages use descriptive headings and visible labels. axe-core is run in 25 frontend test files. | Automated evidence present |
| 2.4.7 Focus Visible | A high-contrast global `:focus-visible` treatment is applied to interactive controls. The skip link only enters view when focused. | Automated and visual evidence |
| 2.4.11 Focus Not Obscured (Minimum) | The skip link appears below the fixed classification strip. Representative pages have been checked, but all drawers, menus and long pages still need manual acceptance review. | Partial technical evidence |
| 2.5.7 Dragging Movements | Board and calendar changes are available through labelled buttons and forms without drag gestures. | Component evidence present |
| 2.5.8 Target Size (Minimum) | Primary controls use 40-pixel minimum heights; compact inputs use associated larger labels or sufficient spacing. | CSS and component evidence |
| 3.3.1 Error Identification | Required-field failures retain associated labels and visible error text. | Component evidence present |
| 3.3.2 Labels or Instructions | Form controls have visible labels and instructions where format or limits matter. | Automated evidence present |
| 3.3.3 Error Suggestion | Validation messages explain the correction where a safe suggestion can be provided. | Component evidence present |
| 3.3.7 Redundant Entry | Request and workflow context is carried forward rather than requiring routine re-entry. A full journey review remains necessary. | Partial technical evidence |
| 3.3.8 Accessible Authentication (Minimum) | Password-manager-compatible native fields and autocomplete metadata are used. The MVP credential model is not production authentication assurance. | Technical evidence, product risk remains |
| 4.1.2 Name, Role, Value | axe-core component checks and Testing Library role queries exercise accessible names, roles and state on representative controls. | Automated evidence present |
| 4.1.3 Status Messages | Loading, success, error and notification states use text and semantic status patterns rather than colour alone. | Component evidence present |

Criteria not listed in the matrix are either not directly affected by this
interface, require content-level review, or still need manual confirmation. They
must not be assumed to pass solely because axe-core reports no violation.

## Automated evidence

- The complete frontend test suite passed after the accessibility changes.
- Aggregate frontend coverage was 99.48 per cent for lines and statements,
  95.08 per cent for branches and 95.85 per cent for functions.
- Twenty-five frontend test files execute axe-core checks.
- Dedicated contrast tests cover semantic text, strong boundaries, primary
  actions and classification banners in both themes.
- A regression test verifies the authenticated skip link, its focusable target
  and an axe-core scan of the rendered shell.
- TypeScript, ESLint, documentation links, terminology, line limits, dead-code,
  licence, dependency, secret and build checks passed through the repository
  quality command.
- The production Docker image built successfully and passed the configured
  JavaScript and CSS bundle budgets.

## Production-browser observations

The 10 August production build was inspected in the in-app Chromium browser on
an authenticated Team Manager page.

- At 320 by 800 CSS pixels, the document did not overflow horizontally.
- The primary navigation rendered as a two-column grid and did not create an
  internal horizontal scroll area.
- `Skip to main content` was the first focusable element and preceded the brand,
  primary navigation and page controls.
- The skip link was off-screen while idle, retained a target height above 40
  pixels and was configured to become visible on keyboard focus.
- Named complementary, navigation, banner and main landmarks were exposed, with
  descriptive headings and form-control names in the inspected workflow.

## Cross-browser baseline

This baseline was recorded on 7 August 2026 using Playwright and axe-core 4.10.2.
It is dated technical evidence and does not provide continuing conformance
without the current candidate review described above.

| Page or workspace | Browser context | Axe result |
| --- | --- | --- |
| Login | Chromium | 0 violations, no incomplete checks |
| Customer request register | Edge, 390 by 844 CSS pixels | 0 violations, no incomplete checks |
| Released request detail | Chromium | 0 violations, no incomplete checks |
| CRIOC statistics | Chromium | 0 violations, no incomplete checks |
| Command statistics | Chromium | 0 violations, no incomplete checks |
| SSG Team workspace | Firefox | 0 violations, no incomplete checks |

The tested pages produced 12 applicable axe rule passes in the Customer journey.
No critical, serious, moderate or minor violation was reported in those named
page checks.

## Human acceptance still required

Before claiming WCAG 2.2 Level AA conformance, commission and record:

1. End-to-end keyboard-only testing for every supported role and critical
   workflow, including all dialogs, drawers, menus, calendars and boards.
2. NVDA with current Chrome or Edge testing on Windows. Add JAWS testing if it is
   part of the deployment support matrix.
3. VoiceOver with Safari testing if macOS or iOS is supported.
4. 200 and 400 per cent zoom, text-spacing overrides and narrow-viewport testing
   across every critical page, not only the representative shell.
5. Windows high-contrast and forced-colours review.
6. Focus-not-obscured review with sticky headers, overlays and validation errors.
7. Cognitive and plain-language review with representative users.
8. A named reviewer, defect log, retest record and explicit conformance decision.

## Artefacts

- `output/playwright/customer-edge-narrow.png`
- `output/playwright/customer-chrome-narrow.png`
- `output/playwright/team-firefox-desktop.png`
- component accessibility and interaction tests under `apps/web/src`

This record is technical evidence for acceptance. It deliberately does not
self-approve the human accessibility gate.
