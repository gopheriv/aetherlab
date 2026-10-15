# Manim Settings Upgrade for UNT Format

Status: proposal (2026-10-15)
Audience: Kazakhstan high-school students preparing for the 2026+ physics UNT
Scope: `aetherlab/core/render_profile.py`, `aetherlab/core/settings.py`,
`aetherlab/services/manim_runtime.py`, `aetherlab/services/scene_generator.py`,
`aetherlab/services/scene_validation.py`, `aetherlab/services/voiceover.py`,
lesson assembly + exports. Pinned renderer: Manim Community 0.21.0.

## 1. Goal

Add exam-paced, trilingual UNT render settings alongside the existing
cinematic presets, without breaking `preview` / `standard` / `cinematic`:

- Deterministic 1080p study output (`unt`) + portrait cut (`unt_vertical`).
- Official-style task structure: Given → Find → Solution → Answer + units.
- One MP4 with selectable `kk/ru/en` audio + subtitle tracks, Russian default.
- Tighter duration and validation gates than cinematic mode.

Non-goals: changing the frozen `--manim` relay, changing RAG sources, or
reproducing textbook pages or NCT variant scans.

## 2. Current state (verified)

| Area | File | Behavior |
|---|---|---|
| Presets | `aetherlab/core/render_profile.py` | `preview 854x480@30 q=l`, `standard 1280x720@30 q=m`, `cinematic 1920x1080@60 q=h`, all `cairo`, 16:9 only |
| CLI | `aetherlab/services/manim_runtime.py:_manim_render_command` | Always explicit `--fps` + `-r W,H` + `--seed` + `--renderer` + `--disable_caching` + isolated `--media_dir`; `--max-inflight-encoders` default 4 (env `AETHERLAB_MAX_INFLIGHT_ENCODERS`, 1..8) |
| Settings | `aetherlab/core/settings.py:AppSettings` | `render_preset`, `render_quality`, `render_width/height/fps/renderer`, `adaptive_quality`; env `AETHERLAB_*` wins over saved `settings.json` |
| Cache key | `render_profile.py:identity_key()` | `WxH@fps|renderer|quality|preset|adaptive` hash — preset change invalidates cached media |
| Scene prompt | `aetherlab/services/scene_generator.py` | Cinematic 5-act, wonder target, `±20%` duration, max 3 focal objects, no sentence burn-in, `Text 30-40 / labels 18-24`, `MathTex` once (never in updaters), never touch `config.frame_width/pixel_width` |
| UNT content | `content/ent/*.json`, `services/ent_lesson_catalog.py` | 2026 NCT spec: 40 physics tasks, ~2 min/task; reference route `constant_acceleration_cloud_5min` = 300 s, selectable audio/subtitles, exam graph + key (Testcenter-3 p.2 → B, 12 m) |

## 3. UNT format requirements (distilled)

- In scope: NCT 2026 physics specification topic list (e.g. kinematics = Mechanics 01).
- Pacing: ~2 min/task reminder on task chapters; full topic lesson ~5 min segmented.
- Languages: `kk` + `ru` + `en` narration + `.srt`; `ru` audio default; native teacher review still required for wording.
- Exam blocks on screen: Given (`Берілді` / `Дано`) → Find → Solution → Answer + units + answer letter.
- Graphs: axes labeled with units (`v, m/s`, `t, s`); kinematics area-under-graph shaded and segmented (e.g. `2 + 8 + 2 = 12 m`).
- Citations: specification + textbook cross-checks; no copied tables or page images when source restricts redistribution.

## 4. Proposed settings

### 4.1 New presets

Add to `VALID_PRESETS` in `render_profile.py`:

| Preset | Canvas | FPS | Renderer | `-q` | Adaptive | Use |
|---|---|---|---|---|---|---|
| `unt` | `1920x1080` | 30 | `cairo` | `h` | `False` | Default study output; crisp Cyrillic/Kazakh, deterministic |
| `unt_vertical` | `1080x1920` | 30 | `cairo` | `h` | `False` | Shorts/Reels cut; requires explicit width/height |

Notes:

