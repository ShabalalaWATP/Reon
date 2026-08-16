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
  managedProduct?: boolean;
  deliverableTitle?: string;
  deliverableText?: string;
  information?: string;
  question?: string;
  responseDeadline?: string;
  threadId?: string;
  expectedVersion?: number;
  recipients?: string;
};

const reasonActions = new Set<WorkActionName>([
  "request_information",
  "close",
  "withdraw",
  "return_to_triage",
  "hold",
  "return_to_coordination",
  "return_for_reallocation",
  "changes_required",
]);

type ValidationContext = Parameters<Parameters<typeof workActionSchemaBase.superRefine>[0]>[1];

type ActionValidator = (values: WorkActionValues, context: ValidationContext) => void;

function requireField(
  values: WorkActionValues,
  context: ValidationContext,
  field: keyof WorkActionValues,
  message: string,
) {
  if (!String(values[field] ?? "").trim()) {
    context.addIssue({ code: "custom", message, path: [field] });
  }
}

function validateAssignment(values: WorkActionValues, context: ValidationContext) {
  requireField(values, context, "specialistId", "Choose a Lead Analyst.");
  if ((values.reason?.trim().length ?? 0) < 10) {
    context.addIssue({
      code: "custom",
      message: "Give an assignment reason of at least 10 characters.",
      path: ["reason"],
    });
  }
  if (values.contributorIds?.includes(values.specialistId ?? "")) {
    context.addIssue({
      code: "custom",
      message: "The Lead cannot also be a Contributor.",
      path: ["contributorIds"],
    });
  }
}

const actionValidators: Partial<Record<WorkActionName, ActionValidator>> = {
  progress: (values, context) => {
    requireField(values, context, "destinationUnitId", "Choose a destination unit.");
    requireField(values, context, "priority", "Choose a priority.");
    // The message is optional, but a supplied one must say something the
    // receiving command can act on, matching the API's minimum length.
    const note = values.note?.trim() ?? "";
    if (note && note.length < 3) {
      context.addIssue({
        code: "custom",
        message: "Add a fuller message, or leave it blank.",
        path: ["note"],
      });
    }
  },
  send_to_allocation: (values, context) => {
    requireField(values, context, "destinationUnitId", "Choose a destination unit.");
    requireField(values, context, "note", "Explain this routing decision.");
  },
  resume: (values, context) =>
    requireField(values, context, "note", "Explain why work is resuming."),
  allocate: (values, context) => {
    requireField(values, context, "destinationUnitId", "Choose a destination unit.");
    requireField(values, context, "requiredCapabilities", "Add at least one required capability.");
  },
  assign: validateAssignment,
  submit: (values, context) => {
    if (values.managedProduct) return;
    requireField(values, context, "deliverableTitle", "Enter a product title.");
    requireField(values, context, "deliverableText", "Enter the product text.");
  },
  provide_information: (values, context) =>
    requireField(values, context, "information", "Provide the requested information."),
  request_clarification: (values, context) => {
    requireField(values, context, "question", "Enter the question for the Customer.");
    requireField(values, context, "reason", "Explain why the information is needed.");
    requireField(values, context, "responseDeadline", "Choose a response deadline.");
  },
  provide_clarification: (values, context) => {
    requireField(values, context, "information", "Provide the requested information.");
    requireField(values, context, "threadId", "The clarification record is unavailable.");
    if (!values.expectedVersion) {
      context.addIssue({
        code: "custom",
        message: "The clarification record is unavailable.",
        path: ["expectedVersion"],
      });
    }
  },
  release: (values, context) => {
    if (!values.managedProduct) {
      requireField(values, context, "recipients", "Add at least one dissemination recipient.");
    }
  },
};

const workActionSchemaBase = z.object({
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
  managedProduct: z.boolean().optional(),
  deliverableTitle: z.string().optional(),
  deliverableText: z.string().optional(),
  information: z.string().optional(),
  question: z.string().optional(),
  responseDeadline: z.string().optional(),
  threadId: z.string().optional(),
  expectedVersion: z.number().int().positive().optional(),
  recipients: z.string().optional(),
});

