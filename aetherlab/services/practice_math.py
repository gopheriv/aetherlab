"""Readable prose for the supported math subset in the authored practice bank.

Typeset solutions retain their original LaTeX. This formatter only replaces
those same expressions inside prose; it never evaluates or changes answers.
Unsupported expressions are preserved rather than silently losing operators.
"""

from __future__ import annotations

import re

_SYMBOLS = {
    "Delta": "Δ", "Phi": "Φ", "beta": "β", "gamma": "γ",
    "lambda": "λ", "pi": "π", "rho": "ρ", "varepsilon": "ε",
    "cdot": "·", "times": "×", "left": "", "right": "",
}
_SUBSCRIPTS = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")
_SUPERSCRIPTS = str.maketrans("0123456789+-n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ")


def readable_formula(source: str) -> str:
    """Translate a bounded LaTeX subset, retaining fraction/root grouping."""
    text = str(source).strip()
    if text.startswith("$") and text.endswith("$"):
        text = text[1:-1]
    pos = 0

    def argument() -> str:
        nonlocal pos
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != "{":
            raise ValueError("Expected a grouped formula argument")
        pos += 1
        return sequence(grouped=True)

    def sequence(grouped: bool = False) -> str:
        nonlocal pos
        output = []
        while pos < len(text):
            char = text[pos]
            pos += 1
            if char == "}":
                if not grouped:
                    raise ValueError("Unexpected formula group end")
                return "".join(output)
            if char == "{":
                output.append("(" + sequence(grouped=True) + ")")
            elif char == "\\":
                match = re.match(r"[A-Za-z]+", text[pos:])
                if match is None:
                    if pos < len(text) and text[pos] in ",;! ":
                        output.append(" " if text[pos] != "!" else "")
                        pos += 1
                        continue
                    raise ValueError("Unsupported formula escape")
                command = match.group()
                pos += len(command)
                if command == "frac":
                    numerator, denominator = argument(), argument()
                    output.append(f"({numerator})/({denominator})")
                elif command == "sqrt":
                    output.append(f"√({argument()})")
                elif command == "mathrm":
                    output.append(argument())
                elif command == "overline":
                    value = argument()
                    output.append((value if len(value) == 1 else f"({value})") + "̄")
                elif command in _SYMBOLS:
                    output.append(_SYMBOLS[command])
                    # Whitespace terminates TeX commands; it is not a factor.
                    while pos < len(text) and text[pos].isspace():
                        pos += 1
                else:
                    raise ValueError(f"Unsupported formula command: {command}")
            elif char in "_^":
                if pos < len(text) and text[pos] == "{":
                    value = argument()
                else:
                    match = re.match(r"[+-]?\d+|[A-Za-z]", text[pos:])
                    if match is None:
                        raise ValueError("Missing formula script")
                    value = match.group()
                    pos += len(value)
                allowed = "0123456789+-" if char == "_" else "0123456789+-n"
                table = _SUBSCRIPTS if char == "_" else _SUPERSCRIPTS
                output.append(value.translate(table) if all(c in allowed for c in value) else f"{char}({value})")
            elif char == "$":
                raise ValueError("Unexpected math delimiter")
            else:
                output.append(char)
        if grouped:
            raise ValueError("Unterminated formula argument")
        return "".join(output)

    return sequence()


def readable_explanation(question: dict, language: str) -> str:
    """Replace only source-matched formulas, never arbitrary prose or numbers."""
    explanation = str(question["explanation"])
    replacements = {}
    for expression in question.get("solution_latex", ()):
        formula = str(expression).strip()
        for candidate in (formula, formula.split("=", 1)[-1]):
            if not any(symbol in candidate for symbol in ("\\", "_", "^")):
                continue
            for variant in {candidate, candidate.replace(".", ",") if language != "en" else candidate}:
                try:
                    replacements[variant] = readable_formula(variant)
                except ValueError:
                    continue
    if not replacements:
        return explanation
    # One pass avoids modifying text introduced by another replacement.
    pattern = re.compile("|".join(re.escape(value) for value in sorted(replacements, key=len, reverse=True)))
    return pattern.sub(lambda match: replacements[match.group()], explanation)
