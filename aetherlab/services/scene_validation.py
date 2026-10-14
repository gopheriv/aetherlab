"""Static pre-render validation for generated Manim scenes.

The compile() gate catches syntax only; the dominant real-world failures —
hallucinated API names, invalid constructor kwargs, broken LaTeX — all pass it
and die (or misbehave) at render time. This battery catches those *before* the
expensive render, converting crash-repair cycles into first-try successes.

The AST gates are conservative (they only flag constructs that are invalid or
explicitly disallowed for the installed ManimCE target):

1. ``lint_manim_names``  — unknown top-level names (classic ManimGL leftovers
   like ``ShowCreation``/``TexMobject`` that NameError at render).
2. ``lint_constructor_kwargs`` — keyword args that the target class's
   ``__init__`` chain, when every ``**kwargs`` hop visibly forwards to a strict base.
3. ``lint_manim_method_kwargs`` — kwargs for direct calls on statically known
   Manim objects, when the installed method signature is conclusive.
4. ``lint_forbidden_manimgl`` — legacy constructs that must not be generated.
5. ``check_latex_strings`` — structural validation of every MathTex/Tex string
   literal (balanced braces/environments and required arguments on common
   fraction/binomial macros — frequent LaTeX crash causes).

Plus ``estimate_duration`` — an advisory beat-sum of play/wait run_times so the
pipeline can compare against the request's target-duration window without rendering.

``check_timeline_runtime`` compares literal play/wait budgets between beat
markers with their scheduled absolute windows. It skips loops and dynamic
durations that it cannot measure safely.

4. ``frame_rebuild_issues`` rejects Tex-family mobjects rebuilt by an updater
   or ``always_redraw`` (a per-frame LaTeX compile/cache storm).

``scene_hygiene_warnings`` adds NIMA-inspired layout/readability heuristics:
repeated same-coordinate placement without cleanup, object accumulation,
stale copies, abrupt ``self.clear()``, and dominant unstyled grids. These are
advisory because some advanced scenes intentionally keep ghost overlays/trails.

``validate_scene`` bundles the hard static and animation-safety checks into one
verdict. Duration and scene hygiene are advisory-only (fallback templates are
deliberately short).

Leaf module: stdlib + (lazily) the installed manim for ground truth.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import io
import math
import re
import textwrap
import tokenize
from dataclasses import dataclass, field
from functools import lru_cache

# ── shared AST helpers ──────────────────────────────────────────────────────


def _parse(code: str) -> ast.Module | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None  # syntax is the compile() gate's job — never double-report


def count_construct_play_calls(code: str) -> int:
    """Count syntactic ``self.play`` calls in the first scene's construct()."""
    tree = _parse(code)
    if tree is None:
        return 0
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        construct = next(
            (
                node for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "construct"
            ),
            None,
        )
        if construct is None:
            continue
        return sum(
            1
            for node in ast.walk(construct)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "play"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        )
    return 0


def check_updater_animation_conflicts(code: str) -> list[str]:
    """Flag a mobject animated while its updater also mutates that mobject."""
    tree = _parse(code)
    if tree is None:
        return []
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        construct = next(
            (
                node for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "construct"
            ),
            None,
        )
        if construct is None:
            continue
        active_updaters: set[str] = set()
        conflicts: set[str] = set()
        ordered_nodes = sorted(
            ast.walk(construct),
            key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0)),
        )
        for node in ordered_nodes:
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            receiver = node.func.value
            if (
                node.func.attr == "add_updater"
                and isinstance(receiver, ast.Name)
            ):
                active_updaters.add(receiver.id)
                continue
            if (
                node.func.attr == "clear_updaters"
                and isinstance(receiver, ast.Name)
            ):
                active_updaters.discard(receiver.id)
                continue
            if node.func.attr != "play" or not (
                isinstance(receiver, ast.Name) and receiver.id == "self"
            ):
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Attribute) or child.attr != "animate":
                    continue
                if isinstance(child.value, ast.Name) and child.value.id in active_updaters:
                    conflicts.add(child.value.id)
        return [
            f"[MANIM:UPDATER_ANIMATE] {name} is animated in self.play while it has "
            "an updater; animate its controlling ValueTracker or clear the updater first."
            for name in sorted(conflicts)
        ]
    return []


def check_dynamic_numeric_fade_conflicts(code: str) -> list[str]:
    """Catch live numeric readouts whose family changes during an entrance.

    A DecimalNumber/Integer can gain or lose glyph submobjects as an updater
    changes its ValueTracker. If it is also shown in that same ``self.play``,
    Manim interpolates the old and new families and raises a zip-length
    ValueError. Fade the readout in during an earlier call, then animate its
    tracker separately.
    """
    tree = _parse(code)
    if tree is None:
        return []
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        construct = next(
            (
                node for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "construct"
            ),
            None,
        )
        if construct is None:
            continue

        numeric_names: set[str] = set()
        for node in ast.walk(construct):
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            if not isinstance(value, ast.Call) or _call_name(value.func).split(".")[-1] not in {
                "DecimalNumber", "Integer",
            }:
                continue
            numeric_names.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )

        container_members: dict[str, set[str]] = {}
        for node in ast.walk(construct):
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            if value is None:
                continue
            group_calls = [
                call for call in ast.walk(value)
                if isinstance(call, ast.Call)
                and _call_name(call.func).split(".")[-1] in {"Group", "VGroup"}
            ]
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if group_calls:
                    container_members.setdefault(target.id, set()).update(
                        item.id
                        for call in group_calls
                        for argument in call.args
                        for item in ast.walk(argument)
                        if isinstance(item, ast.Name)
                    )

        for node in ast.walk(construct):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"add", "add_to_back", "add_to_front"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in container_members
            ):
                continue
            container_members[node.func.value.id].update(
                item.id
                for argument in node.args
                for item in ast.walk(argument)
                if isinstance(item, ast.Name)
            )

        controllers: dict[str, set[str]] = {}
        for node in ast.walk(construct):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_updater"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in numeric_names
            ):
                continue
            tracker_names = {
                access.value.id
                for argument in node.args
                for access in ast.walk(argument)
                if isinstance(access, ast.Attribute)
                and access.attr == "get_value"
                and isinstance(access.value, ast.Name)
            }
            if tracker_names:
                controllers[node.func.value.id] = tracker_names

        conflicts: set[tuple[str, str]] = set()
        for node in ast.walk(construct):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "play"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                continue
            names_in_play = {
                item.id for item in ast.walk(node) if isinstance(item, ast.Name)
            }
            animated_trackers = {
                item.value.id
                for item in ast.walk(node)
                if isinstance(item, ast.Attribute)
                and item.attr == "animate"
                and isinstance(item.value, ast.Name)
            }
            shown_readouts = set(controllers) & names_in_play
            pending_containers = list(container_members.keys() & names_in_play)
            inspected_containers: set[str] = set()
            while pending_containers:
                container = pending_containers.pop()
                if container in inspected_containers:
                    continue
                inspected_containers.add(container)
                members = container_members[container]
                shown_readouts.update(members & set(controllers))
                pending_containers.extend(
                    (members & container_members.keys()) - inspected_containers
                )
            for readout, tracker_names in controllers.items():
                active_trackers = tracker_names & animated_trackers
                if readout in shown_readouts and active_trackers:
                    conflicts.add((readout, ", ".join(sorted(active_trackers))))

        return [
            f"[MANIM:DYNAMIC_NUMBER_FADE] {readout} is shown while its changing "
            f"ValueTracker ({trackers}) is animated in the same self.play; fade "
            "the readout in first, then animate the tracker to avoid mismatched "
            "mobject families."
            for readout, trackers in sorted(conflicts)
        ]
    return []


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
_FORBIDDEN_MANIMGL = {
    "ShowCreation": "Create",
    "ShowCreationThenDestruction": "Create followed by FadeOut",
    "ShowCreationThenFadeOut": "Create followed by FadeOut",
    "TextMobject": "Text",
    "TexMobject": "MathTex",
    "GraphScene": "Axes inside a Scene",
    "ThreeDVMobject": "Surface or ParametricFunction",
}

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


