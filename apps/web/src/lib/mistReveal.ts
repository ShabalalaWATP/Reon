type Listener = () => void;

const listeners = new Set<Listener>();

export function revealThroughMist() {
  listeners.forEach((listener) => listener());
}

export function onMistReveal(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
