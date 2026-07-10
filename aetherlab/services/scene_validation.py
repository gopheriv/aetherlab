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

``scene_hygiene_warnings`` adds NIMA-inspired layout/readability heuristics:
repeated same-coordinate placement without cleanup, object accumulation,
stale copies, abrupt ``self.clear()``, and dominant unstyled grids. These are
advisory because some advanced scenes intentionally keep ghost overlays/trails.

``validate_scene`` bundles the three hard checks into one verdict. Duration and
scene hygiene are advisory-only (fallback templates are deliberately short).

Leaf module: stdlib + (lazily) the installed manim for ground truth.
"""

from __future__ import annotations

import ast
import builtins
import io
import inspect
import re
import tokenize
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

_MANIM_COLOR_NAMES = {
    "BLACK", "WHITE", "BLUE", "GREEN", "RED", "YELLOW", "TEAL", "PURPLE",
    "MAROON", "GOLD", "ORANGE", "PINK", "LIGHT_PINK", "DARK_BLUE",
    "DARK_BROWN", "LIGHT_BROWN", "GRAY", "GREY", "GRAY_BROWN", "GREY_BROWN",
    "LIGHT_GRAY", "LIGHT_GREY", "DARK_GRAY", "DARK_GREY", "LIGHTER_GRAY",
    "LIGHTER_GREY", "DARKER_GRAY", "DARKER_GREY", "PURE_RED", "PURE_GREEN",
    "PURE_BLUE", "PURE_CYAN", "PURE_MAGENTA", "PURE_YELLOW", "LOGO_BLACK",
    "LOGO_WHITE", "LOGO_BLUE", "LOGO_GREEN", "LOGO_RED",
    *{
        f"{base}_{suffix}"
        for base in (
            "BLUE", "GREEN", "RED", "YELLOW", "TEAL", "PURPLE", "MAROON",
            "GOLD", "GRAY", "GREY",
        )
        for suffix in "ABCDE"
    },
}
_COLOR_ALIASES = {
    "BROWN": "DARK_BROWN",
    "CYAN": "PURE_CYAN",
    "MAGENTA": "PURE_MAGENTA",
    "NAVY": "DARK_BLUE",
    "SILVER": "LIGHT_GRAY",
    "LIME": "GREEN",
    "AQUA": "TEAL",
}
_COLOR_FAMILIES = (
    "BLUE", "GREEN", "RED", "YELLOW", "TEAL", "PURPLE", "MAROON", "GOLD",
    "ORANGE", "PINK", "GRAY", "GREY", "BROWN", "CYAN", "MAGENTA", "WHITE", "BLACK",
)


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


def _nearest_color_name(name: str, available: set[str]) -> str | None:
    if name in _COLOR_ALIASES:
        return _COLOR_ALIASES[name]
    parts = set(name.split("_"))
    for family in _COLOR_FAMILIES:
        if family not in parts:
            continue
        base = _COLOR_ALIASES.get(family, family)
        for prefix in ("DARK", "LIGHT", "PURE"):
            candidate = f"{prefix}_{base}"
            if prefix in parts and candidate in available:
                return candidate
        if base in available:
            return base
    return None


def repair_unknown_color_constants(code: str) -> tuple[str, dict[str, str]]:
    """Map invented all-caps color identifiers to real Manim constants.

    Only unknown names in Load context are candidates. Tokenization performs
    the replacement so strings, comments, attributes, and user definitions are
    never rewritten. If Manim is unavailable, the pinned built-in color list is
    still enough for this fail-soft repair.
    """
    tree = _parse(code)
    if tree is None:
        return code, {}
    manim_ns = _manim_namespace()
    available = _MANIM_COLOR_NAMES | (manim_ns & _MANIM_COLOR_NAMES)
    defined = _module_defined_names(tree)
    known = manim_ns | defined | set(dir(builtins)) | _EXTRA_KNOWN
    replacements: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id.isupper()
            and node.id not in known
        ):
            continue
        replacement = _nearest_color_name(node.id, available)
        if replacement:
            replacements[node.id] = replacement
    if not replacements:
        return code, {}
    tokens = tokenize.generate_tokens(io.StringIO(code).readline)
    fixed = tokenize.untokenize(
        token._replace(string=replacements.get(token.string, token.string))
        if token.type == tokenize.NAME
        else token
        for token in tokens
    )
    return fixed, replacements


_DYNAMIC_ANIMATIONS = {
    "Transform", "ReplacementTransform", "TransformFromCopy", "TransformMatchingShapes",
    "TransformMatchingTex", "MoveAlongPath", "Rotate", "ApplyMethod", "ApplyFunction",
    "UpdateFromFunc", "UpdateFromAlphaFunc", "Restore", "Swap",
}


def motion_contract_issues(code: str) -> list[str]:
    """Reject provably static generated scenes without judging artistic style."""
    tree = _parse(code)
    if tree is None:
        return []
    plays = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr == "play"
    ]
    if not plays:
        return [
            "[MOTION:NO_PLAY] Scene has no self.play animation; a static add()/wait() "
            "scene cannot satisfy the visible-motion contract."
        ]
    call_names = {
        _call_name(node.func).split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    has_animate = any(
        isinstance(node, ast.Attribute) and node.attr == "animate"
        for node in ast.walk(tree)
    )
    has_updater = bool(call_names & {"add_updater", "always_redraw", "TracedPath"})
    has_transform = bool(call_names & _DYNAMIC_ANIMATIONS)
    if not (has_animate or has_updater or has_transform):
        return [
            "[MOTION:REVEAL_ONLY] Scene only reveals static objects; use .animate, "
            "Transform/MoveAlongPath, or an updater so the physics evolves on-screen."
        ]
    return []


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


_INTRO_ANIMS = {
    "Create", "Write", "FadeIn", "GrowFromCenter", "GrowArrow",
    "DrawBorderThenFill", "ShowCreation",
}
_CLEANUP_ANIMS = {"FadeOut", "ReplacementTransform", "Transform", "Uncreate"}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _assignment_owner(tree: ast.Module, call: ast.Call) -> str | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or node.value is not call:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                return target.id
    return None


def _placement_owner(tree: ast.Module, call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return call.func.value.id
    return _assignment_owner(tree, call)


def _has_cleanup_between(lines: list[str], first: int, second: int, owner: str) -> bool:
    between = "\n".join(lines[max(first, 0):max(second - 1, first)])
    return (
        f"FadeOut({owner}" in between
        or f"Uncreate({owner}" in between
        or f"self.remove({owner}" in between
        or f"ReplacementTransform({owner}" in between
        or f"Transform({owner}" in between
        or "FadeOut(*self.mobjects" in between
    )


def _placement_warnings(code: str, tree: ast.Module) -> list[str]:
    lines = code.splitlines()
    placements: dict[str, list[tuple[str, int, str]]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "move_to"
            and node.args
        ):
            continue
        owner = _placement_owner(tree, node)
        if not owner:
            continue
        pos = ast.get_source_segment(code, node.args[0]) or ""
        norm = re.sub(r"\s+", "", pos)
        if norm:
            placements.setdefault(norm, []).append((owner, node.lineno, pos))

    warnings: list[str] = []
    for _norm, owners in placements.items():
        if len(owners) < 2:
            continue
        owners = sorted(owners, key=lambda x: x[1])
        for (prev_owner, prev_line, pos), (owner, line, _pos) in zip(owners, owners[1:]):
            if owner == prev_owner or _has_cleanup_between(lines, prev_line, line, prev_owner):
                continue
            warnings.append(
                f"[HYGIENE:OVERLAP] {prev_owner} (line {prev_line}) and {owner} "
                f"(line {line}) both move_to({pos}) without cleanup of {prev_owner}."
            )
            break
    return warnings


def _copy_warnings(code: str) -> list[str]:
    warnings: list[str] = []
    for match in re.finditer(r"\b(\w+)\.copy\(\)", code):
        original = match.group(1)
        line_no = code[:match.start()].count("\n") + 1
        after = "\n".join(code[match.end():].splitlines()[:20])
        if not any(
            token in after
            for token in (
                f"FadeOut({original}", f"Uncreate({original}", f"self.remove({original}",
                f"ReplacementTransform({original}", f"Transform({original}",
            )
        ):
            warnings.append(
                f"[HYGIENE:STALE_COPY] {original}.copy() at line {line_no} has no "
                "nearby FadeOut/Transform/remove for the original."
            )
    return warnings


def scene_hygiene_warnings(code: str) -> list[str]:
    """Return advisory warnings for likely visual layout bugs."""
    tree = _parse(code)
    if tree is None:
        return []
    warnings: list[str] = []
    warnings.extend(_placement_warnings(code, tree))

    call_names = [
        _call_name(node.func).split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    ]
    intro_count = sum(1 for name in call_names if name in _INTRO_ANIMS)
    cleanup_count = sum(1 for name in call_names if name in _CLEANUP_ANIMS)
    if intro_count >= 12 and cleanup_count < max(2, intro_count // 4):
        warnings.append(
            f"[HYGIENE:ACCUMULATION] {intro_count} introduced objects but only "
            f"{cleanup_count} cleanup/transform calls; high clutter risk."
        )

    if re.search(r"\bself\.clear\(\)", code):
        warnings.append(
            "[HYGIENE:CLEAR] self.clear() abruptly wipes continuity; prefer "
            "self.play(FadeOut(*self.mobjects)) or section cleanup."
        )
    if re.search(r"\bNumberPlane\s*\(\s*\)", code) and "stroke_opacity" not in code:
        warnings.append(
            "[HYGIENE:GRID] Bare NumberPlane() lacks subtle stroke_opacity styling; "
            "the grid can dominate the physics."
        )
    if re.search(r"\w+\s*\[\s*\d+\s*\]\s*\[\s*\d+\s*\]", code):
        warnings.append(
            "[HYGIENE:MATH_INDEX] Deep MathTex indexing is fragile; prefer "
            "get_part_by_tex(), set_color_by_tex(), or TransformMatchingTex."
        )

    warnings.extend(_copy_warnings(code))
    return warnings


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


def validate_scene(code: str, *, require_motion: bool = False) -> tuple[bool, list[str]]:
    """Run the three hard gates. Returns (ok, issues). Duration is not part of
    the verdict — callers surface it as an advisory diagnostic."""
    issues = lint_manim_names(code) + lint_constructor_kwargs(code) + check_latex_strings(code)
    if require_motion:
        issues.extend(motion_contract_issues(code))
    return (not issues), issues