def lint_forbidden_manimgl(code: str) -> list[str]:
    """Reject known ManimGL-era constructs in generated ManimCE scenes."""
    tree = _parse(code)
    if tree is None:
        return []
    issues: list[str] = []
    seen: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            if any(name == "manimlib" or name.startswith("manimlib.") for name in modules):
                key = ("manimlib", node.lineno)
                if key not in seen:
                    seen.add(key)
                    issues.append(
                        f"ManimGL import on line {node.lineno}; use the Manim Community `manim` package."
                    )
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in _FORBIDDEN_MANIMGL:
                        issues.append(
                            f"ManimGL construct '{alias.name}' imported on line {node.lineno}; "
                            f"use {_FORBIDDEN_MANIMGL[alias.name]} instead."
                        )
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_MANIMGL:
            key = (node.id, node.lineno)
            if key not in seen:
                seen.add(key)
                issues.append(
                    f"ManimGL construct '{node.id}' on line {node.lineno}; use "
                    f"{_FORBIDDEN_MANIMGL[node.id]} instead."
                )
        if isinstance(node, ast.ClassDef):
            for statement in node.body:
                targets = []
                if isinstance(statement, ast.Assign):
                    targets = statement.targets
                elif isinstance(statement, ast.AnnAssign):
                    targets = [statement.target]
                if any(isinstance(target, ast.Name) and target.id == "CONFIG" for target in targets):
                    issues.append(
                        f"ManimGL class-level CONFIG on line {statement.lineno}; "
                        "pass settings through the scene constructor instead."
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


# Spelled-out diagonals models invent for Manim's UR/UL/DR/DL (live: UP_RIGHT).
_DIRECTION_ALIASES = {
    "UP_RIGHT": "UR", "RIGHT_UP": "UR", "UPPER_RIGHT": "UR",
    "UP_LEFT": "UL", "LEFT_UP": "UL", "UPPER_LEFT": "UL",
    "DOWN_RIGHT": "DR", "RIGHT_DOWN": "DR", "LOWER_RIGHT": "DR",
    "DOWN_LEFT": "DL", "LEFT_DOWN": "DL", "LOWER_LEFT": "DL",
}


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
        replacement = _DIRECTION_ALIASES.get(node.id) or _nearest_color_name(node.id, available)
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


def _forwards_var_keyword_to_super(init, parameter_name: str) -> bool:
    """Prove an initializer directly forwards its **kwargs to super().__init__."""
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(init)))
    except (OSError, TypeError, SyntaxError):
        return False
    initializer = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        None,
    )
    if initializer is None:
        return False
    for statement in initializer.body:
        expression = None
        if isinstance(statement, ast.Expr):
            expression = statement.value
        elif isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Return)):
            expression = statement.value
        if not isinstance(expression, ast.Call):
            continue
        receiver = expression.func.value if isinstance(expression.func, ast.Attribute) else None
        if not (
            isinstance(expression.func, ast.Attribute)
            and expression.func.attr == "__init__"
            and isinstance(receiver, ast.Call)
            and isinstance(receiver.func, ast.Name)
            and receiver.func.id == "super"
        ):
            continue
        if any(
            keyword.arg is None
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == parameter_name
            for keyword in expression.keywords
        ):
            return True
    return False


