"""Stage N: build trilingual study-guide PDFs from canonical v2 content.

Inputs (only): canonical.json v2, practice.json H1-H5, registry.md citations,
Stage G solution numbers. No re-invented solutions: every number/formula is
copied from stage outputs; script fails loudly on unexpected content.

Pipeline per lang: matplotlib figures (DejaVu Sans) -> .tex (xelatex,
Times New Roman + amsmath) -> compile -> verify (log scan, fitz text/
formulas/figures/metadata, sources page-range check) -> verify_report.md.

Usage: python tools/lesson_pipeline/stage_n_pdf.py [ru kk en]
"""

if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()


import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fontTools.ttLib import TTFont

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
OUT = ROOT / "output" / "stage_n_pdf"
REFS = Path(r"C:\Users\sunak\Projects\References")
CANON = ROOT / "output" / "stage_f_content" / "canonical.json"
PRACTICE = ROOT / "output" / "stage_h_practice" / "practice.json"

LANGS = ["ru", "kk", "en"]
FONTS_DIR = Path(r"C:/Windows/Fonts")

# ---------------------------------------------------------------- data ---

T = {
    "title": {"ru": "Равноускоренное прямолинейное движение",
              "kk": "Теңүдемелі түзу сызықты қозғалыс",
              "en": "Uniformly accelerated rectilinear motion"},
    "lang_name": {"ru": "Русский", "kk": "Қазақша", "en": "English"},
    "guide_word": {"ru": "конспект", "kk": "конспект", "en": "study guide"},
    "content_word": {"ru": "содержание", "kk": "мазмұн", "en": "content"},
    "goal": {
        "ru": None,  # verbatim from canonical.json
        "kk": "Видео соңында оқушы бастапқы жылдамдық, үдеу және уақыт бойынша "
              "теңүдемелі дененің жылдамдығы мен орын ауыстыруын есептеп, жауапты "
              "v(t) графигі астындағы ауданмен тексере алады.",
        "en": "After the video the student can find the velocity and displacement "
              "of a uniformly accelerated body from initial velocity, acceleration "
              "and time, and check the answer by the area under the v(t) graph."},
    "sec": {
        "goal": {"ru": "Цель", "kk": "Мақсат", "en": "Goal"},
        "expl": {"ru": "Коротко о главном", "kk": "Негізгі мәселе",
                 "en": "The idea in brief"},
        "quant": {"ru": "Величины и единицы", "kk": "Шамалар мен бірліктер",
                  "en": "Quantities and units"},
        "form": {"ru": "Формулы и условия", "kk": "Формулалар мен шарттар",
                 "en": "Formulas and conditions"},
        "fig": {"ru": "Рисунки", "kk": "Суреттер", "en": "Figures"},
        "example": {"ru": "Решённый пример", "kk": "Шығарылған мысал",
                    "en": "Worked example"},
        "traps": {"ru": "Ловушки", "kk": "Қақпандар", "en": "Traps"},
        "tasks": {"ru": "Самостоятельные задания", "kk": "Өздік тапсырмалар",
                  "en": "Practice tasks"},
        "answers": {"ru": "Ответы", "kk": "Жауаптар", "en": "Answers"},
        "sources": {"ru": "Источники", "kk": "Дереккөздер", "en": "Sources"},
    },
    # conditions: standard-physics prose, data-free (from applicability/axis)
    "cond": {
        "ru": ["Движение прямолинейное, ось Ox направлена по движению.",
               "Ускорение постоянно по величине и направлению.",
               "Скорость не меняет знак — разворота нет, перемещение равно пути.",
               "Все величины в СИ: м, с, м/с, м/с²."],
        "kk": ["Қозғалыс түзу сызықты, Ox осі қозғалыс бойымен бағытталған.",
               "Үдеу шамасы мен бағыты бойынша тұрақты.",
               "Жылдамдық таңбасын өзгертпейді — бұрылыс жоқ, "
               "орын ауыстыру жолға тең.",
               "Барлық шамалар СИ жүйесінде: м, с, м/с, м/с²."],
        "en": ["Motion is rectilinear, the x axis points along the motion.",
               "Acceleration is constant in magnitude and direction.",
               "Velocity keeps its sign — no reversal, displacement equals distance.",
               "All quantities in SI: m, s, m/s, m/s²."],
    },
    "fname": {  # formula display names (terms.md grounded)
        "F-accel-def": {"ru": "Определение ускорения", "kk": "Үдеудің анықтамасы",
                        "en": "Definition of acceleration"},
        "F-vel": {"ru": "Скорость", "kk": "Жылдамдық", "en": "Velocity"},
        "F-disp": {"ru": "Перемещение", "kk": "Орын ауыстыру", "en": "Displacement"},
        "F-avg": {"ru": "Перемещение через среднюю скорость",
                  "kk": "Орташа жылдамдық арқылы орын ауыстыру",
                  "en": "Displacement via average velocity"},
    },
    "qname": {  # quantity names (terms.md) + units
        "v0": ({"ru": "начальная скорость", "kk": "бастапқы жылдамдық",
                "en": "initial velocity"},
               {"ru": "м/с", "kk": "м/с", "en": "m/s"}),
        "v": ({"ru": "конечная скорость", "kk": "соңғы жылдамдық",
               "en": "final velocity"},
              {"ru": "м/с", "kk": "м/с", "en": "m/s"}),
        "a": ({"ru": "ускорение", "kk": "үдеу", "en": "acceleration"},
              {"ru": "м/с²", "kk": "м/с²", "en": "m/s²"}),
        "t": ({"ru": "время", "kk": "уақыт", "en": "time"},
              {"ru": "с", "kk": "с", "en": "s"}),
        "s": ({"ru": "перемещение", "kk": "орын ауыстыру", "en": "displacement"},
              {"ru": "м", "kk": "м", "en": "m"}),
    },
    "given": {"ru": "Дано", "kk": "Берілгені", "en": "Given"},
    "find": {"ru": "Найти", "kk": "Табу керек", "en": "Find"},
    "check_units": {
        "ru": "Проверка единиц: м/с² · с = м/с — сходится.",
        "kk": "Бірліктерді тексеру: м/с² · с = м/с — сәйкес.",
        "en": "Units check: m/s² · s = m/s — consistent."},
    "trap1": {
        "ru": "Ловушка 1: $14\\cdot 4 = 56$ — неверно: скорость росла, "
              "брать надо среднюю.",
        "kk": "Қақпан 1: $14\\cdot 4 = 56$ — қате: жылдамдық өсті, "
              "орташасын алу керек.",
        "en": "Trap 1: $14\\cdot 4 = 56$ — wrong: the speed was growing, "
              "take the average."},
    "trap2": {
        "ru": "Ловушка 2: наклон — это ускорение, площадь — перемещение.",
        "kk": "Қақпан 2: көлбеу — бұл үдеу, аудан — орын ауыстыру.",
        "en": "Trap 2: slope is acceleration, area is displacement."},
    "pause": {  # B6: data from canon D2-*, standard task form
        "ru": "Машина стартует с места с ускорением 2 м/с². "
              "Сколько она пройдёт за 5 с?",
        "kk": "Мәшине орнынан 2 м/с² үдеумен қозғалды. "
              "5 с-та қанша жол жүреді?",
        "en": "A car starts from rest with acceleration 2 m/s². "
              "How far does it go in 5 s?"},
    "pause_ans": {
        "ru": "$s = 0\\cdot 5 + 2\\cdot 25/2 = 25$ м.",
        "kk": "$s = 0\\cdot 5 + 2\\cdot 25/2 = 25$ м.",
        "en": "$s = 0\\cdot 5 + 2\\cdot 25/2 = 25$ m."},
    "cap_vt": {
        "ru": "График $v(t) = 2 + 3t$: наклон прямой — ускорение $a = 3$; "
              "закрашенная площадь — перемещение $s = 32$.",
        "kk": "$v(t) = 2 + 3t$ графигі: түзудің көлбеуі — үдеу $a = 3$; "
              "боялған аудан — орын ауыстыру $s = 32$.",
        "en": "Graph of $v(t) = 2 + 3t$: the slope is the acceleration $a = 3$; "
              "the shaded area is the displacement $s = 32$."},
    "cap_bars": {
        "ru": "Перемещение двумя слагаемыми: $v_0t = 8$ плюс $at^2/2 = 24$; "
              "итого $s = 32$ м.",
        "kk": "Орын ауыстыру екі қосылғышпен: $v_0t = 8$ плюс $at^2/2 = 24$; "
              "барлығы $s = 32$ м.",
        "en": "Displacement in two terms: $v_0t = 8$ plus $at^2/2 = 24$; "
              "total $s = 32$ m."},
    "status": {
        "ru": "Статус: физика и ключи проверены независимо (этап G); "
              "переводы и термины требуют проверки учителем.",
        "kk": "Күйі: физика мен кілттер тәуелсіз тексерілді (G кезең); "
              "аударма мен терминдерді мұғалім тексеруі керек.",
        "en": "Status: physics and keys independently checked (Stage G); "
              "translations and terms need teacher review."},
    "sources_intro": {
        "ru": "Определения, формулы и графические правила сверены с учебниками; "
              "номера — страницы PDF-файлов. Задания конспекта оригинальные.",
        "kk": "Анықтамалар, формулалар мен график ережелері оқулықтармен "
              "салыстырылды; нөмірлер — PDF-беттер. Конспект тапсырмалары төл.",
        "en": "Definitions, formulas and graph rules are cross-checked against "
              "the textbooks; numbers are PDF page numbers. Guide tasks are original."},
}

