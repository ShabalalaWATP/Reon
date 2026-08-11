from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx
from camunda_orchestration_sdk import CamundaAsyncClient, errors
from camunda_orchestration_sdk.models import (
    CancelProcessInstanceData,
    LimitBasedPagination,
    ProcessCreationById,
    ProcessInstanceCreationInstructionByIdVariables,
    ProcessInstanceResult,
    ProcessInstanceSearchQuery,
    ProcessInstanceSearchQueryFilter,
    UserTaskAssignmentRequest,
    UserTaskCompletionRequest,
    UserTaskCompletionRequestVariables,
    UserTaskResult,
    UserTaskSearchQuery,
    UserTaskSearchQueryFilter,
    UserTaskStateExactMatch,
)
from camunda_orchestration_sdk.semantic_types import (
    BusinessId,
    ElementId,
    ProcessDefinitionId,
    ProcessInstanceKey,
    TenantId,
    UserTaskKey,
)

from istari_service.workflow.camunda_call import call_camunda
from istari_service.workflow.errors import (
    AmbiguousWorkflowProcess,
    WorkflowConflict,
    WorkflowContractError,
    WorkflowProcessNotVisible,
)
from istari_service.workflow.projection import (
    ensure_action_matches_element,
)
from istari_service.workflow.types import (
    ActiveTaskQuery,
    CancelProcessCommand,
    ClaimTaskCommand,
    CompleteTaskCommand,
    ProcessStateQuery,
    StartedProcess,
    StartedProcessQuery,
    StartProcessCommand,
    WorkflowProcessSnapshot,
    WorkflowProcessState,
    WorkflowTask,
    WorkflowTaskState,
)
from istari_service.workflow.variables import completion_variables
from istari_service.workflow_start_identity import returned_start_matches

Sleep = Callable[[float], Awaitable[None]]


