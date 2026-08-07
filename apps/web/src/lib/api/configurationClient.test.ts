import { describe, expect, it } from "vitest";

import { configurationVersion } from "../../test/configurationFixtures";
import { json, mockFetch } from "../../test/render";
import { configurationApi } from "./configurationClient";

describe("configuration API client", () => {
  it("uses the immutable registry, preview, snapshot and action contracts", async () => {
    const requests: Array<{ body: unknown; method: string; path: string }> = [];
    mockFetch((url, init) => {
      requests.push({ body: init.body ? JSON.parse(String(init.body)) : null, method: init.method ?? "GET", path: `${url.pathname}${url.search}` });
      return json({ items: [] });
    }, false, false, false, false, false);
    const draft = {
      basedOnVersionId: configurationVersion.basedOnVersionId,
      candidateGroups: configurationVersion.candidateGroups,
      edges: configurationVersion.edges,
      effectiveFrom: configurationVersion.effectiveFrom,
      label: configurationVersion.label,
      units: configurationVersion.units,
      workflowTemplate: configurationVersion.workflowTemplate,
    };
    await configurationApi.versions();
    await configurationApi.create(draft, "csrf");
    await configurationApi.version("cfg/2");
    await configurationApi.replace("cfg/2", { ...draft, expectedVersion: 1 }, "csrf");
    await configurationApi.preview("cfg/2");
    await configurationApi.validate("cfg/2", { expectedVersion: 1 }, "csrf");
    await configurationApi.submit("cfg/2", { expectedVersion: 2, reason: "Ready for review" }, "csrf");
    await configurationApi.approve("cfg/2", { expectedVersion: 3, reason: "Independent approval" }, "csrf");
    await configurationApi.reject("cfg/2", { expectedVersion: 3, reason: "Hierarchy is incomplete" }, "csrf");
    await configurationApi.activate("cfg/2", { expectedVersion: 4, reason: "Activate for future requests" }, "csrf");
    await configurationApi.active();
    await configurationApi.organisation("cfg/2", "2026-09-01T09:00:00+01:00");
    await configurationApi.organisation("cfg/2");
    await configurationApi.workflowDefinitions();
    expect(requests.map((request) => `${request.method} ${request.path}`)).toEqual([
      "GET /api/v1/admin/configuration/versions",
      "POST /api/v1/admin/configuration/versions",
      "GET /api/v1/admin/configuration/versions/cfg%2F2",
      "PUT /api/v1/admin/configuration/versions/cfg%2F2",
      "GET /api/v1/admin/configuration/versions/cfg%2F2/preview",
      "POST /api/v1/admin/configuration/versions/cfg%2F2/validate",
      "POST /api/v1/admin/configuration/versions/cfg%2F2/submit",
      "POST /api/v1/admin/configuration/versions/cfg%2F2/approve",
      "POST /api/v1/admin/configuration/versions/cfg%2F2/reject",
      "POST /api/v1/admin/configuration/versions/cfg%2F2/activate",
      "GET /api/v1/admin/configuration/active",
      "GET /api/v1/admin/configuration/versions/cfg%2F2/organisation?at=2026-09-01T09%3A00%3A00%2B01%3A00",
      "GET /api/v1/admin/configuration/versions/cfg%2F2/organisation",
      "GET /api/v1/admin/configuration/workflow-definitions",
    ]);
    expect(requests[5].body).toEqual({ expectedVersion: 1 });
    expect(requests[6].body).toEqual({ expectedVersion: 2, reason: "Ready for review" });
  });
});
