# PhysLab UI audit — 10 October 2026

Scope: current PyQt6 application, baseline 4K screenshots in `ui-screenshots/companions/`, and code in `aetherlab/ui/`. Findings below separate observed layout issues from behavior risks that require interaction testing.

| Screen / control | Observation or risk | Type | Source | Intended correction | Verification |
|---|---|---|---|---|---|
| Home hero | Large full-width blue field holds a short sentence and one button; the companion is squeezed into a 228px card within it. | Observed layout | `student_views.py:StudentDashboard._build` | Give the next step and companion separate balanced cards; reduce unused blue surface. | Render at 960, 1280, 1440, 1920 widths. |
| Narrow home | Companion is hidden at less than 640px available width. | Confirmed behavior risk | `student_views.py:_apply_responsive_layout` | Reflow it beneath the next step; do not hide a primary profile feature. | Resize and verify the companion and selection action remain reachable. |
| Home plan without a goal | Empty ring and “not set” take a large card; no direct setup action is in the dashboard card. | Observed layout / interaction gap | `student_views.py:refresh` | Compact the empty state and route a button to existing goal settings. | Open from home; save a goal; return and see progress. |
| Companion picker | Image rectangles have beige backgrounds inside white option cards; wide vertical gaps dilute hierarchy. | Observed layout | `companion_dialog.py`, `study_visuals.py` | Use one coherent preview surface per option and tighter card layout. | Render all three in RU, KK, EN at laptop size and high DPR. |
| Companion art | QImage is first scaled to widget logical size before QPainter renders on a high-DPR device; crop coordinates are hardcoded against one 4K sheet. | Code risk | `study_visuals.py:CompanionArt.paintEvent` | Render original source rectangle at device resolution; verify 3×3 art grid. | Inspect at DPR 1, 1.5, 2 and all nine combinations. |
| Colors | `theme.py`, `style.py`, CSS token file, widget-local QSS and QPainter literals all define visible color roles independently. | Maintainability / consistency | `theme.py`, `style.py`, `design/tokens/colors.css`, UI modules | Establish a shared semantic palette for shipped student UI, update remaining local overrides. | Color inventory after work; compare all reachable screens. |
| QSS overrides | Some selectors occur again at the bottom of `style.py`; final rule may override an earlier one. | Code risk | `style.py` | Consolidate the shipped state rules. | Inspect effective computed styles and button states. |
| Sidebar | Eight icon-and-tiny-label entries occupy a fixed 92px rail even at wide screen size. | Observed readability issue | `navigation.py:SidebarNav` | Use full labels when space allows; retain compact rail at smaller widths. | Navigate all routes at multiple window widths and languages. |
| Profile avatar | Only initials or crop are expected; long names and photos of different proportions may show errors. | Interaction risk | `profile_avatar.py`, `profile_dialog.py` | Check circular crop, focus, tooltip and persistence. | Switch profiles and restart app. |
| Practice and result | Existing complex views use local color literals and fixed dimensions; redesign can regress timer, answer state, idempotent save or PDF export. | Regression risk | `exam_practice.py`, `ent_practice_progress.py` | Update visual hierarchy without changing scoring semantics. | Finish/cancel/retry mock; review mistakes; export. |
| Leaderboard | Remote endpoint may not be configured; client/server source files do not prove live sync. | Operational risk | `leaderboard_dialog.py`, `leaderboard_client.py` | Explain unconfigured/offline/empty states; never invent peers. | Test missing school ID, missing mock, missing endpoint and live endpoint if available. |
| Language | KK/RU/EN strings are distributed among modules, and fixed widgets may clip long text. | Regression risk | `student_views.py`, `navigation.py`, dialogs | Preserve state during language switch, allow wrapping. | Render and interact in all three languages. |

Baseline image: `ui-screenshots/companions/contact-sheet-physlab-new-companions-4k.png`. The baseline comparison uses isolated screenshot data, not a real learner's profile. Update this table as fixes are verified; do not mark an untested risk as resolved.

## Outcome after implementation

| Finding | Outcome | Evidence / limit |
|---|---|---|
| Oversized home hero and hidden companion | Rebuilt as separate feature cards; companion reflows below at narrow width. | `home-ru-4k.png`, `home-kk-narrow-4k.png`; responsive test checks ownership and visibility. |
| Empty study plan | No empty ring; visible setup action routes to practice goal settings. | `home-ru-4k.png`; `StudentDashboard.plan_settings_requested` is wired in `MainWindow`. |
| Companion backgrounds and blurry DPR render | Uses the three dedicated 4K evolution sheets, cropped by measured column bounds and drawn from original pixels into rounded preview surfaces. The dedicated images are packaged. | `companions-ru-4k.png`, `companions-kk-4k.png`, `companions-en-4k.png`, `contact-sheet-companion-stages-4k.png`; nine forms and three picker languages visually inspected. Source-image cream backgrounds remain intentionally within framed previews. |
| Palette drift | Default student UI now uses muted blue semantic colors in theme, QSS and audited local styles; CSS color tokens were aligned. | 4K captures across major routes; theme/layout regression test. Non-default theme presets still retain their own colors. |
| Fixed compact sidebar | Full labels at wide widths; shorter, non-overlapping rail buttons in short windows. | Wide/narrow captures and short-window geometry test. |
| Empty progress view | Compact framed state with one working practice action. | `progress-ru-4k.png`. |
| Result topic table overflow | Removed horizontal scrolling in the captured 4K result by reducing bar width and table cell spacing. | `result-ru-4k.png`. |
| Standalone companion dialog font | Installs bundled Cyrillic/Kazakh-capable font itself. | `companions-ru-4k.png`; dialog test. |
| Profile and leaderboard | Circular avatar is now in the persistent top bar and opens the profile from every route; the dashboard duplicate is hidden. Existing profile and ranking logic preserved; colors aligned and empty/offline state captured. | `profile-ru-4k.png`, `leaderboard-ru-4k.png`; profile and ranking tests. Online sync not verified because no HTTPS endpoint is configured. |

The screenshot capture tools use `tmp/ui-next-level-preview` and a separate screenshot practice progress file. The perfect 50/50 result image is a generated demonstration attempt; it is not a real student's score.
