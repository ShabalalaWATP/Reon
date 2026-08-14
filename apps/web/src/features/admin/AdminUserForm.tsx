import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type {
  AdminUser,
  AdminUserWriteInput,
  OrganisationUnit,
  UserRole,
} from "../../lib/api/types";
import { roleLabels } from "../../lib/routes";
import { editableRoles, membershipOptions, roleNeedsMembership } from "./adminUserModel";

const schema = z
  .object({
    displayName: z.string().trim().min(2, "Enter a display name.").max(120),
    email: z.string().trim().email("Enter a valid work email.").max(254),
    role: z.enum(editableRoles as [UserRole, ...UserRole[]]),
    scope: z.string().trim().min(1, "Enter a scope.").max(120),
    organisationUnitIds: z.array(z.string()),
    workspacePosition: z.enum(["MANAGER", "MEMBER"]).nullable(),
  })
  .superRefine((value, context) => {
    if (roleNeedsMembership(value.role) && value.organisationUnitIds.length === 0)
      context.addIssue({
        code: "custom",
        message: "Select at least one compatible organisation unit.",
        path: ["organisationUnitIds"],
      });
  });
type Values = z.infer<typeof schema>;

type Props = {
  disabled: boolean;
  onSubmit: (input: AdminUserWriteInput) => void;
  pending?: boolean;
  units: OrganisationUnit[];
  user?: AdminUser;
};

export function AdminUserForm({ disabled, onSubmit, pending = false, units, user }: Props) {
  const form = useAdminUserForm(units, user);
  return (
    <form
      className="admin-user-form"
      noValidate
      onSubmit={(event) => void form.handleSubmit(onSubmit)(event)}
    >
      <IdentityFields form={form} user={user} />
      <AccessFields form={form} />
      <MembershipFields form={form} />
      <div className="form-actions">
        <button className="button button--primary" disabled={disabled} type="submit">
          {pending ? "Saving…" : user ? "Save changes" : "Create user"}
        </button>
      </div>
    </form>
  );
}

function useAdminUserForm(units: OrganisationUnit[], user?: AdminUser) {
  const form = useForm<Values>({
    defaultValues: valuesFor(user),
    resolver: zodResolver(schema),
  });
  const { reset, setValue, watch } = form;
  useEffect(() => reset(valuesFor(user)), [reset, user]);
  const role = watch("role");
  const selected = watch("organisationUnitIds");
  const options = useMemo(() => membershipOptions(role, units), [role, units]);
  useEffect(() => {
    setWorkspacePosition(role, watch("workspacePosition"), setValue);
  }, [role, setValue, watch]);
  useEffect(() => {
    const compatible = new Set(options.map((unit) => unit.id));
    const next = selected.filter((id) => compatible.has(id));
    if (next.length !== selected.length)
      setValue("organisationUnitIds", next, { shouldValidate: true });
  }, [options, selected, setValue]);
  return { ...form, options, role };
}

type FormController = ReturnType<typeof useAdminUserForm>;

function IdentityFields({ form, user }: { form: FormController; user?: AdminUser }) {
  const { errors } = form.formState;
  return (
    <fieldset>
      <legend>Identity</legend>
      <label className="form-field">
        <span>Username</span>
        <input readOnly value={user?.username ?? "Assigned after creation"} />
      </label>
      <label className="form-field">
        <span>Name</span>
        <input aria-invalid={Boolean(errors.displayName)} {...form.register("displayName")} />
        {errors.displayName ? <small role="alert">{errors.displayName.message}</small> : null}
      </label>
      <label className="form-field">
        <span>Work email</span>
        <input
          aria-invalid={Boolean(errors.email)}
          autoComplete="email"
          type="email"
          {...form.register("email")}
        />
        {errors.email ? <small role="alert">{errors.email.message}</small> : null}
      </label>
    </fieldset>
  );
}

function AccessFields({ form }: { form: FormController }) {
  const { errors } = form.formState;
  return (
    <fieldset>
      <legend>Access</legend>
      <label className="form-field">
        <span>Representative role</span>
        <select {...form.register("role")}>
          {editableRoles.map((value) => (
            <option key={value} value={value}>
              {roleLabels[value]}
            </option>
          ))}
        </select>
      </label>
      <label className="form-field">
        <span>Scope</span>
        <input aria-invalid={Boolean(errors.scope)} {...form.register("scope")} />
        {errors.scope ? <small role="alert">{errors.scope.message}</small> : null}
      </label>
    </fieldset>
  );
}

function MembershipFields({ form }: { form: FormController }) {
  const membershipError = form.formState.errors.organisationUnitIds;
  return (
    <fieldset>
      <legend>Organisation membership</legend>
      {form.options.length ? (
        <MembershipOptions form={form} />
      ) : (
        <p className="inline-empty">This role does not require an organisation membership.</p>
      )}
      {membershipError ? (
        <p className="field-error" role="alert">
          {membershipError.message}
        </p>
      ) : null}
    </fieldset>
  );
}

function MembershipOptions({ form }: { form: FormController }) {
  return (
    <>
      <label className="form-field">
        <span>Workspace position</span>
        <select
          {...form.register("workspacePosition", { setValueAs: (value) => value || null })}
          disabled={fixedWorkspacePosition(form.role)}
        >
          <option value="MEMBER">Member</option>
          <option value="MANAGER">Manager</option>
        </select>
        <small>{workspacePositionGuidance(form.role)}</small>
      </label>
      <div className="admin-membership-list">
        {form.options.map((unit) => (
          <label key={unit.id}>
            <input type="checkbox" value={unit.id} {...form.register("organisationUnitIds")} />
            <span>
              <strong>{unit.name}</strong>
              <small>{unit.code}</small>
            </span>
          </label>
        ))}
      </div>
    </>
  );
}

function setWorkspacePosition(
  role: UserRole,
  position: Values["workspacePosition"],
  setValue: FormController["setValue"],
) {
  if (role === "DELIVERY_TEAM_LEAD") return setValue("workspacePosition", "MANAGER");
  if (role === "DELIVERY_SPECIALIST") return setValue("workspacePosition", "MEMBER");
  if (!roleNeedsMembership(role)) return setValue("workspacePosition", null);
  if (!position) setValue("workspacePosition", "MEMBER");
}

function fixedWorkspacePosition(role: UserRole) {
  return role === "DELIVERY_TEAM_LEAD" || role === "DELIVERY_SPECIALIST";
}

function workspacePositionGuidance(role: UserRole) {
  if (role === "DELIVERY_TEAM_LEAD")
    return "Team Managers receive accountable allocation controls.";
  if (role === "DELIVERY_SPECIALIST") return "Analysts are workspace Members.";
  return "Managers can maintain this workspace roster and calendar. Routing decisions remain claim-based.";
}

function valuesFor(user?: AdminUser): Values {
  return user
    ? {
        displayName: user.displayName,
        email: user.email,
        role: user.role,
        scope: user.scope,
        organisationUnitIds: user.memberships.map((membership) => membership.organisationUnitId),
        workspacePosition: user.memberships[0]?.workspacePosition ?? null,
      }
    : {
        displayName: "",
        email: "",
        role: "REQUESTER",
        scope: "",
        organisationUnitIds: [],
        workspacePosition: null,
      };
}