@lru_cache(maxsize=512)
def _constructor_keyword_surface(cls) -> set[str] | None:
    """Return accepted keyword names if a **kwargs chain ends at a strict base.

    Manim often forwards styling keywords through several constructors. Only
    follow a catch-all when its source directly calls ``super().__init__(**kwargs)``;
    if source or forwarding is ambiguous, leave the class unchecked.
    """
    accepted: set[str] = set()
    for base in inspect.getmro(cls):
        if base is object:
            break
        init = base.__dict__.get("__init__")
        if init is None:
            continue
        try:
            params = inspect.signature(init).parameters
        except (ValueError, TypeError):
            return None
        accepted.update(
            parameter.name
            for parameter in params.values()
            if parameter.name not in {"self", "cls"}
            and parameter.kind in {
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
        )
        var_keyword = next(
            (
                parameter
                for parameter in params.values()
                if parameter.kind is inspect.Parameter.VAR_KEYWORD
            ),
            None,
        )
        if var_keyword is None:
            return accepted
        if not _forwards_var_keyword_to_super(init, var_keyword.name):
            return None
    return None


def lint_constructor_kwargs(code: str) -> list[str]:
    """Flag kwargs a Manim constructor chain provably does not accept.

    Direct class calls are checked against the installed Manim signatures.
    Forwarded ``**kwargs`` chains are checked only when each step is visible in
    Python source and ends at an initializer without a catch-all.
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
        accepted = _constructor_keyword_surface(cls)
        if accepted is None:
            continue  # cannot prove that unknown kwargs reach a strict base
        for kw in node.keywords:
            if kw.arg is not None and kw.arg not in accepted:
                issues.append(
                    f"{node.func.id}() got an invalid keyword '{kw.arg}' "
                    f"(line {node.lineno}); accepted: {', '.join(sorted(accepted)) or 'none'}."
                )
    return issues


def lint_manim_method_kwargs(code: str) -> list[str]:
    """Check method kwargs where a local variable is directly assigned a Manim class.

    This intentionally skips unknown receiver types and signatures with **kwargs;
    dynamic or forwarded arguments cannot be rejected safely by static analysis.
    """
    tree = _parse(code)
    if tree is None:
        return []
    try:
        import manim
    except Exception:  # pragma: no cover
        return []

    scene_class = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = _call_name(base).split(".")[-1]
            candidate = getattr(manim, base_name, None)
            if inspect.isclass(candidate) and base_name.endswith("Scene"):
                scene_class = candidate
                break
        if scene_class is not None:
            break

    receiver_classes: dict[str, type] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)):
            continue
        candidate = getattr(manim, value.func.id, None)
        if not inspect.isclass(candidate):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                receiver_classes[target.id] = candidate

    issues: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            continue
        owner = node.func.value.id
        cls = scene_class if owner == "self" else receiver_classes.get(owner)
        if cls is None:
            continue
        method = getattr(cls, node.func.attr, None)
        if not callable(method):
            continue
        try:
            params = inspect.signature(method).parameters
        except (TypeError, ValueError):
            continue
        if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in params.values()):
            continue
        accepted = [
            name for name, param in params.items()
            if name not in {"self", "cls"}
            and param.kind in {
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
        ]
        accepted_set = set(accepted)
        for keyword in node.keywords:
            if keyword.arg is not None and keyword.arg not in accepted_set:
                issues.append(
                    f"{owner}.{node.func.attr}() got an invalid keyword '{keyword.arg}' "
                    f"(line {node.lineno}); accepted: {', '.join(sorted(accepted)) or 'none'}."
                )
    return issues


def repair_scope_for_error(code: str, error: str) -> tuple[str, str, str | None]:
    """Return the narrowest function containing the traceback line, if known."""
    tree = _parse(code)
    if tree is None:
        return "whole scene", code, None
    line_numbers = re.findall(r"\bline\s+(\d+)\b", error or "", flags=re.IGNORECASE)
    if not line_numbers:
        return "whole scene", code, None
    failing_line = int(line_numbers[-1])
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= failing_line <= (node.end_lineno or node.lineno)
    ]
    if not functions:
        return "whole scene", code, None
    function = min(functions, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)
    source = ast.get_source_segment(code, function) or code
    return (
        f"function `{function.name}` (lines {function.lineno}-{function.end_lineno})",
        source,
        function.name,
    )


def manim_api_reference_context(code: str, error: str = "", max_items: int = 8) -> str:
    """Retrieve installed signatures for Manim calls in the failing function."""
    tree = _parse(code)
    if tree is None:
        return ""
    try:
        import manim
    except Exception:  # pragma: no cover
        return ""

    scope_tree: ast.AST = tree
    line_numbers = re.findall(r"\bline\s+(\d+)\b", error or "", flags=re.IGNORECASE)
    if line_numbers:
        line = int(line_numbers[-1])
        functions = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.lineno <= line <= (node.end_lineno or node.lineno)
        ]
        if functions:
            scope_tree = min(functions, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)

    scene_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = _call_name(base).split(".")[-1]
                candidate = getattr(manim, base_name, None)
                if inspect.isclass(candidate) and base_name.endswith("Scene"):
                    scene_class = candidate
                    break
        if scene_class is not None:
            break
    receiver_classes: dict[str, type] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                candidate = getattr(manim, value.func.id, None)
                if inspect.isclass(candidate):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            receiver_classes[target.id] = candidate

    refs: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(scope_tree):
        if not isinstance(node, ast.Call):
            continue
        label = _call_name(node.func)
        target = None
        if isinstance(node.func, ast.Name):
            target = getattr(manim, node.func.id, None)
            if inspect.isclass(target):
                target = target.__init__
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            owner = node.func.value.id
            cls = scene_class if owner == "self" else receiver_classes.get(owner)
            if cls is not None:
                target = getattr(cls, node.func.attr, None)
        if not label or label in seen or not callable(target):
            continue
        relevant = bool(node.keywords) or any(part in (error or "") for part in label.split("."))
        if not relevant:
            continue
        try:
            signature = str(inspect.signature(target))
        except (TypeError, ValueError):
            continue
        doc = inspect.getdoc(target) or ""
        first_line = " ".join(doc.splitlines()).strip()[:180]
        refs.append(f"- `{label}{signature}`" + (f": {first_line}" if first_line else ""))
        seen.add(label)
        if len(refs) >= max_items:
            break
    return "\n".join(refs)


# ── 3. LaTeX structural validation ──────────────────────────────────────────

_TEX_CALLS = {"MathTex", "Tex", "SingleStringMathTex"}
_ENV_RE = re.compile(r"\\(begin|end)\{([^{}]*)\}")
_TWO_ARGUMENT_TEX_COMMANDS = frozenset({
    "frac", "dfrac", "tfrac", "binom", "dbinom", "tbinom", "overset", "underset",
})


def _tex_argument_end(tex: str, start: int) -> int | None:
    """Return the end of one TeX token/group argument, or None if missing/broken."""
    i = start
    while i < len(tex) and tex[i].isspace():
        i += 1
    if i >= len(tex):
        return None

    if tex[i] == "{":
        depth = 1
        i += 1
        while i < len(tex):
            if tex[i] == "\\":
                # Escaped braces are literal characters within the group.
                i += 2
                continue
            if tex[i] == "{":
                depth += 1
            elif tex[i] == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return None

    if tex[i] == "\\":
        i += 1
        if i >= len(tex):
            return None
        if tex[i].isalpha():
            while i < len(tex) and tex[i].isalpha():
                i += 1
            return i
        return i + 1

    # TeX permits a single token (including one character) as an argument.
    return i + 1


def _check_required_tex_arguments(tex: str) -> str | None:
    """Catch missing mandatory arguments on common two-argument math macros."""
    i = 0
    while i < len(tex):
        if tex[i] != "\\" or i + 1 >= len(tex):
            i += 1
            continue
        if not tex[i + 1].isalpha():
            i += 2  # a control symbol such as \\ or \% is one token
            continue

        end = i + 2
        while end < len(tex) and tex[end].isalpha():
            end += 1
        command = tex[i + 1:end]
        if command in _TWO_ARGUMENT_TEX_COMMANDS:
            arg_end = _tex_argument_end(tex, end)
            if arg_end is None:
                return rf"\{command} is missing required argument 1"
            if _tex_argument_end(tex, arg_end) is None:
                return rf"\{command} is missing required argument 2"
        i = end
    return None


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

    missing_argument = _check_required_tex_arguments(tex)
    if missing_argument:
        return missing_argument

    # Double superscript/subscript without braces is a classic crash.
    if re.search(r"\^[^{\s]\^", tex) or re.search(r"_[^{\s]_", tex):
        return "double superscript/subscript without braces"
    return None


# Math-mode-only constructs. `Tex` renders in LaTeX *text* mode, where a bare
# `_`/`^` or a math command is illegal — LaTeX aborts with "Missing $ inserted."
# and the whole render dies (observed on real cloud renders: Tex("m_1"),
# Tex("\\theta_1")). The fix is MathTex, not a different string.
# Allow-list rather than a math-command blacklist: enumerating every math macro
# is a losing game (the first pass missed \mathcal and the render still died).
# Any other LaTeX letter-command in a text-mode Tex(...) is treated as math.
# Escaped punctuation (\%, \&, \_, \$, \#) never matches — it isn't a letter run.
_TEXT_SAFE_COMMANDS = frozenset({
    "textbf", "textit", "texttt", "textrm", "textsf", "textsc", "emph", "text",
    "rm", "bf", "it", "sf", "tt", "quad", "qquad", "ldots", "dots", "textbackslash",
    "textasciitilde", "textasciicircum", "textless", "textgreater", "par", "newline",
})


def _needs_math_mode(tex: str) -> bool:
    """True when a text-mode Tex(...) string contains math-only constructs.

    ``Tex`` renders in LaTeX text mode, so a bare ``_``/``^`` or a math macro
    (``\\theta``, ``\\frac``, ``\\mathcal`` ...) aborts the compile. Content
    already wrapped in ``$...$`` is explicit math and compiles fine.
    """
    outside = re.sub(r"\$[^$]*\$", "", tex)
    if re.search(r"(?<!\\)[_^]", outside):
        return True
    return any(
        match.group(1) not in _TEXT_SAFE_COMMANDS
        for match in re.finditer(r"\\([A-Za-z]+)", outside)
    )


def _nonpositive_literal(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
        and node.value <= 0
    )


def _self_timed_call(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    )


def _wait_duration_node(call: ast.Call) -> ast.AST | None:
    if call.args:
        return call.args[0]
    return next((kw.value for kw in call.keywords if kw.arg == "duration"), None)


def repair_zero_waits(code: str) -> tuple[str, int]:
    """Drop ``self.wait(0)`` statements: a no-op that Manim 0.21 rejects.

    Models write ``self.wait(0.0)`` to mark an empty hold between beats; the
    render then dies with "wait() has a duration of 0 <= 0 seconds". Removing
    the statement changes no timing. A block left empty gets ``pass``.
    """
    tree = _parse(code)
    if tree is None:
        return code, 0
    lines = code.splitlines(keepends=True)
    removals: list[tuple[int, int, bool]] = []
    for parent in ast.walk(tree):
        for field_name in ("body", "orelse", "finalbody"):
            block = getattr(parent, field_name, None)
            if not isinstance(block, list):
                continue
            zero = [
                statement for statement in block
                if isinstance(statement, ast.Expr)
                and _self_timed_call(statement.value, "wait")
                and _nonpositive_literal(_wait_duration_node(statement.value))
            ]
            for statement in zero:
                removals.append((
                    statement.lineno, statement.end_lineno or statement.lineno,
                    len(zero) == len(block) and statement is zero[0],
                ))
    if not removals:
        return code, 0
    for start, end, needs_pass in sorted(removals, reverse=True):
        indent = lines[start - 1][: len(lines[start - 1]) - len(lines[start - 1].lstrip())]
        newline = "\r\n" if lines[start - 1].endswith("\r\n") else "\n"
        lines[start - 1:end] = [f"{indent}pass{newline}"] if needs_pass else []
    repaired = "".join(lines)
    return (repaired, len(removals)) if _parse(repaired) is not None else (code, 0)


def lint_nonpositive_durations(code: str) -> list[str]:
    """Literal ``run_time``/``wait`` durations <= 0 crash the render (Manim 0.21)."""
    tree = _parse(code)
    if tree is None:
        return []
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _self_timed_call(node, "wait") and _nonpositive_literal(_wait_duration_node(node)):
            issues.append(
                f"self.wait() with a duration <= 0 on line {node.lineno}; Manim raises "
                "ValueError at render. Remove it or use a positive hold."
            )
        for keyword in node.keywords:
            if keyword.arg == "run_time" and _nonpositive_literal(keyword.value):
                issues.append(
                    f"run_time <= 0 on line {node.lineno}; Manim raises ValueError at "
                    "render. Use a positive run_time."
                )
    return issues


def repair_text_mode_math(code: str) -> tuple[str, list[str]]:
    """Promote ``Tex("<math>")`` to ``MathTex`` so text-mode math can't crash.

    Returns the (possibly rewritten) code and a note per promotion. Rewrites are
    applied bottom-up so earlier source offsets stay valid.
    """
    tree = _parse(code)
    if tree is None:
        return code, []

    targets: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Tex"
        ):
            continue
        for arg in node.args:
            if (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and _needs_math_mode(arg.value)
            ):
                targets.append((node.func.lineno, node.func.col_offset, arg.value))
                break

    if not targets:
        return code, []

    lines = code.splitlines(keepends=True)
    notes: list[str] = []
    for lineno, col, sample in sorted(targets, reverse=True):
        index = lineno - 1
        if index >= len(lines):
            continue
        line = lines[index]
        if line[col : col + 3] == "Tex":
            lines[index] = line[:col] + "MathTex" + line[col + 3 :]
            notes.append(
                f"line {lineno}: Tex({sample[:32]!r}) -> MathTex (text-mode math)"
            )
    return "".join(lines), notes


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
                if problem is None and node.func.id == "Tex" and _needs_math_mode(arg.value):
                    problem = "math content in text-mode Tex (use MathTex)"
                if problem:
                    snippet = arg.value[:60].replace("\n", " ")
                    issues.append(
                        f"{node.func.id} LaTeX problem (line {node.lineno}): {problem} "
                        f"in '{snippet}'."
                    )
    return issues


# ── 4. advisory duration estimate ───────────────────────────────────────────


def frame_rebuild_issues(code: str) -> list[str]:
    """Reject Tex-family mobjects reconstructed by frame callbacks.

    ``always_redraw`` and ``add_updater`` execute on every rendered frame.
    Recreating MathTex/Tex there can launch or cache hundreds of LaTeX builds,
    turning a 20-second scene into a multi-minute timeout. Static formulas are
    fine; changing numbers should use DecimalNumber.set_value().
    """
    tree = _parse(code)
    if tree is None:
        return []
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    issues: list[str] = []
    seen: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callback_kind = _call_name(node.func).split(".")[-1]
        if callback_kind not in {"always_redraw", "add_updater"} or not node.args:
            continue
        callback = node.args[0]
        callback_tree: ast.AST | None = callback
        if isinstance(callback, ast.Name):
            callback_tree = functions.get(callback.id)
        if callback_tree is None:
            continue
        for inner in ast.walk(callback_tree):
            if not isinstance(inner, ast.Call):
                continue
            tex_name = _call_name(inner.func).split(".")[-1]
            if tex_name not in _TEX_CALLS:
                continue
            marker = (node.lineno, tex_name)
            if marker in seen:
                continue
            seen.add(marker)
            issues.append(
                f"[PERF:TEX_PER_FRAME] {callback_kind} at line {node.lineno} "
                f"rebuilds {tex_name} every frame; create formulas once and use "
                "DecimalNumber.set_value() for changing numeric readouts."
            )
    return issues


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
        or re.search(
            rf"\b(?:Replacement)?Transform\(\s*{re.escape(owner)}\s*,",
            between,
        ) is not None
        or "FadeOut(*self.mobjects" in between
    )


def _is_transform_target_in_beat(
    lines: list[str], start_line: int, source: str, target: str
) -> bool:
    """Treat a same-beat Transform(source, target) as replacing its target layout.

    Scene targets are often positioned before the play call. They are not
    visible simultaneously with the source, so identical move_to coordinates
    are intentional in that case.
    """
    following = lines[max(start_line - 1, 0):]
    next_beat = next(
        (index for index, line in enumerate(following[1:], 1)
         if re.match(r"\s*#\s*BEAT\s+[AS]\d+\.B\d+\b", line)),
        len(following),
    )
    beat_source = "\n".join(following[:next_beat])
    pattern = (
        rf"\b(?:Replacement)?Transform\(\s*{re.escape(source)}\s*,\s*"
        rf"{re.escape(target)}\b"
    )
    return re.search(pattern, beat_source) is not None


def _literal_point(node: ast.AST) -> tuple[float, float] | None:
    """Read a literal 2D/3D point without evaluating generated Python."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value[:2]):
        return None
    return float(value[0]), float(value[1])


def _placement_warnings(code: str, tree: ast.Module) -> list[str]:
    lines = code.splitlines()
    placements: dict[str, list[tuple[str, int, str]]] = {}
    try:
        import manim

        half_width = float(manim.config.frame_width) / 2.0
        half_height = float(manim.config.frame_height) / 2.0
    except Exception:  # pragma: no cover - conservative default Manim landscape
        half_width, half_height = 7.11, 4.0
    off_frame: list[str] = []
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
        point = _literal_point(node.args[0])
        if point is not None and (
            abs(point[0]) > half_width - 0.35 or abs(point[1]) > half_height - 0.35
        ):
            off_frame.append(
                f"[HYGIENE:OFF_FRAME] {owner} is centered at {pos} on line {node.lineno}, "
                "near or beyond the render frame edge; leave room for the mobject's size."
            )
        norm = re.sub(r"\s+", "", pos)
        if norm:
            placements.setdefault(norm, []).append((owner, node.lineno, pos))

    warnings: list[str] = off_frame
    for _norm, owners in placements.items():
        if len(owners) < 2:
            continue
        owners = sorted(owners, key=lambda x: x[1])
        for (prev_owner, prev_line, pos), (owner, line, _pos) in zip(owners, owners[1:]):
            if (
                owner == prev_owner
                or _has_cleanup_between(lines, prev_line, line, prev_owner)
                or _is_transform_target_in_beat(lines, line, prev_owner, owner)
            ):
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


def _performance_warnings(code: str, tree: ast.Module) -> list[str]:
    """Flag known-slow Manim patterns before the expensive render.

    These are advisory: they surface in diagnostics and are fed back to the
    codegen model, nudging it toward cheaper idioms (update in place instead of
    rebuilding every frame, batch with LaggedStart, use ``axes.plot``). Every
    check is conservative to keep the false-positive rate low.
    """
    warnings: list[str] = []

    # 1) always_redraw / add_updater that REBUILDS a group every frame via a
    #    comprehension — the classic O(N·frames) hot loop. Update-in-place
    #    (mob.become(...) / shifting points) is dramatically cheaper.
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in {"always_redraw"}:
            continue
        if node.args and isinstance(node.args[0], ast.Lambda):
            body = node.args[0].body
            if any(
                isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp))
                for n in ast.walk(body)
            ):
                warnings.append(
                    f"[PERF:REDRAW_REBUILD] always_redraw at line {node.lineno} rebuilds a "
                    "group from a comprehension every frame; update the existing mobject "
                    "in place (become/shift) or redraw only the changing part."
                )
                break

    # 2) add_updater whose callback loops to construct mobjects each frame.
    updater_funcs = {
        node.args[0].id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_updater"
        and node.args
        and isinstance(node.args[0], ast.Name)
    }
    if updater_funcs:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name in updater_funcs
                and any(isinstance(n, ast.For) for n in ast.walk(node))
            ):
                warnings.append(
                    f"[PERF:UPDATER_LOOP] updater '{node.name}' (line {node.lineno}) runs a "
                    "for-loop every frame; precompute outside the updater and mutate in place."
                )
                break

    # 3) Many sequential single self.play() calls with no batching primitive —
    #    each emits a partial-movie file and slows assembly. LaggedStart /
    #    AnimationGroup / Succession collapse them into one beat.
    play_calls = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "play"
    )
    if play_calls >= 18 and not re.search(
        r"\b(LaggedStart|AnimationGroup|Succession)\b", code
    ):
        warnings.append(
            f"[PERF:SEQUENTIAL_PLAY] {play_calls} separate self.play() beats and no "
            "LaggedStart/AnimationGroup; batch related animations to cut render + assembly time."
        )

    # 4) Hand-rolled ParametricFunction/FunctionGraph when Axes are present —
    #    axes.plot(...) is the idiomatic, less error-prone path (fewer API-name
    #    hallucinations, which is our top render-failure class).
    if re.search(r"\b(ParametricFunction|FunctionGraph)\s*\(", code) and re.search(
        r"\b(Axes|NumberPlane)\s*\(", code
    ):
        warnings.append(
            "[PERF:PARAMETRIC] Prefer axes.plot(...) over a hand-rolled "
            "ParametricFunction/FunctionGraph when an Axes/NumberPlane already exists."
        )

    return warnings


