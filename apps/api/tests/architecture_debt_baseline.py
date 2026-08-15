"""Explicit, shrinking baselines for architecture fitness tests."""

# Counts are ceilings for legacy modules, not approved architecture. Remove a
# module as soon as its concrete dependencies move to composition.
SERVICE_INFRASTRUCTURE_DEBT: dict[str, int] = {}
ROUTER_INFRASTRUCTURE_DEBT: dict[str, int] = {}
REPOSITORY_SERVICE_DEBT: dict[str, int] = {}
IMPORT_CYCLE_DEBT: set[tuple[str, ...]] = set()
# Composition-facing unions that hand one consumer every method of several
# narrow ports. The width check now resolves inherited methods, so these are
# measured rather than hidden. Each entry is a ceiling: split the consumer's
# dependency and lower the number, never raise it.
_PRODUCT_PORTS = "mist_service.services.product_repository_port"
WIDE_PORT_DEBT: dict[str, int] = {
    "mist_service.admin_ports:AdminApplicationPort": 18,
    "mist_service.board_ports:BoardRepositoryPort": 19,
    "mist_service.calendar_ports:CalendarRepositoryPort": 13,
    "mist_service.platform_security_ports:PlatformSecurityApplicationPort": 17,
    "mist_service.services.configuration_ports:ConfigurationApplicationPort": 16,
    f"{_PRODUCT_PORTS}:ProductPackageServiceRepository": 24,
    f"{_PRODUCT_PORTS}:ProductReleaseServiceRepository": 24,
    f"{_PRODUCT_PORTS}:ProductRepository": 36,
    f"{_PRODUCT_PORTS}:ProductUploadServiceRepository": 25,
}
SOURCE_HEADROOM_DEBT: dict[str, int] = {}
RAW_PROTECTED_KEY_DEBT: set[str] = set()
FRONTEND_API_PATH_DEBT: set[str] = set()
