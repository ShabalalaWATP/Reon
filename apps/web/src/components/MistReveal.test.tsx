import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { onMistReveal, revealThroughMist } from "../lib/mistReveal";
import { requesterSession } from "../test/fixtures";
import { json, mockFetch, renderApp } from "../test/render";
import { MistReveal } from "./MistReveal";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function stubMotionPreference(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches }));
}

function overlay() {
  return document.querySelector(".mist-reveal");
}

describe("mist reveal transition", () => {
  it("rolls in dense mist on sign-in, clears it and then leaves the page", async () => {
    vi.useFakeTimers();
    stubMotionPreference(false);
    render(<MistReveal />);
    expect(overlay()).toBeNull();

    act(() => revealThroughMist());
    expect(screen.getByRole("status")).toHaveTextContent("Signing you in…");
    expect(overlay()).toHaveClass("mist-reveal--dense");

    act(() => void vi.advanceTimersByTime(1900));
    expect(overlay()).toHaveClass("mist-reveal--clearing");

    act(() => void vi.advanceTimersByTime(3900));
    expect(overlay()).toBeNull();
  });

  it("keeps the transition brief when reduced motion is preferred", () => {
    vi.useFakeTimers();
    stubMotionPreference(true);
    render(<MistReveal />);
    act(() => revealThroughMist());
    expect(overlay()).toHaveClass("mist-reveal--dense");
    act(() => void vi.advanceTimersByTime(250));
    expect(overlay()).toHaveClass("mist-reveal--clearing");
    act(() => void vi.advanceTimersByTime(250));
    expect(overlay()).toBeNull();
  });

  it("restarts from dense mist if sign-in happens while clearing", () => {
    vi.useFakeTimers();
    stubMotionPreference(false);
    render(<MistReveal />);
    act(() => revealThroughMist());
    act(() => void vi.advanceTimersByTime(1900));
    expect(overlay()).toHaveClass("mist-reveal--clearing");
    act(() => revealThroughMist());
    expect(overlay()).toHaveClass("mist-reveal--dense");
  });

  it("delivers a reveal announced before the lazily loaded overlay mounts", () => {
    vi.useFakeTimers();
    stubMotionPreference(false);
    // The overlay is code-split, so in production the first sign-in fires
    // before any listener exists. The announcement must survive that gap.
    act(() => revealThroughMist());
    expect(overlay()).toBeNull();

    render(<MistReveal />);
    expect(overlay()).toHaveClass("mist-reveal--dense");
    expect(screen.getByRole("status")).toHaveTextContent("Signing you in…");
  });

  it("consumes a latched reveal exactly once", () => {
    vi.useFakeTimers();
    stubMotionPreference(false);
    act(() => revealThroughMist());
    const first = render(<MistReveal />);
    expect(overlay()).toHaveClass("mist-reveal--dense");
    first.unmount();
    render(<MistReveal />);
    expect(overlay()).toBeNull();
  });

  it("survives the sign-in re-key of the session subtree in the real app shell", async () => {
    // Sign-in rotates the protected query client, which re-keys everything
    // under AuthProvider. An overlay mounted inside that subtree receives the
    // reveal and is unmounted in the same commit, so it never shows. This
    // drives the genuine login path through the production composition.
    stubMotionPreference(false);
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json({ detail: "Signed out" }, 401);
      if (url.pathname.endsWith("/auth/login") && init.method === "POST") {
        return json(requesterSession);
      }
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/login");
    await user.type(await screen.findByLabelText(/Account ID/), "admin2");
    await user.type(screen.getByLabelText(/Password/), "synthetic-password");
    await user.click(screen.getByRole("button", { name: "Sign in to Mist" }));

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(overlay()).toHaveClass("mist-reveal--dense");
    expect(screen.getByRole("status")).toHaveTextContent("Signing you in…");
  });

  it("stops listening after unmount and tolerates a missing matchMedia", () => {
    vi.useFakeTimers();
    vi.stubGlobal("matchMedia", undefined);
    const view = render(<MistReveal />);
    act(() => revealThroughMist());
    expect(overlay()).toHaveClass("mist-reveal--dense");
    view.unmount();
    expect(overlay()).toBeNull();
    expect(() => revealThroughMist()).not.toThrow();
    const stop = onMistReveal(() => undefined);
    stop();
  });
});