class CamundaWorkflowEngine:
    """Translate the narrow application port to the official V2 SDK models."""

    _call = staticmethod(call_camunda)

    def __init__(
        self,
        client: CamundaAsyncClient,
        *,
        start_recovery_attempts: int = 5,
        start_recovery_delay_seconds: float = 0.05,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not 1 <= start_recovery_attempts <= 20:
            raise ValueError("start_recovery_attempts must be between 1 and 20")
        if not 0 <= start_recovery_delay_seconds <= 5:
            raise ValueError("start recovery delay must be from zero to five")
        self._client = client
        self._start_recovery_attempts = start_recovery_attempts
        self._start_recovery_delay_seconds = start_recovery_delay_seconds
        self._sleep = sleep

    async def is_reachable(self) -> bool:
        try:
            await self._client.get_status()
        except (errors.ApiError, httpx.HTTPError):
            return False
        return True

    async def start_process(self, command: StartProcessCommand) -> StartedProcess:
        request_id = str(command.request_id)
        variables = ProcessInstanceCreationInstructionByIdVariables()
        variables["requestId"] = request_id
        variables["requesterId"] = str(command.requester_id)
        try:
            data = ProcessCreationById(
                process_definition_id=ProcessDefinitionId(
                    command.process_definition_id
                ),
                process_definition_version=command.process_definition_version,
                variables=variables,
                business_id=BusinessId(request_id),
            )
            if command.tenant_id is not None:
                data.tenant_id = TenantId(command.tenant_id)
        except ValueError as exc:
            raise WorkflowContractError("invalid Camunda V2 process identity") from exc
        try:
            result = await self._call(
                "start_process",
                self._client.create_process_instance(data=data),
            )
        except WorkflowConflict as conflict:
            return await self._recover_started_process(
                StartedProcessQuery.from_start(command),
                conflict,
            )
        if result.business_id is None or str(result.business_id) != request_id:
            raise WorkflowContractError("Camunda returned the wrong business ID")
        if not returned_start_matches(
            expected_process_id=command.process_definition_id,
            expected_process_version=command.process_definition_version,
            actual_process_id=str(result.process_definition_id),
            actual_process_version=result.process_definition_version,
        ):
            raise WorkflowContractError("Camunda returned the wrong process identity")
        return StartedProcess(
            process_instance_key=str(result.process_instance_key),
            process_definition_key=str(result.process_definition_key),
            process_definition_id=str(result.process_definition_id),
            process_definition_version=result.process_definition_version,
            business_id=request_id,
        )

    async def find_started_process(
        self, query: StartedProcessQuery
    ) -> StartedProcess | None:
        filter_ = ProcessInstanceSearchQueryFilter(
            process_definition_id=query.process_definition_id,
            business_id=str(query.request_id),
        )
        if query.process_definition_version != -1:
            filter_.process_definition_version = query.process_definition_version
        if query.tenant_id is not None:
            filter_.tenant_id = query.tenant_id
        result = await self._call(
            "find_started_process",
            self._client.search_process_instances(
                data=ProcessInstanceSearchQuery(
                    filter_=filter_,
                    page=LimitBasedPagination(limit=2),
                )
            ),
        )
        processes = tuple(self._map_process(item, query) for item in result.items)
        if len(processes) > 1:
            raise AmbiguousWorkflowProcess(
                "multiple processes matched the request business ID"
            )
        return processes[0] if processes else None

    async def find_process_state(
        self,
        query: ProcessStateQuery,
    ) -> WorkflowProcessSnapshot | None:
        try:
            process_key = ProcessInstanceKey(query.process_instance_key)
        except ValueError as exc:
            raise WorkflowContractError("invalid Camunda V2 process key") from exc
        filter_ = ProcessInstanceSearchQueryFilter(process_instance_key=process_key)
        result = await self._call(
            "find_process_state",
            self._client.search_process_instances(
                data=ProcessInstanceSearchQuery(
                    filter_=filter_,
                    page=LimitBasedPagination(limit=2),
                )
            ),
        )
        if len(result.items) > 1:
            raise AmbiguousWorkflowProcess("process instance key is not unique")
        if not result.items:
            return None
        process = result.items[0]
        if str(process.process_instance_key) != query.process_instance_key:
            raise WorkflowContractError("Camunda returned a different process key")
        try:
            state = WorkflowProcessState(process.state.value)
        except ValueError as exc:
            raise WorkflowContractError("Camunda returned an invalid state") from exc
        return WorkflowProcessSnapshot(query.process_instance_key, state)

    async def search_active_tasks(
        self,
        query: ActiveTaskQuery,
    ) -> tuple[WorkflowTask, ...]:
        filter_ = UserTaskSearchQueryFilter(
            state=UserTaskStateExactMatch.CREATED,
            process_instance_key=query.process_instance_key,
        )
        if query.expected_element_id is not None:
            try:
                filter_.element_id = ElementId(query.expected_element_id)
            except ValueError as exc:
                raise WorkflowContractError("invalid Camunda V2 task element") from exc
        result = await self._call(
            "search_active_tasks",
            self._client.search_user_tasks(
                data=UserTaskSearchQuery(
                    filter_=filter_,
                    page=LimitBasedPagination(limit=2),
                )
            ),
        )
        return tuple(self._map_task(task) for task in result.items)

    async def claim_task(self, command: ClaimTaskCommand) -> None:
        try:
            task_key = UserTaskKey(command.task_key)
        except ValueError as exc:
            raise WorkflowContractError(
                "task key is invalid for the Camunda V2 contract"
            ) from exc
        await self._call(
            "claim_task",
            self._client.assign_user_task(
                task_key,
                data=UserTaskAssignmentRequest(
                    assignee=str(command.assignee_id),
                    allow_override=False,
                    action="claim",
                ),
            ),
        )

    async def complete_task(self, command: CompleteTaskCommand) -> None:
        ensure_action_matches_element(command.expected_element_id, command.action)
        try:
            task_key = UserTaskKey(command.task_key)
        except ValueError as exc:
            raise WorkflowContractError(
                "task key is invalid for the Camunda V2 contract"
            ) from exc
        variables = UserTaskCompletionRequestVariables()
        for name, value in completion_variables(command).items():
            variables[name] = value

        completion = UserTaskCompletionRequest(action=command.action.value)
        if variables.additional_keys:
            completion.variables = variables
        await self._call(
            "complete_task",
            self._client.complete_user_task(
                task_key,
                data=completion,
            ),
        )

    async def cancel_process(self, command: CancelProcessCommand) -> None:
        try:
            process_key = ProcessInstanceKey(command.process_instance_key)
        except ValueError as exc:
            raise WorkflowContractError(
                "process instance key is invalid for the Camunda V2 contract"
            ) from exc
        await self._call(
            "cancel_process",
            self._client.cancel_process_instance(
                process_key,
                data=CancelProcessInstanceData(),
            ),
        )

    @staticmethod
    def _map_task(task: UserTaskResult) -> WorkflowTask:
        try:
            state = WorkflowTaskState(task.state.value)
        except ValueError as exc:
            raise WorkflowContractError(
                "Camunda returned an invalid user-task result"
            ) from exc
        return WorkflowTask(
            task_key=str(task.user_task_key),
            process_instance_key=str(task.process_instance_key),
            element_id=str(task.element_id),
            state=state,
            assignee=task.assignee,
        )

    @staticmethod
    def _map_process(
        process: ProcessInstanceResult,
        query: StartedProcessQuery,
    ) -> StartedProcess:
        business_id = None if process.business_id is None else str(process.business_id)
        if business_id != str(query.request_id):
            raise WorkflowContractError(
                "Camunda returned a process with a different business ID"
            )
        if str(process.process_definition_id) != query.process_definition_id:
            raise WorkflowContractError(
                "Camunda returned a process for a different definition"
            )
        if (
            query.process_definition_version != -1
            and process.process_definition_version != query.process_definition_version
        ):
            raise WorkflowContractError(
                "Camunda returned a process for a different definition version"
            )
        if query.tenant_id is not None and str(process.tenant_id) != query.tenant_id:
            raise WorkflowContractError(
                "Camunda returned a process for a different tenant"
            )
        if process.parent_process_instance_key is not None:
            raise WorkflowContractError(
                "Camunda returned a child process for a root start recovery"
            )
        return StartedProcess(
            process_instance_key=str(process.process_instance_key),
            process_definition_key=str(process.process_definition_key),
            process_definition_id=str(process.process_definition_id),
            process_definition_version=process.process_definition_version,
            business_id=business_id,
        )

    async def _recover_started_process(
        self,
        query: StartedProcessQuery,
        conflict: WorkflowConflict,
    ) -> StartedProcess:
        for attempt in range(self._start_recovery_attempts):
            process = await self.find_started_process(query)
            if process is not None:
                return process
            if attempt + 1 < self._start_recovery_attempts:
                await self._sleep(self._start_recovery_delay_seconds)
        raise WorkflowProcessNotVisible(
            "conflicting process start was not visible within the recovery bound"
        ) from conflict
