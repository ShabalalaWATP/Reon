# Request coordination language and ownership

## Purpose

Use language that tells staff what needs attention while keeping stable Camunda
stage and role identifiers inside the technical boundary.

## User outcomes

- Staff in the selected command see an `Incoming requests` queue.
- The queue explains that a new request requires attention and must be claimed
  before a routing decision is recorded.
- An unclaimed shared action names the responsible unit as
  `<unit> · Awaiting owner`.
- The same action is labelled with the claimant's name after an individual has
  accepted it.
- Action summaries use `New request requires attention`. The technical
  `CHOOSE_OPS_GROUP` identifier remains inside the API and workflow boundary.
- Profiles, navigation, request status, lifecycle graphics, Camunda task names
  and current documentation use `Request coordination` consistently.

## Rules

1. The selected route unit remains the source of organisational responsibility.
2. Shared visibility is not personal assignment. `Available to <unit>` and
   `<unit> · Awaiting owner` must remain visually distinct from `Assigned to
   you`.
3. Unit names are resolved when the action workspace is read so renames and
   existing projections are represented correctly.
4. Once an action is personal, the authenticated claimant's display name is the
   current owner.
5. Internal enum values, BPMN element identifiers and API action codes remain
   stable for compatibility.

## Acceptance criteria

- No deprecated coordination terminology remains in user-facing text.
- DIGOC, SYGOC, MYGOC and future configured units are shown by their actual
  configured names, with no hard-coded DIGOC special case.
- Existing and newly submitted requests use the same ownership presentation.
- Backend and frontend tests cover shared and personal ownership, queue labels
  and friendly action labels.
