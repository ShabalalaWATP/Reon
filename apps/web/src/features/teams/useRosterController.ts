import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  EligibleRosterAnalyst,
  TeamMember,
  TeamWorkspaceAccess,
} from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { canManageRoster } from "./peopleSorting";

export type RosterMode = "add" | "transfer";

export function useRosterController(access: TeamWorkspaceAccess) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const client = useQueryClient();
  const [mode, setModeState] = useState<RosterMode>("add");
  const [selectedId, setSelectedId] = useState("");
  const [reason, setReason] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const canManage = canManageRoster(access);
  const people = useQuery({
    queryKey: queryKeys.teamPeople(access.teamId),
    queryFn: () => api.teamPeople(access.teamId),
  });
  const eligible = useQuery({
    queryKey: queryKeys.teamEligibleAnalysts(access.teamId),
    queryFn: () => api.eligibleRosterAnalysts(access.teamId, access.grantId ?? ""),
    enabled: canManage,
  });
  const mutation = useMutation({
    mutationFn: () =>
      saveRosterChange({
        access,
        effectiveFrom,
        eligible: eligible.data?.items ?? [],
        mode,
        reason,
        selectedId,
        session,
      }),
    onSuccess: (data) => {
      client.setQueryData(queryKeys.teamPeople(access.teamId), data);
      setSelectedId("");
      setReason("");
      setEffectiveFrom("");
      void client.invalidateQueries({ queryKey: queryKeys.teamEligibleAnalysts(access.teamId) });
    },
  });
  return {
    canManage,
    effectiveFrom,
    eligibleError: eligible.isError,
    eligiblePending: eligible.isPending,
    error: mutation.isError ? rosterErrorMessage(mutation.error) : undefined,
    mode,
    options: rosterOptions(eligible.data?.items ?? [], mode, access.teamId),
    people: people.data?.items ?? [],
    peopleError: people.isError,
    peoplePending: people.isPending,
    reason,
    refetchEligible: () => void eligible.refetch(),
    refetchPeople: () => void people.refetch(),
    saving: mutation.isPending,
    selectedId,
    setEffectiveFrom,
    setMode: (nextMode: RosterMode) => {
      setModeState(nextMode);
      setSelectedId("");
    },
    setReason,
    setSelectedId,
    submit: () => mutation.mutate(),
  };
}

export function useEndMembershipController(access: TeamWorkspaceAccess, member: TeamMember) {
  const { session } = useAuth();
  const client = useQueryClient();
  const queryKeys = protectedQueryKeys(session);
  const [ending, setEnding] = useState(false);
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      api.endTeamMembership(
        access.teamId,
        member.membershipId,
        { grantId: access.grantId ?? "", expectedVersion: member.version, reason },
        session?.csrfToken ?? "",
      ),
    onSuccess: (data) => {
      client.setQueryData(queryKeys.teamPeople(access.teamId), data);
      setEnding(false);
    },
  });
  return {
    ending,
    error: mutation.isError ? rosterErrorMessage(mutation.error) : undefined,
    reason,
    saving: mutation.isPending,
    setEnding,
    setReason,
    submit: () => mutation.mutate(),
  };
}

type SaveRosterInput = {
  access: TeamWorkspaceAccess;
  effectiveFrom: string;
  eligible: EligibleRosterAnalyst[];
  mode: RosterMode;
  reason: string;
  selectedId: string;
  session: ReturnType<typeof useAuth>["session"];
};

async function saveRosterChange(input: SaveRosterInput) {
  const analyst = input.eligible.find((item) => item.accountId === input.selectedId);
  if (!input.session || !analyst || !input.access.grantId)
    throw new Error("Select a compatible Member.");
  if (input.mode === "add") {
    return api.addTeamMember(
      input.access.teamId,
      {
        analystId: analyst.accountId,
        grantId: input.access.grantId,
        reason: input.reason,
      },
      input.session.csrfToken,
    );
  }
  assertTransferDetails(analyst, input.effectiveFrom);
  return api.transferTeamMember(
    input.access.teamId,
    {
      analystId: analyst.accountId,
      currentMembershipId: analyst.currentMembershipId,
      effectiveFrom: new Date(input.effectiveFrom).toISOString(),
      expectedVersion: analyst.currentMembershipVersion,
      grantId: input.access.grantId,
      reason: input.reason,
    },
    input.session.csrfToken,
  );
}

function assertTransferDetails(
  analyst: EligibleRosterAnalyst,
  effectiveFrom: string,
): asserts analyst is EligibleRosterAnalyst & {
  currentMembershipId: string;
  currentMembershipVersion: number;
} {
  if (!analyst.currentMembershipId || analyst.currentMembershipVersion === null || !effectiveFrom) {
    throw new Error("Complete the transfer details.");
  }
}

function rosterOptions(items: EligibleRosterAnalyst[], mode: RosterMode, teamId: string) {
  if (mode === "add") return items.filter((item) => item.currentTeamId === null);
  return items.filter((item) => item.currentTeamId !== null && item.currentTeamId !== teamId);
}

function rosterErrorMessage(error: Error) {
  return error instanceof ApiError
    ? error.message
    : error.message || "The roster change could not be saved.";
}

export function localRosterDateMinimum() {
  const value = new Date(Date.now() + 60_000);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}
