# Authentication and session remediation

## Status and scope

Status: implemented and locally verified. Last reviewed 18 August 2026.

This specification closes the authentication and browser-session findings from
the final defensive security review. It covers local password authentication,
password assistance, CSRF bootstrap, session activity and browser privacy state.

## Required outcomes

- Passive queries, page polling and `GET /auth/me` are read-only and never extend
  the idle window.
- Only a throttled, CSRF-protected `/auth/activity` request prompted by keyboard,
  pointer or touch activity records human activity.
- The browser enforces both server-provided absolute expiry and idle expiry,
  clears protected query state, and propagates logout or expiry to other tabs.
- CSRF bootstrap is stable for an opaque session. Opening or refreshing one tab
  cannot invalidate mutations already in progress in another tab.
- Password and password-visibility state are cleared after failed sign-in, after
  leaving the sign-in mode and after failed privileged step-up.
- Login throttling is atomic and shared between replicas. Source budgets and
  one-way keyed normalised-identifier budgets limit both distributed and local
  brute force without allowing an attacker to hard-lock a named account.
- Password assistance serialises its count-and-insert decision, records no raw
  submitted address, and returns the same public response when a limit is reached.

## Acceptance criteria

1. Repeated authenticated reads leave `last_seen_at` unchanged.
2. A valid activity heartbeat advances `last_seen_at`; missing CSRF does not.
3. Multiple tabs receive the same CSRF token and a logout in one tab clears the
   others.
4. A distributed sequence against one normalised account ID exhausts only its
   opaque credential budget, while unrelated IDs remain usable.
5. Existing account lock fields are no longer set by public authentication.
6. Targeted backend and frontend authentication tests pass.

## Non-goals

- This change does not replace the approved synthetic local password model with
  enterprise identity or multi-factor authentication.
- Passive network traffic is deliberately not treated as proof of user presence.