# registry.md citations: (file, pages, role) — verified against References/
SOURCES = [
    ("Физика Закирова 9.pdf", "19–29",
     {"ru": "определения и таблица формул",
      "kk": "анықтамалар мен формулалар кестесі",
      "en": "definitions and formula table"}),
    ("Физика Закирова 10 ЖМ.pdf", "15–18, 20",
     {"ru": "графики и правило площади (§3)",
      "kk": "графиктер мен аудан ережесі (§3)",
      "en": "graphs and the area rule (§3)"}),
    ("FBS (1).pdf", "6–7",
     {"ru": "сверка формул и терминов (Sailaubaev)",
      "kk": "формулалар мен терминдерді салыстыру (Sailaubaev)",
      "en": "formula and term cross-check (Sailaubaev)"}),
    ("Testcenter -3.pdf", "2, 37",
     {"ru": "формат ЕНТ-задачи на площадь графика (задача 1, с. 2; ключ B, с. 37)",
      "kk": "график ауданына ҰБТ есебінің форматы (1-есеп, 2-б.; B кілті, 37-б.)",
      "en": "ENT graph-area task format (task 1, p. 2; key B, p. 37)"}),
]
NCT_URLS = [
    ("ru", "https://new.testcenter.kz/wp-content/uploads/2024/12/obr_var_test_02.pdf"),
    ("en", "https://new.testcenter.kz/wp-content/uploads/2025/06/PHYSICS.pdf"),
]

