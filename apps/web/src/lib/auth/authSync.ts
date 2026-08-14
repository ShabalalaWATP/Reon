import type { Session } from "../api/types";

const AUTH_SYNC_KEY = "istari:auth-state";

type AuthSyncMessage = { kind: "context-changed" } | { kind: "signed-out" } | { kind: "unrelated" };

export function parseAuthSyncEvent(event: StorageEvent): AuthSyncMessage {
  if (event.key !== AUTH_SYNC_KEY) return { kind: "unrelated" };
  if (event.newValue?.startsWith("signed-out:")) return { kind: "signed-out" };
  if (event.newValue?.startsWith("context-changed:")) {
    return { kind: "context-changed" };
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

function writeMessage(message: string) {
  window.localStorage.setItem(AUTH_SYNC_KEY, message);
}