def _text_size_warnings(tree: ast.Module, minimum_font_size: float = 20.0) -> list[str]:
    """Flag explicitly tiny Manim text while leaving computed sizes advisory."""
    text_types = {"Text", "Tex", "MathTex", "MarkupText", "Paragraph"}
    warnings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        type_name = _call_name(node.func).split(".")[-1]
        if type_name not in text_types:
            continue
        for keyword in node.keywords:
            if keyword.arg != "font_size":
                continue
            try:
                value = ast.literal_eval(keyword.value)
            except (ValueError, TypeError, SyntaxError):
                continue
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and 0 < float(value) < minimum_font_size
            ):
                warnings.append(
                    f"[HYGIENE:TEXT_SIZE] {type_name} uses "
                    f"font_size={value:g}, below the advisory {minimum_font_size:g} minimum; "
                    "check legibility at the selected render quality."
                )
                break
    return warnings


_REDRAWN_TEXT_TYPES = frozenset({
    "DecimalNumber", "Integer", "Variable", "Text", "MarkupText", "MathTex", "Tex",
})
_POSITIONING_METHODS = frozenset({
    "move_to", "next_to", "to_edge", "to_corner", "shift", "align_to",
    "set_x", "set_y", "set_z", "center", "arrange", "match_x", "match_y",
})


