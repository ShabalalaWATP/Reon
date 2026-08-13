import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  alternativeStaffedScenario,
  staffedScenario,
} from "./camunda-smoke-scenarios.mjs";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const scriptPath = join(scriptDirectory, "smoke-camunda.ps1");
const scenarios = [staffedScenario, alternativeStaffedScenario];
const calls = [];
const handlerErrors = [];
const starts = [];
const states = new Map(
  scenarios.map((scenario) => [
    scenario.processInstanceKey,
    { scenario, routeStage: 0, assigned: false },
  ]),
);

const camundaConfig = await readFile(
  join(repositoryRoot, "infra/camunda/application-postgresql.yaml"),
  "utf8",
);
const smokeCompose = await readFile(
  join(repositoryRoot, ".github/compose.camunda-smoke.yml"),
  "utf8",
);
assert.match(camundaConfig, /business-id-uniqueness-enabled:\s*true/u);
assert.match(
  smokeCompose,
  /CAMUNDA_PROCESSINSTANCECREATION_BUSINESSIDUNIQUENESSENABLED:\s*"true"/u,
);
assert.match(smokeCompose, /CAMUNDA_HOST_PORT:-18080\}:8080/u);
assert.match(smokeCompose, /CAMUNDA_MANAGEMENT_HOST_PORT:-19600\}:9600/u);
assert.match(
  smokeCompose,
  /orchestration:[\s\S]*networks:\s*\n\s*- data\s*\n\s*- workflow\s*\n\s*- smoke-host/u,
  "the CI smoke service must retain internal networks and add a host-reachable network",
);
assert.match(smokeCompose, /networks:\s*\n\s*smoke-host: \{\}/u);

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

function sendJson(response, value, status = 200) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(value));
}

function sendEmpty(response) {
  response.writeHead(204);
  response.end();
}

function taskPage(task, processInstanceKey) {
  return {
    items: [
      {
        userTaskKey: task.taskKey,
        tenantId: "<default>",
        processInstanceKey,
        rootProcessInstanceKey: processInstanceKey,
        elementId: task.elementId,
        name: task.name,
        state: "CREATED",
        candidateGroups: task.candidateGroup ? [task.candidateGroup] : [],
        candidateUsers: [],
        assignee: task.assignee ?? null,
      },
    ],
    page: {
      totalItems: 1,
      hasMoreTotalItems: false,
      startCursor: "c3RhcnQ=",
      endCursor: "ZW5k",
    },
  };
}

function assertStartRequest(body) {
  assert.deepEqual(Object.keys(body).sort(), [
    "businessId",
    "processDefinitionId",
    "processDefinitionVersion",
    "variables",
  ]);
  assert.equal(body.processDefinitionId, "service-request-v1");
  assert.equal(body.processDefinitionVersion, 1);
  assert.deepEqual(Object.keys(body.variables).sort(), ["requestId", "requesterId"]);
  assert.match(body.variables.requestId, /^[0-9a-f-]{36}$/u);
  assert.match(body.variables.requesterId, /^[0-9a-f-]{36}$/u);
  assert.equal(body.businessId, body.variables.requestId);
}

function handleProcessStart(body, response) {
  assertStartRequest(body);
  const duplicate = starts.find((start) => start.body.businessId === body.businessId);
  if (duplicate) {
    assert.deepEqual(body, duplicate.body);
    assert.equal(duplicate.scenario, staffedScenario);
    assert.equal(states.get(staffedScenario.processInstanceKey).routeStage, 0);
    sendJson(
      response,
      { title: "Conflict", status: 409, detail: "Duplicate active business ID" },
      409,
    );
    return;
  }

  const scenario = scenarios[starts.length];
  assert(scenario, "smoke started an unexpected third unique process");
  for (const task of scenario.route) {
    if (task.assignee === "__REQUESTER_ID__") {
      task.assignee = body.variables.requesterId;
      task.actorId = body.variables.requesterId;
    }
  }
  starts.push({ body, scenario });
  sendJson(response, {
    processDefinitionId: "service-request-v1",
    processDefinitionVersion: 1,
    tenantId: "<default>",
    variables: body.variables,
    processDefinitionKey: "2251799813685249",
    processInstanceKey: scenario.processInstanceKey,
    tags: [],
    businessId: body.businessId,
  });
}

function findTaskState(body) {
  const processInstanceKey = body.filter?.processInstanceKey;
  const state = states.get(processInstanceKey);
  assert(state, "task search used an unknown process instance");
  const task = state.scenario.route[state.routeStage];
  assert(task, "task search advanced past its scenario route");
  assert.deepEqual(body, {
    filter: {
      state: "CREATED",
      processInstanceKey,
      elementId: task.elementId,
    },
    page: { limit: 2 },
  });
  return { processInstanceKey, state, task };
}

