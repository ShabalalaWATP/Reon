import type { Session } from "../api/types";

const AUTH_SYNC_KEY = "mist:auth-state";

type AuthSyncMessage =
  | { kind: "context-changed" }
  | { kind: "session-rotated" }
  | { kind: "signed-out" }
  | { kind: "unrelated" };

export function parseAuthSyncEvent(event: StorageEvent): AuthSyncMessage {
  if (event.key !== AUTH_SYNC_KEY) return { kind: "unrelated" };
  if (event.newValue?.startsWith("signed-out:")) return { kind: "signed-out" };
  if (event.newValue?.startsWith("context-changed:")) {
    return { kind: "context-changed" };
  }
  if (event.newValue?.startsWith("session-rotated:")) {
    return { kind: "session-rotated" };
  }
  return { kind: "unrelated" };
}

export function broadcastSignedIn() {
  writeMessage(`signed-in:${Date.now()}`);
}

export function broadcastSignedOut() {
  writeMessage(`signed-out:${Date.now()}`);
}

export function broadcastContextChanged(session: Session) {
  writeMessage(`context-changed:${session.activeContext}:${session.contextVersion}:${Date.now()}`);
}

export function broadcastSessionRotated() {
  writeMessage(`session-rotated:${Date.now()}`);
}

function writeMessage(message: string) {
  window.localStorage.setItem(AUTH_SYNC_KEY, message);
}
