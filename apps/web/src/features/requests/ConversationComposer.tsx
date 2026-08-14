import { useEffect, useRef, useState } from "react";

import type { ConversationMessageInput, ConversationTarget } from "../../lib/api/types";
import type { ReplySelection } from "./ConversationTimeline";

type Props = {
  error: Error | null;
  isSending: boolean;
  onCancelReply: () => void;
  onSend: (input: ConversationMessageInput) => Promise<void>;
  reply: ReplySelection | null;
  targets: ConversationTarget[];
};

export function ConversationComposer({
  error,
  isSending,
  onCancelReply,
  onSend,
  reply,
  targets,
}: Props) {
  const [body, setBody] = useState("");
  const [subject, setSubject] = useState("");
  const [targetKey, setTargetKey] = useState(targetValue(targets[0]));
  const mutationId = useRef(globalThis.crypto.randomUUID());
  const target = targets.find((candidate) => targetValue(candidate) === targetKey) ?? targets[0];

  useEffect(() => {
    if (!targets.some((candidate) => targetValue(candidate) === targetKey)) {
      setTargetKey(targetValue(targets[0]));
    }
  }, [targetKey, targets]);

  const submit = async () => {
    const trimmed = body.trim();
    if (!reply && !target) return;
    try {
      if (reply) {
        await onSend({
          body: trimmed,
          clientMutationId: mutationId.current,
          conversationId: reply.conversation.id,
          replyToMessageId: reply.message.id,
        });
      } else {
        await onSend({
          body: trimmed,
          clientMutationId: mutationId.current,
          subject: subject.trim() || undefined,
          targetType: target.type,
          targetUnitId: target.unitId ?? undefined,
        });
      }
    } catch {
      return;
    }
    setBody("");
    setSubject("");
    mutationId.current = globalThis.crypto.randomUUID();
    onCancelReply();
  };

  if (!reply && targets.length === 0) {
    return (
      <p className="conversation-compose-unavailable">
        No authorised message destinations are available at this stage.
      </p>
    );
  }
  return (
    <form
      className="conversation-compose"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {reply ? (
        <div className="conversation-reply-context">
          <span>Replying in {reply.conversation.subject}</span>
          <strong>
            {reply.message.senderDisplayName}: {reply.message.body}
          </strong>
          <button className="conversation-reply" onClick={onCancelReply} type="button">
            Cancel reply
          </button>
        </div>
      ) : (
        <>
          <label className="form-field">
            <span>Send to</span>
            <select
              disabled={isSending}
              onChange={(event) => setTargetKey(event.target.value)}
              value={targetKey}
            >
              {targets.map((candidate) => (
                <option key={targetValue(candidate)} value={targetValue(candidate)}>
                  {candidate.label}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>
              Subject <small>(optional)</small>
            </span>
            <input
              disabled={isSending}
              maxLength={160}
              onChange={(event) => setSubject(event.target.value)}
              value={subject}
            />
          </label>
        </>
      )}
      <label className="form-field">
        <span>{reply ? "Reply" : "Message"}</span>
        <textarea
          disabled={isSending}
          maxLength={2000}
          minLength={3}
          onChange={(event) => setBody(event.target.value)}
          required
          rows={4}
          value={body}
        />
      </label>
      <button
        className="button button--primary"
        disabled={isSending || (!reply && !target)}
        type="submit"
      >
        {isSending ? "Sending…" : reply ? "Send reply" : "Send message"}
      </button>
      {error ? (
        <p className="form-banner form-banner--error" role="alert">
          {error.message}
        </p>
      ) : null}
    </form>
  );
}

function targetValue(target?: ConversationTarget) {
  return target ? `${target.type}:${target.unitId ?? ""}` : "";
}
