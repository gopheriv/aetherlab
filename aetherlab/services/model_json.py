"""Conservative JSON recovery for OpenAI-compatible model responses."""

from __future__ import annotations

import json
import re
from typing import Any


_LATEX_COMMANDS = {
    "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda",
    "mu", "pi", "rho", "sigma", "tau", "phi", "psi", "omega",
    "frac", "sqrt", "partial", "nabla", "vec", "hat", "dot", "ddot",
    "times", "cdot", "left", "right", "begin", "end", "text", "mathrm",
    "sum", "prod", "int", "infty",
}
_HEX = frozenset("0123456789abcdefABCDEF")


def _first_json_object(text: str) -> str | None:
    """Return the first balanced JSON-looking object, ignoring braces in strings."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def _repair_json_strings(text: str) -> str:
    """Escape only malformed string content; leave JSON structure untouched."""
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            in_string = not in_string
            out.append(char)
            index += 1
            continue
        if not in_string:
            out.append(char)
            index += 1
            continue
        if char in "\r\n\t":
            out.append({"\r": "\\r", "\n": "\\n", "\t": "\\t"}[char])
            index += 1
            continue
        if char != "\\" or index + 1 >= len(text):
            out.append(char)
            index += 1
            continue

        nxt = text[index + 1]
        if nxt == "\\":
            out.extend(("\\", "\\"))
            index += 2
            continue
        command = re.match(r"[A-Za-z]+", text[index + 1:])
        if command and command.group(0) in _LATEX_COMMANDS:
            out.extend(("\\", "\\"))
            index += 1
            continue
        if nxt == "u":
            digits = text[index + 2:index + 6]
            if len(digits) != 4 or any(ch not in _HEX for ch in digits):
                out.extend(("\\", "\\"))
            else:
                out.append("\\")
            index += 1
            continue
        if nxt not in {'"', "/", "b", "f", "n", "r", "t"}:
            out.extend(("\\", "\\"))
        else:
            out.append("\\")
        index += 1
    return "".join(out)


def load_model_json(text: str) -> dict[str, Any]:
    """Parse a model JSON object with one string-only repair pass."""
    cleaned = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL).strip()
    candidate = _first_json_object(cleaned) or cleaned
    repaired = _repair_json_strings(candidate)
    last_error: json.JSONDecodeError | None = None
    for payload in dict.fromkeys((repaired, candidate)):
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(value, dict):
            raise ValueError("Model response JSON must be an object.")
        return value
    if last_error is not None:
        raise last_error
    raise ValueError("Model response did not contain a JSON object.")
