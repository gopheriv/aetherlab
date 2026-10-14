"""Static safety gate for LLM-generated Manim scene code.

This module owns *safety*, not *syntax*. It uses only the standard-library
``ast`` module and imports nothing from the rest of the project, so it can be
reused (and unit-tested) in isolation and can never be the source of a circular
import in the pipeline.

The gate is deliberately conservative and *fail-closed*: any code that reaches
the renderer must first pass :func:`validate_code_safety`. Generated scenes are
executed by Manim in a subprocess with full interpreter privileges, so an
unguarded scene is a genuine arbitrary-code-execution hole. This blocks the
common sandbox-escape and side-effect vectors while still accepting the
libraries a legitimate Manim scene needs.
"""

from __future__ import annotations

import ast

# Modules a legitimate Manim scene may import. Everything else is rejected.
ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "manim",
        "manimlib",
        "numpy",
        "math",
        "random",
        "itertools",
        "functools",
        "typing",
        "__future__",
        "cmath",
        "fractions",
        "decimal",
        # Pure colour-space maths (HSV/HLS <-> RGB), no I/O. MiniMax reaches
        # for it to colour blackbody glows (live 2026-10-02).
        "colorsys",
    }
)

# Builtins that enable code execution, dynamic import, or host I/O. Using any of
# these names (called or merely referenced) is rejected.
BANNED_NAMES: frozenset[str] = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "__import__",
        "__builtins__",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "dir",
        "type",
    }
)

# Attribute names used by the classic ``().__class__.__bases__[0].__subclasses__()``
# style sandbox-escape chains, plus dunder handles that leak the import machinery.
BANNED_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "__globals__",
        "__builtins__",
        "__class__",
        "__dict__",
        "__subclasses__",
        "__bases__",
        "__mro__",
        "__import__",
        "__code__",
        "__getattribute__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__loader__",
        "__spec__",
    }
)

# ``numpy`` is a legitimate scientific import, but its file-I/O surface is an
# arbitrary host read/write vector no real Manim scene needs: raw-array
# read/write (``ndarray.tofile`` / ``numpy.fromfile`` / ``frombuffer``), text
# load/save to an exact path (``savetxt`` / ``loadtxt`` / ``genfromtxt``),
# pickle-bearing ``load``/``save``, memory-mapping, and ``DataSource`` URL
# fetches. A raw ``tofile``/``savetxt`` to a Startup folder is arbitrary file
# write -> code execution. None of these attribute names appear in legitimate
# generated scenes, so any use of them is rejected as an attribute sink.
BANNED_IO_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "tofile",
        "fromfile",
        "frombuffer",
        "fromstring",
        "fromregex",
        "save",
        "savez",
        "savez_compressed",
        "savetxt",
        "load",
        "loadtxt",
        "genfromtxt",
        "dump",
        "memmap",
        "DataSource",
    }
)


def _top_level_module(name: str) -> str:
    """Return the leading component of a dotted module path (``a.b.c`` -> ``a``)."""
    return name.split(".", 1)[0]


def validate_code_safety(code: str) -> tuple[bool, list[str]]:
    """Statically check generated scene code for unsafe constructs.

    Returns ``(is_safe, issues)``. ``is_safe`` is ``True`` when no unsafe
    construct was found. ``issues`` is a list of human-readable descriptions of
    every problem found (empty when safe).

    Syntax is *not* this module's concern: if the code does not parse, the gate
    returns ``(True, [])`` and defers to the caller's existing ``compile()``
    check so a single syntax error is never reported twice.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Not our job — the compile() gate owns syntax errors.
        return True, []

    issues: list[str] = []

    for node in ast.walk(tree):
        # --- imports ---------------------------------------------------------
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = _top_level_module(alias.name)
                if top not in ALLOWED_IMPORTS:
                    issues.append(
                        f"Disallowed import '{alias.name}' (line {node.lineno}): "
                        f"module '{top}' is not in the allowlist."
                    )
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (``from . import x``) have no importable top-level
            # module name and are never legitimate in a standalone scene.
            if node.level and node.level > 0:
                issues.append(
                    f"Disallowed relative import (line {node.lineno})."
                )
                continue
            top = _top_level_module(node.module or "")
            if top not in ALLOWED_IMPORTS:
                issues.append(
                    f"Disallowed import 'from {node.module} ...' (line {node.lineno}): "
                    f"module '{top}' is not in the allowlist."
                )
        # --- banned name references -----------------------------------------
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES:
                issues.append(
                    f"Use of banned builtin '{node.id}' (line {node.lineno})."
                )
        # --- banned attribute access (sandbox escapes) ----------------------
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRIBUTES:
                issues.append(
                    f"Access to banned attribute '{node.attr}' (line {node.lineno})."
                )
            elif node.attr in BANNED_IO_ATTRIBUTES:
                issues.append(
                    f"Access to banned file-I/O method '{node.attr}' (line {node.lineno}): "
                    "raw/host file read/write is not allowed in scene code."
                )
        # --- string-based dunder escape helpers -----------------------------
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in BANNED_ATTRIBUTES or node.value in BANNED_NAMES:
                issues.append(
                    f"Reference to banned runtime handle '{node.value}' (line {node.lineno})."
                )

    return (not issues), issues
