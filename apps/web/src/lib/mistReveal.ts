/**
 * Signals for the sign-in mist overlay.
 *
 * `gather` raises opaque mist the moment a sign-in is attempted, before any
 * network call, so the destination page is never painted in the open. `reveal`
 * confirms the sign-in and starts the slow clearing over the new page.
 * `dismiss` drops the mist when the attempt fails. The overlay is lazily
 * loaded, so a signal that arrives before any listener exists is latched and
 * delivered once to the first subscriber.
 */
export type MistSignal = "gather" | "reveal" | "dismiss";

type Listener = (signal: MistSignal) => void;

const listeners = new Set<Listener>();
let pending: MistSignal | null = null;

function emit(signal: MistSignal) {
  if (listeners.size === 0) {
    pending = signal;
    return;
  }
  listeners.forEach((listener) => listener(signal));
}

export function gatherMist() {
  emit("gather");
}

export function revealThroughMist() {
  emit("reveal");
}

export function dismissMist() {
  emit("dismiss");
}

export function onMistSignal(listener: Listener) {
  listeners.add(listener);
  if (pending !== null) {
    const signal = pending;
    pending = null;
    listener(signal);
  }
  return () => {
    listeners.delete(listener);
  };
}
