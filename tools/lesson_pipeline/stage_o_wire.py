"""Stage O: wire the prebuilt 5-min v2 lesson into the app catalog/storage.

Inputs (only): canonical.json v2 (chapters/narrations), practice.json H1-H5
(questions), params.json (measured block durations), Stage M finals + SRT,
Stage N PDFs.
Outputs: content/ent/constant_acceleration_5min.json (frozen v2 content +
media manifest) and content/ent/media/constant_acceleration_5min/<lang>/
(lesson mp4/srt/pdf copies). Verifies offsets, hashes, counts.
"""
from __future__ import annotations

if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()


import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "output/stage_f_content/canonical.json"
PRACTICE = ROOT / "output/stage_h_practice/practice.json"
PARAMS = ROOT / "output/stage_m_final/params.json"
FINALS = ROOT / "output/stage_m_final"
PDFS = ROOT / "output/stage_n_pdf"
OUT_JSON = ROOT / "content/ent/constant_acceleration_5min.json"
OUT_MEDIA = ROOT / "content/ent/media/constant_acceleration_5min"

LANGS = ("ru", "kk", "en")
BLOCKS = [f"B{i}" for i in range(8)]

EQ = {
    "F-accel-def": "a = \u0394v/\u0394t",
    "F-vel": "v = v\u2080 + at",
    "F-disp": "s = v\u2080t + at\u00b2/2",
    "F-avg": "s = (v\u2080 + v)\u00b7t/2",
}
M_BY_LANG = {"ru": "\u043c", "kk": "\u043c", "en": "m"}

