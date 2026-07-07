"""Typeset math → QPixmap rendering (design v2 §5: "Formulas are the brand").

Renders LaTeX-subset math through matplotlib's mathtext engine (STIX fonts —
the KaTeX/Cambria-Math look the design specifies) onto transparent pixmaps at
2× device resolution. Every typeset element is an image with a known size,
exactly as the design's build notes require — never selectable rich text.

Design rules honored here:
- never raises: any unparseable input returns None and callers fall back to
  styled text, so LLM prose can't break a panel;
- pixmaps are cached (the same equation is re-rendered constantly by list
  rebuilds);
- pure service: no Qt imports at module level besides QtGui via qt_compat,
  no widget knowledge.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_CACHE: dict[tuple[str, int, str], "object"] = {}
_CACHE_MAX = 256

# Parameter-name → LaTeX symbol map for the live parameter rows (§5.5).
# Deterministic and safe: names not listed fall back to upright text.
SYMBOL_MAP: dict[str, str] = {
    "damping": r"\zeta",
    "zeta": r"\zeta",
    "stiffness": r"k",
    "mass": r"m",
    "gravity": r"g",
    "length": r"\ell",
    "omega": r"\omega",
    "omega0": r"\omega_0",
    "omega_n": r"\omega_n",
    "theta": r"\theta",
    "theta0": r"\theta_0",
    "phi": r"\varphi",
    "tau": r"\tau",
    "alpha": r"\alpha",
    "beta": r"\beta",
    "gamma": r"\gamma",
    "lambda": r"\lambda",
    "mu": r"\mu",
    "sigma": r"\sigma",
    "amplitude": r"A",
    "frequency": r"f",
    "period": r"T",
    "energy": r"E",
    "velocity": r"v",
    "v0": r"v_0",
    "x0": r"x_0",
    "charge": r"q",
    "current": r"I",
    "voltage": r"V",
    "resistance": r"R",
    "inductance": r"L",
    "capacitance": r"C",
    "wavelength": r"\lambda",
    "hbar": r"\hbar",
    "temperature": r"T",
    "pressure": r"P",
    "eccentricity": r"e",
}

# Ambient watermark formulas (§5.4) — decorative, rendered at ≤6% opacity.
WATERMARK_FORMULAS: tuple[str, ...] = (
    r"i\hbar\,\frac{\partial}{\partial t}\Psi = \hat{H}\Psi",
    r"\nabla \times \vec{E} = -\frac{\partial \vec{B}}{\partial t}",
    r"\frac{d}{dt}\frac{\partial L}{\partial \dot{q}} - \frac{\partial L}{\partial q} = 0",
    r"e^{i\pi} + 1 = 0",
)


def latex_for_param(name: str) -> str:
    """LaTeX symbol for a solver variable name (upright-text fallback)."""
    key = name.strip().lower()
    if key in SYMBOL_MAP:
        return SYMBOL_MAP[key]
    # camel/snake tails like "spring_k" → try the last token too
    tail = re.split(r"[_\s]+", key)[-1]
    if tail in SYMBOL_MAP:
        return SYMBOL_MAP[tail]
    safe = name.replace("_", r"\_")
    return rf"\mathrm{{{safe}}}"


_LATEX_TO_UNICODE = {
    r"\zeta": "ζ", r"\omega": "ω", r"\theta": "θ", r"\varphi": "φ",
    r"\phi": "φ", r"\pi": "π", r"\tau": "τ", r"\alpha": "α", r"\beta": "β",
    r"\gamma": "γ", r"\lambda": "λ", r"\mu": "μ", r"\sigma": "σ",
    r"\Delta": "Δ", r"\partial": "∂", r"\nabla": "∇", r"\hbar": "ℏ",
    r"\cdot": "·", r"\times": "×", r"\pm": "±", r"\approx": "≈",
    r"\leq": "≤", r"\geq": "≥", r"\infty": "∞", r"\sqrt": "√",
    r"\cos": "cos", r"\sin": "sin", r"\tan": "tan", r"\exp": "exp",
    r"\log": "log", r"\rightarrow": "→", r"\left": "", r"\right": "",
}

_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def plain_math(text: str) -> str:
    """Best-effort LaTeX → readable unicode for plain-painted labels (e.g. the
    canvas title, which is QPainter text, not a typeset pixmap)."""
    import re as _re

    s = text.strip().strip("$")
    for cmd, uni in _LATEX_TO_UNICODE.items():
        s = s.replace(cmd, uni)
    # x_{0} / x_0 → x₀ ; drop remaining braces and ^ markers
    s = _re.sub(r"_\{?([0-9]+)\}?", lambda m: m.group(1).translate(_SUBSCRIPT), s)
    s = _re.sub(r"\^\{([^}]*)\}", r"^\1", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    return _re.sub(r"\s+", " ", s).strip()


def looks_like_math(text: str) -> bool:
    """Heuristic: is this short string worth attempting to typeset?"""
    if not text or len(text) > 160 or "\n" in text:
        return False
    if not any(ch in text for ch in "=^_\\/·×±∝≈"):
        return False
    # Prose sentences (many long words, few operators) are not math.
    words = re.findall(r"[A-Za-z]{5,}", text)
    return len(words) <= 4


def _prepare(expr: str) -> str:
    """Light cleanup of solver-authored math for the mathtext parser."""
    s = expr.strip()
    if s.startswith("$") and s.endswith("$"):
        s = s.strip("$")
    # Unicode → LaTeX the parser understands
    # Word-commands carry a trailing space so adjacent letters don't fuse
    # into unknown commands (e.g. "ωt" must become "\omega t", not "\omegat").
    replacements = {
        "ζ": r"\zeta ", "ω": r"\omega ", "θ": r"\theta ", "φ": r"\varphi ",
        "π": r"\pi ", "τ": r"\tau ", "α": r"\alpha ", "β": r"\beta ",
        "γ": r"\gamma ", "λ": r"\lambda ", "μ": r"\mu ", "σ": r"\sigma ",
        "Δ": r"\Delta ", "∂": r"\partial ", "∇": r"\nabla ", "ℏ": r"\hbar ",
        "·": r"\cdot ", "×": r"\times ", "±": r"\pm ", "∝": r"\propto ",
        "≈": r"\approx ", "≤": r"\leq ", "≥": r"\geq ", "→": r"\rightarrow ",
        "∞": r"\infty ", "²": r"^2", "³": r"^3", "₀": r"_0", "₁": r"_1",
        "₂": r"_2", "√": r"\sqrt ", "−": "-",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    return f"${s}$"


def render_math(
    expr: str,
    px_size: int = 22,
    color: str = "#F8FAFC",
):
    """Render a LaTeX-subset expression to a transparent QPixmap at 2× DPR.

    Returns a QtGui.QPixmap, or None if the expression cannot be typeset —
    callers must fall back to styled text. Never raises.
    """
    key = (expr, px_size, color)
    if key in _CACHE:
        return _CACHE[key]
    try:
        import matplotlib

        matplotlib.use("Agg", force=False)
        from matplotlib import figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        from aetherlab.ui.qt_compat import QtGui

        prepared = _prepare(expr)

        fig = figure.Figure(figsize=(0.1, 0.1), dpi=200)
        FigureCanvasAgg(fig)
        fig.patch.set_alpha(0.0)
        # mathtext with STIX fonts — the Cambria-Math/KaTeX look of the design
        with matplotlib.rc_context({"mathtext.fontset": "stix"}):
            text = fig.text(0, 0, prepared, fontsize=px_size, color=color)
            renderer = fig.canvas.get_renderer()
            bbox = text.get_window_extent(renderer=renderer)
            fig.set_size_inches(
                max(bbox.width, 1) / 200 + 0.04, max(bbox.height, 1) / 200 + 0.04
            )
            text.set_position((0.02 * 200 / max(bbox.width, 1), 0.5))
            text.set_verticalalignment("center")
            fig.canvas.draw()
            buf, (w, h) = fig.canvas.print_to_buffer()

        image = QtGui.QImage(buf, w, h, QtGui.QImage.Format.Format_RGBA8888).copy()
        pixmap = QtGui.QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(2.0)  # rendered at 200dpi ≈ 2× screen
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = pixmap
        return pixmap
    except Exception as exc:  # noqa: BLE001 — typesetting must never break UI
        log.debug("mathtext render failed for %r: %s", expr[:60], exc)
        _CACHE[key] = None
        return None


def render_param_symbol(name: str, px_size: int = 15, color: str = "#F8FAFC"):
    """Typeset pixmap for a parameter symbol (§5.5), or None."""
    return render_math(latex_for_param(name), px_size=px_size, color=color)
