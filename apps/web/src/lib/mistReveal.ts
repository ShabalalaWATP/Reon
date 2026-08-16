type Listener = () => void;

const listeners = new Set<Listener>();
let pending = false;

/**
 * Announce a sign-in so the mist overlay can roll in.
 *
 * The overlay is a lazily loaded component, so the first reveal of a session
 * usually fires before any listener exists. The announcement is latched until
 * a subscriber arrives, then delivered once, so the transition cannot be lost
 * to load timing.
 */
export function revealThroughMist() {
  if (listeners.size === 0) {
    pending = true;
    return;
  }
  listeners.forEach((listener) => listener());
}

export function onMistReveal(listener: Listener) {
  listeners.add(listener);
  if (pending) {
    pending = false;
    listener();
  }
  return () => {
    listeners.delete(listener);
  };
}
