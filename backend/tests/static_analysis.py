"""
backend/tests/static_analysis.py
────────────────────────────────
AST helpers used by the architecture-constraint tests.

Text matching is not good enough here: a docstring that *describes* a rule
("MUST NOT import flask") would otherwise fail the very test that enforces it.
These helpers inspect the parsed syntax tree instead, so only real code counts.
"""

import ast
from functools import lru_cache


@lru_cache(maxsize=None)
def _parse(path: str) -> ast.Module:
    """Parse a Python source file into an AST, cached per path."""
    with open(path, encoding='utf-8') as handle:
        return ast.parse(handle.read(), filename=path)


def imported_modules(path: str) -> set[str]:
    """Collect every top-level module name imported by a source file.

    ``from firebase_admin import auth`` and ``import firebase_admin.auth`` both
    yield ``'firebase_admin'``.

    Args:
        path: Filesystem path to the Python module to inspect.

    Returns:
        Set of root module names actually imported by the code.
    """
    names: set[str] = set()
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split('.')[0])
    return names


def called_function_names(path: str) -> set[str]:
    """Collect the callee names of every call expression in a source file.

    ``open(...)`` yields ``'open'``; ``img.save(...)`` yields ``'save'``;
    ``os.path.join(...)`` yields ``'join'``.

    Args:
        path: Filesystem path to the Python module to inspect.

    Returns:
        Set of called function/method names.
    """
    names: set[str] = set()
    for node in ast.walk(_parse(path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def source_without_comments_or_docstrings(path: str) -> str:
    """Return the file's executable source with docstrings and comments stripped.

    Args:
        path: Filesystem path to the Python module to inspect.

    Returns:
        The unparsed AST as source text, which drops comments entirely and
        keeps docstrings only as inert string expressions.
    """
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)
