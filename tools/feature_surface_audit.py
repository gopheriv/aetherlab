"""Audit visible app surfaces against the canonical feature tracker.

The tracker remains the source of truth; this script is a guardrail that looks
for current code surfaces likely to represent user-facing features and checks
that their words appear in at least one tracker row.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKER = ROOT / "AetherLab_Feature_Tracker.csv"
SOURCE_ROOT = ROOT / "aetherlab"

GENERIC_LABELS = {
    "",
    "cancel",
    "copy",
    "details",
    "dismiss",
    "download",
    "export",
    "gif",
    "issues",
    "learn",
    "open",
    "run",
    "save",
}

IGNORE_SETTING_FIELDS = {
    # Internal attribution/debug field, not a user-configurable setting.
    "provider_source",
    "api_key_source",
    "provider_warning",
}

LOCALE_CODES = {"kk", "ru", "en"}
LANGUAGE_NAMES = {"kk": "kazakh", "ru": "russian", "en": "english"}
LANGUAGE_LABEL_ALIASES = {
    "қазақша": "kazakh",
    "русский": "russian",
    "english": "english",
}


@dataclass(frozen=True)
class Surface:
    kind: str
    name: str
    file: str
    line: int


def _words(value: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[^\W_]+", value.replace("_", " ").casefold(), flags=re.UNICODE)
        if w not in {"a", "an", "as", "i", "my", "the", "to", "with"}
    }


def _literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _append_string_surfaces(path: Path, tree: ast.AST, out: list[Surface]) -> None:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        label: str | None = None
        if name in {"QPushButton", "QCheckBox"} and node.args:
            label = _literal(node.args[0])
        elif name in {"addAction", "addItem"} and node.args:
            label = _literal(node.args[0])
        elif name == "addItems" and node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
            for item in node.args[0].elts:
                text = _literal(item)
                if text:
                    out.append(Surface("ui-label", text, rel, item.lineno))
            continue
        if label is not None:
            clean = " ".join(label.split())
            if clean.lower() not in GENERIC_LABELS and len(_words(clean)) >= 2:
                out.append(Surface("ui-label", clean, rel, node.lineno))


def _append_cli_surfaces(path: Path, tree: ast.AST, out: list[Surface]) -> None:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node) != "add_argument":
            continue
        for arg in node.args:
            value = _literal(arg)
            if value and value.startswith("--"):
                out.append(Surface("cli-flag", value, rel, node.lineno))


def _append_settings_surfaces(path: Path, tree: ast.AST, out: list[Surface]) -> None:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "AppSettings":
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                field = stmt.target.id
                if field not in IGNORE_SETTING_FIELDS:
                    out.append(Surface("setting", field, rel, stmt.lineno))


def _append_localized_surfaces(path: Path, tree: ast.AST, out: list[Surface]) -> None:
    """Track user-facing copy stored in locale dictionaries, not just literals.

    UI text passed through ``self._t[...]`` is invisible to the literal-widget
    scanner. A single record per localized dictionary keeps the audit useful
    without treating every sentence as a separate feature.
    """
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    for stmt in tree.body:
        value: ast.AST | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            value = stmt.value
        if not isinstance(value, ast.Dict):
            continue

        locale_values: dict[str, ast.Dict] = {}
        for key, locale_value in zip(value.keys, value.values):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value in LOCALE_CODES
                and isinstance(locale_value, ast.Dict)
            ):
                locale_values[key.value] = locale_value
        if len(locale_values) < 2:
            continue

        locale_names = " ".join(LANGUAGE_NAMES[code] for code in sorted(locale_values))
        constant_name = ""
        target = getattr(stmt, "target", None)
        if isinstance(stmt, ast.Assign) and stmt.targets and isinstance(stmt.targets[0], ast.Name):
            constant_name = stmt.targets[0].id
        elif isinstance(target, ast.Name):
            constant_name = target.id
        labels = f"{path.stem} {constant_name} {locale_names} localization"
        out.append(Surface("localized-copy", labels, rel, stmt.lineno))


def collect_surfaces() -> list[Surface]:
    surfaces: list[Surface] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        _append_string_surfaces(path, tree, surfaces)
        _append_cli_surfaces(path, tree, surfaces)
        _append_settings_surfaces(path, tree, surfaces)
        _append_localized_surfaces(path, tree, surfaces)
    deduped: dict[tuple[str, str], Surface] = {}
    for surface in surfaces:
        deduped.setdefault((surface.kind, surface.name), surface)
    return sorted(deduped.values(), key=lambda s: (s.kind, s.name.lower(), s.file, s.line))


def load_tracker_rows() -> list[dict[str, str]]:
    with TRACKER.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tracker_matches(surface: Surface, rows: list[dict[str, str]]) -> list[str]:
    if surface.kind == "localized-copy":
        source_words = _words(Path(surface.file).stem)
        language_words = {
            language for language in LANGUAGE_NAMES.values() if language in _words(surface.name)
        }
        hits: list[str] = []
        for row in rows:
            declared_source = _words(row.get("Source File(s)", ""))
            declared_languages = _words(" ".join(row.values()))
            if (
                source_words <= declared_source
                and language_words <= declared_languages
            ):
                hits.append(row["ID"])
        return hits
    want = _words(surface.name)
    if surface.kind == "ui-label":
        want = {LANGUAGE_LABEL_ALIASES.get(word, word) for word in want}
    if surface.kind == "cli-flag":
        want = _words(surface.name.lstrip("-"))
    if not want:
        return []
    hits: list[str] = []
    for row in rows:
        haystack = _words(" ".join(row.values()))
        if want <= haystack:
            hits.append(row["ID"])
    return hits


def audit() -> dict[str, object]:
    rows = load_tracker_rows()
    surfaces = collect_surfaces()
    covered = []
    uncovered = []
    for surface in surfaces:
        matches = tracker_matches(surface, rows)
        record = {
            "kind": surface.kind,
            "name": surface.name,
            "file": surface.file,
            "line": surface.line,
            "matches": matches[:5],
        }
        if matches:
            covered.append(record)
        else:
            uncovered.append(record)
    return {
        "tracker": str(TRACKER.relative_to(ROOT)),
        "feature_count": len(rows),
        "surface_count": len(surfaces),
        "localized_copy_count": sum(1 for surface in surfaces if surface.kind == "localized-copy"),
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "covered": covered,
        "uncovered": uncovered,
    }


def main() -> int:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Audit code surfaces against the feature tracker.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any surface is uncovered.",
    )
    args = parser.parse_args()

    report = audit()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['covered_count']}/{report['surface_count']} surfaces covered "
            f"by {report['feature_count']} tracker rows"
        )
        for item in report["uncovered"]:
            print(
                f"UNCOVERED {item['kind']}: {item['name']} "
                f"({item['file']}:{item['line']})"
            )
    return 1 if args.check and report["uncovered_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