def _redraw_position_warnings(tree: ast.Module) -> list[str]:
    """Flag always_redraw(lambda: Text/DecimalNumber(...)) that never positions itself.

    always_redraw rebuilds the mobject from scratch every frame, at the origin.
    Placing the redraw outside the lambda (arrange/next_to on the returned
    object) only moves the first frame, so the live number jumps to the centre
    of the screen and its label is left with a blank gap.
    """
    warnings: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and _call_name(node.func).split(".")[-1] == "always_redraw"
            and node.args
            and isinstance(node.args[0], ast.Lambda)
        ):
            continue
        body = node.args[0].body
        built = [
            _call_name(child.func).split(".")[-1]
            for child in ast.walk(body)
            if isinstance(child, ast.Call)
        ]
        if not any(name in _REDRAWN_TEXT_TYPES for name in built):
            continue
        if any(name in _POSITIONING_METHODS for name in built):
            continue
        warnings.append(
            f"[HYGIENE:REDRAW_POSITION] always_redraw at line {node.lineno} rebuilds a "
            "text/number mobject at the screen centre every frame; position it inside "
            "the lambda (for example `.next_to(label, RIGHT)`), or use a DecimalNumber "
            "with add_updater(lambda m: m.set_value(tracker.get_value())) instead."
        )
    return warnings


