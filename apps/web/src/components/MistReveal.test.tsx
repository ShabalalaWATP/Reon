import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { onMistReveal, revealThroughMist } from "../lib/mistReveal";
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
