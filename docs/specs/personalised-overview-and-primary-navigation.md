# Personalised Overview and Primary Navigation

## Purpose

Make the staff landing page immediately answer three questions: who is signed
in, what work belongs to them personally, and what wider workload they are
authorised to monitor. Make the primary navigation describe destinations in
plain operational language and order them by the normal user journey.

## Information hierarchy

The staff overview greets the account holder by first name. It then separates:

1. **Your workload**, sourced from the authenticated action projection and
   limited to personal action, waiting and due-soon counts.
2. **Organisation workload**, sourced from the authorised statistics scope and
   explicitly labelled as combined organisation data, not personal workload.
3. **Quick access**, containing purpose-labelled tiles for the destinations the
   account can open from the primary navigation, except the current Home page.

A current routing workspace Member without a statistics management grant still
receives the personal workload region and exact-unit workspace destinations.
The overview omits organisation measures and the statistics destination rather
than treating the deliberately narrower account as misconfigured.

The quick-access section deliberately mirrors authorised sidebar destinations
because it adds explanatory context rather than another navigation label list.
It uses the same navigation builder and capability context as the sidebar, so it
cannot introduce a destination that the primary navigation has withheld. Child-
organisation comparison and drill-down remain on Operational statistics rather
than appearing directly on an individual's home page.

Team Managers use this same personal Home. Home must not redirect to the shared
team workspace: it separates the Manager's assigned actions from the authorised
team workload, then links to the team workspace as a distinct destination.
The same default applies to every staff representative type, including Platform
Administrators and Team Analysts. After a normal sign-in they land on Home,
while Customers continue to land on `My requests`. Authorised deep links remain
available when an already authenticated user intentionally opens a specific
destination. A sign-in never resumes the protected route that caused the login
screen to open, because the new session always starts from its role landing page.

## Primary navigation

Staff navigation follows the operating sequence:

1. `Home`
2. `My assigned actions`
3. the named organisation workspace, containing the unit work queue
4. `Personal calendar` and product tools where applicable
5. `Request tracking` where authorised
6. `Operational statistics` where authorised
7. `Organisation directory`

Customer navigation is intentionally shorter. It contains only `My requests`
and `New request`. Calendar, organisation-directory, team-workspace and team-
member-profile destinations are staff operational tools and add no value to the
Customer request journey. A Customer opening any staff URL directly returns to
`My requests`; the hidden link is not treated as the authorisation control.

Legacy role queue labels name their purpose, for example `JIOC routing queue`,
`Incoming requests` and `Ops routing queue`. They remain available for deep
links and accounts without a current workspace. The labels do not alter route,
role, object or action authorisation.

## Acceptance criteria

- A routing overview greets the user by first name.
- A Team Manager's Home is a personal landing page and does not redirect to the
  shared team workspace.
- Every staff representative type defaults to Home after sign-in; Customers
  default to `My requests`.
- A successful sign-in ignores any previously visited or originally requested
  protected route. Session restoration and authenticated deep links do not
  change this explicit sign-in rule.
- Personal and organisation metrics are in separately named regions with short
  scope explanations.
- The organisation explanation states that it is not personal workload.
- Home presents the other authorised primary-navigation destinations as a
  responsive tile grid with one short purpose description per destination.
- The tile grid omits Home, uses the same link targets as the sidebar and does
  not expose direct child-organisation data.
- Dynamic workspace and statistics tiles retain deterministic positions.
- A routing Member without a statistics grant receives a useful personal Home
  page and cannot see organisation measures or a statistics destination.
- Active, hover and keyboard-focus navigation styling remains unchanged.
- Customer navigation contains only `My requests` and `New request`.
- Customer direct access to the personal calendar, organisation directory,
  team workspace or team-member profile is redirected to `My requests` without
  loading the staff page or its protected data.
- Analyst, Manager, QC and Administrator destinations remain authorised exactly
  as before.
- WCAG 2.2 AA semantics, responsive layout and reduced-motion behaviour remain
  covered.
