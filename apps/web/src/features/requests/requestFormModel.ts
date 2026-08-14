import { z } from "zod";

import type { RequestDraftInput } from "../../lib/api/types";
import { localDateInputValue } from "../../lib/dateInputs";

export const requestToday = () => localDateInputValue(new Date());
const requiredText = (minimum: number, message: string, maximum: number) =>
  z.string().trim().min(minimum, message).max(maximum);

export const requestFormSchema = z
  .object({
    title: requiredText(3, "Enter a clear request title.", 160),
    description: requiredText(20, "Describe the need in at least 20 characters.", 5000),
    questionToAnswer: requiredText(10, "State the specific question to answer.", 2000),
    desiredOutcome: requiredText(10, "Describe the desired outcome.", 2000),
    backgroundContext: requiredText(1, "Add the known background and context.", 5000),
    subjectAreaOrLocation: requiredText(2, "Define the subject area or location.", 1000),
    coverageStart: z.string().min(1, "Choose the start of the relevant period."),
    coverageEnd: z.string().min(1, "Choose the end of the relevant period."),
    customerUrgency: z.enum(["ROUTINE", "TIME_SENSITIVE", "IMMEDIATE"]),
    supportedActivityOrDecision: requiredText(
      5,
      "Explain the activity or decision this will support.",
      2000,
    ),
    requiredBy: z
      .string()
      .min(1, "Choose a required-by date.")
      .refine((value) => value >= requestToday(), "The required-by date cannot be in the past."),
    requiredByReason: requiredText(
      5,
      "Explain why this date matters and the impact of delay.",
      1000,
    ),
    preferredDeliverableType: requiredText(2, "Choose a product type.", 80),
    successCriteria: requiredText(5, "Describe how success will be assessed.", 2000),
    constraintsOrCaveats: requiredText(1, "Add constraints or state that none are known.", 2000),
    supportingInformation: requiredText(
      1,
      "Describe supporting material or state that none is available.",
      2000,
    ),
    sensitivity: z.enum(["STANDARD", "SENSITIVE", "RESTRICTED"]),
    handlingInstructions: requiredText(
      1,
      "Add handling instructions, or state that standard handling applies.",
      2000,
    ),
  })
  .refine(coverageWindowIsValid, {
    message: "The end cannot be before the start.",
    path: ["coverageEnd"],
  });

function coverageWindowIsValid(values: { coverageEnd: string; coverageStart: string }) {
  if (!values.coverageStart || !values.coverageEnd) return true;
  return values.coverageEnd >= values.coverageStart;
}

export type RequestFormValues = z.infer<typeof requestFormSchema>;

export const requestTextLimits: Partial<Record<keyof RequestFormValues, number>> = {
  title: 160,
  description: 5000,
  questionToAnswer: 2000,
  desiredOutcome: 2000,
  backgroundContext: 5000,
  subjectAreaOrLocation: 1000,
  supportedActivityOrDecision: 2000,
  requiredByReason: 1000,
  successCriteria: 2000,
  constraintsOrCaveats: 2000,
  supportingInformation: 2000,
  handlingInstructions: 2000,
};

export type RequestSectionDefinition = {
  description: string;
  fields: readonly (keyof RequestFormValues)[];
  id: string;
  title: string;
};

export const requestFormSections: readonly RequestSectionDefinition[] = [
  {
    description:
      "Describe the need in plain language. Internal teams and routes are selected later.",
    fields: ["title", "description", "questionToAnswer", "desiredOutcome", "backgroundContext"],
    id: "need",
    title: "The need",
  },
  {
    description: "Define what the work should cover and what it will support.",
    fields: [
      "subjectAreaOrLocation",
      "coverageStart",
      "coverageEnd",
      "supportedActivityOrDecision",
    ],
    id: "scope",
    title: "Scope and purpose",
  },
  {
    description: "Set urgency, timing, format and the measure of success.",
    fields: [
      "customerUrgency",
      "requiredBy",
      "preferredDeliverableType",
      "requiredByReason",
      "successCriteria",
    ],
    id: "expectations",
    title: "Product expectations",
  },
  {
    description: "Record caveats, available material and any handling needs.",
    fields: [
      "constraintsOrCaveats",
      "supportingInformation",
      "sensitivity",
      "handlingInstructions",
    ],
    id: "handling",
    title: "Supporting information and handling",
  },
];

