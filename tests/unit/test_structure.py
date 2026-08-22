"""Guard rails for the package layout: everything imports and every reference resolves.

These run without any backend (no Postgres/Redis/MinIO/LLM) and are the fastest way
to catch a bad move/rename after a refactor.
"""

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

import app
from app.core.config import settings

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = ["app", "tests", "examples", "scripts"]


def py_files():
    for root in SOURCE_ROOTS:
        for path in (ROOT / root).rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path


ALL_MODULES = [m.name for m in pkgutil.walk_packages(app.__path__, "app.")]


@pytest.mark.parametrize("module", ALL_MODULES)
def test_module_imports(module):
    importlib.import_module(module)


def test_every_prompt_reference_resolves():
    """After the per-agent prompt split, `Prompts.X` must exist in the module imported."""
    problems = []
    for path in py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prompt_module = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(a.name == "Prompts" for a in node.names):
                    prompt_module = node.module
        if not prompt_module:
            continue
        prompts = importlib.import_module(prompt_module).Prompts
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Prompts"
                and not hasattr(prompts, node.attr)
            ):
                problems.append(f"{path.relative_to(ROOT)}:{node.lineno} -> {prompt_module}.Prompts.{node.attr}")
    assert not problems, problems


def test_every_settings_attribute_exists():
    problems = []
    for path in py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = {"settings"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "config" in node.module:
                aliases |= {a.asname or a.name for a in node.names if a.name == "settings"}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and not hasattr(settings, node.attr)
            ):
                problems.append(f"{path.relative_to(ROOT)}:{node.lineno} -> settings.{node.attr}")
    assert not problems, problems


def test_every_internal_import_resolves():
    """Covers lazy imports inside functions, which plain module import cannot reach."""
    problems = []
    for path in py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module):
                continue
            if not node.module.startswith(("app.", "tests.", "scripts.")):
                continue
            try:
                module = importlib.import_module(node.module)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{path.relative_to(ROOT)}:{node.lineno} -> {node.module}: {exc}")
                continue
            for alias in node.names:
                if alias.name == "*" or hasattr(module, alias.name):
                    continue
                try:
                    importlib.import_module(f"{node.module}.{alias.name}")
                except Exception:  # noqa: BLE001
                    problems.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} -> {node.module} has no '{alias.name}'"
                    )
    assert not problems, problems


def test_package_exports_resolve():
    problems = []
    for name in ALL_MODULES:
        module = importlib.import_module(name)
        for symbol in getattr(module, "__all__", []) or []:
            if not hasattr(module, symbol):
                problems.append(f"{name}.__all__ lists missing '{symbol}'")
    assert not problems, problems


LAYERS = {
    "app/agents": ["app.api"],
    "app/orchestrator": ["app.api"],
    "app/services": ["app.api"],
    "app/infra": ["app.api", "app.services", "app.agents"],
    "app/core": ["app.api", "app.services", "app.agents", "app.infra"],
}


def test_dependency_rule_is_one_way():
    """api -> services -> orchestrator -> agents -> infra -> core -> db. Never backwards."""
    problems = []
    for layer, forbidden in LAYERS.items():
        for path in (ROOT / layer).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                elif isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                for module in modules:
                    for bad in forbidden:
                        if module == bad or module.startswith(bad + "."):
                            problems.append(f"{path.relative_to(ROOT)}:{node.lineno} imports {module}")
    assert not problems, problems


HOME_MARKER = "/" + "home" + "/"


def test_no_absolute_paths_hardcoded():
    problems = [
        f"{p.relative_to(ROOT)}"
        for p in py_files()
        if p != Path(__file__) and HOME_MARKER in p.read_text(encoding="utf-8")
    ]
    assert not problems, f"dùng app.core.paths thay vì đường dẫn tuyệt đối: {problems}"


def test_db_models_and_dto_stay_separate():
    import app.schemas as schemas

    leaked = [n for n in dir(schemas) if getattr(getattr(schemas, n), "__tablename__", None)]
    assert not leaked, f"SQLModel table lọt vào app.schemas: {leaked}"
