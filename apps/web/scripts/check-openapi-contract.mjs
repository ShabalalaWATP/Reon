import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import process from "node:process";
import { fileURLToPath, URL } from "node:url";

const apiRoot = fileURLToPath(new URL("../../api/", import.meta.url));
const openApiCommand = [
  "run",
  "--directory",
  apiRoot,
  "python",
  "-c",
  "import json; from istari_service.main import app; print(json.dumps(app.openapi()))",
];
const result = spawnSync("uv", openApiCommand, { encoding: "utf8" });

if (result.error) throw result.error;
if (result.status !== 0) {
  process.stderr.write(result.stderr);
  process.exit(result.status ?? 1);
}

const document = JSON.parse(result.stdout);
const schemas = document.components?.schemas;
const paths = document.paths ?? {};
const deliverable = schemas?.DeliverableView;
const requestDetailDeliverable = schemas?.RequestDetail?.properties?.deliverable;

function resolveSchema(value) {
  if (!value?.$ref) return value;
  const name = value.$ref.split("/").at(-1);
  return schemas?.[name];
}

function requireFields(schema, fields, label) {
  for (const field of fields) {
    assert.ok(schema?.required?.includes(field), `${label} must require ${field}.`);
    assert.ok(schema?.properties?.[field], `${label} is missing ${field}.`);
  }
}

function getPath(pattern, label) {
  const path = Object.keys(paths).find((candidate) => pattern.test(candidate));
  assert.ok(path, `OpenAPI is missing ${label}.`);
  assert.ok(paths[path].get, `${label} must support GET.`);
  return paths[path].get;
}

function jsonListItem(operation, label) {
  const response = operation.responses?.["200"];
  const envelope = resolveSchema(response?.content?.["application/json"]?.schema);
  assert.equal(envelope?.properties?.items?.type, "array", `${label} must return an items list.`);
  return resolveSchema(envelope.properties.items.items);
}

assert.ok(deliverable, "OpenAPI is missing DeliverableView.");
for (const field of ["id", "title", "text", "releasedAt"]) {
  assert.ok(deliverable.required?.includes(field), `DeliverableView must require ${field}.`);
}
assert.equal(deliverable.properties.id.format, "uuid");
assert.equal(deliverable.properties.title.type, "string");
assert.equal(deliverable.properties.text.type, "string");

const releasedAtVariants = deliverable.properties.releasedAt.anyOf;
assert.ok(
  releasedAtVariants.some((variant) => variant.type === "string" && variant.format === "date-time"),
  "DeliverableView.releasedAt must accept a date-time string.",
);
assert.ok(
  releasedAtVariants.some((variant) => variant.type === "null"),
  "DeliverableView.releasedAt must remain nullable.",
);
assert.ok(
  requestDetailDeliverable.anyOf.some(
    (variant) => variant.$ref === "#/components/schemas/DeliverableView",
  ) && requestDetailDeliverable.anyOf.some((variant) => variant.type === "null"),
  "RequestDetail.deliverable must be a nullable DeliverableView.",
);

const organisationOperation = getPath(/\/organisation\/units$/, "GET /organisation/units");
const organisationUnit = jsonListItem(organisationOperation, "Organisation units");
requireFields(
  organisationUnit,
  ["id", "code", "name", "kind", "parentId", "staffingStatus"],
  "OrganisationUnitView",
);
requireFields(organisationUnit, ["version"], "OrganisationUnitView");
assert.deepEqual(resolveSchema(organisationUnit.properties.kind).enum, [
  "ROOT",
  "COMMAND",
  "OPS_GROUP",
  "TEAM",
]);
assert.deepEqual(resolveSchema(organisationUnit.properties.staffingStatus).enum, [
  "ROUTING_POOL",
  "STAFFED",
  "UNSTAFFED",
]);

