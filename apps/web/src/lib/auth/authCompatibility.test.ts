import { describe, expect, it, vi } from "vitest";

import { capabilityApi, disabledCapabilities } from "../api/capabilityClient";
import { requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch } from "../../test/render";
import {
  broadcastContextChanged,
  broadcastSessionRotated,
  broadcastSignedIn,
  broadcastSignedOut,
  parseAuthSyncEvent,
} from "./authSync";
import { requireCompatibleSession } from "./sessionCompatibility";

describe("authentication compatibility boundaries", () => {
  it("accepts a complete session, optional idle fields and duplicate contexts", () => {
    const session = requireCompatibleSession({
      ...requesterSession,
      availableContexts: ["CUSTOMER", "CUSTOMER"],
      idleExpiresAt: undefined,
      idleTimeoutSeconds: undefined,
    });

    expect(session.availableContexts).toEqual(["CUSTOMER"]);
    expect(session.idleExpiresAt).toBeUndefined();
    expect(session.idleTimeoutSeconds).toBeUndefined();
  });

  it.each([
    null,
    [],
    {},
    { ...requesterSession, user: null },
    { ...requesterSession, user: { ...requesterSession.user, role: "LEGACY" } },
    { ...requesterSession, user: { ...requesterSession.user, id: " " } },
    { ...requesterSession, user: { ...requesterSession.user, organisationUnitIds: [1] } },
    { ...requesterSession, activeContext: "LEGACY" },
    { ...requesterSession, availableContexts: [] },
    { ...requesterSession, availableContexts: ["LEGACY"] },
    { ...requesterSession, availableContexts: ["STAFF"] },
    { ...requesterSession, csrfToken: "" },
    { ...requesterSession, expiresAt: "not-a-date" },
    { ...requesterSession, idleExpiresAt: "not-a-date" },
    { ...requesterSession, idleTimeoutSeconds: 0 },
    { ...requesterSession, elevatedUntil: "not-a-date" },
    { ...requesterSession, contextVersion: -1 },
  ])("rejects incompatible session input %#", (value) => {
    expect(() => requireCompatibleSession(value)).toThrow(
      "The server returned an incompatible session.",
    );
  });

  it("parses and broadcasts only recognised cross-tab messages", () => {
    vi.spyOn(Date, "now").mockReturnValue(123);
    expect(
      parseAuthSyncEvent(
        new StorageEvent("storage", {
          key: "another-key",
          newValue: "signed-out:123",
        }),
      ),
    ).toEqual({ kind: "unrelated" });
    expect(
      parseAuthSyncEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "signed-out:123",
        }),
      ),
    ).toEqual({ kind: "signed-out" });
    expect(
      parseAuthSyncEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "context-changed:CUSTOMER:2:123",
        }),
      ),
    ).toEqual({ kind: "context-changed" });
    expect(
      parseAuthSyncEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "session-rotated:123",
        }),
      ),
    ).toEqual({ kind: "session-rotated" });
    expect(
      parseAuthSyncEvent(
        new StorageEvent("storage", {
          key: "mist:auth-state",
          newValue: "signed-in:123",
        }),
      ),
    ).toEqual({ kind: "unrelated" });

    broadcastSignedIn();
    expect(localStorage.getItem("mist:auth-state")).toBe("signed-in:123");
    broadcastSignedOut();
    expect(localStorage.getItem("mist:auth-state")).toBe("signed-out:123");
    broadcastContextChanged(requesterSession);
    expect(localStorage.getItem("mist:auth-state")).toBe("context-changed:CUSTOMER:1:123");
    broadcastSessionRotated();
    expect(localStorage.getItem("mist:auth-state")).toBe("session-rotated:123");
  });

  it("normalises capabilities independently and defaults unknown values off", async () => {
    mockFeatureFetch((url) =>
      url.pathname.endsWith("/me/capabilities")
        ? json({
            conversationReads: true,
            conversationWrites: "true",
            contextSwitching: false,
            myWork: true,
            notifications: 1,
            configuration: true,
            products: null,
            managedFileUploads: true,
            planning: false,
            statistics: true,
          })
        : json({}),
    );

    expect(await capabilityApi.capabilities()).toEqual({
      ...disabledCapabilities,
      conversationReads: true,
      myWork: true,
      configuration: true,
      managedFileUploads: true,
      statistics: true,
    });
  });

  it("defaults a non-object capability response to the disabled contract", async () => {
    mockFeatureFetch(() => json([]));
    expect(await capabilityApi.capabilities()).toEqual(disabledCapabilities);
  });
});
