"""Static pre-render validation for generated Manim scenes.

The compile() gate catches syntax only; the dominant real-world failures —
hallucinated API names, invalid constructor kwargs, broken LaTeX — all pass it
and die (or misbehave) at render time. This battery catches those *before* the
expensive render, converting crash-repair cycles into first-try successes.

Three checks, all AST-based and conservative (they only flag what is provably
wrong against the *installed* Manim, never guesses):

1. ``lint_manim_names``  — unknown top-level names (classic ManimGL leftovers
   like ``ShowCreation``/``TexMobject`` that NameError at render).
2. ``lint_constructor_kwargs`` — keyword args that the target class's
   ``__init__`` provably does not accept (no ``**kwargs`` escape hatch).
3. ``check_latex_strings`` — structural validation of every MathTex/Tex string
   literal (balanced braces/environments — the top LaTeX crash causes).

Plus ``estimate_duration`` — an advisory beat-sum of play/wait run_times so the
pipeline can compare against its 15–22s contract without rendering.

``validate_scene`` bundles the three hard checks into one verdict. Duration is
advisory-only (fallback templates are deliberately short).

Leaf module: stdlib + (lazily) the installed manim for ground truth.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import re
from dataclasses import dataclass, field


# ── shared AST helpers ──────────────────────────────────────────────────────


def _parse(code: str) -> ast.Module | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None  # syntax is the compile() gate's job — never double-report


def _module_defined_names(tree: ast.Module) -> set[str]:
    """Names bound anywhere in the module (assignments, defs, args, loops...)."""
    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = node.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs]:
                defined.add(arg.arg)
            if a.vararg:
                defined.add(a.vararg.arg)
            if a.kwarg:
                defined.add(a.kwarg.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            defined.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                defined.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, (ast.comprehension,)):
            for tgt in ast.walk(node.target):
                if isinstance(tgt, ast.Name):
                    defined.add(tgt.id)
    return defined


def _manim_namespace() -> set[str]:
    try:
        import manim
    except Exception:  # pragma: no cover — manim optional at import time
        return set()
    return set(dir(manim))


_EXTRA_KNOWN = {"np", "self", "math", "numpy", "random", "itertools", "functools"}


# ── 1. unknown-name lint ────────────────────────────────────────────────────


def lint_manim_names(code: str) -> list[str]:
    """Flag loaded names that exist nowhere: not builtins, not module-defined,
    not in the installed manim's namespace. These are guaranteed NameErrors
    at render (``ShowCreation``, ``TexMobject``, invented rate functions...)."""
    tree = _parse(code)
    if tree is None:
        return []
    manim_ns = _manim_namespace()
    if not manim_ns:  # can't establish ground truth — stay silent, not wrong
        return []
    defined = _module_defined_names(tree)
    known = manim_ns | defined | set(dir(builtins)) | _EXTRA_KNOWN

    issues: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id not in known
            and node.id not in seen
        ):
            seen.add(node.id)
            issues.append(
                f"Unknown name '{node.id}' (line {node.lineno}) — not defined in the "
                "scene, Python builtins, or the installed Manim; this will NameError "
                "at render."
            )
    return issues


# ── 2. constructor-kwarg lint ───────────────────────────────────────────────


def lint_constructor_kwargs(code: str) -> list[str]:
    """Flag kwargs a Manim class constructor provably does not accept.

    Conservative: only checks direct ``ClassName(...)`` calls where ClassName
    resolves to a class in the installed manim whose ``__init__`` has **no**
    ``**kwargs`` catch-all. Anything with a catch-all is skipped (most Manim
    mobjects forward kwargs), so false positives are structurally impossible.
    """
    tree = _parse(code)
    if tree is None:
        return []
    try:
        import manim
    except Exception:  # pragma: no cover
        return []

    issues: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        cls = getattr(manim, node.func.id, None)
        if not inspect.isclass(cls):
            continue
        try:
            sig = inspect.signature(cls.__init__)
        except (ValueError, TypeError):
            continue
        params = sig.parameters
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            continue  # **kwargs catch-all — can't prove anything wrong
        accepted = {name for name in params if name != "self"}
        for kw in node.keywords:
            if kw.arg is not None and kw.arg not in accepted:
                issues.append(
                    f"{node.func.id}() got an invalid keyword '{kw.arg}' "
                    f"(line {node.lineno}); accepted: {', '.join(sorted(accepted)) or 'none'}."
                )
    return issues


# ── 3. LaTeX structural validation ──────────────────────────────────────────

_TEX_CALLS = {"MathTex", "Tex", "SingleStringMathTex"}
_ENV_RE = re.compile(r"\\(begin|end)\{([^{}]*)\}")


def _check_tex_source(tex: str) -> str | None:
    """Return a problem description for structurally broken LaTeX, else None."""
    # Brace balance (ignoring escaped braces).
    stripped = tex.replace(r"\{", "").replace(r"\}", "")
    depth = 0
    for ch in stripped:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return "unbalanced braces (extra '}')"
    if depth != 0:
        return "unbalanced braces (unclosed '{')"

    # \left / \right pairing.
    if stripped.count(r"\left") != stripped.count(r"\right"):
        return r"unbalanced \left/\right pair"

    # begin/end environment pairing (stack-based).
    stack: list[str] = []
    for kind, name in _ENV_RE.findall(tex):
        if kind == "begin":
            stack.append(name)
        elif not stack or stack.pop() != name:
            return rf"mismatched \begin/\end for environment '{name}'"
    if stack:
        return rf"unclosed environment '{stack[-1]}'"

    # Double superscript/subscript without braces is a classic crash.
    if re.search(r"\^[^{\s]\^", tex) or re.search(r"_[^{\s]_", tex):
        return "double superscript/subscript without braces"
    return None


def check_latex_strings(code: str) -> list[str]:
    """Structurally validate every literal string passed to MathTex/Tex."""
    tree = _parse(code)
    if tree is None:
        return []
    issues: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _TEX_CALLS
        ):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                problem = _check_tex_source(arg.value)
                if problem:
                    snippet = arg.value[:60].replace("\n", " ")
                    issues.append(
                        f"{node.func.id} LaTeX problem (line {node.lineno}): {problem} "
                        f"in '{snippet}'."
                    )
    return issues


# ── 4. advisory duration estimate ───────────────────────────────────────────


@dataclass
class DurationEstimate:
    total_seconds: float
    play_calls: int
    wait_calls: int
    notes: list[str] = field(default_factory=list)


def estimate_duration(code: str) -> DurationEstimate:
    """Statically sum self.play(run_time=...) and self.wait(...) durations.

    Manim defaults: play run_time=1.0, wait duration=1.0. Non-literal values
    count as the default and are noted. Advisory only — loops multiply beats
    in ways a static pass can't always see.
    """
    tree = _parse(code)
    est = DurationEstimate(0.0, 0, 0)
    if tree is None:
        return est
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
            continue
        if node.func.attr == "play":
            est.play_calls += 1
            run_time = 1.0
            for kw in node.keywords:
                if kw.arg == "run_time":
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, (int, float)):
                        run_time = float(kw.value.value)
                    else:
                        est.notes.append(f"non-literal run_time at line {node.lineno} (counted as 1s)")
            est.total_seconds += run_time
        elif node.func.attr == "wait":
            est.wait_calls += 1
            duration = 1.0
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, (int, float)):
                duration = float(node.args[0].value)
            est.total_seconds += duration
    # A rough flag for loops around play calls — static sums undercount them.
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "play"
                ):
                    est.notes.append("play() inside a loop — estimate is a lower bound")
                    break
            else:
                continue
            break
    return est


# ── bundle ──────────────────────────────────────────────────────────────────


def validate_scene(code: str) -> tuple[bool, list[str]]:
    """Run the three hard gates. Returns (ok, issues). Duration is not part of
    the verdict — callers surface it as an advisory diagnostic."""
    issues = lint_manim_names(code) + lint_constructor_kwargs(code) + check_latex_strings(code)
    return (not issues), issues
