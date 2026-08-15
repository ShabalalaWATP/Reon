"""Executable dependency-direction and thin-boundary fitness rules."""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path("src/mist_service")
FRAMEWORKS = ("fastapi", "sqlalchemy", "camunda_orchestration_sdk")
DOMAIN_POLICY_FILES = (
    "authorisation.py",
    "configuration_policy.py",
    "configuration_validation.py",
    "policies.py",
    "product_security.py",
    "text_safety.py",
)
BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match)
SQL_BUILDERS = {"select", "insert", "update", "delete", "and_", "or_"}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(tree: ast.AST) -> set[str]:
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }


def _is_endpoint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and isinstance(decorator.func.value, ast.Name)
        and decorator.func.value.id == "router"
        for decorator in node.decorator_list
    )


def test_domain_policy_is_framework_free() -> None:
    for filename in DOMAIN_POLICY_FILES:
        imports = _imports(_tree(SOURCE / filename))
        assert not any(module.startswith(FRAMEWORKS) for module in imports), filename


def test_business_http_endpoints_are_thin_and_sql_free() -> None:
    for path in (SOURCE / "routers").glob("*.py"):
        if path.name in {"__init__.py", "health.py"}:
            continue
        tree = _tree(path)
        assert not any(module.startswith("sqlalchemy") for module in _imports(tree)), (
            path.name
        )
        for node in tree.body:
            is_function = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            if is_function and _is_endpoint(node):
                assert len(node.body) <= 4, f"{path.name}:{node.name}"
                assert not any(
                    isinstance(child, BRANCH_NODES) for child in ast.walk(node)
                ), f"{path.name}:{node.name}"


def test_application_services_do_not_build_sql_expressions() -> None:
    for path in (SOURCE / "services").glob("*.py"):
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in SQL_BUILDERS, (
                    f"{path.name}:{node.lineno} builds SQL outside a repository"
                )


def test_repositories_do_not_import_http_or_camunda_frameworks() -> None:
    for path in (SOURCE / "repositories").glob("*.py"):
        imports = _imports(_tree(path))
        assert not any(
            module.startswith(("fastapi", "camunda_orchestration_sdk"))
            for module in imports
        ), path.name
