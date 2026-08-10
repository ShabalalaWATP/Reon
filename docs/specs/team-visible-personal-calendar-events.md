# Team-visible Personal Calendar Events

## Purpose

Personal calendar activity created by a current organisation member is visible
with its title, category and notes to the member's exact team by default. A user
can deliberately protect an appointment through one plain-language control.

## Behaviour

- `My event` starts with team-detail visibility.
- The same default and choice apply from both `My calendar` and the member's
  shared organisation calendar. Personal calendar creation obtains the unit
  name without enabling Manager-only unit or commitment controls.
- The form presents one unchecked `Private appointment` checkbox instead of a
  technical visibility selector.
- Selecting the checkbox changes the event to private visibility and explains
  that colleagues will see only `Busy` and the event time.
- Unit events and ticket commitments always start with team-detail visibility.
- The personal-event API rejects availability-only creation so a client cannot
  conceal detail without making the explicit private choice.
- Existing private and availability-only events retain their stored visibility.
- Calendar reads remain limited to current exact-team membership. Higher and
  sibling organisations receive no event detail.

## Acceptance criteria

1. A normal personal event appears with detail in the exact-team calendar.
2. The private option is visible, unchecked and keyboard operable.
3. A selected private appointment is stored as private and projected as `Busy`
   without title or notes to colleagues.
4. Changing between personal, unit and commitment modes resets visibility to the
   appropriate team-visible value.
5. Frontend accessibility and backend policy regression tests pass.
