"""Immutable per-request organisation, catalogue and product policy."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID

from istari_service.configuration_projection import (
    active_parents,
    active_units,
    candidate_groups,
)
from istari_service.configuration_types import (
    CandidateGroupPurpose,
    ConfigurationDraftSpec,
    StaffingCount,
)
from istari_service.errors import InvalidAction
from istari_service.organisation_models import OrganisationKind, StaffingStatus
from istari_service.schemas.organisation import OrganisationUnitView
from istari_service.work_command_types import RoutingSelection

REQUEST_POLICY_SCHEMA = "istari.request-policy/v1"
GROUP_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?")


@dataclass(frozen=True, slots=True)
class PinnedOrganisationUnit:
    unit_id: UUID
    code: str
    name: str
    kind: OrganisationKind
    routing_enabled: bool
    staffing_status: StaffingStatus
    sort_order: int


@dataclass(frozen=True, slots=True)
class PinnedProductPolicy:
    """Request-scoped lower bound for product validation.

    Product handling must also enforce the environment allow-list as an upper bound.
    """

    service_categories: tuple[str, ...]
    product_types: tuple[str, ...]
    artefact_types: tuple[str, ...]
    approved_link_domains: frozenset[str]
    approved_link_domains_digest: str


@dataclass(frozen=True, slots=True)
class RequestConfigurationPolicy:
    configuration_sequence: int
    root_unit_id: UUID
    units: Mapping[UUID, PinnedOrganisationUnit]
    parents: Mapping[UUID, UUID]
    candidate_groups: Mapping[UUID, Mapping[CandidateGroupPurpose, str]]
    product: PinnedProductPolicy

    def routing_options(
        self,
        parent_id: UUID,
        expected_kind: OrganisationKind,
    ) -> list[OrganisationUnitView]:
        units = [
            unit
            for unit in self.units.values()
            if self.parents.get(unit.unit_id) == parent_id
            and unit.kind is expected_kind
            and unit.routing_enabled
        ]
        return [
            self._view(unit)
            for unit in sorted(
                units,
                key=lambda item: (item.sort_order, item.code, str(item.unit_id)),
            )
        ]

    def routing_selection(
        self,
        *,
        parent_id: UUID,
        destination_id: UUID,
        expected_kind: OrganisationKind,
        selected_position: int,
    ) -> RoutingSelection:
        unit = self.units.get(destination_id)
        if (
            unit is None
            or not unit.routing_enabled
            or unit.kind is not expected_kind
            or self.parents.get(destination_id) != parent_id
        ):
            raise InvalidAction("Select a direct child of the current route.")
        groups = self.candidate_groups.get(destination_id, {})
        purposes = (
            (CandidateGroupPurpose.MANAGER, CandidateGroupPurpose.ANALYST)
            if expected_kind is OrganisationKind.TEAM
            else (CandidateGroupPurpose.ROUTING,)
        )
        selected = tuple(groups.get(purpose, "") for purpose in purposes)
        if any(GROUP_PATTERN.fullmatch(group) is None for group in selected):
            raise InvalidAction(
                "The destination routing group is not configured safely."
            )
        return RoutingSelection(
            unit_id=unit.unit_id,
            unit_code=unit.code,
            unit_name=unit.name,
            position=selected_position,
            candidate_groups=selected,
            staffed=unit.staffing_status is StaffingStatus.STAFFED,
        )

    def _view(self, unit: PinnedOrganisationUnit) -> OrganisationUnitView:
        return OrganisationUnitView(
            id=unit.unit_id,
            code=unit.code,
            name=unit.name,
            kind=unit.kind,
            parent_id=self.parents.get(unit.unit_id),
            staffing_status=unit.staffing_status,
            version=self.configuration_sequence,
        )


def canonical_link_domains(domains: Sequence[str]) -> tuple[tuple[str, ...], str]:
    canonical = tuple(sorted({item.strip().lower().rstrip(".") for item in domains}))
    encoded = json.dumps(canonical, separators=(",", ":")).encode()
    return canonical, hashlib.sha256(encoded).hexdigest()


def build_request_policy_snapshot(
    specification: ConfigurationDraftSpec,
    *,
    at: datetime,
    staffing: Mapping[UUID, StaffingCount],
    sort_orders: Mapping[UUID, int],
) -> dict[str, object]:
    units = active_units(specification, at)
    parents = active_parents(specification, at)
    groups = candidate_groups(specification)
    domains, domains_digest = canonical_link_domains(
        specification.workflow_template.approved_link_domains
    )
    ordered_units = sorted(
        units.values(),
        key=lambda item: (sort_orders.get(item.unit_id, 1_000_000), item.code),
    )
    return {
        "requestPolicySchema": REQUEST_POLICY_SCHEMA,
        "organisation": {
            "rootUnitId": str(specification.workflow_template.organisation_root_id),
            "units": [
                {
                    "unitId": str(unit.unit_id),
                    "code": unit.code,
                    "name": unit.name,
                    "kind": unit.kind.value,
                    "routingEnabled": unit.routing_enabled,
                    "staffingStatus": _staffing_status(unit, staffing).value,
                    "sortOrder": sort_orders.get(unit.unit_id, index),
                }
                for index, unit in enumerate(ordered_units)
            ],
            "edges": [
                {"parentUnitId": str(parent), "childUnitId": str(child)}
                for child, parent in sorted(
                    parents.items(), key=lambda item: str(item[0])
                )
            ],
            "candidateGroups": [
                {
                    "unitId": str(unit_id),
                    "purpose": purpose.value,
                    "candidateGroup": group,
                }
                for unit_id, mappings in sorted(
                    groups.items(), key=lambda item: str(item[0])
                )
                for purpose, group in sorted(
                    mappings.items(), key=lambda item: item[0].value
                )
                if unit_id in units
            ],
        },
        "catalogue": {
            "serviceCategories": list(
                specification.workflow_template.service_categories
            ),
            "productTypes": list(specification.workflow_template.product_types),
            "artefactTypes": list(specification.workflow_template.artefact_types),
        },
        "approvedLinkDomains": list(domains),
        "approvedLinkDomainsDigest": domains_digest,
    }


def parse_request_configuration_policy(
    snapshot: Mapping[str, Any],
) -> RequestConfigurationPolicy:
    try:
        if snapshot["requestPolicySchema"] != REQUEST_POLICY_SCHEMA:
            raise ValueError("unsupported request policy schema")
        organisation = _mapping(snapshot["organisation"])
        units = _parse_units(_sequence(organisation["units"]))
        parents = {
            UUID(str(item["childUnitId"])): UUID(str(item["parentUnitId"]))
            for raw in _sequence(organisation["edges"])
            for item in (_mapping(raw),)
        }
        groups: dict[UUID, dict[CandidateGroupPurpose, str]] = defaultdict(dict)
        for raw in _sequence(organisation["candidateGroups"]):
            item = _mapping(raw)
            groups[UUID(str(item["unitId"]))][
                CandidateGroupPurpose(str(item["purpose"]))
            ] = _string(item["candidateGroup"])
        catalogue = _mapping(snapshot["catalogue"])
        domains = tuple(_strings(snapshot["approvedLinkDomains"]))
        canonical, digest = canonical_link_domains(domains)
        supplied_digest = _string(snapshot["approvedLinkDomainsDigest"])
        if domains != canonical or supplied_digest != digest:
            raise ValueError("link-domain policy digest mismatch")
        product = PinnedProductPolicy(
            service_categories=tuple(_strings(catalogue["serviceCategories"])),
            product_types=tuple(_strings(catalogue["productTypes"])),
            artefact_types=tuple(_strings(catalogue["artefactTypes"])),
            approved_link_domains=frozenset(domains),
            approved_link_domains_digest=digest,
        )
        return RequestConfigurationPolicy(
            configuration_sequence=_positive_int(snapshot["configurationSequence"]),
            root_unit_id=UUID(str(organisation["rootUnitId"])),
            units=MappingProxyType(units),
            parents=MappingProxyType(parents),
            candidate_groups=MappingProxyType(
                {
                    unit_id: MappingProxyType(mappings)
                    for unit_id, mappings in groups.items()
                }
            ),
            product=product,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("the pinned request policy is invalid") from exc


def _parse_units(values: Sequence[Any]) -> dict[UUID, PinnedOrganisationUnit]:
    units: dict[UUID, PinnedOrganisationUnit] = {}
    for raw in values:
        item = _mapping(raw)
        unit_id = UUID(str(item["unitId"]))
        routing_enabled = item["routingEnabled"]
        if not isinstance(routing_enabled, bool):
            raise TypeError("routingEnabled must be boolean")
        units[unit_id] = PinnedOrganisationUnit(
            unit_id=unit_id,
            code=_string(item["code"]),
            name=_string(item["name"]),
            kind=OrganisationKind(str(item["kind"])),
            routing_enabled=routing_enabled,
            staffing_status=StaffingStatus(str(item["staffingStatus"])),
            sort_order=_nonnegative_int(item["sortOrder"]),
        )
    return units


def _staffing_status(
    unit: Any, staffing: Mapping[UUID, StaffingCount]
) -> StaffingStatus:
    if unit.kind is not OrganisationKind.TEAM:
        return StaffingStatus.ROUTING_POOL
    count = staffing.get(unit.unit_id, StaffingCount())
    if (
        count.managers >= unit.minimum_managers
        and count.analysts >= unit.minimum_analysts
    ):
        return StaffingStatus.STAFFED
    return StaffingStatus.UNSTAFFED


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("value must be an object")
    return value


def _sequence(value: Any) -> Sequence[Any]:
    if not isinstance(value, list):
        raise TypeError("value must be an array")
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("value must be a non-empty string")
    return value


def _strings(value: Any) -> list[str]:
    return [_string(item) for item in _sequence(value)]


def _positive_int(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise TypeError("value must be a positive integer")
    return value


def _nonnegative_int(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TypeError("value must be a non-negative integer")
    return value
