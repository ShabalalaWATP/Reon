import type { ChangeEvent, ReactNode } from "react";

import type { Iteration, WorkPackage, WorkPackagePriority } from "../../lib/api/boardTypes";
import type { TeamMember } from "../../lib/api/teamTypes";
import type { WorkPackageFormValue } from "./workPackageFormModel";

type Props = {
  canChooseOwner: boolean;
  dependencies?: WorkPackage[];
  iterations: Iteration[];
  members: TeamMember[];
  mode: "create" | "edit";
  onChange: (value: WorkPackageFormValue) => void;
  value: WorkPackageFormValue;
};

export function WorkPackageFields({
  canChooseOwner,
  dependencies = [],
  iterations,
  members,
  mode,
  onChange,
  value,
}: Props) {
  const current = members.filter((member) => member.state === "CURRENT");
  const contributors =
    mode === "create" ? current.filter((member) => member.role === "DELIVERY_SPECIALIST") : current;
  const label = (create: string, edit: string) => (mode === "edit" ? edit : create);
  const update = <K extends keyof WorkPackageFormValue>(name: K, next: WorkPackageFormValue[K]) =>
    onChange({ ...value, [name]: next });
  const selectedContributors = (event: ChangeEvent<HTMLSelectElement>) => {
    const selected = Array.from(event.target.selectedOptions, (option) => option.value);
    update("contributorIds", selected.slice(0, 10));
  };

  return (
    <>
      <Field label={label("Title", "Edit title")}>
        <input
          maxLength={160}
          minLength={3}
          onChange={(event) => update("title", event.target.value)}
          required
          value={value.title}
        />
      </Field>
      <Field label={label("Description", "Edit description")}>
        <textarea
          maxLength={4000}
          onChange={(event) => update("description", event.target.value)}
          required
          rows={mode === "create" ? 4 : undefined}
          value={value.description}
        />
      </Field>
      <div className="planning-form-grid">
        <Field label={label("Owner", "Edit owner")}>
          <select
            disabled={!canChooseOwner}
            onChange={(event) => update("ownerUserId", event.target.value)}
            required
            value={value.ownerUserId}
          >
            {mode === "create" ? <option value="">Select an owner</option> : null}
            {current.map((member) => (
              <option key={member.accountId} value={member.accountId}>
                {member.displayName}
              </option>
            ))}
          </select>
        </Field>
        <Field label={label("Contributors", "Edit contributors")}>
          <select
            multiple
            onChange={selectedContributors}
            required
            size={Math.min(7, Math.max(3, contributors.length))}
            value={value.contributorIds}
          >
            {contributors.map((member) => (
              <option key={member.accountId} value={member.accountId}>
                {member.displayName}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="planning-form-grid">
        <Field label={label("Estimate points", "Edit estimate points")}>
          <input
            max={100}
            min={1}
            onChange={(event) => update("estimatePoints", Number(event.target.value))}
            required
            type="number"
            value={value.estimatePoints}
          />
        </Field>
        <Field label={label("Remaining effort (minutes)", "Edit remaining minutes")}>
          <input
            max={100000}
            min={0}
            onChange={(event) => update("remainingEffortMinutes", Number(event.target.value))}
            required
            type="number"
            value={value.remainingEffortMinutes}
          />
        </Field>
      </div>
      <div className="planning-form-grid">
        <Field label={label("Due date", "Edit due date")}>
          <input
            onChange={(event) => update("dueOn", event.target.value)}
            required
            type="date"
            value={value.dueOn}
          />
        </Field>
        <Field label={label("Priority", "Edit priority")}>
          <select
            onChange={(event) => update("priority", event.target.value as WorkPackagePriority)}
            required
            value={value.priority}
          >
            {["LOW", "MEDIUM", "HIGH", "URGENT"].map((priority) => (
              <option key={priority}>{priority}</option>
            ))}
          </select>
        </Field>
      </div>
      <Field label={label("Blockers or none", "Edit blockers or none")}>
        <textarea
          maxLength={4000}
          onChange={(event) => update("blockers", event.target.value)}
          required
          rows={mode === "create" ? 3 : undefined}
          value={value.blockers}
        />
      </Field>
      <Field label={label("Acceptance criteria", "Edit acceptance criteria")}>
        <textarea
          maxLength={4000}
          onChange={(event) => update("acceptanceCriteria", event.target.value)}
          required
          rows={mode === "create" ? 3 : undefined}
          value={value.acceptanceCriteria}
        />
      </Field>
      <div className="planning-form-grid">
        <Optional label={label("Linked request ID", "Edit linked request ID")}>
          <input
            onChange={(event) => update("linkedRequestId", event.target.value)}
            placeholder="UUID"
            value={value.linkedRequestId}
          />
        </Optional>
        <Optional label={label("Iteration", "Edit iteration")}>
          <select
            onChange={(event) => update("iterationId", event.target.value)}
            value={value.iterationId}
          >
            <option value="">No iteration</option>
            {iterations
              .filter(
                (iteration) => iteration.status !== "CLOSED" || iteration.id === value.iterationId,
              )
              .map((iteration) => (
                <option key={iteration.id} value={iteration.id}>
                  {iteration.name}
                </option>
              ))}
          </select>
        </Optional>
      </div>
      {mode === "edit" ? (
        <Optional label="Edit dependencies">
          <select
            multiple
            onChange={(event) =>
              update(
                "dependencyIds",
                Array.from(event.target.selectedOptions, (option) => option.value),
              )
            }
            value={value.dependencyIds}
          >
            {dependencies.map((dependency) => (
              <option key={dependency.id} value={dependency.id}>
                {dependency.title}
              </option>
            ))}
          </select>
        </Optional>
      ) : null}
    </>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="form-field">
      {label}
      <span className="field-hint">Required</span>
      {children}
    </label>
  );
}

function Optional({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="form-field">
      {label}
      <span className="field-hint">Optional</span>
      {children}
    </label>
  );
}