async function handle(request, response) {
  calls.push(`${request.method} ${request.url}`);
  const rawBody = await readBody(request);
  if (request.method === "GET" && request.url === "/v2/topology") {
    sendJson(response, { brokers: [], clusterSize: 1, partitionsCount: 1 });
    return;
  }
  if (request.url === "/v2/deployments") {
    assert.match(request.headers["content-type"], /^multipart\/form-data;/u);
    assert.match(rawBody, /service-request\.bpmn/u);
    sendJson(response, {
      deploymentKey: "2251799813685248",
      deployments: [
        {
          processDefinition: {
            processDefinitionId: "service-request-v1",
            processDefinitionVersion: 1,
            processDefinitionKey: "2251799813685249",
            resourceName: "service-request.bpmn",
            tenantId: "<default>",
          },
        },
      ],
    });
    return;
  }

  if (request.url === "/v2/process-instances") {
    handleProcessStart(JSON.parse(rawBody), response);
    return;
  }

  if (
    request.method === "GET" &&
    [...scenarios].some(
      ({ processInstanceKey }) =>
        request.url === `/v2/process-instances/${processInstanceKey}`,
    )
  ) {
    const processInstanceKey = request.url.split("/").at(-1);
    const state = states.get(processInstanceKey);
    assert(state);
    assert.equal(
      state.routeStage,
      state.scenario.route.length,
    );
    sendJson(response, {
      processInstanceKey,
      state: "COMPLETED",
      endDate: "2026-08-06T12:00:00.000Z",
    });
    return;
  }

  const body = JSON.parse(rawBody);
  if (request.url === "/v2/user-tasks/search") {
    const { processInstanceKey, task } = findTaskState(body);
    sendJson(response, taskPage(task, processInstanceKey));
    return;
  }

  const state = [...states.values()].find(({ scenario, routeStage }) => {
    const task = scenario.route[routeStage];
    return task && request.url.includes(task.taskKey);
  });
  assert(state, "task mutation used an unknown task key");
  const task = state.scenario.route[state.routeStage];
  if (request.url === `/v2/user-tasks/${task.taskKey}/assignment`) {
    assert.equal(task.assignee, undefined, "pre-assigned task must not be claimed");
    assert.deepEqual(body, {
      assignee: task.actorId,
      allowOverride: false,
      action: "claim",
    });
    state.assigned = true;
    sendEmpty(response);
    return;
  }

  assert.equal(request.url, `/v2/user-tasks/${task.taskKey}/completion`);
  assert.equal(
    state.assigned || task.assignee === task.actorId,
    true,
    "task completion must follow a claim or exact direct assignment",
  );
  assert.deepEqual(body, { action: task.action, variables: task.variables });
  state.routeStage += 1;
  state.assigned = false;
  sendEmpty(response);
}

const server = createServer((request, response) => {
  handle(request, response).catch((error) => {
    handlerErrors.push(error);
    sendJson(response, { title: "Synthetic contract failure" }, 500);
  });
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const address = server.address();
assert(address && typeof address !== "string");

let output = "";
let errors = "";
let timedOut = false;
const child = spawn(
  "pwsh",
  [
    "-NoLogo",
    "-NoProfile",
    "-File",
    scriptPath,
    "-BaseUri",
    `http://127.0.0.1:${address.port}`,
    "-MaxAttempts",
    "2",
    "-RetryDelaySeconds",
    "1",
  ],
  { windowsHide: true },
);
child.stdout.on("data", (chunk) => (output += chunk));
child.stderr.on("data", (chunk) => (errors += chunk));
const timeout = setTimeout(() => {
  timedOut = true;
  child.kill();
}, 20_000);
const exitCode = await new Promise((resolve) => child.on("close", resolve));
clearTimeout(timeout);
await new Promise((resolve) => server.close(resolve));

assert.equal(timedOut, false, "smoke contract test timed out");
assert.deepEqual(handlerErrors, []);
assert.equal(exitCode, 0, errors);
assert.equal(starts.length, 2, "smoke did not start two unique instances");
assert.notEqual(starts[0].body.businessId, starts[1].body.businessId);
assert.equal(
  states.get(staffedScenario.processInstanceKey).routeStage,
  staffedScenario.route.length,
  "staffed SSG path did not complete",
);
assert.equal(
  states.get(alternativeStaffedScenario.processInstanceKey).routeStage,
  alternativeStaffedScenario.route.length,
  "staffed Beacon path did not complete",
);
assert.match(output, /JOCK -> ACSA-B Ops -> SSG Team/u);
assert.match(output, /COMPLETED/u);
assert.match(output, /SYGOC -> Nimbus Ops -> Beacon Team/u);
assert.match(output, /beacon-team-managers/u);
assert.match(output, /beacon-team-analysts/u);
assert.match(
  output,
  /StaffedClarificationLoops\s*:\s*(?:\u001B\[[0-9;]*m)?2/u,
);

function mutationCalls(task) {
  return [
    `POST /v2/user-tasks/${task.taskKey}/assignment`,
    `POST /v2/user-tasks/${task.taskKey}/completion`,
  ];
}

function completedRouteCalls(scenario, count = scenario.route.length) {
  return scenario.route.slice(0, count).flatMap((task) => [
    "POST /v2/user-tasks/search",
    ...(task.assignee ? [] : mutationCalls(task).slice(0, 1)),
    `POST /v2/user-tasks/${task.taskKey}/completion`,
  ]);
}

assert.deepEqual(calls, [
  "GET /v2/topology",
  "POST /v2/deployments",
  "POST /v2/process-instances",
  "POST /v2/process-instances",
  ...completedRouteCalls(staffedScenario),
  `GET /v2/process-instances/${staffedScenario.processInstanceKey}`,
  "POST /v2/process-instances",
  ...completedRouteCalls(alternativeStaffedScenario),
  `GET /v2/process-instances/${alternativeStaffedScenario.processInstanceKey}`,
]);
console.log("Camunda SSG and alternative-team V2 smoke contract passed.");
