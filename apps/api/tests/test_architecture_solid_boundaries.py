"""SOLID, dependency-direction and source-headroom architecture ratchets."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

from architecture_debt_baseline import (
    FRONTEND_API_PATH_DEBT,
    IMPORT_CYCLE_DEBT,
    RAW_PROTECTED_KEY_DEBT,
    REPOSITORY_SERVICE_DEBT,
    ROUTER_INFRASTRUCTURE_DEBT,
    SERVICE_INFRASTRUCTURE_DEBT,
    SOURCE_HEADROOM_DEBT,
    WIDE_PORT_DEBT,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND = PROJECT_ROOT / "apps/api/src/istari_service"
FRONTEND = PROJECT_ROOT / "apps/web/src"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _backend_paths() -> list[Path]:
    return sorted(BACKEND.rglob("*.py"))


def _module(path: Path) -> str:
    relative = path.relative_to(BACKEND.parent).with_suffix("")
    return ".".join(relative.parts)


def _resolved_imports(path: Path) -> set[str]:
    current_package = _module(path).split(".")[:-1]
    result: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(current_package) - node.level + 1
                prefix = current_package[: max(keep, 0)]
                if node.module:
                    result.add(".".join([*prefix, node.module]))
                else:
                    result.update(
                        ".".join([*prefix, alias.name]) for alias in node.names
                    )
            elif node.module:
                result.add(node.module)
    return {module for module in result if module}


def _debt_edges(source: str, target_prefixes: tuple[str, ...]) -> set[str]:
    root = BACKEND / source
    return {
        f"{_module(path)} -> {imported}"
        for path in sorted(root.glob("*.py"))
        for imported in _resolved_imports(path)
        if imported.startswith(target_prefixes)
    }


def _debt_import_counts(source: str, targets: tuple[str, ...]) -> dict[str, int]:
    edges = _debt_edges(source, targets)
    return dict(
        Counter(edge.split(" -> ", maxsplit=1)[0].rsplit(".", 1)[-1] for edge in edges)
    )


def _internal_graph() -> dict[str, set[str]]:
    paths = _backend_paths()
    modules = {_module(path) for path in paths}
    graph: dict[str, set[str]] = {}
    for path in paths:
        imported = _resolved_imports(path)
        graph[_module(path)] = {
            candidate
            for candidate in imported
            if candidate in modules and candidate != _module(path)
        }
    return graph


def _strong_components(graph: dict[str, set[str]]) -> set[tuple[str, ...]]:
    """Return deterministic non-trivial Tarjan components."""

    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    stacked: set[str] = set()
    components: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        stacked.add(node)
        for child in sorted(graph[node]):
            if child not in indexes:
                visit(child)
                lowlinks[node] = min(lowlinks[node], lowlinks[child])
            elif child in stacked:
                lowlinks[node] = min(lowlinks[node], indexes[child])
        if lowlinks[node] != indexes[node]:
            return
        component: list[str] = []
        while stack:
            child = stack.pop()
            stacked.remove(child)
            component.append(child)
            if child == node:
                break
        if len(component) > 1:
            components.add(tuple(sorted(component)))

    for node in sorted(graph):
        if node not in indexes:
            visit(node)
    return components


def _protocol_widths() -> dict[str, int]:
    widths: dict[str, int] = {}
    for path in _backend_paths():
        for node in _tree(path).body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {base.id for base in node.bases if isinstance(base, ast.Name)} | {
                base.attr for base in node.bases if isinstance(base, ast.Attribute)
            }
            if "Protocol" not in bases:
                continue
            count = sum(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                for child in node.body
            )
            if count > 12:
                widths[f"{_module(path)}:{node.name}"] = count
    return widths


def _source_over_headroom() -> dict[str, int]:
    paths = [*_backend_paths(), *_frontend_production_paths()]
    result: dict[str, int] = {}
    for path in paths:
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > 330:
            result[path.relative_to(PROJECT_ROOT).as_posix()] = count
    return result


def _frontend_production_paths() -> list[Path]:
    return sorted(
        path
        for suffix in ("*.ts", "*.tsx")
        for path in FRONTEND.rglob(suffix)
        if ".test." not in path.name and path.name != "setup.ts"
    )


def _frontend_matches(needle: str) -> set[str]:
    return {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in _frontend_production_paths()
        if needle in path.read_text(encoding="utf-8")
    }


def _frontend_regex(pattern: str) -> set[str]:
    expression = re.compile(pattern)
    return {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in _frontend_production_paths()
        if expression.search(path.read_text(encoding="utf-8"))
    }


def _assert_exact_debt(actual: set[str], expected: set[str], label: str) -> None:
    assert actual == expected, (
        f"{label} changed. Remove remediated entries or reject new debt. "
        f"Added={sorted(actual - expected)}; removed={sorted(expected - actual)}"
    )


def test_services_do_not_add_concrete_infrastructure_dependencies() -> None:
    composition_modules = tuple(
        _module(path) for path in BACKEND.glob("*_composition.py")
    )
    actual = _debt_import_counts(
        "services",
        (
            "istari_service.repositories",
            *composition_modules,
            "sqlalchemy",
        ),
    )
    assert actual == SERVICE_INFRASTRUCTURE_DEBT, (
        "Service infrastructure-import counts changed. Reduce the debt map after "
        f"remediation or reject new coupling. Actual={actual}"
    )


def test_repositories_do_not_add_reverse_service_dependencies() -> None:
    actual = _debt_import_counts("repositories", ("istari_service.services",))
    assert actual == REPOSITORY_SERVICE_DEBT, (
        "Repository service-import counts changed. Reduce the debt map after "
        f"remediation or reject new reverse coupling. Actual={actual}"
    )


def test_routers_do_not_add_concrete_persistence_dependencies() -> None:
    actual = _debt_import_counts(
        "routers", ("istari_service.repositories", "sqlalchemy")
    )
    assert actual == ROUTER_INFRASTRUCTURE_DEBT, (
        "Router infrastructure-import counts changed. Move construction to "
        f"composition or reject new coupling. Actual={actual}"
    )


def test_backend_import_cycles_do_not_grow() -> None:
    actual = _strong_components(_internal_graph())
    assert actual == IMPORT_CYCLE_DEBT, (
        "Backend import-cycle debt changed. Remove remediated components or reject "
        f"new cycles. Actual={sorted(actual)}"
    )


def test_application_ports_are_narrow_or_explicit_debt() -> None:
    actual = _protocol_widths()
    assert actual.keys() == WIDE_PORT_DEBT.keys() and all(
        actual[name] <= limit for name, limit in WIDE_PORT_DEBT.items()
    ), (
        "Ports above 12 methods changed. Split capabilities or shrink the explicit "
        f"debt map. Actual={actual}"
    )


def test_source_files_retain_refactoring_headroom() -> None:
    actual = _source_over_headroom()
    assert actual.keys() == SOURCE_HEADROOM_DEBT.keys() and all(
        actual[path] <= limit for path, limit in SOURCE_HEADROOM_DEBT.items()
    ), (
        "Source above the 330-line refactoring target changed. New files must stay "
        f"within headroom; shrink the map after splitting legacy files. Actual={actual}"
    )


def test_frontend_api_access_remains_isolated() -> None:
    raw_fetch = _frontend_regex(r"(?<![A-Za-z])fetch\(")
    assert raw_fetch <= {
        "apps/web/src/lib/api/productClient.ts",
        "apps/web/src/lib/api/transport.ts",
    }, f"Raw fetch escaped the API adapter boundary: {sorted(raw_fetch)}"
    api_paths = {
        path
        for path in _frontend_matches("/api/v1")
        if not path.startswith("apps/web/src/lib/api/")
    }
    _assert_exact_debt(api_paths, FRONTEND_API_PATH_DEBT, "frontend API-path debt")


def test_protected_query_keys_use_the_central_factory() -> None:
    factory = (FRONTEND / "lib/api/queryKeys.ts").read_text(encoding="utf-8")
    assert re.search(
        r'const root = \[\s*"protected",\s*scope\.userId,\s*'
        r"scope\.activeContext,\s*scope\.contextVersion",
        factory,
    ), "Protected keys must include stable identity, actor context and version"
    raw_keys = _frontend_matches('["protected"') - {"apps/web/src/lib/api/queryKeys.ts"}
    _assert_exact_debt(raw_keys, RAW_PROTECTED_KEY_DEBT, "raw protected-key debt")