- `QUALITY_DIMS` stays landscape-only. Vertical works because `_manim_render_command` already passes explicit `-r W,H`; `resolve_resolution()` must receive `render_width=1080` + `render_height=1920` (or env) — never derive vertical from `-q`.
- Clamp range already allows it: `320-3840 x 240-2160`, even-canvas normalized.
- `cinematic` keeps `1080p60`; `4K (k)` stays explicit-flag-only, never a preset.
- `tier_map`: add `unt → unt`, `unt_vertical → unt_vertical`, legacy `ent → unt`.

### 4.2 Settings + env precedence (unchanged order)

1. Explicit function args (`quality=`, `preset=`)
2. Env overrides
3. `AppSettings` fields (env > saved `settings.json` > default)
4. Preset defaults

New/continued env:

| Setting | Env | Example |
|---|---|---|
| Preset | `AETHERLAB_RENDER_PRESET` | `unt`, `unt_vertical` |
| Size (vertical) | `AETHERLAB_RENDER_WIDTH`, `AETHERLAB_RENDER_HEIGHT` | `1080`, `1920` |
| FPS | `AETHERLAB_MANIM_FPS` | `30` |
| Quality | `AETHERLAB_MANIM_QUALITY` | `h` |
| Renderer | `AETHERLAB_MANIM_RENDERER` | `cairo` |
| Adaptive | `AETHERLAB_ADAPTIVE_QUALITY` | `off` for UNT |
| Encoders | `AETHERLAB_MAX_INFLIGHT_ENCODERS` | `4` (1..8) |

`settings.py`: extend `render_preset` validator to accept `unt` / `unt_vertical`; keep `render_width/height/fps = 0` meaning derive, except `unt_vertical` which requires explicit `1080/1920`.

Never silently downgrade: any adaptive fallback must use `describe_fallback()` and land in diagnostics/logs (existing contract).

## 5. Scene generation: UNT mode

Add `unt_mode` storyboard path (do not replace cinematic):

- Acts: `Hook 8 s → Theory 60 s → Worked example 90 s → Official-style task 90 s → Recap + 2-min tactic 30 s`. Segmented per-chapter renders, then existing assembly path.
- Duration gate: `±10%` for UNT (vs `±20%` cinematic). Keep living idle loop in final 2-3 s so the last three sampled frames differ.
- Required elements per task chapter: Given → Find → Solution → Answer, units on every quantity, graph axis labels, shaded area segments where applicable, answer letter (`B`) at hero frame + recap.
- Staging: max 3 focal objects; `ReplacementTransform` / `TransformMatchingTex` for idea continuity; fast reveals `0.6-1.0 s`, climax `2.5-4 s`.
- Portrait: same acts, but layout via `.to_edge()`, `.arrange()`, `scale_to_fit_width()` only. No `config.frame_width/pixel_width` writes in generated code (existing hard constraint).

## 6. Typography, language, safe areas

- LaTeX missing → `Text`-only + unicode math (existing `detect_latex()` rule). LaTeX present → `MathTex` created once, morphed; never construct `MathTex/Tex` inside `always_redraw`/updaters.
- 1080p UNT minimums: titles `36-44`, formulas `32+`, axis labels `24+`, answer letter `40+`. Short labels only; narration carries sentences.
- Font fallback must cover Kazakh `ӘҒҚҢӨҰҮІ`, Cyrillic, Latin. Smoke strings: `Бірқалыпты айнымалы`, `скорость`, `velocity`.
- Palette: 2-3 hues + 1 accent; semantic color stable across acts (driver vs response vs aha). Hero curve glow = wide dim stroke + thin bright stroke.
- Safe areas (1080p): reserve bottom `~180 px` for subtitles/player; no hero text there. `unt_vertical`: reserve bottom `~300 px` + top `~200 px` for platform chrome.

## 7. Narration, subtitles, multi-audio

Keep `services/voiceover.py` pipeline (edge-tts → PyAV measure → optional one re-synth at adjusted rate → imageio-ffmpeg merge). UNT defaults:

- Voices: `kk-KZ-*`, `ru-RU-*`, `en-US-*` (current default `en-US-AndrewMultilingualNeural` stays for English). Fail-soft: missing tts/ffmpeg → keep silent render.
- Sync: re-synth once if `|audio-video| > 10%/15%`; audio-longer pads last frame (`tpad`); audio-shorter keeps full video (no `-shortest`) so closing beats survive.
- Output: one MP4 with 3 audio + 3 `.srt` tracks, `ru` default (matches `constant_acceleration_cloud_5min.json:video_layout`). Narration chunked per chapter and verified against the chapter timeline.
- Exports: study-guide PDF + `ent_practice_pdf.py` answer letters must match the video hero frame.

