import { useQuery } from "@tanstack/react-query";
import { MapPin } from "lucide-react";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { OrganisationUnit } from "../../lib/api/types";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";
import { StepUpPanel } from "../admin/StepUpPanel";
import {
  buildOrganisationTree,
  locateViewer,
  type OrganisationTreeNode,
  type ViewerPlacement,
} from "./organisationTree";
import { RenameOrganisationUnit } from "./RenameOrganisationUnit";

const kindLabels: Record<OrganisationUnit["kind"], string> = {
  ROOT: "JIOC root",
  COMMAND: "Command",
  OPS_GROUP: "Operations group",
  TEAM: "Team",
};

const staffingLabels: Record<OrganisationUnit["staffingStatus"], string> = {
  ROUTING_POOL: "Routing",
  STAFFED: "Analysis Team",
  UNSTAFFED: "Analysis Team · Awaiting staffing",
};

export function OrganisationPage() {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const query = useQuery({
    queryKey: queryKeys.organisationUnits(),
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
  const placement = locateViewer(units, session?.user.organisationUnitIds ?? []);
  const staffedTeams = units.filter(
    (unit) => unit.kind === "TEAM" && unit.staffingStatus === "STAFFED",
  ).length;
  const unstaffedTeams = units.filter(
    (unit) => unit.kind === "TEAM" && unit.staffingStatus === "UNSTAFFED",
  ).length;
  const routingUnits = units.filter((unit) => unit.staffingStatus === "ROUTING_POOL").length;
  const admin = session?.user.role === "PLATFORM_ADMIN";
  const editable = admin && isSessionElevated(session);

  return (
    <main className="page-stack organisation-page">
      <header className="page-heading">
        <div>
          <span>Organisation reference</span>
          <h1>JIOC routing hierarchy</h1>
          <p>
            Browse routing responsibility and analysis-team staffing. QC is a shared function across
            the hierarchy. Analysis Team badges identify delivery units and show when staffing is
            still awaited.
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
          <YourPlace placement={placement} />
          <section aria-label="Organisation function summary">
            <dl className="organisation-summary">
              <div>
                <dt>Routing</dt>
                <dd>{routingUnits}</dd>
              </div>
              <div>
                <dt>Analysis Teams</dt>
                <dd>{staffedTeams}</dd>
              </div>
              <div>
                <dt>QC</dt>
                <dd>Shared</dd>
              </div>
              <div>
                <dt>Analysis Teams awaiting staffing</dt>
                <dd>{unstaffedTeams}</dd>
              </div>
            </dl>
          </section>
          <section aria-labelledby="organisation-tree-title">
            <div className="section-heading">
              <span>Current structure</span>
              <h2 id="organisation-tree-title">Organisation units</h2>
            </div>
            <ul aria-label="Organisation hierarchy" className="organisation-tree">
              {tree.map((node) => (
                <OrganisationBranch
                  editable={editable}
                  key={node.id}
                  node={node}
                  placement={placement}
                />
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}

function YourPlace({ placement }: { placement: ViewerPlacement }) {
  if (placement.trail.length === 0) return null;
  const here = placement.trail[placement.trail.length - 1]!;
  return (
    <section aria-labelledby="your-place-title" className="organisation-place">
      <MapPin aria-hidden="true" size={20} />
      <div>
        <span>Your place</span>
        <h2 id="your-place-title">{here.name}</h2>
        <ol aria-label="Path from the root to your unit" className="organisation-place__trail">
          {placement.trail.map((unit, index) => (
            <li
              key={unit.id}
              aria-current={index === placement.trail.length - 1 ? "location" : undefined}
            >
              {unit.name}
            </li>
          ))}
        </ol>
        {placement.own.size > 1 ? (
          <small>
            You belong to {placement.own.size} units. Each is marked in the structure below.
          </small>
        ) : null}
      </div>
    </section>
  );
}

function OrganisationBranch({
  editable,
  node,
  placement,
}: {
  editable: boolean;
  node: OrganisationTreeNode;
  placement: ViewerPlacement;
}) {
  const here = placement.own.has(node.id);
  const onPath = placement.path.has(node.id);
  const className = [
    "organisation-unit",
    `organisation-unit--${node.kind.toLowerCase()}`,
    here ? "organisation-unit--here" : "",
    onPath && !here ? "organisation-unit--path" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <li className="organisation-branch">
      <article aria-current={here ? "location" : undefined} className={className}>
        <div className="organisation-unit__identity">
          <strong>{node.name}</strong>
          <small>
            {kindLabels[node.kind]}
            <span className="mono-ref">{node.code}</span>
            {node.children.length > 0 ? (
              <span className="organisation-unit__count">
                {node.children.length} {node.children.length === 1 ? "unit" : "units"}
              </span>
            ) : null}
          </small>
        </div>
        {here ? (
          <span className="organisation-here-badge">
            <MapPin aria-hidden="true" size={13} />
            You are here
          </span>
        ) : null}
        <span className={`staffing-badge staffing-badge--${node.staffingStatus.toLowerCase()}`}>
          {staffingLabels[node.staffingStatus]}
        </span>
        {editable ? <RenameOrganisationUnit unit={node} /> : null}
      </article>
      {node.children.length > 0 ? (
        <ul>
          {node.children.map((child) => (
            <OrganisationBranch
              editable={editable}
              key={child.id}
              node={child}
              placement={placement}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}
