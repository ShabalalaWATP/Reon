import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import {
  executeCalendarMutation,
  initialOccurrenceDraft,
  type CalendarMutationCommand,
  type CalendarOccurrenceAction,
  type CalendarOccurrenceDraft,
} from "./calendarOccurrenceModel";

export function useCalendarOccurrence({
  canManage,
  item,
  onClose,
  queryKey,
}: {
  canManage: boolean;
  item: CalendarOccurrence;
  onClose: () => void;
  queryKey: readonly unknown[];
}) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => initialOccurrenceDraft(item));
  const ownsEvent = session?.user.id === item.subjectUserId && item.kind === "PERSONAL";
  const canChange = ownsEvent || (canManage && item.kind !== "PERSONAL");
  const pendingCommitment =
    session?.user.id === item.subjectUserId &&
    item.kind === "COMMITMENT" &&
    item.commitmentStatus === "PENDING";
  const mutation = useMutation({
    mutationFn: (command: CalendarMutationCommand) => {
      if (!session) throw new Error("Sign in is required.");
      return executeCalendarMutation(command, draft, item, session.csrfToken);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey });
      onClose();
    },
  });
  const update = <Key extends keyof CalendarOccurrenceDraft>(
    key: Key,
    value: CalendarOccurrenceDraft[Key],
  ) => setDraft((current) => ({ ...current, [key]: value }));
  const selectAction = (action: CalendarOccurrenceAction) => update("action", action);

  return {
    acknowledge: () => mutation.mutate({ acknowledge: true, type: "commitment" }),
    canChange,
    draft,
    mutation,
    pendingCommitment,
    selectAction,
    submit: () =>
      mutation.mutate(
        draft.action === "dispute" ? { acknowledge: false, type: "commitment" } : { type: "event" },
      ),
    update,
  };
}
