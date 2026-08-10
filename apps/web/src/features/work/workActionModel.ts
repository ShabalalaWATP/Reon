import { z } from "zod";

import type { WorkAction } from "../../lib/api/types";

export type WorkActionName = WorkAction["action"];
export type WorkActionValues = {
  action: WorkActionName;
  reason?: string;
  note?: string;
  priority?: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
  destinationUnitId?: string;
  requiredCapabilities?: string;
  specialistId?: string;
  contributorIds?: string[];
  deliverableTitle?: string;
  deliverableText?: string;
  information?: string;
  question?: string;
  responseDeadline?: string;
  threadId?: string;
  expectedVersion?: number;
  recipients?: string;
};

const reasonActions: WorkActionName[] = [
  "request_information",
  "close",
  "withdraw",
  "return_to_triage",
  "hold",
  "return_to_coordination",
  "return_for_reallocation",
  "changes_required",
];

export const workActionSchema = z.object({
  action: z.enum([
    "request_information",
    "progress",
    "close",
    "provide_information",
    "withdraw",
    "send_to_allocation",
    "return_to_triage",
    "hold",
    "resume",
    "allocate",
    "return_to_coordination",
    "assign",
    "return_for_reallocation",
    "submit",
    "request_clarification",
    "provide_clarification",
    "approve",
    "changes_required",
    "release",
  ]),
  reason: z.string().optional(),
  note: z.string().optional(),
  priority: z.enum(["LOW", "MEDIUM", "HIGH", "URGENT"], { error: "Choose a priority." }).optional(),
  destinationUnitId: z.string().optional(),
  requiredCapabilities: z.string().optional(),
  specialistId: z.string().optional(),
  contributorIds: z.array(z.string()).max(10).optional(),
  deliverableTitle: z.string().optional(),
  deliverableText: z.string().optional(),
  information: z.string().optional(),
  question: z.string().optional(),
  responseDeadline: z.string().optional(),
  threadId: z.string().optional(),
  expectedVersion: z.number().int().positive().optional(),
  recipients: z.string().optional(),
}).superRefine((values, context) => {
  const required = (field: keyof WorkActionValues, message: string) => {
    if (!String(values[field] ?? "").trim()) context.addIssue({ code: "custom", message, path: [field] });
  };
  const action = values.action as WorkActionName;
  if (reasonActions.includes(action)) required("reason", "Explain this decision.");
  if (action === "progress") {
    required("destinationUnitId", "Choose a destination unit.");
    required("priority", "Choose a priority.");
  }
  if (action === "send_to_allocation") {
    required("destinationUnitId", "Choose a destination unit.");
    required("note", "Explain this routing decision.");
  }
  if (action === "resume") required("note", "Explain why work is resuming.");
  if (action === "allocate") {
    required("destinationUnitId", "Choose a destination unit.");
    required("requiredCapabilities", "Add at least one required capability.");
  }
  if (action === "assign") {
    required("specialistId", "Choose a Lead Analyst.");
    if ((values.reason?.trim().length ?? 0) < 10) {
      context.addIssue({ code: "custom", message: "Give an assignment reason of at least 10 characters.", path: ["reason"] });
    }
    if (values.contributorIds?.includes(values.specialistId ?? "")) {
      context.addIssue({ code: "custom", message: "The Lead cannot also be a Contributor.", path: ["contributorIds"] });
    }
  }
  if (action === "submit") {
    required("deliverableTitle", "Enter a product title.");
    required("deliverableText", "Enter the product text.");
  }
  if (action === "provide_information") required("information", "Provide the requested information.");
  if (action === "request_clarification") {
    required("question", "Enter the question for the Customer.");
    required("reason", "Explain why the information is needed.");
    required("responseDeadline", "Choose a response deadline.");
  }
  if (action === "provide_clarification") {
    required("information", "Provide the requested information.");
    required("threadId", "The clarification record is unavailable.");
    if (!values.expectedVersion) context.addIssue({ code: "custom", message: "The clarification record is unavailable.", path: ["expectedVersion"] });
  }
  if (action === "release") required("recipients", "Add at least one dissemination recipient.");
});

export const actionLabels: Record<WorkActionName, string> = {
  request_information: "Request more information",
  progress: "Route to command",
  close: "Close without production",
  provide_information: "Provide information",
  withdraw: "Withdraw request",
  send_to_allocation: "Route to Ops group",
  return_to_triage: "Return to JIOC",
  hold: "Place on hold",
  resume: "Resume command routing",
  allocate: "Route to team",
  return_to_coordination: "Return to command routing",
  assign: "Assign Analysts",
  return_for_reallocation: "Return to Ops routing",
  submit: "Submit product",
  request_clarification: "Ask Customer for information",
  provide_clarification: "Send information to Analyst",
  approve: "Approve",
  changes_required: "Require changes",
  release: "Disseminate to customer",
};

const destinationActions: WorkActionName[] = [
  "progress",
  "send_to_allocation",
  "allocate",
];

export function actionRequiresDestination(action?: WorkActionName) {
  return action !== undefined && destinationActions.includes(action);
}

const lines = (value?: string) => value?.split("\n").map((item) => item.trim()).filter(Boolean) ?? [];

export function buildWorkAction(values: WorkActionValues): WorkAction {
  switch (values.action) {
    case "request_information": return { action: values.action, reason: values.reason! };
    case "progress": return { action: values.action, destinationUnitId: values.destinationUnitId!, priority: values.priority! };
    case "close": return { action: values.action, reason: values.reason! };
    case "provide_information": return { action: values.action, information: values.information! };
    case "withdraw": return { action: values.action, reason: values.reason! };
    case "send_to_allocation": return { action: values.action, destinationUnitId: values.destinationUnitId!, note: values.note! };
    case "return_to_triage": return { action: values.action, reason: values.reason! };
    case "hold": return { action: values.action, reason: values.reason! };
    case "resume": return { action: values.action, note: values.note! };
    case "allocate": return { action: values.action, destinationUnitId: values.destinationUnitId!, requiredCapabilities: lines(values.requiredCapabilities) };
    case "return_to_coordination": return { action: values.action, reason: values.reason! };
    case "assign": return { action: values.action, specialistId: values.specialistId!, contributorIds: values.contributorIds ?? [], reason: values.reason! };
    case "return_for_reallocation": return { action: values.action, reason: values.reason! };
    case "submit": return { action: values.action, deliverableTitle: values.deliverableTitle!, deliverableText: values.deliverableText! };
    case "request_clarification": return { action: values.action, question: values.question!, reason: values.reason!, responseDeadline: values.responseDeadline! };
    case "provide_clarification": return { action: values.action, threadId: values.threadId!, expectedVersion: values.expectedVersion!, information: values.information! };
    case "approve": return { action: values.action };
    case "changes_required": return { action: values.action, reason: values.reason! };
    case "release": return { action: values.action, recipients: lines(values.recipients) };
  }
}