def _is_stage_clear(node: ast.Call) -> bool:
    """True when the whole stage is cleared or gathered into one managed group.

    FadeOut(*self.mobjects) removes everything; Group(*self.mobjects) collects
    everything so it can be moved or shrunk as one (for example into a thumbnail).
    """
    if _call_name(node.func).split(".")[-1] not in {"FadeOut", "Group", "VGroup"}:
        return False
    return any(
        isinstance(arg, ast.Starred)
        and isinstance(arg.value, ast.Attribute)
        and arg.value.attr == "mobjects"
        and isinstance(arg.value.value, ast.Name)
        and arg.value.value.id == "self"
        for arg in node.args
    )


_STATIC_TEXT_TYPES = frozenset({
    "Text", "Tex", "MathTex", "SingleStringMathTex", "MarkupText", "Paragraph",
})
_STATIC_POSITIONING = frozenset({
    "move_to", "next_to", "to_edge", "to_corner", "shift", "arrange",
    "align_to", "match_x", "match_y", "set_x", "set_y",
})
_STATIC_REVEALS = frozenset({
    "FadeIn", "Write", "Create", "GrowFromCenter", "GrowFromEdge", "AddTextWordByWord",
})


def check_static_overlaps(code: str) -> list[str]:
    """Advisory static overlap/crowding checks (never blockers).

    The [HYGIENE:OVERLAP] duplicate-placement check stays the only blocking
    overlap gate (see manim_runtime._LAYOUT_BLOCKERS); everything here uses
    the [HYGIENE:CROWDING] prefix so it can only advise, nudge the codegen
    model, and feed the critic proxy — never reject a scene on its own.
    """
    tree = _parse(code)
    if tree is None:
        return []
    warnings: list[str] = []
    # 1) TEXT_PILE: 3+ text objects shown with no positioning at all — they
    # all render at the origin on top of each other.
    text_vars: dict[str, int] = {}
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if not isinstance(value, ast.Call):
            continue
        built = {
            _call_name(child.func).split(".")[-1]
            for child in ast.walk(value) if isinstance(child, ast.Call)
        }
        if not (built & _STATIC_TEXT_TYPES):
            continue
        positioned = bool(built & _STATIC_POSITIONING)
        for target in targets:
            if isinstance(target, ast.Name) and not positioned:
                text_vars.setdefault(target.id, node.lineno)
    if len(text_vars) >= 3:
        shown = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func).split(".")[-1]
            if name in _STATIC_REVEALS or (
                    name in {"add", "play"} and isinstance(node.func, ast.Attribute)):
                shown.update(
                    item.id for item in ast.walk(node)
                    if isinstance(item, ast.Name) and item.id in text_vars)
        piled = sorted(set(text_vars) & shown)
        if len(piled) >= 3:
            warnings.append(
                f"[HYGIENE:CROWDING] {len(piled)} text objects "
                f"({', '.join(piled[:4])}{'...' if len(piled) > 4 else ''}) are shown "
                "with no move_to/next_to/arrange positioning; they pile at the "
                "origin. Stack them in one VGroup(...).arrange(DOWN, buff=0.3) or "
                "sequence them so one focal label shows per beat."
            )
    # 2) EDGE_PILE: 2+ mobjects pinned to the same frame edge with no relative
    # positioning between them — titles, legends, and readouts collide.
    edge_pins: dict[str, list[tuple[str, int]]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "to_edge" or not node.args:
            continue
        edge = ast.get_source_segment(code, node.args[0]) or ""
        edge = re.sub(r"\s+", "", edge).split(",")[0]
        owner = _placement_owner(tree, node)
        if edge and owner:
            edge_pins.setdefault(edge, []).append((owner, node.lineno))
    for edge, owners in sorted(edge_pins.items()):
        if len(owners) < 2:
            continue
        names = sorted({owner for owner, _ in owners})
        if len(names) < 2:
            continue
        first, second = sorted(owners, key=lambda item: item[1])[:2]
        if _has_cleanup_between(code.splitlines(), first[1], second[1], first[0]):
            continue
        warnings.append(
            f"[HYGIENE:CROWDING] {names[0]} (line {first[1]}) and {names[1]} "
            f"(line {second[1]}) both pin to_edge({edge}) with no arrange/next_to "
            "between them; stack them with next_to(..., buff=0.3) or move one to "
            "a distinct region (title vs readout)."
        )
        break
    return warnings


def scene_hygiene_warnings(code: str) -> list[str]:
    """Return advisory warnings for likely visual layout bugs."""
    tree = _parse(code)
    if tree is None:
        return []
    warnings: list[str] = []
    warnings.extend(_placement_warnings(code, tree))
    warnings.extend(_text_size_warnings(tree))
    warnings.extend(_redraw_position_warnings(tree))
    warnings.extend(check_static_overlaps(code))

    # A whole-stage clear or gather (FadeOut/Group(*self.mobjects)) manages
    # everything introduced before it, so only introductions after it count.
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    last_clear = max(
        (node.lineno for node in calls if _is_stage_clear(node)), default=0
    )
    call_names = [_call_name(node.func).split(".")[-1] for node in calls]
    intro_count = sum(
        1 for node, name in zip(calls, call_names)
        if name in _INTRO_ANIMS and node.lineno > last_clear
    )
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
    warnings.extend(_performance_warnings(code, tree))
    return warnings


_TIMED_BEAT_MARKER_RE = re.compile(
    # A<act>.B<n> in single scenes; S<segment>.B<n> in long-video segments.
    r"(?m)^[ \t]*#[ \t]*BEAT[ \t]+([AS]\d+\.B\d+)[ \t]*\|[ \t]*"
    r"(\d+(?:\.\d+)?)[ \t]*-[ \t]*(\d+(?:\.\d+)?)[ \t]*s[ \t]*\r?$"
)


def normalize_timeline_markers(code: str, timeline: list[dict] | None) -> str:
    """Canonicalize beat labels/windows when generated marker count is exact.

    Models occasionally duplicate or permute otherwise correctly placed marker
    comments. The source order still follows the visual actions, so when there
    is exactly one marker slot per scheduled event we can safely restore the
    canonical IDs and timestamps without moving or editing any animation.
    Missing/extra marker slots are ambiguous and remain for the normal repair
    path to handle.
    """
    if not isinstance(timeline, list) or not timeline:
        return code
    expected: list[tuple[str, float, float]] = []
    for event in timeline:
        if not isinstance(event, dict) or not event.get("id"):
            continue
        beat_id = str(event["id"])
        if not re.fullmatch(r"[AS]\d+\.B\d+", beat_id):
            return code
        try:
            start_s = float(event["start_s"])
            end_s = float(event["end_s"])
        except (KeyError, TypeError, ValueError):
            return code
        if not math.isfinite(start_s) or not math.isfinite(end_s) or end_s < start_s:
            return code
        expected.append((beat_id, start_s, end_s))

    markers = list(_TIMED_BEAT_MARKER_RE.finditer(code))
    if not expected or len(markers) != len(expected):
        return code

    normalized = code
    for match, (beat_id, start_s, end_s) in reversed(list(zip(markers, expected, strict=True))):
        indent_match = re.match(r"[ \t]*", match.group(0))
        indent = indent_match.group(0) if indent_match else ""
        line_ending = "\r" if match.group(0).endswith("\r") else ""
        canonical = f"# BEAT {beat_id} | {start_s:.2f}-{end_s:.2f} s{line_ending}"
        normalized = normalized[:match.start()] + indent + canonical + normalized[match.end():]
    return normalized


def restore_beat_markers(original: str, repaired: str) -> str:
    """Put back ``# BEAT`` markers that a repair or revision dropped.

    Each marker returns in front of the first code line that followed it in
    the original, matched in order in the repaired code. Live 2026-10-02: two
    repairs of one segment fixed the real error but deleted every marker, so
    both failed validation. If any anchor line cannot be found the repaired
    code is returned unchanged and the marker check reports it as before.
    """
    original_markers = list(_TIMED_BEAT_MARKER_RE.finditer(original))
    if not original_markers or _TIMED_BEAT_MARKER_RE.search(repaired):
        return repaired
    original_lines = original.splitlines()
    repaired_lines = repaired.splitlines()
    insertions: list[tuple[int, str]] = []
    previous_anchor_line, previous_position = -1, -1
    for marker in original_markers:
        marker_line = original.count("\n", 0, marker.start())
        anchor_line = next(
            (index for index in range(marker_line + 1, len(original_lines))
             if original_lines[index].strip()
             and not original_lines[index].strip().startswith("#")),
            None,
        )
        if anchor_line is None:
            return repaired
        if anchor_line == previous_anchor_line:
            position = previous_position          # adjacent markers share a line
        else:
            anchor = original_lines[anchor_line].strip()
            position = next(
                (index for index in range(previous_position + 1, len(repaired_lines))
                 if repaired_lines[index].strip() == anchor),
                None,
            )
            if position is None:
                return repaired
        line = repaired_lines[position]
        insertions.append((position, line[: len(line) - len(line.lstrip())] + marker.group(0).strip()))
        previous_anchor_line, previous_position = anchor_line, position
    for position, text in reversed(insertions):
        repaired_lines.insert(position, text)
    return "\n".join(repaired_lines) + ("\n" if repaired.endswith("\n") else "")


def check_timeline_markers(code: str, timeline: list[dict] | None) -> list[str]:
    """Require one ordered source marker for each scheduled visual beat."""
    if not isinstance(timeline, list) or not timeline:
        return []
    expected = [
        event for event in timeline
        if isinstance(event, dict) and event.get("id")
    ]
    if not expected:
        return []
    markers = list(_TIMED_BEAT_MARKER_RE.finditer(code))
    expected_ids = [str(event["id"]) for event in expected]
    actual_ids = [match.group(1) for match in markers]
    issues: list[str] = []
    if actual_ids != expected_ids:
        missing = [beat_id for beat_id in expected_ids if beat_id not in actual_ids]
        extra = [beat_id for beat_id in actual_ids if beat_id not in expected_ids]
        details = []
        if missing:
            details.append("missing " + ", ".join(missing[:5]))
        if extra:
            details.append("unexpected " + ", ".join(extra[:5]))
        if not details:
            details.append("markers are duplicated or out of order")
        issues.append("[TIMING:BEAT_MARKERS] " + "; ".join(details) + ".")
        return issues

    for event, marker in zip(expected, markers):
        try:
            start_s = float(event["start_s"])
            end_s = float(event["end_s"])
            marked_start = float(marker.group(2))
            marked_end = float(marker.group(3))
        except (KeyError, TypeError, ValueError):
            issues.append(
                f"[TIMING:BEAT_WINDOW] {event.get('id')} has no numeric time window."
            )
            continue
        if abs(start_s - marked_start) > 0.05 or abs(end_s - marked_end) > 0.05:
            issues.append(
                f"[TIMING:BEAT_WINDOW] {event['id']} marker says "
                f"{marked_start:.2f}-{marked_end:.2f}s; schedule requires "
                f"{start_s:.2f}-{end_s:.2f}s."
            )
    return issues


def check_timeline_runtime(
    code: str,
    timeline: list[dict] | None,
    *,
    tolerance_s: float = 0.35,
) -> list[str]:
    """Compare each marked beat's literal play/wait budget with its schedule.

    This is deliberately conservative: dynamic durations and loops are not
    multiplied or guessed, so the check declines those scenes instead of
    inventing a timeline. For a statically measurable ``construct``, cumulative
    action boundaries must stay close to the storyboard's absolute boundaries.
    """
    if not isinstance(timeline, list) or not timeline:
        return []
    events = [item for item in timeline if isinstance(item, dict) and item.get("id")]
    markers = list(_TIMED_BEAT_MARKER_RE.finditer(code))
    if not events or len(markers) != len(events):
        return []  # the ordered marker check reports the more useful error

    tree = _parse(code)
    if tree is None:
        return []
    construct = next((
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "construct"
    ), None)
    if construct is None:
        return []

    calls = []
    for node in ast.walk(construct):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
            continue
        if node.func.attr in {"play", "wait"}:
            calls.append(node)
    calls.sort(key=lambda node: (node.lineno, node.col_offset))

    # Control-flow or nested helpers make execution order/count uncertain.
    for node in ast.walk(construct):
        if isinstance(node, (ast.For, ast.While, ast.If, ast.Try, ast.Match)) and any(
            call in ast.walk(node) for call in calls
        ):
            return []
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            and node is not construct
            and any(call in ast.walk(node) for call in calls)
        ):
            return []

    def number(node: ast.AST) -> float | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            value = float(node.value)
            return value if value >= 0 else None
        return None

    def call_duration(node: ast.Call) -> float | None:
        if node.func.attr == "wait":
            value = number(node.args[0]) if node.args else 1.0
            for keyword in node.keywords:
                if keyword.arg == "duration":
                    value = number(keyword.value)
                    break
            return value
        for keyword in node.keywords:
            if keyword.arg == "run_time":
                return number(keyword.value)
        # LaggedStart/AnimationGroup/Succession derive their length from their
        # children and lag (six lagged 1 s FadeIns run 2.5 s, not 1 s), so
        # without an explicit run_time the beat cannot be measured statically.
        if _untimed_composite_animation(node):
            return None
        # With no Scene.play override, Manim uses the longest child animation
        # duration. Nested run_time values are literal for this conservative
        # approximation; if none are present, Manim's default is one second.
        child_times = [
            number(keyword.value)
            for child in ast.walk(node)
            if isinstance(child, ast.Call) and child is not node
            for keyword in child.keywords
            if keyword.arg == "run_time"
        ]
        if any(value is None for value in child_times):
            return None
        return max(child_times, default=1.0)

    durations = [(call, call_duration(call)) for call in calls]
    if any(duration is None for _, duration in durations):
        return []  # a dynamic duration makes following boundaries uncertain

    issues: list[str] = []
    first_marker_line = code.count("\n", 0, markers[0].end()) + 1
    # Intro animation before the first marked beat consumes timeline too. Count
    # it so a marker cannot make an untimed prelude disappear from the budget.
    elapsed = sum(
        float(duration)
        for call, duration in durations
        if call.lineno < first_marker_line
    )
    for event, marker, next_marker in zip(
        events, markers, [*markers[1:], None], strict=True,
    ):
        start_line = code.count("\n", 0, marker.end()) + 1
        end_line = (
            code.count("\n", 0, next_marker.start()) + 1
            if next_marker is not None else (construct.end_lineno or construct.lineno) + 1
        )
        beat_duration = sum(
            float(duration)
            for call, duration in durations
            if start_line <= call.lineno < end_line
        )
        try:
            expected_start = float(event["start_s"])
            expected_end = float(event["end_s"])
        except (KeyError, TypeError, ValueError):
            elapsed += beat_duration
            continue
        actual_end = elapsed + beat_duration
        # Judge each beat by its OWN length, plus a looser bound on how far the
        # running clock has drifted. Comparing absolute boundaries at 0.35 s
        # made one short intro shift fail every later beat; live runs then spent
        # four repair calls per attempt chasing a constant offset.
        scheduled = max(0.0, expected_end - expected_start)
        length_tolerance = max(tolerance_s, 0.15 * scheduled)
        try:
            total = float(events[-1].get("end_s") or expected_end)
        except (TypeError, ValueError):
            total = expected_end
        drift_tolerance = max(1.5, 0.08 * total)
        if (
            abs(beat_duration - scheduled) > length_tolerance
            or abs(actual_end - expected_end) > drift_tolerance
        ):
            issues.append(
                f"[TIMING:BEAT_RUNTIME] {event['id']} action budget spans "
                f"{elapsed:.2f}-{actual_end:.2f}s ({beat_duration:.2f}s); schedule "
                f"requires {expected_start:.2f}-{expected_end:.2f}s ({scheduled:.2f}s, "
                f"tolerance {length_tolerance:.2f}s per beat, {drift_tolerance:.2f}s "
                "drift). Adjust this beat's animation or hold times."
            )
        elapsed = actual_end
    return issues