TITLES = {
    "B0": {"ru": "\u041a\u0440\u044e\u0447\u043e\u043a \u0438 \u0446\u0435\u043b\u044c",
           "kk": "\u0406\u043b\u043c\u0435\u043a \u0436\u04d9\u043d\u0435 \u043c\u0430\u049b\u0441\u0430\u0442",
           "en": "Hook and goal"},
    "B1": {"ru": "\u0427\u0442\u043e \u0437\u043d\u0430\u0447\u0438\u0442 \u00ab\u0440\u0430\u0432\u043d\u043e\u0443\u0441\u043a\u043e\u0440\u0435\u043d\u043d\u043e\u00bb",
           "kk": "\u00ab\u0422\u0435\u04a3\u04af\u0434\u0435\u043c\u0435\u043b\u0456\u00bb \u0434\u0435\u0433\u0435\u043d \u043d\u0435",
           "en": "What \u201cuniformly accelerated\u201d means"},
    "B2": {"ru": "\u0421\u043a\u043e\u0440\u043e\u0441\u0442\u044c v = v\u2080 + at",
           "kk": "\u0416\u044b\u043b\u0434\u0430\u043c\u0434\u044b\u049b v = v\u2080 + at",
           "en": "Velocity v = v\u2080 + at"},
    "B3": {"ru": "\u041f\u0435\u0440\u0435\u043c\u0435\u0449\u0435\u043d\u0438\u0435 s = v\u2080t + at\u00b2/2",
           "kk": "\u041e\u0440\u044b\u043d \u0430\u0443\u044b\u0441\u0442\u044b\u0440\u0443 s = v\u2080t + at\u00b2/2",
           "en": "Displacement s = v\u2080t + at\u00b2/2"},
    "B4": {"ru": "\u0413\u0440\u0430\u0444\u0438\u043a v(t)",
           "kk": "v(t) \u0433\u0440\u0430\u0444\u0438\u0433\u0456",
           "en": "The v(t) graph"},
    "B5": {"ru": "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043f\u043b\u043e\u0449\u0430\u0434\u044c\u044e",
           "kk": "\u0410\u0443\u0434\u0430\u043d\u043c\u0435\u043d \u0442\u0435\u043a\u0441\u0435\u0440\u0443",
           "en": "Check by area"},
    "B6": {"ru": "\u041f\u0430\u0443\u0437\u0430-\u0437\u0430\u0434\u0430\u0447\u0430",
           "kk": "\u041a\u0456\u0434\u0456\u0440\u0456\u0441-\u0435\u0441\u0435\u043f",
           "en": "Pause-and-solve"},
    "B7": {"ru": "\u041b\u043e\u0432\u0443\u0448\u043a\u0438 \u0438 \u0438\u0442\u043e\u0433",
           "kk": "\u049a\u0430\u049b\u043f\u0430\u043d\u0434\u0430\u0440 \u043c\u0435\u043d \u049b\u043e\u0440\u044b\u0442\u044b\u043d\u0434\u044b",
           "en": "Traps and recap"},
}
GOALS = {
    "B0": {"ru": "\u041f\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u0432\u043e\u043f\u0440\u043e\u0441 \u0443\u0440\u043e\u043a\u0430: \u0441\u043a\u043e\u043b\u044c\u043a\u043e \u043c\u0435\u0442\u0440\u043e\u0432 \u043f\u0440\u043e\u0448\u043b\u0430 \u043c\u0430\u0448\u0438\u043d\u0430.",
           "kk": "\u0421\u0430\u0431\u0430\u049b \u0441\u04b1\u0440\u0430\u0493\u044b\u043d \u049b\u043e\u044e: \u043c\u04d9\u0448\u0438\u043d\u0435 \u049b\u0430\u043d\u0448\u0430 \u043c\u0435\u0442\u0440 \u0436\u04af\u0440\u0434\u0456.",
           "en": "Pose the lesson question: how far did the car go."},
    "B1": {"ru": "\u0420\u0430\u0432\u043d\u043e\u0443\u0441\u043a\u043e\u0440\u0435\u043d\u043d\u043e \u2014 \u0440\u0430\u0432\u043d\u044b\u0435 \u043f\u0440\u0438\u0431\u0430\u0432\u043a\u0438 \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u0438 \u0437\u0430 \u0440\u0430\u0432\u043d\u044b\u0435 \u0432\u0440\u0435\u043c\u0435\u043d\u0430.",
           "kk": "\u0422\u0435\u04a3\u04af\u0434\u0435\u043c\u0435\u043b\u0456 \u2014 \u0442\u0435\u04a3 \u0443\u0430\u049b\u044b\u0442\u0442\u0430 \u0436\u044b\u043b\u0434\u0430\u043c\u0434\u044b\u049b\u0442\u044b\u04a3 \u0431\u0456\u0440\u0434\u0435\u0439 \u0430\u0440\u0442\u0443\u044b.",
           "en": "Uniformly accelerated means equal velocity gains in equal times."},
    "B2": {"ru": "\u0412\u044b\u0432\u0435\u0441\u0442\u0438 \u0438 \u043f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c v = v\u2080 + at: 2 + 3\u00b74 = 14 \u043c/\u0441.",
           "kk": "v = v\u2080 + at \u0444\u043e\u0440\u043c\u0443\u043b\u0430\u0441\u044b\u043d \u0448\u044b\u0493\u0430\u0440\u044b\u043f \u049b\u043e\u043b\u0434\u0430\u043d\u0443: 2 + 3\u00b74 = 14 \u043c/\u0441.",
           "en": "Derive and apply v = v\u2080 + at: 2 + 3\u00b74 = 14 m/s."},
    "B3": {"ru": "\u0412\u044b\u0447\u0438\u0441\u043b\u0438\u0442\u044c \u043f\u0435\u0440\u0435\u043c\u0435\u0449\u0435\u043d\u0438\u0435 s = v\u2080t + at\u00b2/2 = 32 \u043c.",
           "kk": "\u041e\u0440\u044b\u043d \u0430\u0443\u044b\u0441\u0442\u044b\u0440\u0443\u0434\u044b \u0435\u0441\u0435\u043f\u0442\u0435\u0443: s = v\u2080t + at\u00b2/2 = 32 \u043c.",
           "en": "Compute displacement s = v\u2080t + at\u00b2/2 = 32 m."},
    "B4": {"ru": "\u041f\u043e\u0441\u0442\u0440\u043e\u0438\u0442\u044c \u043f\u0440\u044f\u043c\u0443\u044e v = 2 + 3t; \u043d\u0430\u043a\u043b\u043e\u043d \u0440\u0430\u0432\u0435\u043d \u0443\u0441\u043a\u043e\u0440\u0435\u043d\u0438\u044e.",
           "kk": "v = 2 + 3t \u0442\u04af\u0437\u0443\u0456\u043d \u0441\u0430\u043b\u0443; \u043a\u04e9\u043b\u0431\u0435\u0443 \u04af\u0434\u0435\u0443\u0433\u0435 \u0442\u0435\u04a3.",
           "en": "Plot the line v = 2 + 3t; slope equals acceleration."},
    "B5": {"ru": "\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u043e\u0442\u0432\u0435\u0442 \u043f\u043b\u043e\u0449\u0430\u0434\u044c\u044e \u0442\u0440\u0430\u043f\u0435\u0446\u0438\u0438: 32 \u043c.",
           "kk": "\u0416\u0430\u0443\u0430\u043f\u0442\u044b \u0442\u0440\u0430\u043f\u0435\u0446\u0438\u044f \u0430\u0443\u0434\u0430\u043d\u044b\u043c\u0435\u043d \u0442\u0435\u043a\u0441\u0435\u0440\u0443: 32 \u043c.",
           "en": "Check the answer by the trapezoid area: 32 m."},
    "B6": {"ru": "\u0420\u0435\u0448\u0438\u0442\u044c \u0441\u0430\u043c\u043e\u043c\u0443: v\u2080 = 0, a = 2, t = 5 \u2192 s = 25 \u043c.",
           "kk": "\u04e8\u0437\u0456\u04a3 \u0448\u044b\u0493\u0430\u0440\u0443: v\u2080 = 0, a = 2, t = 5 \u2192 s = 25 \u043c.",
           "en": "Solve alone: v\u2080 = 0, a = 2, t = 5 \u2192 s = 25 m."},
    "B7": {"ru": "\u0420\u0430\u0437\u043e\u0431\u0440\u0430\u0442\u044c \u043b\u043e\u0432\u0443\u0448\u043a\u0438 56 \u043c \u0438 \u00ab\u043d\u0430\u043a\u043b\u043e\u043d\u2194\u043f\u043b\u043e\u0449\u0430\u0434\u044c\u00bb; \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c \u0442\u0440\u0438 \u0444\u043e\u0440\u043c\u0443\u043b\u044b.",
           "kk": "56 \u043c \u0436\u04d9\u043d\u0435 \u00ab\u043a\u04e9\u043b\u0431\u0435\u0443\u2194\u0430\u0443\u0434\u0430\u043d\u00bb \u049b\u0430\u049b\u043f\u0430\u043d\u0434\u0430\u0440\u044b\u043d \u0442\u0430\u043b\u0434\u0430\u0443; \u04af\u0448 \u0444\u043e\u0440\u043c\u0443\u043b\u0430\u043d\u044b \u049b\u0430\u0439\u0442\u0430\u043b\u0430\u0443.",
           "en": "Dissect the 56 m and slope\u2194area traps; recap the three formulas."},
}
SYMBOLS = {
    "B0": [], "B1": ["v", "a", "t"], "B2": ["v\u2080", "a", "t", "v"],
    "B3": ["s", "v\u2080", "a", "t"], "B4": ["v", "t", "a"], "B5": ["s"],
    "B6": ["s", "v\u2080", "a", "t"], "B7": ["v", "s", "a"],
}
CITE_KEYS = {
    "B0": [], "B1": ["zak9"], "B2": ["zak9"], "B3": ["zak9", "zak10"],
    "B4": ["zak10"], "B5": ["zak10", "zak9"], "B6": ["zak10"], "B7": ["tc3", "fbs"],
}
CITES = {
    "zak9": {
        "ru": "\u041d.\u0410. \u0417\u0430\u043a\u0438\u0440\u043e\u0432\u0430, \u00ab\u0424\u0438\u0437\u0438\u043a\u0430\u00bb, 9 \u043a\u043b\u0430\u0441\u0441, PDF \u0441. 19\u201329: \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d\u0438\u044f \u0438 \u0442\u0430\u0431\u043b\u0438\u0446\u0430 \u0444\u043e\u0440\u043c\u0443\u043b.",
        "kk": "\u041d.\u0410. \u0417\u0430\u043a\u0438\u0440\u043e\u0432\u0430, \u00ab\u0424\u0438\u0437\u0438\u043a\u0430\u00bb, 9-\u0441\u044b\u043d\u044b\u043f, PDF 19\u201329-\u0431.: \u0430\u043d\u044b\u049b\u0442\u0430\u043c\u0430\u043b\u0430\u0440 \u043c\u0435\u043d \u0444\u043e\u0440\u043c\u0443\u043b\u0430\u043b\u0430\u0440 \u043a\u0435\u0441\u0442\u0435\u0441\u0456.",
        "en": "N.A. Zakirova, Physics, grade 9, PDF pp. 19\u201329: definitions and formula table."},
    "zak10": {
        "ru": "\u041d.\u0410. \u0417\u0430\u043a\u0438\u0440\u043e\u0432\u0430, \u00ab\u0424\u0438\u0437\u0438\u043a\u0430\u00bb, 10 \u043a\u043b\u0430\u0441\u0441 \u0416\u041c, \u00a73, PDF \u0441. 15\u201318, 20: \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0438 \u043f\u0440\u0430\u0432\u0438\u043b\u043e \u043f\u043b\u043e\u0449\u0430\u0434\u0438.",
        "kk": "\u041d.\u0410. \u0417\u0430\u043a\u0438\u0440\u043e\u0432\u0430, \u00ab\u0424\u0438\u0437\u0438\u043a\u0430\u00bb, 10-\u0441\u044b\u043d\u044b\u043f \u0416\u041c, \u00a73, PDF 15\u201318, 20-\u0431.: \u0433\u0440\u0430\u0444\u0438\u043a\u0442\u0435\u0440 \u043c\u0435\u043d \u0430\u0443\u0434\u0430\u043d \u0435\u0440\u0435\u0436\u0435\u0441\u0456.",
        "en": "N.A. Zakirova, Physics, grade 10, \u00a73, PDF pp. 15\u201318, 20: graphs and the area rule."},
    "fbs": {
        "ru": "Sailaubaev, FBS, PDF \u0441. 6\u20137: \u0441\u0432\u0435\u0440\u043a\u0430 \u0444\u043e\u0440\u043c\u0443\u043b \u0438 \u0442\u0435\u0440\u043c\u0438\u043d\u043e\u0432.",
        "kk": "Sailaubaev, FBS, PDF 6\u20137-\u0431.: \u0444\u043e\u0440\u043c\u0443\u043b\u0430\u043b\u0430\u0440 \u043c\u0435\u043d \u0442\u0435\u0440\u043c\u0438\u043d\u0434\u0435\u0440\u0434\u0456 \u0441\u0430\u043b\u044b\u0441\u0442\u044b\u0440\u0443.",
        "en": "Sailaubaev, FBS, PDF pp. 6\u20137: formula and term cross-check."},
    "tc3": {
        "ru": "\u041d\u0426\u0422, \u0441\u0431\u043e\u0440\u043d\u0438\u043a-3, \u0437\u0430\u0434\u0430\u0447\u0430 1 (PDF \u0441. 2; \u043a\u043b\u044e\u0447 B, \u0441. 37): \u0444\u043e\u0440\u043c\u0430\u0442 \u0437\u0430\u0434\u0430\u0447\u0438 \u043d\u0430 \u043f\u043b\u043e\u0449\u0430\u0434\u044c \u0433\u0440\u0430\u0444\u0438\u043a\u0430.",
        "kk": "\u04b0\u0411\u0422, 3-\u0436\u0438\u043d\u0430\u049b, 1-\u0435\u0441\u0435\u043f (PDF 2-\u0431.; B \u043a\u0456\u043b\u0442\u0456, 37-\u0431.): \u0433\u0440\u0430\u0444\u0438\u043a \u0430\u0443\u0434\u0430\u043d\u044b\u043d\u0430 \u0435\u0441\u0435\u043f \u0444\u043e\u0440\u043c\u0430\u0442\u044b.",
        "en": "NCT collection 3, task 1 (PDF p. 2; key B, p. 37): graph-area task format."},
}
META = {
    "ru": {
        "title": "\u0420\u0430\u0432\u043d\u043e\u0443\u0441\u043a\u043e\u0440\u0435\u043d\u043d\u043e\u0435 \u043f\u0440\u044f\u043c\u043e\u043b\u0438\u043d\u0435\u0439\u043d\u043e\u0435 \u0434\u0432\u0438\u0436\u0435\u043d\u0438\u0435",
        "topic": "\u0420\u0430\u0432\u043d\u043e\u0443\u0441\u043a\u043e\u0440\u0435\u043d\u043d\u043e\u0435 \u0434\u0432\u0438\u0436\u0435\u043d\u0438\u0435 \u00b7 5-\u043c\u0438\u043d\u0443\u0442\u043d\u043e\u0435 \u0432\u0438\u0434\u0435\u043e",
        "prerequisites": ["\u0421\u043a\u043e\u0440\u043e\u0441\u0442\u044c \u0438 \u0435\u0434\u0438\u043d\u0438\u0446\u044b \u043c/\u0441.",
                            "\u041f\u043b\u043e\u0449\u0430\u0434\u044c \u043f\u0440\u044f\u043c\u043e\u0443\u0433\u043e\u043b\u044c\u043d\u0438\u043a\u0430 \u0438 \u0442\u0440\u0435\u0443\u0433\u043e\u043b\u044c\u043d\u0438\u043a\u0430."],
        "objectives": ["\u0412\u044b\u0447\u0438\u0441\u043b\u044f\u0442\u044c v = v\u2080 + at \u0438 s = v\u2080t + at\u00b2/2 \u043f\u043e v\u2080, a, t.",
                       "\u0427\u0438\u0442\u0430\u0442\u044c \u0433\u0440\u0430\u0444\u0438\u043a v(t): \u043d\u0430\u043a\u043b\u043e\u043d \u2014 \u0443\u0441\u043a\u043e\u0440\u0435\u043d\u0438\u0435, \u043f\u043b\u043e\u0449\u0430\u0434\u044c \u2014 \u043f\u0435\u0440\u0435\u043c\u0435\u0449\u0435\u043d\u0438\u0435.",
                       "\u041f\u0440\u043e\u0432\u0435\u0440\u044f\u0442\u044c \u043e\u0442\u0432\u0435\u0442 \u0432\u0442\u043e\u0440\u044b\u043c \u0441\u043f\u043e\u0441\u043e\u0431\u043e\u043c \u0438 \u0443\u0437\u043d\u0430\u0432\u0430\u0442\u044c \u043b\u043e\u0432\u0443\u0448\u043a\u0438 \u0415\u041d\u0422."],
        "misconception": "\u041a\u043e\u043d\u0435\u0447\u043d\u0443\u044e \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u044c \u043d\u0435\u043b\u044c\u0437\u044f \u043f\u043e\u0434\u0441\u0442\u0430\u0432\u043b\u044f\u0442\u044c \u0432 \u0444\u043e\u0440\u043c\u0443\u043b\u0443 \u0440\u0430\u0432\u043d\u043e\u043c\u0435\u0440\u043d\u043e\u0433\u043e \u0434\u0432\u0438\u0436\u0435\u043d\u0438\u044f; \u043d\u0430\u043a\u043b\u043e\u043d \u0433\u0440\u0430\u0444\u0438\u043a\u0430 \u2014 \u044d\u0442\u043e \u0443\u0441\u043a\u043e\u0440\u0435\u043d\u0438\u0435, \u0430 \u043d\u0435 \u043f\u0435\u0440\u0435\u043c\u0435\u0449\u0435\u043d\u0438\u0435."},
    "kk": {
        "title": "\u0422\u0435\u04a3\u04af\u0434\u0435\u043c\u0435\u043b\u0456 \u0442\u04af\u0437\u0443 \u0441\u044b\u0437\u044b\u049b\u0442\u044b \u049b\u043e\u0437\u0493\u0430\u043b\u044b\u0441",
        "topic": "\u0422\u0435\u04a3\u04af\u0434\u0435\u043c\u0435\u043b\u0456 \u049b\u043e\u0437\u0493\u0430\u043b\u044b\u0441 \u00b7 5 \u043c\u0438\u043d\u0443\u0442\u0442\u044b\u049b \u0432\u0438\u0434\u0435\u043e",
        "prerequisites": ["\u0416\u044b\u043b\u0434\u0430\u043c\u0434\u044b\u049b \u0436\u04d9\u043d\u0435 \u043c/\u0441 \u0431\u0456\u0440\u043b\u0456\u043a\u0442\u0435\u0440\u0456.",
                            "\u0422\u0456\u043a\u0442\u04e9\u0440\u0442\u0431\u04b1\u0440\u044b\u0448 \u0436\u04d9\u043d\u0435 \u04af\u0448\u0431\u04b1\u0440\u044b\u0448 \u0430\u0443\u0434\u0430\u043d\u044b."],
        "objectives": ["v\u2080, a, t \u0431\u043e\u0439\u044b\u043d\u0448\u0430 v = v\u2080 + at \u0436\u04d9\u043d\u0435 s = v\u2080t + at\u00b2/2 \u0435\u0441\u0435\u043f\u0442\u0435\u0443.",
                       "v(t) \u0433\u0440\u0430\u0444\u0438\u0433\u0456\u043d \u043e\u049b\u0443: \u043a\u04e9\u043b\u0431\u0435\u0443 \u2014 \u04af\u0434\u0435\u0443, \u0430\u0443\u0434\u0430\u043d \u2014 \u043e\u0440\u044b\u043d \u0430\u0443\u044b\u0441\u0442\u044b\u0440\u0443.",
                       "\u0416\u0430\u0443\u0430\u043f\u0442\u044b \u0435\u043a\u0456\u043d\u0448\u0456 \u0442\u04d9\u0441\u0456\u043b\u043c\u0435\u043d \u0442\u0435\u043a\u0441\u0435\u0440\u0456\u043f, \u04b0\u0411\u0422 \u049b\u0430\u049b\u043f\u0430\u043d\u0434\u0430\u0440\u044b\u043d \u0442\u0430\u043d\u0443."],
        "misconception": "\u0421\u043e\u04a3\u0493\u044b \u0436\u044b\u043b\u0434\u0430\u043c\u0434\u044b\u049b\u0442\u044b \u0431\u0456\u0440\u049b\u0430\u043b\u044b\u043f\u0442\u044b \u049b\u043e\u0437\u0493\u0430\u043b\u044b\u0441 \u0444\u043e\u0440\u043c\u0443\u043b\u0430\u0441\u044b\u043d\u0430 \u049b\u043e\u044e\u0493\u0430 \u0431\u043e\u043b\u043c\u0430\u0439\u0434\u044b; \u0433\u0440\u0430\u0444\u0438\u043a \u043a\u04e9\u043b\u0431\u0435\u0443\u0456 \u2014 \u04af\u0434\u0435\u0443, \u043e\u0440\u044b\u043d \u0430\u0443\u044b\u0441\u0442\u044b\u0440\u0443 \u0435\u043c\u0435\u0441."},
    "en": {
        "title": "Uniformly accelerated rectilinear motion",
        "topic": "Uniformly accelerated motion \u00b7 5-minute video",
        "prerequisites": ["Velocity and m/s units.",
                          "Area of a rectangle and a triangle."],
        "objectives": ["Compute v = v\u2080 + at and s = v\u2080t + at\u00b2/2 from v\u2080, a, t.",
                       "Read a v(t) graph: slope is acceleration, area is displacement.",
                       "Cross-check an answer a second way and spot UNT traps."],
        "misconception": "Final velocity must not go into the uniform-motion formula; graph slope is acceleration, not displacement."},
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
    practice = json.loads(PRACTICE.read_text(encoding="utf-8"))
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    assert canonical.get("version") == 2, "canonical must be v2"
    assert [b["id"] for b in canonical["blocks"]] == BLOCKS
    assert [i["id"] for i in practice["items"]] == ["H1", "H2", "H3", "H4", "H5"]

    # Measured block starts: cumsum of Stage M durations; must agree across langs.
    starts_by_lang = {}
    for lang in LANGS:
        starts, t = [], 0.0
        for b in BLOCKS:
            starts.append(t)
            t += float(params[lang][f"Block{b}"]["duration_s"])
        starts_by_lang[lang] = starts
    for lang in LANGS[1:]:
        assert starts_by_lang[lang] == starts_by_lang["ru"], f"offset drift {lang}"
    offsets = starts_by_lang["ru"]
    total = offsets[-1] + float(params["ru"]["BlockB7"]["duration_s"])
    assert abs(total - 299.96666666666664) < 1e-6, total

    formulas = {f["id"]: f for f in canonical["formulas"]}
    for fid in EQ:
        assert fid in formulas, fid

    def block_equations(bid: str, lang: str) -> list[str]:
        blk = next(b for b in canonical["blocks"] if b["id"] == bid)
        out = [EQ[fid] for fid in blk["formulas"]]
        if bid == "B4":
            out.append("v = 2 + 3t")
        if bid == "B5":
            out.append(f"S = (2 + 14)/2 \u00b7 4 = 32 {M_BY_LANG[lang]}")
        return out

    chapters = {}
    for lang in LANGS:
        vo_key = f"voiceover_{lang}"
        cap_key = "captions" if lang == "ru" else f"captions_{lang}"
        lang_chapters = []
        for blk in canonical["blocks"]:
            bid = blk["id"]
            lang_chapters.append({
                "id": bid.lower(),
                "block": bid,
                "title": TITLES[bid][lang],
                "goal": GOALS[bid][lang],
                "kind": "scene",
                "beats": list(blk[cap_key]),
                "narration": blk[vo_key],
                "key_equations": block_equations(bid, lang),
                "citations": [CITES[k][lang] for k in CITE_KEYS[bid]],
                "key_symbols": list(SYMBOLS[bid]),
            })
        chapters[lang] = lang_chapters

    questions = {}
    for lang in LANGS:
        lang_q = []
        for item in practice["items"]:
            opts = [f"{o['id']}) {o['label'][lang]}" for o in item["options"]]
            correct = next(o for o in item["options"]
                           if o["id"] == item["correct_option_id"])
            lang_q.append({
                "id": item["id"],
                "q": item["prompt"][lang],
                "choices": opts,
                "answer": f"{correct['id']}) {correct['label'][lang]}",
                "why": item["explanation"][lang],
            })
        questions[lang] = lang_q

    # Copy media + manifest with hashes.
    media = {}
    for lang in LANGS:
        dest_dir = OUT_MEDIA / lang
        dest_dir.mkdir(parents=True, exist_ok=True)
        for kind, src in (("video", FINALS / lang / f"lesson_{lang}.mp4"),
                          ("srt", FINALS / lang / f"lesson_{lang}.srt"),
                          ("pdf", PDFS / f"lesson_{lang}.pdf")):
            assert src.is_file() and src.stat().st_size > 0, src
            dest = dest_dir / src.name
            shutil.copy2(src, dest)
            media.setdefault(lang, {})[kind] = {
                "path": f"media/constant_acceleration_5min/{lang}/{src.name}",
                "bytes": dest.stat().st_size,
                "sha256": sha256_of(dest),
            }

    payload = {
        "route_id": "constant_acceleration_5min",
        "version": "physlab-ent-constant-acceleration-5min-v2",
        "audience": "high_school",
        "duration_seconds": total,
        "chapter_offsets": offsets,
        "review_status": {
            "physics_calculation": "checked_by_deterministic_calculation",
            "kazakh_russian_english_wording": "needs_teacher_review",
        },
        "built_from": {
            "canonical_sha256": sha256_of(CANONICAL),
            "practice_sha256": sha256_of(PRACTICE),
            "params": "output/stage_m_final/params.json",
        },
        "meta": META,
        "chapters": chapters,
        "questions": questions,
        "media": media,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    # Verify: round-trip, files, hashes, counts.
    back = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    assert back["chapter_offsets"] == offsets
    base = OUT_JSON.parent
    for lang in LANGS:
        assert len(back["chapters"][lang]) == 8, lang
        assert len(back["questions"][lang]) == 5, lang
        assert all(q["choices"] and q["answer"] in q["choices"]
                   for q in back["questions"][lang]), lang
        assert all(c["narration"] for c in back["chapters"][lang]), lang
        for kind in ("video", "srt", "pdf"):
            entry = back["media"][lang][kind]
            p = base / entry["path"]
            assert p.is_file(), p
            assert sha256_of(p) == entry["sha256"], p
    n_cites = len({c for lang in LANGS for ch in back["chapters"][lang]
                   for c in ch["citations"]})
    print(f"OK: {OUT_JSON.name} 8 chapters x3, 5 questions x3, "
          f"{n_cites} citations, total {total:.3f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
