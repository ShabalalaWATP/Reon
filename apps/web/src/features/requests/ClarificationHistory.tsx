import { CalendarClock, CheckCircle2, MessageSquareText } from "lucide-react";

import type { ClarificationThread } from "../../lib/api/types";
import { formatDate } from "../../lib/status";

const stateLabel: Record<ClarificationThread["status"], string> = {
  ANSWERED: "Answered",
  OPEN: "Response needed",
  WITHDRAWN: "Request withdrawn",
};

export function ClarificationHistory({
  threads,
}: {
  threads: ClarificationThread[];
}) {
  if (threads.length === 0) return null;
  return (
    <section className="clarification-history" aria-labelledby="clarification-title">
      <div className="section-heading">
        <span>Recorded conversation</span>
        <h2 id="clarification-title">Additional information</h2>
      </div>
      <div className="clarification-list">
        {threads.map((thread) => (
          <article className="clarification-thread" key={thread.id}>
            <header>
              <div>
                <span className="mono-ref">Question {thread.sequence}</span>
                <h3>{thread.question}</h3>
              </div>
              <span className={`clarification-state clarification-state--${thread.status.toLowerCase()}`}>
                {thread.status === "ANSWERED" ? <CheckCircle2 aria-hidden="true" size={15} /> : <MessageSquareText aria-hidden="true" size={15} />}
                {stateLabel[thread.status]}
              </span>
            </header>
            <p className="clarification-reason"><strong>Why this is needed:</strong> {thread.reason}</p>
            <p className="clarification-deadline"><CalendarClock aria-hidden="true" size={15} />Response requested by {formatDate(thread.responseDeadline)}</p>
            <ol className="clarification-messages">
              {thread.messages.map((message) => (
                <li key={message.id}>
                  <div><strong>{message.actorDisplayName}</strong><span>{message.kind === "REQUEST" ? "Asked" : message.kind === "RESPONSE" ? "Responded" : "Withdrew"}</span></div>
                  <p>{message.body}</p>
                  <time dateTime={message.createdAt}>{formatDate(message.createdAt, true)}</time>
                </li>
              ))}
            </ol>
          </article>
        ))}
      </div>
    </section>
  );
}
