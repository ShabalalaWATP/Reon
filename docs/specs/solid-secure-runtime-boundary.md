# SOLID and Secure Workflow Runtime Boundary

## Status

Implemented and verified milestone. Last reviewed 18 August 2026.

## Objective

Make Camunda SDK construction, authentication configuration and asynchronous
client shutdown one infrastructure responsibility shared by the API and worker.
Application composition must depend on the existing `WorkflowEngine` port and
must not manage SDK lifecycle details itself.

This is the first bounded delivery from the wider SOLID and Secure by Design
improvement programme. It changes dependency direction and failure handling,
not the human-led workflow or any user-visible route.

## Current problem

The API lifespan and independent worker each construct `CamundaAsyncClient`,
translate settings, cast the SDK configuration type, enter the client and close
it independently. The duplication creates two reasons for each entry point to
change and two places where authentication or shutdown behaviour can drift.

The worker composition also accepts the concrete `CamundaWorkflowEngine`
adapter even though every job requires only the narrower `WorkflowEngine`
application port.

## Required design

- Keep the existing validated Camunda configuration translation in the
  infrastructure layer.
- Add one async context-managed runtime factory that owns SDK client entry,
  adapter construction and guaranteed client exit.
- Isolate the SDK configuration type workaround inside that boundary.
- Let `create_app` accept an injected runtime factory when no engine is already
  supplied.
- Let the worker accept the same runtime factory and pass only the
  `WorkflowEngine` port to job composition.
- Preserve the existing direct engine injection used by tests and supported
  composition.
- Dispose database resources even when Camunda startup, adapter construction or
  worker execution fails.

## Secure by Design controls

- The runtime must use only validated `Settings`; production HTTPS and
  authentication invariants remain authoritative.
- Credentials must not be copied into logs, exceptions, application state or
  test output.
- A failure to enter the SDK client must prevent API or worker startup.
- A successfully entered client must be closed exactly once on normal exit and
  on later construction or execution failure.
- No fallback fake engine, anonymous authentication or alternate endpoint may be
  selected after a runtime failure.

## SOLID outcomes

- Single responsibility: entry points compose processes; the runtime adapter
  owns Camunda client lifecycle.
- Open and closed: a future approved workflow runtime can be injected through
  the existing engine/runtime boundary without rewriting process entry points.
- Liskov substitution: API and worker tests use a context-managed engine double
  with the same success and failure behaviour.
- Interface segregation: worker jobs receive `WorkflowEngine`, not a concrete
  SDK-backed implementation.
- Dependency inversion: application composition depends on the engine port;
  the SDK remains an outer adapter.

## Acceptance criteria

1. API and worker contain no direct `CamundaAsyncClient` construction or SDK
   configuration casts.
2. Both processes use the same managed runtime factory.
3. Lifecycle tests cover normal exit, client-entry failure and failure after a
   client has entered.
4. Existing injected-engine application tests continue to pass unchanged in
   behaviour.
5. Worker database disposal remains guaranteed for every exit path.
6. Static checks, line limits and backend coverage gates remain satisfied.
7. Architecture and threat-model documentation name the single runtime
   boundary and its fail-closed behaviour.

## Out of scope

- Changing BPMN, process variables, candidate groups or human decisions.
- Changing Camunda authentication schemes or production deployment topology.
- Replacing the official Camunda SDK.
- Refactoring request, product, team or statistics services in this milestone.
