import type { FormEvent } from "react";

import { ApiError } from "../../lib/api/client";
import { boardLabel } from "./boardPresentation";

export function BoardSettings({
  current,
  error,
  pending,
  onSave,
}: {
  current: Record<string, number>;
  error: Error | null;
  pending: boolean;
  onSave: (value: Record<string, number>) => void;
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSave(Object.fromEntries(
      ["READY", "IN_PROGRESS", "BLOCKED"].map((key) => [key, Number(data.get(key))]),
    ));
  };
  return (
    <section className="wip-panel">
      <header><span>Flow control</span><h2>Work in progress limits</h2><p>Limits make overload visible. They do not move, stop or assign work automatically.</p></header>
      <form onSubmit={submit}>
        {["READY", "IN_PROGRESS", "BLOCKED"].map((key) => <label className="form-field" key={key}>{boardLabel(key)}<input defaultValue={current[key] ?? 5} max={100} min={1} name={key} required type="number" /></label>)}
        <button className="button button--primary" disabled={pending} type="submit">{pending ? "Saving…" : "Save limits"}</button>
      </form>
      {error ? <p role="alert">{error instanceof ApiError ? error.message : error.message}</p> : null}
    </section>
  );
}
