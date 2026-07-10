"""Cross-run error learning for Manim scene generation.

WP2's self-heal loop repairs a scene *within a single run*. This module makes
the pipeline smarter *across runs* in two ways:

1. A curated knowledge base of the most common Manim-Community pitfalls (mostly
   ManimGL-era API names an LLM still emits) mapped to concrete corrections.
   These turn an opaque ``NameError``/``AttributeError`` into an actionable hint
   for the repair prompt — and, preventively, into a short "avoid these" block
   in the generation system prompt.

2. A small JSON-backed store that remembers which *normalized* error signatures
   have recurred, so a repeatedly-seen failure can be flagged in the repair
   prompt ("you have hit this before").

No third-party dependencies; persistence uses the app's standard-library-only
atomic JSON helper so parallel render candidates cannot overwrite each other.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aetherlab.core.atomic_json import atomic_write_json, path_lock

log = logging.getLogger(__name__)

# How long a remembered error signature stays "recent" before it is pruned.
PATTERN_TTL_DAYS = 30

# ── Signature normalization ──────────────────────────────────────────────────
_EXC_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning)):\s?(.*)")
_HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
_NUM_RE = re.compile(r"\b\d+\b")
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s'\"]+|/[^\s'\"]+")
_WS_RE = re.compile(r"\s+")


def error_signature(stderr: str) -> str:
    """Reduce a render stderr to a stable, comparable signature.

    Line numbers, file paths, and memory addresses are stripped so the *same*
    class of failure collapses to one signature regardless of where it happened.
    """
    text = stderr or ""

    # Prefer the last Python exception line (the actual cause is usually last).
    last_exc = None
    for line in text.splitlines():
        match = _EXC_RE.search(line.strip())
        if match:
            last_exc = match
    if last_exc:
        exc, msg = last_exc.group(1), last_exc.group(2)
        msg = _PATH_RE.sub("<path>", msg)
        msg = _HEX_RE.sub("<addr>", msg)
        msg = _NUM_RE.sub("<n>", msg)
        msg = _WS_RE.sub(" ", msg).strip().lower()
        return f"{exc}: {msg}"[:200]

    low = text.lower()
    if "undefined control sequence" in low:
        return "latexerror: undefined control sequence"
    if "latex error" in low or "! " in text:
        return "latexerror: content"

    # Fall back to the last non-empty line, normalized.
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            stripped = _WS_RE.sub(" ", _NUM_RE.sub("<n>", stripped)).lower()
            return stripped[:200]
    return "unknown"


# ── Curated Manim-Community pitfall knowledge base ───────────────────────────
# (compiled case-insensitive pattern, corrective hint). Ordered roughly by how
# often an LLM emits the mistake.
_PITFALLS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"has no attribute ['\"]get_graph['\"]", re.I),
     "Use `axes.plot(fn)` in Manim CE, not `axes.get_graph(fn)`."),
    (re.compile(r"\bShowCreation\b", re.I),
     "`ShowCreation` is ManimGL; use `Create(...)` in Manim CE."),
    (re.compile(r"\bTextMobject\b", re.I),
     "`TextMobject` is ManimGL; use `Text(...)` for plain text in Manim CE."),
    (re.compile(r"\bTexMobject\b", re.I),
     "`TexMobject` is ManimGL; use `MathTex(...)` for math in Manim CE."),
    (re.compile(r"\bGraphScene\b", re.I),
     "`GraphScene` was removed; build an `Axes` inside a normal `Scene` instead."),
    (re.compile(r"has no attribute ['\"]get_center_of_mass['\"]", re.I),
     "Use `mobject.get_center()` in Manim CE."),
    (re.compile(r"undefined control sequence", re.I),
     "A LaTeX macro is undefined. Use only valid LaTeX in MathTex, or render the "
     "text with `Text(...)` instead of `MathTex(...)`."),
    (re.compile(r"unexpected keyword argument ['\"]color['\"].*Text", re.I),
     "For `Text`, pass `color=` is fine, but style with `font_size=` not `size=`."),
    (re.compile(r"\bCONFIG\b\s*=", re.I),
     "The class-level `CONFIG` dict is ManimGL; pass parameters to `__init__` in "
     "Manim CE."),
    (re.compile(r"name ['\"]FRAME_WIDTH['\"] is not defined", re.I),
     "`FRAME_WIDTH` is not a global; use `config.frame_width` or just default sizing."),
    (re.compile(r"\bShowCreationThenDestruction\b|\bShowCreationThenFadeOut\b", re.I),
     "Use `Create` then `FadeOut`, or `ShowPassingFlash`, in Manim CE."),
)


def known_pitfall_hints(stderr: str) -> list[str]:
    """Return corrective hints for any known Manim-CE pitfalls in ``stderr``."""
    text = stderr or ""
    hints: list[str] = []
    for pattern, hint in _PITFALLS:
        if pattern.search(text) and hint not in hints:
            hints.append(hint)
    return hints


def preventive_pitfalls_block(aesthetic_store: "AestheticPitfallStore | None" = None) -> str:
    """A compact 'avoid these' appendix for the generation system prompt.

    The static half lists the perennial Manim-CE API mistakes. When an
    ``aesthetic_store`` is supplied, the *learned* half appends the aesthetic
    problems the visual critic has repeatedly named on past renders — this is
    how the quality flywheel's losing candidates teach the next generation to
    avoid the same visual mistakes (Phase 3). Fail-soft: a missing/empty/corrupt
    store simply contributes nothing.
    """
    lines = [
        "## Common Manim CE pitfalls to AVOID",
        "- Use `axes.plot(fn)`, never `axes.get_graph(fn)`.",
        "- Use `Create(...)`, never `ShowCreation(...)`.",
        "- Use `Text(...)` for words and `MathTex(...)` for math; never "
        "`TextMobject`/`TexMobject`.",
        "- There is no `GraphScene`/`CONFIG` dict; use a plain `Scene` and pass "
        "kwargs to constructors.",
        "- Only put valid LaTeX inside `MathTex`; otherwise use `Text`.",
    ]
    learned = learned_aesthetic_block(aesthetic_store) if aesthetic_store is not None else ""
    return "\n".join(lines) + ("\n\n" + learned if learned else "")


# ── Aesthetic pitfall learning (the flywheel's "losers teach" channel) ───────
# The visual critic (services/scene_critic) names *aesthetic* problems on a
# render ("text overlaps the axis", "object leaves the frame"). Recording the
# recurring ones and feeding the top offenders back into the generation prompt
# turns crash-only learning into "don't be ugly" learning.

_AESTHETIC_MAX_LEN = 90


def normalize_aesthetic(issue: str) -> str:
    """Collapse a critic issue string to a stable, comparable pitfall phrase."""
    text = _PATH_RE.sub("", str(issue or ""))
    text = _HEX_RE.sub("", text)
    text = _NUM_RE.sub("", text)
    # Drop a leading axis tag like "legibility: " the critic may prepend.
    text = re.sub(r"^\s*[A-Za-z]+\s*:\s*", "", text)
    text = _WS_RE.sub(" ", text).strip().lower().rstrip(".")
    return text[:_AESTHETIC_MAX_LEN]


class AestheticPitfallStore:
    """JSON-backed tally of aesthetic problems the critic has named, with TTL.

    Standard-library only and fail-soft, exactly like :class:`ErrorLearner`: no
    method raises into the render pipeline.
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = Path(store_path) if store_path else None
        self._store: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.store_path or not self.store_path.exists():
            return {}
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return ErrorLearner._prune(data)
        except Exception as exc:  # noqa: BLE001 — corruption must not break render
            log.debug("aesthetic store unreadable, starting fresh: %s", exc)
        return {}

    def _save(self) -> None:
        if not self.store_path:
            return
        try:
            atomic_write_json(self.store_path, self._store)
        except Exception as exc:  # noqa: BLE001 — persistence is best-effort
            log.debug("could not persist aesthetic store: %s", exc)

    def record(self, issues: list[str]) -> None:
        """Tally each non-empty, normalized aesthetic issue once."""
        def _record() -> bool:
            changed = False
            for issue in issues or []:
                phrase = normalize_aesthetic(issue)
                if not phrase:
                    continue
                entry = self._store.setdefault(phrase, {"count": 0, "last_seen": ""})
                entry["count"] = int(entry.get("count", 0)) + 1
                entry["last_seen"] = datetime.now(UTC).isoformat(timespec="seconds")
                changed = True
            return changed

        if not self.store_path:
            _record()
            return
        with path_lock(self.store_path):
            self._store = self._load()
            if _record():
                self._save()

    def top(self, n: int = 6) -> list[tuple[str, int]]:
        """Most-recorded pitfalls first (ties broken by phrase for determinism)."""
        if self.store_path:
            with path_lock(self.store_path):
                self._store = self._load()
        items = [(p, int(e.get("count", 0))) for p, e in self._store.items() if e.get("count", 0) > 0]
        items.sort(key=lambda pc: (-pc[1], pc[0]))
        return items[: max(0, n)]


