import { useQuery } from "@tanstack/react-query";

import { planningEvolutionApi } from "../../lib/api/planningEvolutionClient";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { PlanningCockpit } from "./PlanningCockpit";

export function PlanningEnhancements({
  access,
  session,
}: {
  access: TeamWorkspaceAccess;
  session: Session;
}) {
  const userId = session.user.id;
  const cockpit = useQuery({
    queryKey: protectedQueryKeys.teamPlanningCockpit(userId, access.teamId),
    queryFn: () => planningEvolutionApi.cockpit(access.teamId),
  });
  const templates = useQuery({
    queryKey: protectedQueryKeys.teamPlanningTemplates(userId, access.teamId),
    queryFn: () => planningEvolutionApi.templates(access.teamId),
  });
  const scenarios = useQuery({
    queryKey: protectedQueryKeys.teamPlanningScenarios(userId, access.teamId),
    queryFn: () => planningEvolutionApi.scenarios(access.teamId),
  });
  const retry = () => {
    void cockpit.refetch();
    void templates.refetch();
    void scenarios.refetch();
  };

  if (cockpit.isPending || templates.isPending || scenarios.isPending) {
    return (
      <section aria-busy="true" className="planning-evolution-state">
        <span>Planning projection</span>
        <h2>Building the planning cockpit</h2>
        <p>Calendar, board and package records are being reconciled.</p>
      </section>
    );
  }
  if (cockpit.isError || templates.isError || scenarios.isError) {
    return (
      <section className="planning-evolution-state" role="status">
        <span>Planning projection unavailable</span>
        <h2>Core planning remains available</h2>
        <p>The enhanced cockpit could not be loaded. No workflow or assignment has changed.</p>
        <button className="button" onClick={retry} type="button">Try cockpit again</button>
      </section>
    );
  }
  return (
    <PlanningCockpit
      access={access}
      cockpit={cockpit.data}
      scenarios={scenarios.data.items}
      session={session}
      templates={templates.data.items}
    />
  );
}
