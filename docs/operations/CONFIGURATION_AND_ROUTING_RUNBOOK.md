# Configuration and routing runbook

Status: local release-candidate procedure
Production owner: pending nomination

## Preconditions

1. Confirm the environment, current configuration title, effective time and
   change authority. Never test configuration changes in production.
2. Confirm a second active Platform Administrator is available for independent
   review.
3. Confirm PostgreSQL, configuration readiness, Camunda and maintenance health.
4. Use the application interface and operator deployment process only. Never edit
   application or Camunda-owned database tables.
5. Keep request narrative, product content, credentials and Customer identifiers
   out of tickets, screenshots and administrative reasons.

## Health checks

Run from the repository root in the target environment. Do not paste response
bodies containing operational detail into an unrestricted ticket.

```powershell
docker compose ps
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:8000/ready -UseBasicParsing
uv run --directory apps/api python -m mist_service.maintenance status
```

Expected local results are running or healthy containers, HTTP 200 for health,
HTTP 200 for readiness and a content-free maintenance status with no failed
supervisor. HTTP 503 readiness is a stop condition for new routing. Diagnose its
named dependency before continuing. HTTP 200 health does not override failed
readiness.

For a pre-0018 database whose imported current configuration has no independent
approval and activation evidence, 503 is expected. Prepare, validate,
independently approve and activate a successor. Never insert, copy or backdate
evidence for the historical baseline.

## Prepare a change

1. Open **Configuration**, complete password confirmation and select the current
   configuration.
2. Choose **Propose changes**, enter a descriptive change title and an effective
   date. The interface displays the browser timezone and stores an absolute time.
3. Search by unit name, stable code or type. Confirm the root-to-unit breadcrumb
   before editing.
4. For a new or moved unit, choose from the compatible parents shown. Absence of
   an option means the proposed effective structure has no valid parent.
5. Configure candidate groups and minimum Manager/Analyst staffing. A valid
   unstaffed team remains visible to routing users with an explicit warning.
6. Review every preview item. Existing warnings may remain validation findings
   without appearing as newly introduced changes.
7. Validate the complete configuration and resolve every error. Do not work
   around validation by altering API payloads.

## Independent review and activation

1. Submit the validated changes with a content-free reason of at least ten
   characters.
2. A different Platform Administrator signs in, confirms their password and
   checks the title, effective time, organisation path, preview and findings.
3. The reviewer approves or rejects the exact proposed changes. Any subsequent
   mutation invalidates the earlier review state.
4. Activate only after approval and only when the effective time and operational
   readiness are correct.
5. Confirm readiness, the active configuration title, candidate-group mapping,
   organisation closure and one representative new route.
6. Confirm an existing in-flight request remains on its original pinned route.

## Stop and escalation authority

- Any operator who observes possible disclosure, integrity loss or unsafe
  routing stops the affected manual intake and escalates immediately.
- The named Product or Incident Owner decides whether all new intake is paused.
  These owners are pending nomination, so production use remains blocked.
- Existing in-flight work is not migrated, deleted or rerouted as part of the
  stop. Human owners use the established incident route.
- A proposed change that should not proceed is rejected by an independent
  reviewer or left inactive pending investigation. There is no destructive
  abandon action. A replacement proposal may be created after the issue is
  understood.
- A Platform Administrator cannot self-authorise workflow deployment, database
  repair, request-content access or emergency recovery.

## Routing incident diagnosis

| Symptom | Safe checks | Response |
|---|---|---|
| Destination missing | Current request pin, parent-child relationship, effective time, routing state | Correct through new proposed changes; do not edit the active snapshot |
| Destination unexpectedly present | Same checks plus current candidate-group mapping | Stop affected new routing if risk is material; prepare a superseding change |
| Team awaiting staffing | Active Manager and Analyst memberships, management grant and candidate groups | Restore qualified membership or route new work elsewhere by human decision |
| User cannot claim | Active account, exact candidate group, task state and competing claim | Correct identity/membership or allow the winning claimant to continue |
| Stale-edit conflict | Proposal title, last updater and current change history | Reload and reapply the intended change; never overwrite blindly |
| Preview reports unexpected workflow impact | Form/policy identifiers, approved workflow reference and canonical schedule | Stop review and investigate; approval must not proceed on an unexplained preview |
| Search unavailable | Configuration API and browser console without capturing data | Use configuration history and the full authorised tree; treat search as degraded UI |

## Recovery and reversal

- Reverse an activated mistake by preparing, validating, independently approving
  and activating a superseding change. Historical configuration is immutable.
- Do not migrate in-flight requests implicitly. A future migration requires a
  separate approved plan and per-request evidence.
- After restore, verify the active pointer, immutable snapshot digest,
  organisation closure, candidate groups, request pins and Camunda process
  identity before reopening routing.
- If no complete route remains or the active snapshot cannot be reconciled,
  fail readiness closed and escalate as P2, or P1 if data exposure is possible.
- Before reopening, prove PostgreSQL revision, active pointer, approval and
  activation digest equality, organisation closure, exact candidate groups,
  in-flight pins, approved Camunda process identity, outbox/reconciliation state
  and managed-product object/scan metadata.
- Recovery targets are not accepted. Record actual start, integrity-complete and
  reopen times without presenting the local rehearsal as a production RTO.

## Failed activation or integrity mismatch

1. Do not retry repeatedly or alter sealed rows.
2. Capture the content-free correlation, configuration identifier, timestamps,
   readiness reason and command result.
3. Keep affected new routing closed. Existing pinned requests remain on their
   recorded snapshot unless a separately approved recovery plan says otherwise.
4. Verify whether the failure is stale revision, missing independent evidence,
   digest mismatch, incompatible workflow identity or database/Camunda outage.
5. For an erroneous but intact current configuration, activate an independently
   approved successor. For suspected tampering or corruption, follow the support
   incident runbook and restore only into an empty controlled target.

## Evidence to retain

- Change title and immutable identifier.
- Creator, independent reviewer, effective and activation times.
- Validation result, content-free reason and preview digest.
- Readiness result and representative new/in-flight route checks.
- Correlation and audit identifiers, not request content.