const routingOperation = getPath(
  /\/work-items\/\{[^}]+\}\/routing-options$/,
  "GET /work-items/{id}/routing-options",
);
const routingUnit = jsonListItem(routingOperation, "Routing options");
requireFields(routingUnit, ["id", "name", "kind", "staffingStatus"], "Routing option");

const trackingOperation = getPath(/\/tracked-requests$/, "GET /tracked-requests");
const trackedRequest = jsonListItem(trackingOperation, "Tracked requests");
requireFields(
  trackedRequest,
  [
    "id",
    "reference",
    "title",
    "status",
    "currentOwner",
    "requiredBy",
    "createdAt",
    "updatedAt",
    "route",
    "awaitingTeamStaffing",
  ],
  "TrackedRequest",
);
const trackedRouteUnit = resolveSchema(trackedRequest.properties.route.items);
requireFields(trackedRouteUnit, ["id", "name", "kind"], "TrackedRouteUnit");

const trackingDetailOperation = getPath(
  /\/tracked-requests\/\{[^}]+\}$/,
  "GET /tracked-requests/{id}",
);
const trackedDetail = resolveSchema(
  trackingDetailOperation.responses?.["200"]?.content?.["application/json"]?.schema,
);
requireFields(
  trackedDetail,
  ["id", "reference", "title", "requesterDisplayName", "description", "questionToAnswer", "route"],
  "TrackedRequestDetail",
);
for (const field of ["deliverable", "product", "clarifications", "feedback", "availableActions"]) {
  assert.equal(
    trackedDetail.properties[field],
    undefined,
    `TrackedRequestDetail must not expose ${field}.`,
  );
}

for (const name of ["ProgressRequest", "SendToAllocation", "AllocateRequest"]) {
  requireFields(schemas?.[name], ["action", "destinationUnitId"], name);
}
assert.equal(
  schemas?.AllocateRequest?.properties?.deliveryTeam,
  undefined,
  "AllocateRequest must not accept deliveryTeam.",
);

const productOperation = getPath(/\/requests\/\{[^}]+\}\/product$/, "GET /requests/{id}/product");
assert.ok(
  productOperation.responses?.["200"]?.content?.["text/plain"],
  "Product download must document a text/plain response.",
);

const adminUsersOperation = getPath(/\/admin\/users$/, "GET /admin/users");
const adminUser = jsonListItem(adminUsersOperation, "Administrator users");
requireFields(
  adminUser,
  [
    "id",
    "username",
    "displayName",
    "role",
    "scope",
    "isActive",
    "version",
    "createdAt",
    "updatedAt",
    "memberships",
  ],
  "AdminUser",
);
for (const forbidden of ["request", "title", "description", "deliverable", "workflowTask"]) {
  assert.equal(
    adminUser.properties[forbidden],
    undefined,
    `AdminUser must not expose ${forbidden}.`,
  );
}
const membership = resolveSchema(adminUser.properties.memberships.items);
requireFields(
  membership,
  ["organisationUnitId", "organisationUnitName", "organisationUnitKind"],
  "AdminMembership",
);

const adminUserPath = Object.keys(paths).find((candidate) =>
  /\/admin\/users\/\{[^}]+\}$/.test(candidate),
);
assert.ok(adminUserPath, "OpenAPI is missing administrator user detail.");
assert.ok(paths[adminUserPath].get, "Administrator user detail must support GET.");
assert.ok(paths[adminUserPath].patch, "Administrator user detail must support PATCH.");
const statusPath = Object.keys(paths).find((candidate) =>
  /\/admin\/users\/\{[^}]+\}\/status$/.test(candidate),
);
assert.ok(paths[statusPath]?.patch, "Administrator status must support PATCH.");
const renamePath = Object.keys(paths).find((candidate) =>
  /\/admin\/organisation\/units\/\{[^}]+\}$/.test(candidate),
);
assert.ok(paths[renamePath]?.patch, "Administrator organisation rename must support PATCH.");

process.stdout.write(
  "OpenAPI contract check passed for administration, hierarchy, routing, tracking and product download.\n",
);
