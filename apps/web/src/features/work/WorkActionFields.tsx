import type { ComponentType } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import {
  AllocateFields,
  AssignmentFields,
  EmptyActionFields,
  InformationFields,
  ProgressFields,
  ProvideClarificationFields,
  ReasonFields,
  ReleaseFields,
  RequestClarificationFields,
  ResumeFields,
  SendToAllocationFields,
  SubmitFields,
  type WorkActionFieldGroupProps,
} from "./WorkActionFieldGroups";
import type { WorkActionName, WorkActionValues } from "./workActionModel";

type Props = {
  action: WorkActionName;
  contributorIds: string[];
  destinationUnitId?: string;
  errors: FieldErrors<WorkActionValues>;
  managedProducts: boolean;
  register: UseFormRegister<WorkActionValues>;
  routingOptions: RoutingOptions;
  specialistId?: string;
  specialistOptions: SpecialistOptions;
};

const actionFieldGroups: Record<WorkActionName, ComponentType<WorkActionFieldGroupProps>> = {
  request_information: ReasonFields,
  progress: ProgressFields,
  close: ReasonFields,
  provide_information: InformationFields,
  withdraw: ReasonFields,
  send_to_allocation: SendToAllocationFields,
  return_to_triage: ReasonFields,
  hold: ReasonFields,
  resume: ResumeFields,
  allocate: AllocateFields,
  return_to_coordination: ReasonFields,
  assign: AssignmentFields,
  return_for_reallocation: ReasonFields,
  submit: SubmitFields,
  request_clarification: RequestClarificationFields,
  provide_clarification: ProvideClarificationFields,
  approve: EmptyActionFields,
  changes_required: ReasonFields,
  release: ReleaseFields,
};

export function WorkActionFields({ action, ...props }: Props) {
  const FieldGroup = actionFieldGroups[action];
  return <FieldGroup {...props} />;
}
