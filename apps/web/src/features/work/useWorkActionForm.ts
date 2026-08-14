import { zodResolver } from "@hookform/resolvers/zod";
import { type ChangeEvent, useEffect } from "react";
import { useForm } from "react-hook-form";

import type { ClarificationThread, WorkAction } from "../../lib/api/types";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import {
  actionRequiresDestination,
  buildWorkAction,
  workActionSchema,
  type WorkActionName,
  type WorkActionValues,
} from "./workActionModel";

type ControllerInput = {
  actions: WorkActionName[];
  clarification?: ClarificationThread;
  managedProducts: boolean;
  onActionChange?: (action: WorkActionName) => void;
  onSubmit: (action: WorkAction) => void;
  routingOptions: RoutingOptions;
  specialistOptions: SpecialistOptions;
};

function defaultValues(
  actions: WorkActionName[],
  clarification: ClarificationThread | undefined,
  managedProducts: boolean,
): WorkActionValues {
  return {
    action: actions[0],
    contributorIds: [],
    expectedVersion: clarification?.version,
    managedProduct: managedProducts,
    threadId: clarification?.id,
  };
}

function actionUnavailable(
  action: WorkActionName,
  clarification: ClarificationThread | undefined,
  routingOptions: RoutingOptions,
  specialistOptions: SpecialistOptions,
) {
  const assignmentUnavailable =
    action === "assign" &&
    (specialistOptions.status !== "ready" || specialistOptions.items.length === 0);
  const routingUnavailable =
    actionRequiresDestination(action) &&
    (routingOptions.status !== "ready" || routingOptions.items.length === 0);
  const clarificationUnavailable =
    action === "provide_clarification" && clarification === undefined;
  return assignmentUnavailable || routingUnavailable || clarificationUnavailable;
}

export function useWorkActionForm(input: ControllerInput) {
  const form = useForm<WorkActionValues>({
    defaultValues: defaultValues(input.actions, input.clarification, input.managedProducts),
    resolver: zodResolver(workActionSchema),
  });
  const { register, reset, setValue, watch } = form;
  useEffect(
    () => reset(defaultValues(input.actions, input.clarification, input.managedProducts)),
    [input.actions, input.clarification, input.managedProducts, reset],
  );
  const action = watch("action") ?? input.actions[0];
  const contributorIds = watch("contributorIds");
  const destinationUnitId = watch("destinationUnitId");
  const specialistId = watch("specialistId");
  const actionField = register("action");

  useEffect(() => {
    if (!specialistId || !contributorIds?.includes(specialistId)) return;
    setValue(
      "contributorIds",
      contributorIds.filter((id) => id !== specialistId),
      { shouldDirty: true, shouldValidate: true },
    );
  }, [contributorIds, setValue, specialistId]);

  const changeAction = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextAction = event.currentTarget.value as WorkActionName;
    void actionField.onChange(event);
    input.onActionChange?.(nextAction);
  };
  const submit = form.handleSubmit((values) => input.onSubmit(buildWorkAction(values)));

  return {
    action,
    actionField,
    changeAction,
    contributorIds: contributorIds ?? [],
    destinationUnitId,
    errors: form.formState.errors,
    register,
    specialistId,
    submit,
    unavailable: actionUnavailable(
      action,
      input.clarification,
      input.routingOptions,
      input.specialistOptions,
    ),
  };
}
