# Lesson video pipeline (ENT Manim stages)

Stage tooling for the trilingual (ru/kk/en) 300-second ENT physics video
lesson *"Uniformly accelerated rectilinear motion"*. These scripts generate
and verify the lesson artefacts under `output/stage_*` — they are a snapshot
of the working pipeline, kept for reproducibility.

Workflow context: `docs/PHYSLAB_MANIM_ENT_VIDEO_MASTER_PROMPT.md` (stages
C–P) and `docs/PHYSLAB_ENT_VIDEO_WORKLOG.md` (SyncFix K2/L2 entry).

> All scripts hardcode `ROOT = C:\Users\sunak\Projects\aetherlab` — adjust
> to your checkout. Voice scripts need `edge-tts`.

## Core flow (in order)

| Script | Purpose |
|---|---|
| `lesson_template.py` | Master Manim template: 8 Scene classes (B0–B7) with per-shot timing; `GEN:*` placeholders baked per language |
| `gen_scenes.py` | Bakes `lesson_template.py` → `output/stage_l_scenes/lesson_{ru,kk,en}.py` (captions/formulas/LaTeX→unicode) |
| `verify_l.py` | Stage L gate: canonical-data match, no-LaTeX, 8 Scene subclasses, caption refs, preflight duration ±0.6 s + zero off-frame (with sub-frame-wait correction) |
| `gen_fragments.py` | Splits whole-block narration into 45 measured fragments → `stage_k2_fragments/fragments.json` |
| `stage_k2_synth.py` | Synthesizes 135 fragment clips (45 × 3 langs) with retry/backoff → `durations.json` |
| `check_k2.py` | Cross-checks K2 fragment sums against whole-block K clips |
| `mux_plan.py` | Per-language fragment offsets per shot (gap ≥ 0.15 s) → `mux_plan.json` for Stage M |
| `probe_words.py` / `show_words.py` | edge-tts WordBoundary timings for key fragments (numbers 8/24/32/2/14/56, formula names) |
| `show_texts.py` | Dumps fragment sentences with caption mapping (review aid) |
| `contact_sheet.py` | Builds the per-second preview contact sheet (`contact_sheet.html`) |
| `stage_l_preview.py` | Stage L preview orchestration |

## Earlier-stage scripts

`stage_c_probe.py`, `render_f.py`, `add_i18n.py`, `verify_g.py`,
`verify_h.py`, `verify_i.py`, `verify_j.py`, `stage_k_synth.py`,
`stage_k_b6split.py`, `verify_k.py`, `list_voices.py` — probes, synthesis
and gates for stages C–K, kept for the record.

## Sync-diagnosis probes (SyncFix, 2026-10-13)

`probe_sync.py`, `probe_container.py`, `probe_profiles.py`,
`probe_fullscan.py`, `probe_glyphs.py`, `layout_probe.py`, `probe_b2.py` —
the six-way video exoneration (PTS/frames, per-second accuracy, glyph
regions) plus the preflight `wait(0.3)` measurement probe. Misc reference
helpers: `q1_graph.py`, `ref_dump.py`, `ref_locate.py`, `glyph_match.py`,
`diag_cell.py`, `key_cell.py`.
