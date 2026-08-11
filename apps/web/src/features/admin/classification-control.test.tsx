import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { adminSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

describe("global classification control", () => {
  it("stays locked until the Administrator has a fresh step-up", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) {
        return json({ ...adminSession, elevatedUntil: null });
      }
      if (url.pathname.endsWith("/admin/users")) return json({ items: [] });
      throw new Error(url.pathname);
    });

    renderApp("/admin/users");

    expect(await screen.findByLabelText("Classification")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Apply to everyone" })).toBeDisabled();
  });
});
