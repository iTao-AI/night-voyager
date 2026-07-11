from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_ROOTS = {"fastapi", "sqlalchemy", "night_voyager.adapters"}
PURE_ROOTS = (Path("src/night_voyager/domain"), Path("src/night_voyager/policy"))


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_pure_domain_and_policy_do_not_import_frameworks_or_adapters() -> None:
    violations: list[str] = []
    for root in PURE_ROOTS:
        for path in root.rglob("*.py") if root.exists() else ():
            for module in imported_modules(path):
                if any(module == item or module.startswith(f"{item}.") for item in FORBIDDEN_ROOTS):
                    violations.append(f"{path}: {module}")

    assert violations == []