# explanation = verbatim voiceover sentences (block -> sentence indices)
EXPL_SENT = {"B1": [0, 1, 2, 3, 4, 5, 6], "B2": [0, 1, 3], "B3": [0, 1],
             "B4": [2, 3], "B5": [1]}
EXPL_COUNT = {"B1": 7, "B2": 5, "B3": 6, "B4": 4, "B5": 5}

# prose-embedded formulas in practice.json -> LaTeX (keys have no escapables)
FORMULA_MAP = {
    "v = v₀ + at = 2 + 3·4 = 14": "$v = v_0 + at = 2 + 3\\cdot 4 = 14$",
    "s = v₀t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32":
        "$s = v_0t + at^2/2 = 2\\cdot 4 + 3\\cdot 16/2 = 8 + 24 = 32$",
    "(2 + 14)/2 · 4 = 32": "$(2 + 14)/2 \\cdot 4 = 32$",
    "a = Δv/Δt": "$a = \\Delta v/\\Delta t$",
}
# glyphs that must never reach the .tex as raw text (no Times coverage / wrong)
RISKY = "₀₁₂Δ✓✗→•×"


def esc(text: str) -> str:
    from aetherlab.services.pdf import _latex_escape

    out = _latex_escape(text)
    for raw, latex in FORMULA_MAP.items():
        out = out.replace(raw, latex)
    bad = sorted(set(out) & set(RISKY))
    assert not bad, f"risky glyphs left in tex: {bad} :: {text[:80]}"
    return out


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in text.split(". ")]
    out = []
    for i, p in enumerate(parts):
        if i < len(parts) - 1:
            p += "."
        out.append(p)
    return [p for p in out if p]


