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

The quick-access section deliberately mirrors authorised sidebar destinations
because it adds explanatory context rather than another navigation label list.
It uses the same navigation builder and capability context as the sidebar, so it
cannot introduce a destination that the primary navigation has withheld. Child-
organisation comparison and drill-down remain on Operational statistics rather
than appearing directly on an individual's home page.

## Primary navigation

Staff navigation follows the operating sequence:

1. `Home`
2. `My assigned actions`
3. the role-specific routing or delivery queue
4. the named organisation workspace
5. `My calendar` and product tools where applicable
6. `Request tracking` where authorised
7. `Operational statistics` where authorised
8. `Organisation directory`

Role queue labels name their purpose, for example `JIOC routing queue`,
`Incoming requests` and `Ops routing queue`. The labels do not alter route,
role, object or action authorisation.

## Acceptance criteria

- A routing overview greets the user by first name.
- Personal and organisation metrics are in separately named regions with short
  scope explanations.
- The organisation explanation states that it is not personal workload.
- Home presents the other authorised primary-navigation destinations as a
  responsive tile grid with one short purpose description per destination.
- The tile grid omits Home, uses the same link targets as the sidebar and does
  not expose direct child-organisation data.
- Dynamic workspace and statistics tiles retain deterministic positions.
- Active, hover and keyboard-focus navigation styling remains unchanged.
- Existing Customer, Analyst, Manager, QC and Administrator destinations remain
  authorised exactly as before.
- WCAG 2.2 AA semantics, responsive layout and reduced-motion behaviour remain
  covered.
