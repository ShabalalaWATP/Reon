import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { boardApi } from "../../lib/api/boardClient";
import type { Iteration, WorkPackage } from "../../lib/api/boardTypes";
import { ApiError } from "../../lib/api/client";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { WorkPackageFields } from "./WorkPackageFields";
import { workPackageInput, workPackageValue } from "./workPackageFormModel";

interface Props {
  access: TeamWorkspaceAccess;
  item: WorkPackage;
  items: WorkPackage[];
  iterations: Iteration[];
  members: TeamMember[];
  onUpdated: (item: WorkPackage) => void;
  session: Session;
}

export function WorkPackageEditForm({ access, item, items, iterations, members, onUpdated, session }: Props) {
  const [value, setValue] = useState(() => workPackageValue(item));
  const mutation = useMutation({
    mutationFn: () => boardApi.updatePackage(
      access.teamId,
      item.id,
      { ...workPackageInput(value, access.grantId), expectedVersion: item.version },
      session.csrfToken,
    ),
    onSuccess: onUpdated,
  });
  return (
    <section className="package-edit-panel">
      <header><span>Versioned planning change</span><h2>Edit or hand over package</h2><p>Managers can reassign ownership only to a current member of this team.</p></header>
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <WorkPackageFields canChooseOwner dependencies={items.filter((candidate) => candidate.id !== item.id)} iterations={iterations} members={members} mode="edit" onChange={setValue} value={value} />
        {mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}
        <button className="button button--primary" disabled={mutation.isPending} type="submit">Save package</button>
      </form>
    </section>
  );
}

function message(error: Error) {
  return error instanceof ApiError ? error.message : error.message || "The package change could not be saved.";
}