def check_fonts() -> None:
    """Every non-ASCII text char must exist in Times regular+bold (titles)."""
    cmaps = {}
    for name in ("times.ttf", "timesbd.ttf"):
        font = TTFont(FONTS_DIR / name)
        cmaps[name] = set()
        for table in font["cmap"].tables:
            cmaps[name].update(table.cmap.keys())
    mpl_font = TTFont(Path(matplotlib.get_data_path()) / "fonts" / "ttf"
                      / "DejaVuSans.ttf")
    mpl_cmap = set()
    for table in mpl_font["cmap"].tables:
        mpl_cmap.update(table.cmap.keys())
    return cmaps, mpl_cmap


def assert_covered(text: str, cmaps: dict, where: str) -> None:
    chars = {c for c in text if ord(c) > 127}
    for name, cmap in cmaps.items():
        missing = sorted(c for c in chars if ord(c) not in cmap)
        assert not missing, f"{where}: {name} lacks {missing}"


# ------------------------------------------------------------- figures ---

def fig_vt(lang: str, mpl_cmap: set) -> Path:
    unit_t = T["qname"]["t"][1][lang]
    unit_v = T["qname"]["v"][1][lang]
    xl, yl = f"t, {unit_t}", f"v, {unit_v}"
    pt = f"(4 {unit_t}; 14 {unit_v})"
    assert_covered(xl + yl + pt, {"DejaVuSans": mpl_cmap}, "fig_vt")
    fig, ax = plt.subplots(figsize=(6.2, 3.6), dpi=300)
    ax.plot([0, 4], [2, 14], color="#1a56db", linewidth=2.5)
    ax.fill_between([0, 4], [2, 14], color="#1a56db", alpha=0.18)
    ax.plot([0, 4], [2, 14], "o", color="#1a56db", markersize=5)
    ax.annotate(pt, xy=(4, 14), xytext=(8, -14), textcoords="offset points",
                fontsize=10)
    ax.set_xlim(-0.2, 4.6)
    ax.set_ylim(0, 16)
    ax.set_xlabel(xl, fontsize=11)
    ax.set_ylabel(yl, fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    dst = OUT / f"fig_vt_{lang}.png"
    fig.savefig(dst)
    plt.close(fig)
    return dst


def fig_bars(lang: str, mpl_cmap: set) -> Path:
    unit_s = T["qname"]["s"][1][lang]
    labels = ["$v_0t = 8$", "$at^2/2 = 24$"]
    assert_covered(unit_s, {"DejaVuSans": mpl_cmap}, "fig_bars")
    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=300)
    bars = ax.bar([0, 1], [8, 24], color=["#1a56db", "#0e9f6e"], width=0.55)
    ax.bar_label(bars, labels=[f"{l} {unit_s}" for l in labels], fontsize=11)
    ax.axhline(32, color="#c81e1e", linestyle="--", linewidth=1.5)
    ax.text(1.42, 32, f"$s = 32$ {unit_s}", va="center", fontsize=11,
            color="#c81e1e")
    ax.set_xlim(-0.6, 1.9)
    ax.set_ylim(0, 38)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f"$v_0t$", f"$at^2/2$"], fontsize=12)
    ax.set_ylabel(unit_s, fontsize=11)
    fig.tight_layout()
    dst = OUT / f"fig_bars_{lang}.png"
    fig.savefig(dst)
    plt.close(fig)
    return dst


# ----------------------------------------------------------------- tex ---

