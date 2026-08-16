import { useEffect, useState } from "react";

import "../styles/mist.css";

import { type MistSignal, onMistSignal } from "../lib/mistReveal";

const DENSE_MS = 1900;
const CLEAR_MS = 3900;
const REDUCED_PHASE_MS = 250;

/**
 * gathering: opaque mist raised while a sign-in is in flight; holds until a
 * signal resolves it, so the destination is never painted uncovered.
 * dense: the sign-in succeeded and the mist lingers over the new page.
 * clearing: the mist parts to reveal the page beneath.
 */
type Phase = "hidden" | "gathering" | "dense" | "clearing";

const PHASE_FOR_SIGNAL: Record<MistSignal, Phase> = {
  gather: "gathering",
  reveal: "dense",
  dismiss: "hidden",
};

export function MistReveal() {
  const [phase, setPhase] = useState<Phase>("hidden");
  useEffect(() => onMistSignal((signal) => setPhase(PHASE_FOR_SIGNAL[signal])), []);
  useEffect(() => {
    if (phase === "hidden" || phase === "gathering") return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const wait =
      phase === "dense"
        ? reduced
          ? REDUCED_PHASE_MS
          : DENSE_MS
        : reduced
          ? REDUCED_PHASE_MS
          : CLEAR_MS;
    const timer = window.setTimeout(
      () => setPhase((value) => (value === "dense" ? "clearing" : "hidden")),
      wait,
    );
    return () => window.clearTimeout(timer);
  }, [phase]);
  if (phase === "hidden") return null;
  return (
    <div className={`mist-reveal mist-reveal--${phase}`}>
      <svg aria-hidden="true" className="mist-reveal__filter" focusable="false">
        <filter id="mist-wisp">
          <feTurbulence
            baseFrequency="0.012 0.03"
            numOctaves="3"
            result="noise"
            seed="7"
            type="fractalNoise"
          >
            <animate
              attributeName="baseFrequency"
              dur="14s"
              repeatCount="indefinite"
              values="0.012 0.03;0.016 0.024;0.012 0.03"
            />
          </feTurbulence>
          <feDisplacementMap
            in="SourceGraphic"
            in2="noise"
            scale="90"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </svg>
      <span aria-hidden="true" className="mist-reveal__layer mist-reveal__layer--far" />
      <span aria-hidden="true" className="mist-reveal__layer mist-reveal__layer--mid" />
      <span aria-hidden="true" className="mist-reveal__layer mist-reveal__layer--near" />
      <span aria-hidden="true" className="mist-reveal__layer mist-reveal__layer--drift" />
      <p className="mist-reveal__status" role="status">
        <strong>Mist</strong>
        <span>Signing you in…</span>
      </p>
    </div>
  );
}
