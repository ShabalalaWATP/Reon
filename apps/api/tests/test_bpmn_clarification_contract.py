"""Executable BPMN contract for the production clarification loop."""

from pathlib import Path
from xml.etree import ElementTree

import pytest

from mist_service.models import RequestStatus
from mist_service.workflow.projection import status_after_action
from mist_service.workflow.types import WorkflowAction

BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
ZEEBE = "http://camunda.org/schema/zeebe/1.0"


@pytest.mark.parametrize(
    ("status", "action", "result"),
    [
        (
            RequestStatus.IN_PROGRESS,
            WorkflowAction.REQUEST_CLARIFICATION,
            RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        ),
        (
            RequestStatus.REWORK_REQUIRED,
            WorkflowAction.REQUEST_CLARIFICATION,
            RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
        ),
        (
            RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
            WorkflowAction.PROVIDE_CLARIFICATION,
            RequestStatus.IN_PROGRESS,
        ),
        (
            RequestStatus.CUSTOMER_INFORMATION_REQUIRED,
            WorkflowAction.WITHDRAW,
            RequestStatus.CANCELLED,
        ),
    ],
)
def test_clarification_transition_matrix(
    status: RequestStatus,
    action: WorkflowAction,
    result: RequestStatus,
) -> None:
    assert status_after_action(status, action) is result


def test_production_clarification_is_a_direct_same_assignment_loop() -> None:
    path = Path(__file__).parents[3] / "workflow" / "service-request.bpmn"
    root = ElementTree.parse(path).getroot()  # noqa: S314 - repository-owned XML
    process = root.find(f"{{{BPMN}}}process")
    assert process is not None and process.attrib["id"] == "service-request-v1"

    tasks = {task.attrib["id"]: task for task in process.findall(f"{{{BPMN}}}userTask")}
    response = tasks["customer_clarification_response"]
    assignment = response.find(
        f"{{{BPMN}}}extensionElements/{{{ZEEBE}}}assignmentDefinition"
    )
    assert assignment is not None
    assert assignment.attrib == {"assignee": "= requesterId"}

    delivery_assignment = tasks["delivery_work"].find(
        f"{{{BPMN}}}extensionElements/{{{ZEEBE}}}assignmentDefinition"
    )
    assert delivery_assignment is not None
    assert delivery_assignment.attrib["assignee"] == "= assignedSpecialistId"

    flows = {
        flow.attrib["id"]: flow for flow in process.findall(f"{{{BPMN}}}sequenceFlow")
    }
    request_flow = flows["flow_delivery_clarification"]
    resume_flow = flows["flow_clarification_resume"]
    assert request_flow.attrib["sourceRef"] == "delivery_outcome"
    assert request_flow.attrib["targetRef"] == "customer_clarification_response"
    assert resume_flow.attrib["sourceRef"] == "clarification_outcome"
    assert resume_flow.attrib["targetRef"] == "delivery_work"
    assert request_flow.find(f"{{{BPMN}}}conditionExpression").text == (
        '= deliveryDecision = "request_clarification"'
    )
    assert resume_flow.find(f"{{{BPMN}}}conditionExpression").text == (
        '= clarificationDecision = "provide_clarification"'
    )


def test_bpmn_keeps_clarification_content_out_of_engine_variables() -> None:
    path = Path(__file__).parents[3] / "workflow" / "service-request.bpmn"
    text = path.read_text(encoding="utf-8")
    for forbidden in (
        "clarificationQuestion",
        "clarificationReason",
        "clarificationResponse",
        "requestDescription",
    ):
        assert forbidden not in text
