"""Allow-listed Camunda completion variables derived from validated commands."""

from __future__ import annotations

from istari_service.workflow.projection import decision_variable_for_element
from istari_service.workflow.types import CompleteTaskCommand, WorkflowAction

WorkflowVariable = str | list[str]


def completion_variables(
    command: CompleteTaskCommand,
) -> dict[str, WorkflowVariable]:
    variables: dict[str, WorkflowVariable] = {}
    decision = decision_variable_for_element(command.expected_element_id)
    if decision is not None:
        variables[decision] = command.action.value
    if command.delivery_team_id is not None:
        variables["assignedDeliveryTeamId"] = command.delivery_team_id.value
    route = command.route_selection
    if route is not None and command.action is WorkflowAction.PROGRESS:
        variables["selectedCommandId"] = str(route.unit_id)
        variables["selectedCommandCandidateGroup"] = [route.candidate_groups[0]]
    elif route is not None and command.action is WorkflowAction.SEND_TO_ALLOCATION:
        variables["selectedOpsId"] = str(route.unit_id)
        variables["selectedOpsCandidateGroup"] = [route.candidate_groups[0]]
    elif route is not None and command.action is WorkflowAction.ALLOCATE:
        variables["selectedTeamId"] = str(route.unit_id)
        variables["selectedTeamManagerCandidateGroup"] = [route.candidate_groups[0]]
        variables["selectedTeamAnalystCandidateGroup"] = [route.candidate_groups[1]]
        variables["assignedDeliveryTeamId"] = route.unit_code
    if command.specialist_id is not None:
        variables["assignedSpecialistId"] = str(command.specialist_id)
    return variables
