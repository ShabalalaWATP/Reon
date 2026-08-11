import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BellRing, ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import { boardApi } from "../../lib/api/boardClient";
import { ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { RequestDetail, Session } from "../../lib/api/types";
import { formatDate } from "../../lib/status";

const activeStages = new Set(["IN_PROGRESS", "CUSTOMER_INFORMATION_REQUIRED", "REWORK_REQUIRED"]);

export function TaskHastenerPanel({ access, request, session }: {
  access: TeamWorkspaceAccess;
  request: RequestDetail;
  session: Session;
}) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [recipient, setRecipient] = useState("ALL_ASSIGNED");
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);
  const analysts = useMemo(() => assignedAnalysts(request), [request]);
  const history = request.events.filter((event) => event.type === "task_hastener").reverse();
  const canSend = access.unitKind === "TEAM"
    && access.workspacePosition === "MANAGER"
    && activeStages.has(request.status)
    && analysts.length > 0;
  const mutation = useMutation({
    mutationFn: () => boardApi.sendTaskHastener(access.teamId, request.id, {
      audience: recipient === "ALL_ASSIGNED" ? "ALL_ASSIGNED" : "ONE_ASSIGNED",
      ...(recipient === "ALL_ASSIGNED" ? {} : { recipientUserId: recipient }),
      message,
    }, session.csrfToken),
    onSuccess: () => {
      setMessage("");
      setOpen(false);
      setSent(true);
      void client.invalidateQueries({ queryKey: protectedQueryKeys.request(session.user.id, request.id) });
    },
  });

  if (!canSend && history.length === 0) return null;
  return (
    <section className="task-hasteners" aria-labelledby="task-hasteners-title">
      <header>
        <div><span>Manager follow-up</span><h3 id="task-hasteners-title"><BellRing aria-hidden="true" size={17} />Task reminders</h3><p>Hasteners are recorded in the request history. They do not change its owner or workflow stage.</p></div>
        {canSend ? <button aria-expanded={open} className="button button--quiet" onClick={() => { setOpen((value) => !value); setSent(false); }} type="button"><ChevronDown aria-hidden="true" className={open ? "task-hasteners__chevron task-hasteners__chevron--open" : "task-hasteners__chevron"} size={16} />{open ? "Cancel" : "Send hastener"}</button> : null}
      </header>
      {sent ? <p className="form-banner form-banner--success" role="status">Hastener sent and recorded.</p> : null}
      {open ? (
        <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
          <label className="form-field">Recipients<span className="field-hint">Required</span><select onChange={(event) => setRecipient(event.target.value)} required value={recipient}><option value="ALL_ASSIGNED">All assigned Analysts ({analysts.length})</option>{analysts.map((analyst) => <option key={analyst.id} value={analyst.id}>{analyst.name} · {analyst.role}</option>)}</select></label>
          <label className="form-field">Message<span className="field-hint">Required, 10–500 characters</span><textarea maxLength={500} minLength={10} onChange={(event) => setMessage(event.target.value)} required rows={4} value={message} /></label>
          {mutation.isError ? <p className="form-banner form-banner--error" role="alert">{errorMessage(mutation.error)}</p> : null}
          <button className="button button--primary" disabled={mutation.isPending || message.trim().length < 10} type="submit">{mutation.isPending ? "Sending…" : "Send and record hastener"}</button>
        </form>
      ) : null}
      {history.length ? <ol className="task-hasteners__history">{history.map((event) => <li key={event.id}><p>{event.message}</p><small>{event.actorDisplayName ?? "ISTARI service"} · <time dateTime={event.createdAt}>{formatDate(event.createdAt, true)}</time></small></li>)}</ol> : <p className="task-hasteners__empty">No hasteners have been sent for this request.</p>}
    </section>
  );
}

function assignedAnalysts(request: RequestDetail) {
  const values = [
    ...(request.assignedSpecialist ? [{ id: request.assignedSpecialist.id, name: request.assignedSpecialist.displayName, role: "Lead" }] : []),
    ...request.contributors.map((item) => ({ id: item.id, name: item.displayName, role: "Contributor" })),
  ];
  return [...new Map(values.map((item) => [item.id, item])).values()];
}

function errorMessage(error: Error) {
  return error instanceof ApiError ? error.message : "The hastener could not be sent.";
}