@dataclass
class DurationEstimate:
    total_seconds: float
    play_calls: int
    wait_calls: int
    notes: list[str] = field(default_factory=list)

    @property
    def exact(self) -> bool:
        """True when every counted duration was a literal the sum can trust.

        Any note (loop, non-literal or composite timing) makes the total an
        approximation, so it must not be used to *reject* a scene.
        """
        return not self.notes


_COMPOSITE_ANIMATIONS = frozenset({
    "AnimationGroup", "LaggedStart", "LaggedStartMap", "Succession",
})


def _untimed_composite_animation(play_call: ast.Call) -> bool:
    """True when a play() contains a group animation whose length is implicit."""
    for child in ast.walk(play_call):
        if (
            child is not play_call
            and isinstance(child, ast.Call)
            and _call_name(child.func).split(".")[-1] in _COMPOSITE_ANIMATIONS
            and not any(keyword.arg == "run_time" for keyword in child.keywords)
        ):
            return True
    return False


def _literal_seconds(node: ast.AST) -> float | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return float(node.value)
    return None


def estimate_duration(code: str) -> DurationEstimate:
    """Statically sum self.play(run_time=...) and self.wait(...) durations.

    Manim defaults: play run_time=1.0, wait duration=1.0. Non-literal values
    and group animations without their own run_time count as the default and
    are noted (see ``DurationEstimate.exact``). Loops multiply beats in ways a
    static pass can't always see.
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
            outer = next((kw for kw in node.keywords if kw.arg == "run_time"), None)
            if outer is not None:
                literal = _literal_seconds(outer.value)
                if literal is not None:
                    run_time = literal
                else:
                    est.notes.append(f"non-literal run_time at line {node.lineno} (counted as 1s)")
            elif _untimed_composite_animation(node):
                est.notes.append(
                    f"group animation without run_time at line {node.lineno} (counted as 1s)"
                )
            else:
                # Scene.play lasts as long as its longest child animation.
                child_times = [
                    _literal_seconds(keyword.value)
                    for child in ast.walk(node)
                    if isinstance(child, ast.Call) and child is not node
                    for keyword in child.keywords
                    if keyword.arg == "run_time"
                ]
                if any(value is None for value in child_times):
                    est.notes.append(
                        f"non-literal nested run_time at line {node.lineno} (counted as 1s)"
                    )
                elif child_times:
                    run_time = max(child_times)
            est.total_seconds += run_time
        elif node.func.attr == "wait":
            est.wait_calls += 1
            duration = 1.0
            value = node.args[0] if node.args else next(
                (kw.value for kw in node.keywords if kw.arg == "duration"), None
            )
            if value is not None:
                literal = _literal_seconds(value)
                if literal is not None:
                    duration = literal
                else:
                    est.notes.append(f"non-literal wait at line {node.lineno} (counted as 1s)")
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


def validate_scene(
    code: str,
    *,
    require_motion: bool = False,
    timeline: list[dict] | None = None,
) -> tuple[bool, list[str]]:
    """Run static API, ManimGL, kwargs, and LaTeX gates. Returns (ok, issues). Duration is not part of
    the verdict — callers surface it as an advisory diagnostic."""
    issues = (
        lint_forbidden_manimgl(code)
        + lint_manim_names(code)
        + lint_constructor_kwargs(code)
        + lint_manim_method_kwargs(code)
        + lint_nonpositive_durations(code)
        + check_latex_strings(code)
        + check_timeline_markers(code, timeline)
        + check_timeline_runtime(code, timeline)
        + check_updater_animation_conflicts(code)
        + check_dynamic_numeric_fade_conflicts(code)
        + frame_rebuild_issues(code)
    )
    if require_motion:
        issues.extend(motion_contract_issues(code))
    return (not issues), issues
