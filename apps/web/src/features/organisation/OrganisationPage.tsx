import { useQuery } from "@tanstack/react-query";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { OrganisationUnit } from "../../lib/api/types";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";
import { StepUpPanel } from "../admin/StepUpPanel";
import {
  buildOrganisationTree,
  type OrganisationTreeNode,
} from "./organisationTree";
import { RenameOrganisationUnit } from "./RenameOrganisationUnit";

const kindLabels: Record<OrganisationUnit["kind"], string> = {
  ROOT: "CRIOC root",
  COMMAND: "Command",
  OPS_GROUP: "Operations group",
  TEAM: "Team",
};

const staffingLabels: Record<OrganisationUnit["staffingStatus"], string> = {
  ROUTING_POOL: "Routing function",
  STAFFED: "Team staffed",
  UNSTAFFED: "Team awaiting staffing",
};

export function OrganisationPage() {
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const query = useQuery({
    queryKey: protectedQueryKeys.organisationUnits(userId),
    queryFn: api.organisationUnits,
    enabled: Boolean(session),
  });

  if (query.isPending) {
    return <PageState kind="loading" title="Loading organisation" />;
  }
  if (query.isError) {
    return (
      <PageState
        action={
          <button className="button" onClick={() => void query.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Organisation could not be loaded"
      >
        Check your connection and try again.
      </PageState>
    );
  }

  const units = query.data.items;
  const tree = buildOrganisationTree(units);
  const staffedTeams = units.filter(
    (unit) => unit.kind === "TEAM" && unit.staffingStatus === "STAFFED",
  ).length;
  const unstaffedTeams = units.filter(
    (unit) => unit.kind === "TEAM" && unit.staffingStatus === "UNSTAFFED",
  ).length;
  const routingUnits = units.filter(
    (unit) => unit.staffingStatus === "ROUTING_POOL",
  ).length;
  const admin = session?.user.role === "PLATFORM_ADMIN";
  const editable = admin && isSessionElevated(session);

  return (
    <main className="page-stack organisation-page">
      <header className="page-heading">
        <div>
          <span>Organisation reference</span>
          <h1>CRIOC routing hierarchy</h1>
          <p>
            Browse routing responsibility and delivery-team staffing. CRIOC,
            command and Ops units are staffed routing functions; team badges
            show whether Manager and Analyst roles are currently covered.
          </p>
        </div>
      </header>
      {admin ? <StepUpPanel /> : null}
      {units.length === 0 ? (
        <PageState kind="empty" title="No organisation units configured">
          Routing destinations will appear once the organisation is configured.
        </PageState>
      ) : (
        <>
          <dl className="organisation-summary" aria-label="Staffing summary">
            <div><dt>Routing functions</dt><dd>{routingUnits}</dd></div>
            <div><dt>Staffed teams</dt><dd>{staffedTeams}</dd></div>
            <div><dt>Awaiting staffing</dt><dd>{unstaffedTeams}</dd></div>
          </dl>
          <section aria-labelledby="organisation-tree-title">
            <div className="section-heading">
              <span>Current structure</span>
              <h2 id="organisation-tree-title">Organisation units</h2>
            </div>
            <ul aria-label="Organisation hierarchy" className="organisation-tree">
              {tree.map((node) => <OrganisationBranch editable={editable} key={node.id} node={node} />)}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}

function OrganisationBranch({ editable, node }: { editable: boolean; node: OrganisationTreeNode }) {
  return (
    <li className="organisation-branch">
      <article className="organisation-unit">
        <span className="mono-ref">{node.code}</span>
        <div>
          <strong>{node.name}</strong>
          <small>{kindLabels[node.kind]}</small>
        </div>
        <span
          className={`staffing-badge staffing-badge--${node.staffingStatus.toLowerCase()}`}
        >
          {staffingLabels[node.staffingStatus]}
        </span>
        {editable ? <RenameOrganisationUnit unit={node} /> : null}
      </article>
      {node.children.length > 0 ? (
        <ul>
          {node.children.map((child) => (
            <OrganisationBranch editable={editable} key={child.id} node={child} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}
