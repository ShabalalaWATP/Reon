# Customer intake and account requests

## Outcome

Customers can request an ISTARI account from the sign-in page and submit a complete service brief without choosing an internal organisation, team or recipient. Administrators can review access requests. Internal routing remains a human decision after submission.

## Service-request acceptance criteria

- The form captures the need, key question, desired outcome, context, scope, relevant period, urgency, supported activity or decision, delivery date, product type, success criteria, constraints, supporting information and handling requirements. It does not ask the Customer to classify the service category.
- Requesting business area and intended recipient fields are absent from Customer input and read views.
- Every displayed request field is mandatory. The submit control is disabled until client validation succeeds, the first invalid field receives focus after an attempted submission, and FastAPI independently rejects missing or invalid data.
- Four linked form sections expose the remaining required-field count, completed sections and bounded narrative character allowances without hiding the full form or changing validation authority.
- Period end cannot precede period start and the required-by date cannot be in the past.
- The Customer is the release recipient. Internal routing and assignment are selected later by authorised people.
- Incomplete private drafts remain permitted, but a draft cannot enter workflow until it satisfies the complete request contract.
- `My requests` is the Customer home and action workspace. Clarification responses, released products and feedback due are grouped with the affected request rather than duplicated in the staff-only `My actions` page.
- Customer action notifications deep-link to the affected request. A notification does not replace the action state held on the request.

## Customer profile acceptance criteria

- Every signed-in Customer has a complete profile with name, account ID, representative role, personal workspace access, organisation assignment requirement and session expiry.
- Customers can maintain optional Team or business area, Rank or grade, Service number and Additional information without changing their access or request routing.
- A Customer profile does not show a fictional requesting area or imply that the Customer chooses an internal destination.
- Staff profiles resolve their current organisation assignments from the server-owned organisation directory.
- The compact account menu provides the essential identity and access summary plus a direct link to the complete profile.

## Account-request acceptance criteria

- The login panel offers distinct Sign in and Request account modes.
- Name, work email and reason for access are mandatory and bounded.
- Public submission does not accept a password, role, scope or organisation membership.
- The response does not reveal whether the email already exists.
- Platform Administrators can see pending requests and record an approval or rejection after step-up authentication.
- Approval creates a Customer account using the existing sequential demo account ID and configured MVP password, and audit history records the decision.
- This capability is available only in local and test environments while demo authentication remains enabled.

## Security and accessibility

- Public input is strictly validated, normalised and stored as plain text only.
- Duplicate pending submissions are coalesced by normalised email.
- Administrative decisions use object-level authorisation, CSRF protection, step-up authentication and optimistic concurrency.
- Forms expose labels, required state, field errors, error summaries and keyboard-operable mode controls.
