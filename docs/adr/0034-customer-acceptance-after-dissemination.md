# ADR 0034: Customer acceptance after dissemination

## Status

Accepted

## Context

QC dissemination proves that ISTARI Service released a product to the intended
Customer. It does not prove that the Customer accepted the product. Product
access and feedback are different actions and cannot safely be used as proxies.
The human workflow is already complete at dissemination, so adding another
Camunda task solely to retain passive routing visibility would couple a Customer
acknowledgement to internal task execution.

## Decision

Store explicit acceptance on the immutable dissemination record with its own
idempotency key and timestamp. Only the active originating Customer may accept
the current disseminated package. Append one hash-linked `PRODUCT_ACCEPTED`
request event using the Customer as actor.

Keep `RequestStatus.COMPLETED` as the internal workflow result. The routing
monitor derives its presentation state from both the terminal request state and
managed dissemination acceptance: disseminated but unaccepted work remains
actively monitored, while accepted work moves to completed history. Legacy
deliveries without a managed dissemination retain their existing completed
meaning.

## Consequences

- Dissemination, access, acceptance and feedback remain distinct evidence.
- Routing workspaces can implement the requested operational definition without
  inventing a client-side acceptance signal.
- Acceptance does not reopen or mutate completed Camunda state.
- Replacement or withdrawal requires a new valid current dissemination before
  an acceptance can be recorded.