export const requestFieldLabels: Record<keyof RequestFormValues, string> = {
  title: "Request title",
  description: "Description of the need",
  questionToAnswer: "Specific question to answer",
  desiredOutcome: "Desired outcome",
  backgroundContext: "Background and known context",
  subjectAreaOrLocation: "Subject area or location",
  coverageStart: "Relevant period starts",
  coverageEnd: "Relevant period ends",
  customerUrgency: "Customer urgency",
  supportedActivityOrDecision: "Activity, project or decision supported",
  requiredBy: "Latest useful delivery date",
  requiredByReason: "Why this date matters and impact if late",
  preferredDeliverableType: "Preferred product type",
  successCriteria: "Success criteria",
  constraintsOrCaveats: "Constraints or caveats",
  supportingInformation: "Supporting information available",
  sensitivity: "Sensitivity",
  handlingInstructions: "Handling instructions",
};

const emptyRequestForm: RequestFormValues = {
  title: "",
  description: "",
  questionToAnswer: "",
  desiredOutcome: "",
  backgroundContext: "",
  subjectAreaOrLocation: "",
  coverageStart: "",
  coverageEnd: "",
  customerUrgency: "ROUTINE",
  supportedActivityOrDecision: "",
  requiredBy: "",
  requiredByReason: "",
  preferredDeliverableType: "",
  successCriteria: "",
  constraintsOrCaveats: "",
  supportingInformation: "",
  sensitivity: "STANDARD",
  handlingInstructions: "",
};

export function requestFormDefaults(draft?: RequestDraftInput): RequestFormValues {
  const values = draft ?? emptyRequestForm;
  return {
    title: valueOr(values.title, emptyRequestForm.title),
    description: valueOr(values.description, emptyRequestForm.description),
    questionToAnswer: valueOr(values.questionToAnswer, emptyRequestForm.questionToAnswer),
    desiredOutcome: valueOr(values.desiredOutcome, emptyRequestForm.desiredOutcome),
    backgroundContext: valueOr(values.backgroundContext, emptyRequestForm.backgroundContext),
    subjectAreaOrLocation: valueOr(
      values.subjectAreaOrLocation,
      emptyRequestForm.subjectAreaOrLocation,
    ),
    coverageStart: valueOr(values.coverageStart, emptyRequestForm.coverageStart),
    coverageEnd: valueOr(values.coverageEnd, emptyRequestForm.coverageEnd),
    customerUrgency: valueOr(values.customerUrgency, emptyRequestForm.customerUrgency),
    supportedActivityOrDecision: valueOr(
      values.supportedActivityOrDecision,
      emptyRequestForm.supportedActivityOrDecision,
    ),
    requiredBy: valueOr(values.requiredBy, emptyRequestForm.requiredBy),
    requiredByReason: valueOr(values.requiredByReason, emptyRequestForm.requiredByReason),
    preferredDeliverableType: valueOr(
      values.preferredDeliverableType,
      emptyRequestForm.preferredDeliverableType,
    ),
    successCriteria: valueOr(values.successCriteria, emptyRequestForm.successCriteria),
    constraintsOrCaveats: valueOr(
      values.constraintsOrCaveats,
      emptyRequestForm.constraintsOrCaveats,
    ),
    supportingInformation: valueOr(
      values.supportingInformation,
      emptyRequestForm.supportingInformation,
    ),
    sensitivity: valueOr(values.sensitivity, emptyRequestForm.sensitivity),
    handlingInstructions: valueOr(
      values.handlingInstructions,
      emptyRequestForm.handlingInstructions,
    ),
  };
}

function valueOr<Value>(value: Value | null | undefined, fallback: Value): Value {
  return value ?? fallback;
}

export function invalidRequestFields(values: RequestFormValues) {
  const parsed = requestFormSchema.safeParse(values);
  return new Set(parsed.success ? [] : parsed.error.issues.map((issue) => String(issue.path[0])));
}

export function incompleteFields(
  section: RequestSectionDefinition,
  invalidFields: ReadonlySet<string>,
) {
  return section.fields.filter((name) => invalidFields.has(name)).length;
}
