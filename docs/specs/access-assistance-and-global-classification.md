# Access assistance and global classification marking

Status: accepted for the synthetic MVP on 10 August 2026.

## Outcome

Mist provides a quiet `Forgotten password?` action on the sign-in page and a
thin, persistent classification strip above every public and authenticated
surface. The default marking is `OFFICIAL`. A Platform Administrator with a
fresh step-up session can change the marking for every user.

This feature is an assistance and visual-marking capability. It does not send a
password, create a reset token, reset a credential or infer the classification
of individual request content.

## Account email

- Every active account has one unique, normalised email address.
- New Customer accounts retain the work email supplied in the reviewed account
  request.
- Administrators can set or correct an email while creating or editing an
  account.
- Existing synthetic identities use `adminN@mist.example.test`.
- A user can see their own email on their profile. Platform Administrators can
  see account emails through the identity register. Other users cannot query
  another account's email.

## Forgotten-password journey

1. An unauthenticated user selects `Forgotten password?` on sign-in.
2. The page reveals one required work-email field and moves focus to it.
3. Submission always receives HTTP 202 with the same neutral message, whether
   the account exists, is inactive, is cooling down or is unknown.
4. The service stores a content-minimised attempt containing a one-way source
   key, an optional matched user identifier and a timestamp. It never stores the
   submitted email in the assistance-attempt record.
5. Source, global and matched-account cooldowns prevent notification flooding.
6. When an active account matches, every current active Platform Administrator
   receives a mandatory `ACCOUNT_SECURITY` notification containing only the
   account ID and a link to that administrator-managed account.
7. The Administrator contacts the user through the approved offline process.

The response must not reveal whether the email exists. Notification preferences
cannot suppress account-security messages.

## Global classification marking

The platform stores exactly one versioned global marking:

| Value | Presentation |
| --- | --- |
| `OFFICIAL` | green |
| `OFFICIAL-SENSITIVE` | blue |
| `SECRET` | red |
| `TOP-SECRET` | dark red |

- `OFFICIAL` is created automatically when no setting exists.
- The marking appears above the sign-in page and every authenticated route.
- Clients refresh it periodically and whenever the browser regains focus.
- The public read contract exposes only the value, version and last-change time.
- Mutation requires the Platform Administrator role, valid CSRF protection, a
  fresh password-confirmed step-up session and an expected version.
- Every change appends a content-free event to the tamper-evident administration
  audit chain.
- The marking is a platform-wide visual label. It does not authorise access,
  alter request sensitivity, change dissemination controls or replace formal
  information-handling policy.

## Accessibility and design

- The strip is 22 pixels high, text-labelled and never communicates state by
  colour alone.
- Foreground and background combinations meet WCAG 2.2 AA contrast.
- Keyboard users can open, submit and close the recovery form in a logical
  sequence.
- Status changes use a short colour transition that is disabled when reduced
  motion is requested.
- The new controls reuse Mist typography, spacing, focus and error patterns.
- Every authenticated page provides a focus-revealed `Skip to main content`
  link before repeated navigation. Its target is programmatically focusable.
- At widths down to 320 CSS pixels, page content reflows without document-level
  horizontal scrolling. Mobile primary navigation wraps into readable rows
  instead of relying on a horizontally hidden strip.
- Ordinary text and semantic status colours maintain at least 4.5:1 contrast
  against every core light and dark surface. Strong form and control boundaries
  maintain at least 3:1 non-text contrast.
- Normal pointer targets are at least 24 by 24 CSS pixels. A smaller native
  control must have an associated label that provides the compliant target.

## Acceptance criteria

- An unknown, inactive and active email produce identical public status and
  response bodies.
- Repeated requests inside the cooldown do not create duplicate notifications.
- A successful request is visible to all active Platform Administrators and no
  other role.
- A non-administrator, an administrator without step-up and a stale version are
  rejected when changing the marking.
- A successful change is immediately reflected in the initiating client,
  persists across restart and becomes visible to other clients on refresh.
- All four values render with the required label and colour family on the login
  and authenticated layouts at desktop and narrow widths.
