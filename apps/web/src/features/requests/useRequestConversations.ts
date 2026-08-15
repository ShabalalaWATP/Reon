import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  ConversationMessageInput,
  ConversationWorkspace,
  RequestStatus,
} from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { conversationPollInterval } from "./requestPolling";
import {
  conversationsForView,
  markConversationRead,
  mergeWorkspacePage,
  normaliseWorkspace,
  replaceConversation,
  targetsForView,
  unreadWatermark,
  type ConversationView,
} from "./conversationWorkspaceModel";

export function useRequestConversations(
  requestId: string,
  view: ConversationView,
  writesEnabled = true,
  status?: RequestStatus,
) {
  const { session } = useAuth();
  const client = useQueryClient();
  const queryKeys = useMemo(() => protectedQueryKeys(session), [session]);
  const key = useMemo(() => queryKeys.conversations(requestId), [queryKeys, requestId]);
  const customer = session?.user.role === "REQUESTER";
  const [readErrorIds, setReadErrorIds] = useState<ReadonlySet<string>>(new Set());
  const readAttempts = useRef(new Map<string, string>());
  const query = useQuery({
    queryKey: key,
    queryFn: () => api.requestConversations(requestId),
    enabled: Boolean(session),
    refetchInterval: conversationPollInterval(status),
  });
  const mutation = useMutation({
    mutationKey: [...key, "send"],
    mutationFn: (input: ConversationMessageInput) => {
      if (!session || !writesEnabled) throw new Error("Messaging is not available.");
      return api.postConversationMessage(requestId, input, session.csrfToken);
    },
    onSuccess: async ({ conversation }) => {
      client.setQueryData<ConversationWorkspace>(key, (current) => {
        const workspace = normaliseWorkspace(current);
        return {
          ...workspace,
          conversations: replaceConversation(workspace.conversations, conversation, true),
        };
      });
      await Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.request(requestId) }),
        client.invalidateQueries({ queryKey: queryKeys.trackedRequest(requestId) }),
      ]);
    },
  });
  const conversationPage = useMutation({
    mutationKey: [...key, "conversation-page"],
    mutationFn: (cursor: string) => api.requestConversations(requestId, cursor),
    onSuccess: (page) =>
      client.setQueryData<ConversationWorkspace>(key, (current) =>
        current ? mergeWorkspacePage(current, page) : page,
      ),
  });
  const messagePage = useMutation({
    mutationKey: [...key, "message-page"],
    mutationFn: ({ conversationId, cursor }: { conversationId: string; cursor: string }) =>
      api.conversationMessages(requestId, conversationId, cursor),
    onSuccess: (page) =>
      client.setQueryData<ConversationWorkspace>(key, (current) => {
        const workspace = normaliseWorkspace(current);
        return {
          ...workspace,
          conversations: replaceConversation(workspace.conversations, page, false),
        };
      }),
  });
  const markRead = useCallback(
    async (conversationId: string, watermark: string) => {
      if (!session || !writesEnabled) return;
      try {
        await api.markConversationRead(requestId, conversationId, session.csrfToken);
        setReadErrorIds((current) => withoutId(current, conversationId));
        client.setQueryData<ConversationWorkspace>(key, (current) =>
          markConversationRead(current, conversationId),
        );
      } catch {
        if (readAttempts.current.get(conversationId) === watermark) {
          setReadErrorIds((current) => new Set(current).add(conversationId));
        }
      }
    },
    [client, key, requestId, session, writesEnabled],
  );
  const workspace = useMemo(() => normaliseWorkspace(query.data), [query.data]);
  const visibleConversations = useMemo(
    () => conversationsForView(workspace, customer, view),
    [customer, view, workspace],
  );
  const visibleWatermarks = useMemo(
    () =>
      visibleConversations
        .map((conversation) => [conversation.id, unreadWatermark(conversation)] as const)
        .filter((entry): entry is readonly [string, string] => entry[1] !== null),
    [visibleConversations],
  );

  useEffect(() => {
    visibleWatermarks.forEach(([conversationId, watermark]) => {
      if (!writesEnabled || readAttempts.current.get(conversationId) === watermark) return;
      readAttempts.current.set(conversationId, watermark);
      void markRead(conversationId, watermark);
    });
  }, [markRead, visibleWatermarks, writesEnabled]);

  return {
    conversationPage,
    customer,
    markReadAgain: (conversationId: string) => {
      const conversation = workspace.conversations.find(
        (candidate) => candidate.id === conversationId,
      );
      const watermark = conversation ? unreadWatermark(conversation) : null;
      if (!watermark) return;
      readAttempts.current.delete(conversationId);
      readAttempts.current.set(conversationId, watermark);
      void markRead(conversationId, watermark);
    },
    messagePage,
    mutation,
    query,
    readErrorIds,
    targets: targetsForView(workspace, customer, view),
    visibleConversations,
    workspace,
  };
}

function withoutId(current: ReadonlySet<string>, id: string) {
  const next = new Set(current);
  next.delete(id);
  return next;
}
