"""Stage G: independent verification of the lesson numbers.

Inputs are stated HERE (not imported from the solution text) and cross-checked
against canonical.json; derived values are recomputed three ways. On success
the script flips the `verified` flags in canonical.json and writes a report.
"""

import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = ROOT / "output" / "stage_f_content" / "canonical.json"
REPORT = ROOT / "output" / "stage_g_checks" / "report.md"
REPORT.parent.mkdir(parents=True, exist_ok=True)

# --- 1. Problem statement and data (independent of solution text) ---
# Main example: v0 = 2 m/s, a = 3 m/s^2, t = 4 s. Find v and s.
# Pause task (B6): v0 = 0, a = 2 m/s^2, t = 5 s. Find s.
V0, A, T = Fraction(2), Fraction(3), Fraction(4)
W0, B, U = Fraction(0), Fraction(2), Fraction(5)

canon = json.loads(CANON.read_text(encoding="utf-8"))
inputs = {d["id"]: d["value"] for d in canon["data"] if d["kind"] == "input"}

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

assert inputs == {"D-v0": 2, "D-a": 3, "D-t": 4,
                  "D2-v0": 0, "D2-a": 2, "D2-t": 5}, inputs
print("inputs match canonical.json")

# --- 2-3. Solution + programmatic recomputation ---
v = V0 + A * T                                  # F-vel
s_form = V0 * T + A * T**2 / 2                   # F-disp
s_trap = (V0 + v) * T / 2                        # F-avg (trapezoid area)
s_num = sum(V0 + A * (T * i / 10000) for i in range(10000)) * (T / 10000)
s_b6 = W0 * U + B * U**2 / 2
print(f"v={v} s_form={s_form} s_trap={s_trap} s_num~{float(s_num):.4f} s_b6={s_b6}")
assert (v, s_form, s_trap) == (14, 32, 32), "main example mismatch"
assert abs(float(s_num) - 32) < 0.01, "numerical integration mismatch"
assert s_b6 == 25, "B6 mismatch"

derived = {d["id"]: d["value"] for d in canon["data"] if d["kind"] == "derived"}
assert derived == {"D-v": 14, "D-s": 32, "D2-s": 25}, derived
print("derived values match canonical.json")

# --- 4. Dimensions, physical sense, range, rounding ---
dim = {"v0": (1, -1), "a": (1, -2), "t": (0, 1)}  # (m, s) exponents


def add(*ds):
    return (sum(d[0] for d in ds), sum(d[1] for d in ds))


assert add(dim["a"], dim["t"]) == dim["v0"] == (1, -1), "v dims"
assert add(dim["v0"], dim["t"]) == add(dim["a"], dim["t"], dim["t"]) == (1, 0), "s dims"
assert v > V0 > 0 and s_form > 0, "sense"
assert V0 * T < s_form < v * T, "s must lie between v0*t and v*t (no reversal)"
assert all(float(x).is_integer() for x in (v, s_form, s_b6)), "exact integers"
print("dimensions/sense/range/rounding ok")

# --- 6. No errors -> stamp verified, write report ---
for d in canon["data"]:
    if d["kind"] == "derived":
        d["verified"] = "Stage G 2026-10-12"
CANON.write_text(json.dumps(canon, ensure_ascii=False, indent=1), encoding="utf-8")

REPORT.write_text(
    "# Stage G — решение и запись проверок\n\n"
    "Условие (основной пример): v0 = 2 м/с, a = 3 м/с², t = 4 с. Найти v, s.\n\n"
    "## Решение для ученика\n\n"
    "1. Скорость: v = v0 + at = 2 + 3·4 = 14 м/с.\n"
    "2. Перемещение: s = v0·t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32 м.\n"
    "3. Второй способ (трапеция под v(t)): s = (v0 + v)·t/2 = "
    "(2 + 14)·4/2 = 32 м. Сошлось.\n\n"
    "Пауза-задача B6: v0 = 0, a = 2 м/с², t = 5 с → "
    "s = 0·5 + 2·25/2 = 25 м.\n\n"
    "## Независимые проверки (verify_g.py, Fraction-арифметика)\n\n"
    "- Входы скрипта совпали с inputs canonical.json.\n"
    "- v = 14, s = 32 (формула), s = 32 (трапеция), s ≈ 32.00 "
    "(численное интегрирование v(t), 10000 шагов), s_b6 = 25.\n"
    "- Размерности: [a][t] = [v] = м/с; [v][t] = [a][t²] = [s] = м.\n"
    "- Физсмысл: v > v0 > 0, s > 0; 8 < 32 < 56 (между v0·t и v·t, "
    "разворота нет — рамка урока соблюдена).\n"
    "- Округление: все ответы — точные целые, конфликтов нет.\n"
    "- canonical.json: флаги derived → «Stage G 2026-10-12».\n",
    encoding="utf-8",
)
print("report written, canonical.json stamped")
