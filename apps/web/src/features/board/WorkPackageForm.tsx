import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { boardApi } from "../../lib/api/boardClient";
import type { Iteration, WorkPackage } from "../../lib/api/boardTypes";
import { ApiError } from "../../lib/api/client";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { WorkPackageFields } from "./WorkPackageFields";
import { emptyWorkPackage, workPackageInput } from "./workPackageFormModel";

export function WorkPackageForm({ access, iterations, members, onCreated, session }: {
  access: TeamWorkspaceAccess;
  iterations: Iteration[];
  members: TeamMember[];
  onCreated: (item: WorkPackage) => void;
  session: Session;
}) {
  const isManager = Boolean(access.grantId && access.permissions.includes("BOARD"));
  const initialOwner = isManager ? "" : session.user.id;
  const [value, setValue] = useState(() => emptyWorkPackage(initialOwner));
  const mutation = useMutation({
    mutationFn: () => boardApi.createPackage(
      access.teamId,
      workPackageInput(value, access.grantId),
      session.csrfToken,
    ),
    onSuccess: (item) => {
      setValue(emptyWorkPackage(initialOwner));
      onCreated(item);
    },
  });
  return (
    <section className="package-form-panel">
      <header><span>Analyst team planning</span><h2>Create internal card</h2><p>This card stays on the team’s internal Kanban and does not change the Customer request workflow.</p></header>
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <WorkPackageFields canChooseOwner={isManager} iterations={iterations} members={members} mode="create" onChange={setValue} value={value} />
        {mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}
        <button className="button button--primary" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Creating…" : "Add card to Kanban"}</button>
      </form>
    </section>
  );
}

function message(error: Error) {
  return error instanceof ApiError ? error.message : error.message || "The work package could not be created.";
}