def learned_aesthetic_block(store: "AestheticPitfallStore | None", n: int = 6) -> str:
    """A prompt appendix listing the top learned aesthetic pitfalls ('' if none)."""
    if store is None:
        return ""
    top = store.top(n)
    if not top:
        return ""
    lines = ["## Aesthetic problems seen on past renders — actively AVOID these:"]
    lines.extend(f"- {phrase} (seen {count}x)" for phrase, count in top)
    return "\n".join(lines)


class ErrorLearner:
    """Remembers normalized error signatures across runs (best-effort, on disk)."""

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = Path(store_path) if store_path else None
        self._store: dict[str, dict] = self._load()

    # -- persistence (never raises into the pipeline) -------------------------
    def _load(self) -> dict[str, dict]:
        if not self.store_path or not self.store_path.exists():
            return {}
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return self._prune(data)
        except Exception as exc:  # noqa: BLE001 — corruption must not break render
            log.debug("error store unreadable, starting fresh: %s", exc)
        return {}

    def _save(self) -> None:
        if not self.store_path:
            return
        try:
            atomic_write_json(self.store_path, self._store)
        except Exception as exc:  # noqa: BLE001 — persistence is best-effort
            log.debug("could not persist error store: %s", exc)

    @staticmethod
    def _prune(data: dict[str, dict]) -> dict[str, dict]:
        cutoff = datetime.now(UTC) - timedelta(days=PATTERN_TTL_DAYS)
        kept: dict[str, dict] = {}
        for sig, entry in data.items():
            last = entry.get("last_seen", "")
            try:
                if last and datetime.fromisoformat(last) < cutoff:
                    continue
            except ValueError:
                pass
            kept[sig] = entry
        return kept

    # -- public API -----------------------------------------------------------
    def seen_count(self, stderr: str) -> int:
        """How many times this error signature has been recorded before now."""
        if self.store_path:
            with path_lock(self.store_path):
                self._store = self._load()
        return int(self._store.get(error_signature(stderr), {}).get("count", 0))

    def record(self, stderr: str) -> str:
        """Record one occurrence of ``stderr``; returns its signature."""
        sig = error_signature(stderr)

        def _record() -> None:
            entry = self._store.setdefault(sig, {"count": 0, "last_seen": ""})
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["last_seen"] = datetime.now(UTC).isoformat(timespec="seconds")

        if not self.store_path:
            _record()
            return sig
        with path_lock(self.store_path):
            self._store = self._load()
            _record()
            self._save()
        return sig

    def hints_for(self, stderr: str) -> list[str]:
        """Combine curated pitfall hints with a recurrence warning if applicable."""
        hints = known_pitfall_hints(stderr)
        if self.seen_count(stderr) >= 1:
            hints.append(
                "You have produced this exact error before - do not repeat the "
                "same construct; take a different approach."
            )
        return hints