def build_tex(lang: str, canon: dict, practice: dict, cmaps: dict) -> str:
    assert canon["version"] == 2
    data = {d["symbol"]: d for d in canon["data"] if "scope" not in d}
    assert (data["v0"]["value"], data["a"]["value"], data["t"]["value"],
            data["v"]["value"], data["s"]["value"]) == (2, 3, 4, 14, 32)
    d2 = {d["symbol"]: d for d in canon["data"] if d.get("scope") == "B6"}
    assert (d2["v0"]["value"], d2["a"]["value"], d2["t"]["value"],
            d2["s"]["value"]) == (0, 2, 5, 25)
    formulas = {f["id"]: f["latex"] for f in canon["formulas"]}
    assert set(formulas) == {"F-accel-def", "F-vel", "F-disp", "F-avg"}
    blocks = {b["id"]: b for b in canon["blocks"]}
    S = T["sec"]

    L: list[str] = []
    sha8 = hashlib.sha256(CANON.read_bytes()).hexdigest()[:8]
    title = esc(T["title"][lang])
    L.append(r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\usepackage{amsmath,amssymb}
\usepackage[margin=2.3cm]{geometry}
\usepackage{booktabs,graphicx,xcolor}
\usepackage{hyperref}
\hypersetup{colorlinks=true,urlcolor=blue}
\sloppy
""")
    L.append(f"\\hypersetup{{pdftitle={{{title}}},"
             f"pdfsubject={{PhysLab study guide, content canonical v2 ({sha8}), "
             f"lang {lang}}},pdfauthor={{PhysLab}},pdflang={{{lang}}}}}")
    L.append("\\begin{document}")
    L.append(f"{{\\small\\color{{gray}} PhysLab / ЕНТ • ҰБТ / "
             f"{esc(T['lang_name'][lang])} \\quad "
             f"{esc(T['guide_word'][lang])} v2 \\quad "
             f"{esc(T['content_word'][lang])} canonical v2 ({sha8})}}\n")
    L.append(f"\\section*{{{title}}}")

    # goal
    goal = canon["goal"] if lang == "ru" else T["goal"][lang]
    L.append(f"\\subsection*{{{esc(S['goal'][lang])}}}\n{esc(goal)}\n")

    # explanation: verbatim voiceover sentences
    L.append(f"\\subsection*{{{esc(S['expl'][lang])}}}")
    for bid, idxs in EXPL_SENT.items():
        vo = blocks[bid][f"voiceover_{lang}"]
        sents = split_sentences(vo)
        assert len(sents) == EXPL_COUNT[bid], (bid, lang, len(sents))
        for i in idxs:
            L.append(esc(sents[i]) + "\n")

    # quantities + units
    L.append(f"\\subsection*{{{esc(S['quant'][lang])}}}")
    L.append("\\begin{tabular}{lll}\\toprule")
    for sym in ("v0", "a", "t", "v", "s"):
        names, units = T["qname"][sym]
        sym_tex = {"v0": "$v_0$", "a": "$a$", "t": "$t$", "v": "$v$",
                   "s": "$s$"}[sym]
        L.append(f"{sym_tex} & {esc(names[lang])} & "
                 f"{data[sym]['value']} {esc(units[lang])} \\\\")
    L.append("\\bottomrule\\end{tabular}\n")

    # formulas + conditions
    L.append(f"\\subsection*{{{esc(S['form'][lang])}}}")
    for fid in ("F-accel-def", "F-vel", "F-disp", "F-avg"):
        L.append(f"\\textbf{{{esc(T['fname'][fid][lang])}:}} "
                 f"\\[{formulas[fid]}\\]")
    L.append("\\begin{itemize}")
    for c in T["cond"][lang]:
        L.append(f"\\item {esc(c)}")
    L.append("\\end{itemize}\n")

    # figures
    L.append(f"\\subsection*{{{esc(S['fig'][lang])}}}")
    L.append("\\begin{figure}[htbp]\\centering")
    L.append(f"\\includegraphics[width=0.85\\textwidth]{{fig_vt_{lang}.png}}"
             f"\\caption{{{T['cap_vt'][lang]}}}\\end{{figure}}\n")
    L.append("\\begin{figure}[htbp]\\centering")
    L.append(f"\\includegraphics[width=0.7\\textwidth]{{fig_bars_{lang}.png}}"
             f"\\caption{{{T['cap_bars'][lang]}}}\\end{{figure}}\n")

    # worked example (Stage G numbers, fixed)
    L.append(f"\\subsection*{{{esc(S['example'][lang])}}}")
    uv, ua, ut, us = (T["qname"][k][1][lang] for k in ("v", "a", "t", "s"))
    L.append(f"{esc(T['given'][lang])}: $v_0 = 2$ {esc(uv)}, $a = 3$ {esc(ua)}, "
             f"$t = 4$ {esc(ut)}. {esc(T['find'][lang])}: $v$, $s$.\n")
    L.append("\\begin{enumerate}")
    L.append(f"\\item $v = v_0 + at = 2 + 3\\cdot 4 = 14$ {esc(uv)}.")
    L.append(f"\\item $s = v_0t + at^2/2 = 2\\cdot 4 + 3\\cdot 16/2 "
             f"= 8 + 24 = 32$ {esc(us)}.")
    L.append(f"\\item $s = (v_0+v)t/2 = (2+14)\\cdot 4/2 = 32$ {esc(us)}.")
    L.append("\\end{enumerate}")
    L.append(esc(T["check_units"][lang]) + "\n")

    # traps
    L.append(f"\\subsection*{{{esc(S['traps'][lang])}}}")
    L.append("\\begin{itemize}")
    L.append(f"\\item {T['trap1'][lang]}")
    L.append(f"\\item {esc(T['trap2'][lang])}")
    L.append("\\end{itemize}\n")

    # tasks H1-H5 + pause B6
    L.append(f"\\subsection*{{{esc(S['tasks'][lang])}}}")
    L.append("\\begin{enumerate}")
    items = practice["items"]
    assert [it["id"] for it in items] == ["H1", "H2", "H3", "H4", "H5"]
    for it in items:
        L.append(f"\\item {esc(it['prompt'][lang])}")
        opts = " \\quad ".join(
            f"\\textbf{{{o['id']})}} {esc(o['label'][lang])}"
            for o in it["options"])
        L.append(opts + "\n")
    L.append(f"\\item {esc(T['pause'][lang])}")
    L.append("\\end{enumerate}")

    # answers on their own page
    L.append(f"\\newpage\\subsection*{{{esc(S['answers'][lang])}}}")
    L.append("\\begin{enumerate}")
    for it in items:
        L.append(f"\\item \\textbf{{{it['correct_option_id']}}} — "
                 f"{esc(it['explanation'][lang])}\n")
    L.append(f"\\item \\textbf{{25 {esc(us)}}} — {T['pause_ans'][lang]}")
    L.append("\\end{enumerate}\n")

    # sources
    L.append(f"\\subsection*{{{esc(S['sources'][lang])}}}")
    L.append(esc(T["sources_intro"][lang]))
    L.append("\\begin{itemize}")
    for fname, pages, role in SOURCES:
        L.append(f"\\item {esc(fname)} — {esc(role[lang])}: PDF с. {pages}.")
    for slang, url in NCT_URLS:
        L.append(f"\\item NCT physics sample ({slang}): \\url{{{url}}}")
    L.append("\\end{itemize}\n")
    L.append(esc(T["status"][lang]))
    L.append("\\end{document}\n")

    tex = "\n".join(L)
    # font coverage: strip math spans (CM fonts), check the rest vs Times
    text_only = re.sub(r"\\\[.*?\\\]", "", tex, flags=re.S)
    text_only = re.sub(r"\$.*?\$", "", text_only)
    assert_covered(text_only, cmaps, f"tex/{lang}")
    return tex


# ------------------------------------------------------------- compile ---

def compile_tex(tex_path: Path) -> dict:
    proc = subprocess.run(
        ["xelatex", "-interaction=nonstopmode",
         "-output-directory", str(OUT), str(tex_path)],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace")
    log_path = OUT / (tex_path.stem + ".log")
    log = log_path.read_text(encoding="utf-8", errors="replace") \
        if log_path.is_file() else ""
    missing = len(re.findall(r"Missing character", log))
    overfull = re.findall(r"Overfull \\hbox \(([\d.]+)pt", log)
    return {"returncode": proc.returncode, "missing_chars": missing,
            "overfull": [float(x) for x in overfull]}


# -------------------------------------------------------------- verify ---

def verify_pdf(lang: str, problems: list[str]) -> dict:
    import fitz

    pdf = OUT / f"lesson_{lang}.pdf"
    doc = fitz.open(pdf)
    pages = len(doc)
    full = "\n".join(p.get_text("text") for p in doc)
    meta = doc.metadata
    S = T["sec"]
    facts: dict = {"pages": pages, "chars": len(full),
                   "title": meta.get("title"), "subject": meta.get("subject")}
    assert pages >= 4, (lang, pages)
    assert len(full) > 4000, (lang, len(full))  # selectable body text
    for fp in ["14", "32", "25", "56", "2 + 3", "37", "19", "29",
               S["answers"][lang], S["sources"][lang], "testcenter.kz",
               "canonical v2"]:
        assert fp in full, (lang, f"missing fingerprint {fp!r}")
    assert meta.get("title") == T["title"][lang], meta
    assert f"lang {lang}" in (meta.get("subject") or ""), meta
    # figures: >=2 images, all inside page rect (no clipping)
    n_img = 0
    for pno, page in enumerate(doc):
        for img in page.get_images(full=True):
            for r in page.get_image_rects(img[0]):
                inside = (r.x0 >= -1 and r.y0 >= -1
                          and r.x1 <= page.rect.x1 + 1
                          and r.y1 <= page.rect.y1 + 1)
                assert inside, (lang, pno, tuple(r))
                n_img += 1
    assert n_img >= 2, (lang, n_img)
    facts["images"] = n_img
    # review PNGs for the human page-check (Stage P)
    thumbs = OUT / "pages" / lang
    thumbs.mkdir(parents=True, exist_ok=True)
    for pno, page in enumerate(doc):
        page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(
            thumbs / f"p{pno + 1:02d}.png")
    facts["thumbs"] = pages
    doc.close()
    return facts


def verify_sources() -> dict:
    import fitz

    need = {"Физика Закирова 9.pdf": 29, "Физика Закирова 10 ЖМ.pdf": 20,
            "FBS (1).pdf": 7, "Testcenter -3.pdf": 37}
    out = {}
    for fname, min_pages in need.items():
        p = REFS / fname
        assert p.is_file(), fname
        with fitz.open(p) as doc:
            out[fname] = len(doc)
            assert len(doc) >= min_pages, (fname, len(doc))
    return out


# ---------------------------------------------------------------- main ---

def main(langs: list[str]) -> None:
    canon = json.loads(CANON.read_text(encoding="utf-8"))
    practice = json.loads(PRACTICE.read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    cmaps, mpl_cmap = check_fonts()
    print("fonts ok: Times regular+bold, DejaVuSans", flush=True)
    src_pages = verify_sources()
    print(f"sources ok: {src_pages}", flush=True)

    report = ["# Stage N — verify report", ""]
    for lang in langs:
        fig_vt(lang, mpl_cmap)
        fig_bars(lang, mpl_cmap)
        tex = build_tex(lang, canon, practice, cmaps)
        tex_path = OUT / f"lesson_{lang}.tex"
        tex_path.write_text(tex, encoding="utf-8")
        comp = compile_tex(tex_path)
        assert comp["returncode"] == 0, (lang, comp)
        assert comp["missing_chars"] == 0, (lang, comp)
        assert not comp["overfull"], (lang, comp)
        print(f"{lang}: compiled, no missing glyphs, no overfull", flush=True)
        facts = verify_pdf(lang, [])
        print(f"{lang}: {facts['pages']} pages, {facts['chars']} chars, "
              f"{facts['images']} figures placed", flush=True)
        report += [f"## {lang}",
                   f"- pages: {facts['pages']}, chars: {facts['chars']}, "
                   f"figures: {facts['images']}",
                   f"- compile: rc=0, missing=0, overfull={comp['overfull']}",
                   f"- fingerprints 14/32/25/56/B6-key/registry-pages: present",
                   f"- metadata: {facts['title']} / {facts['subject']}", ""]
    report += ["## sources (References/ page counts)",
               *[f"- {k}: {v} pages" for k, v in src_pages.items()]]
    (OUT / "verify_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"report -> {OUT / 'verify_report.md'}", flush=True)


if __name__ == "__main__":
    want = [a for a in sys.argv[1:] if a in LANGS] or LANGS
    assert set(sys.argv[1:]) <= set(LANGS), sys.argv[1:]
    main(want)