## 8. Validation gates (`scene_validation.py`)

Fail fast with repair hint:

1. Unknown Manim names / invalid kwargs / malformed LaTeX (existing).
2. UNT duration `±10%` + obvious-motion contract (every act has `.animate`/updater evolution; final frames differ).
3. Required blocks present: Given/Find/Solution/Answer, units, axis labels, answer letter on task chapters.
4. Portrait overflow check for `unt_vertical` (off-screen / overlap).
5. Trilingual number/unit consistency (`12 m` / `12 м` / `12 м`).

Generation/repair prompts must list the safe color palette and require visible motion in every act (existing pattern).

## 9. Perf, cloud, packaging

- Local: `unt` 1080p30 is the laptop-safe default; `max_local_renders = cpu//2 (1..4)`; `render_timeout_scale 0.25-4.0` for 5-min lessons.
- Cloud (`render_mode=auto`, `cloud_render_threshold=3.0`, `600 s` timeout, `8 s` poll): route full 5-min assembles to cloud; single 60-90 s task solves stay local.
- Frozen: keep `aetherlab --manim render ...` relay (PyInstaller `collect_all manim/manimpango/skia/moderngl/av/cloup`); Manim 0.20+ encodes via PyAV so no ffmpeg-CLI dependency for the base render.

## 10. Tests

- `tests/test_render_profile.py`: `unt`/`unt_vertical` resolve; env > settings > preset; even-canvas normalization; `identity_key` invalidates on preset switch; `manim_args()` always explicit `--fps`; invalid preset/renderer fall back with warning.
- `python test_features.py` (250 checks) + `tools/tracker_integrity_audit.py --check` + `tools/feature_surface_audit.py --check` + `python -m pytest -q`.
- Headless media: one `unt` task (60-90 s) + one `unt_vertical` cut; assert `-r` in render logs, `.srt` timings align to chapters, 3 audio tracks present via `av`, no frozen ending.
- Frozen: `packaging/build.py` smoke must print `Scene status: rendered`.

## 11. Rollout

1. Land `render_profile.py` + `settings.py` preset change + unit tests (no prompt change).
2. Add `unt_mode` storyboard + validation gates behind a flag; re-render `constant_acceleration` route as reference.
3. Wire narration/subtitle mux defaults (`ru` default, `kk/en` selectable); verify with native teacher review.
4. Expand ENT bank chapter by chapter; keep `preview/standard/cinematic` untouched.

## 12. Risks

- Vertical depends on explicit `-r 1080,1920` + portrait-safe code; `-q` alone yields landscape — needs the overflow gate.
- Kazakh TTS lexicon (`v нөл`, units) and wording need native physics-teacher review; current JSONs are `clear-draft`.
- 5-min 1080p + vision critic + tournament can wedge laptops — keep UNT `adaptive=False`, cheap-first tournament (`ESCALATE_BELOW_SCORE=8.0`, auto cap 3), and cloud for full lessons.
- No-LaTeX student machines must stay legible `Text`-only; MathTex is enhancement only.

## 13. Acceptance

- `AETHERLAB_RENDER_PRESET=unt python -m aetherlab --smoke` renders 1080p30 with explicit `--fps 30 -r 1920,1080` in logs.
- `unt_vertical` renders `1080x1920@30` with no off-screen hero text.
- Reference task shows Given/Find/Solution/Answer + units + `B`; `.srt` + 3 audio tracks present; study-guide letter matches video.
- Existing `preview/standard/cinematic` renders byte-comparable in behavior (only cache-key invalidation on preset switch).

## References

- `aetherlab/core/render_profile.py`, `aetherlab/core/settings.py`
- `aetherlab/services/manim_runtime.py`, `scene_generator.py`, `scene_validation.py`, `voiceover.py`
- `content/ent/constant_acceleration_cloud_5min.json`, `content/ent/constant_acceleration_route.json`
- `docs/MANIM_BOT_SETTINGS_COMPAT.md`, `docs/ENT_MVP_PLAN.md`, `docs/CLOUD_RENDERING.md`
- NCT 2026 physics specification (authoritative; link in content JSON `official_exam_alignment`)
