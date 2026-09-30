"""Shared plumbing for the v6 problem videos (typeset math, width guards, data).

Only plumbing lives here. Each video's staging, device and pacing stay in its
own module, because a scaffold shared by every topic was rated lower than
topic-specific ideas.

Templates are filled with ``fill`` rather than ``str.format`` so LaTeX braces
need no escaping: ``__CLASS__`` becomes the scene class and ``__DATA__`` a dict
literal of every number and label the scene states.
"""

from __future__ import annotations

import math
from typing import Any

# Glyphs confirmed to render in both the local and the Cloud font (t_f216/t_f218;
# "ö" confirmed in the v6 Cloud render of "Schrödinger").
VERIFIED_GLYPHS = frozenset("°²·½×ħΔΣγθλπψω₁₂→∂√∝≈⁰¹³⁴⁵⁶⁷⁸⁹ö")

# Scene-side helpers, pasted into each generated scene.
HELPERS = r'''
def fit(m, width=13.0):
    # Cloud and local fonts differ in width: never let a line leave the frame.
    if m.width > width:
        m.scale_to_fit_width(width)
    return m


def eq(tex, plain, size=34, color=WHITE, width=13.0):
    # Typeset math when LaTeX is available, the same content as text otherwise.
    try:
        m = MathTex(tex, font_size=size, color=color)
    except Exception:
        m = Text(plain, font_size=int(size * 0.72), color=color)
    return fit(m, width)


def chip(text):
    return fit(Text(text, font_size=24, color=YELLOW_A), 8.0).to_corner(UL, buff=0.3)


def label(text, size=24, color=WHITE, width=13.0):
    return fit(Text(text, font_size=size, color=color), width)
'''


def fill(template: str, class_name: str, data: dict[str, Any]) -> str:
    code = template.replace("__HELPERS__", HELPERS.strip("\n"))
    return code.replace("__CLASS__", class_name).replace("__DATA__", repr(data))


def text_of(solver: Any) -> str:
    return " ".join([" ".join(getattr(solver, "keywords", []) or []),
                     getattr(solver, "summary", "") or ""]).lower()


def variables_of(solver: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in dict(getattr(solver, "variables", {}) or {}).items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out[str(k).lower().replace("{", "").replace("}", "")] = f
    return out


def pick(variables: dict[str, float], names: tuple[str, ...]) -> float | None:
    for name in names:
        if name in variables:
            return variables[name]
    return None


def sci(x: float, digits: int = 3) -> tuple[str, str]:
    """(LaTeX, plain) scientific notation: 1.10\\times10^{-10} and "1.10 × 10^-10"."""
    if x == 0:
        return "0", "0"
    exp = int(math.floor(math.log10(abs(x))))
    mant = x / 10 ** exp
    m = f"{mant:.{digits - 1}f}"
    # Superscript minus is not a verified glyph, so plain text spells the power out.
    return f"{m}\\times10^{{{exp}}}", f"{m} × 10^{exp}"


def plain_glyphs(data: Any) -> set[str]:
    """Every non-ASCII character in the plain-text strings of a data dict."""
    found: set[str] = set()
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack += [v for k, v in item.items() if not str(k).startswith("tex")]
        elif isinstance(item, (list, tuple)):
            stack += list(item)
        elif isinstance(item, str):
            found |= {c for c in item if ord(c) > 127}
    return found
