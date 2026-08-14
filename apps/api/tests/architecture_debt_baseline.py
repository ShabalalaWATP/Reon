"""Explicit, shrinking baselines for architecture fitness tests."""

# Counts are ceilings for legacy modules, not approved architecture. Remove a
# module as soon as its concrete dependencies move to composition.
SERVICE_INFRASTRUCTURE_DEBT: dict[str, int] = {}
ROUTER_INFRASTRUCTURE_DEBT: dict[str, int] = {}
REPOSITORY_SERVICE_DEBT: dict[str, int] = {}
IMPORT_CYCLE_DEBT: set[tuple[str, ...]] = set()
WIDE_PORT_DEBT: dict[str, int] = {}
SOURCE_HEADROOM_DEBT: dict[str, int] = {}
RAW_PROTECTED_KEY_DEBT: set[str] = set()
FRONTEND_API_PATH_DEBT: set[str] = set()
