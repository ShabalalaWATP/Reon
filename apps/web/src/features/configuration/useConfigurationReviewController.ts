import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { configurationApi } from "../../lib/api/configurationClient";
import type { ConfigurationVersion } from "../../lib/api/configurationTypes";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";

export type ConfigurationReviewAction = "validate" | "submit" | "approve" | "reject" | "activate";

export function useConfigurationReviewController(
  version: ConfigurationVersion,
  onChanged: () => Promise<unknown>,
) {
  const { session } = useAuth();
  const [reason, setReason] = useState("");
  const elevated = isSessionElevated(session);
  const independent = session!.user.id !== version.createdByUserId;
  const next = nextActions(version);
  const action = useMutation({
    mutationFn: (name: ConfigurationReviewAction) =>
      runAction(name, version, reason, session!.csrfToken),
    onSuccess: async () => {
      setReason("");
      await onChanged();
    },
  });

  return {
    action,
    canRun: (name: ConfigurationReviewAction) => canRun(name, elevated, independent, reason),
    elevated,
    independent,
    needsReason: next.some((name) => name !== "validate"),
    next,
    reason,
    setReason,
  };
}

function nextActions(version: ConfigurationVersion): ConfigurationReviewAction[] {
  if (version.status === "DRAFT") return ["validate"];
  if (version.status === "VALIDATED") return ["submit"];
  if (version.status === "AWAITING_APPROVAL" && !version.approval) return ["approve", "reject"];
  if (version.status === "AWAITING_APPROVAL" && version.approval?.decision === "APPROVED")
    return ["activate"];
  return [];
}

function canRun(
  action: ConfigurationReviewAction,
  elevated: boolean,
  independent: boolean,
  reason: string,
) {
  if (!elevated) return false;
  if ((action === "approve" || action === "reject") && !independent) return false;
  return action === "validate" || reason.trim().length >= 10;
}

function runAction(
  action: ConfigurationReviewAction,
  version: ConfigurationVersion,
  reason: string,
  csrfToken: string,
) {
  const base = { expectedVersion: version.version };
  if (action === "validate") return configurationApi.validate(version.id, base, csrfToken);
  const review = { ...base, reason: reason.trim() };
  if (action === "submit") return configurationApi.submit(version.id, review, csrfToken);
  if (action === "approve") return configurationApi.approve(version.id, review, csrfToken);
  if (action === "reject") return configurationApi.reject(version.id, review, csrfToken);
  return configurationApi.activate(version.id, review, csrfToken);
}