export const workActionSchema = workActionSchemaBase.superRefine((values, context) => {
  const action = values.action as WorkActionName;
  if (reasonActions.has(action)) {
    requireField(values, context, "reason", "Explain this decision.");
  }
  actionValidators[action]?.(values, context);
});

export const actionLabels: Record<WorkActionName, string> = {
  request_information: "Request more information",
  progress: "Route to command",
  close: "Close without production",
  provide_information: "Provide information",
  withdraw: "Withdraw request",
  send_to_allocation: "Route to Ops group",
  return_to_triage: "Return to CRIOC",
  hold: "Place on hold",
  resume: "Resume request coordination",
  allocate: "Route to team",
  return_to_coordination: "Return for request coordination",
  assign: "Assign Analysts",
  return_for_reallocation: "Return to Ops routing",
  submit: "Submit product",
  request_clarification: "Ask Customer for information",
  provide_clarification: "Send information to Analyst",
  approve: "Approve",
  changes_required: "Require changes",
  release: "Disseminate to customer",
};

const destinationActions: WorkActionName[] = ["progress", "send_to_allocation", "allocate"];

export function actionRequiresDestination(action?: WorkActionName) {
  return action !== undefined && destinationActions.includes(action);
}

const lines = (value?: string) =>
  value
    ?.split("\n")
    .map((item) => item.trim())
    .filter(Boolean) ?? [];

type ActionBuilder = (values: WorkActionValues) => WorkAction;
const reasonAction =
  (action: WorkActionName): ActionBuilder =>
  (values) =>
    ({
      action,
      reason: values.reason!,
    }) as WorkAction;

const actionBuilders: Record<WorkActionName, ActionBuilder> = {
  request_information: reasonAction("request_information"),
  progress: (values) => ({
    action: "progress",
    destinationUnitId: values.destinationUnitId!,
    priority: values.priority!,
    // Optional: omitted entirely when blank so the API applies its default label.
    ...(values.note?.trim() ? { note: values.note.trim() } : {}),
  }),
  close: reasonAction("close"),
  provide_information: (values) => ({
    action: "provide_information",
    information: values.information!,
  }),
  withdraw: reasonAction("withdraw"),
  send_to_allocation: (values) => ({
    action: "send_to_allocation",
    destinationUnitId: values.destinationUnitId!,
    note: values.note!,
  }),
  return_to_triage: reasonAction("return_to_triage"),
  hold: reasonAction("hold"),
  resume: (values) => ({ action: "resume", note: values.note! }),
  allocate: (values) => ({
    action: "allocate",
    destinationUnitId: values.destinationUnitId!,
    requiredCapabilities: lines(values.requiredCapabilities),
  }),
  return_to_coordination: reasonAction("return_to_coordination"),
  assign: (values) => ({
    action: "assign",
    specialistId: values.specialistId!,
    contributorIds: values.contributorIds ?? [],
    reason: values.reason!,
  }),
  return_for_reallocation: reasonAction("return_for_reallocation"),
  submit: (values) =>
    values.managedProduct
      ? { action: "submit", managedProduct: true }
      : {
          action: "submit",
          deliverableTitle: values.deliverableTitle!,
          deliverableText: values.deliverableText!,
        },
  request_clarification: (values) => ({
    action: "request_clarification",
    question: values.question!,
    reason: values.reason!,
    responseDeadline: values.responseDeadline!,
  }),
  provide_clarification: (values) => ({
    action: "provide_clarification",
    threadId: values.threadId!,
    expectedVersion: values.expectedVersion!,
    information: values.information!,
  }),
  approve: () => ({ action: "approve" }),
  changes_required: reasonAction("changes_required"),
  release: (values) =>
    values.managedProduct
      ? { action: "release", managedProduct: true }
      : { action: "release", recipients: lines(values.recipients) },
};

export function buildWorkAction(values: WorkActionValues): WorkAction {
  return actionBuilders[values.action](values);
}
