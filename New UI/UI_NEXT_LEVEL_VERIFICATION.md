# PhysLab UI next level — verification

The redesign was applied to the PyQt6 app. Captures in `ui-screenshots/ui-next-level/` are 3840×2160 PNG made from an isolated preview data directory. Existing user profiles were not used for screenshots.

| Screen | Control / action | Expected behavior | Verified result |
|---|---|---|---|
| Shell | Sidebar: Home, Topics, Progress, AI, Library, History, Lab | Opens the selected route; selected item follows route | Existing route test passes; individual route PNGs captured and inspected. Practice item opens its modal and returns selection to the previous route. |
| Home | Train topic | Opens training with recommended topic ID | Signal and handler traced; topic route/practice tests pass. |
| Home | Study | Opens the existing lesson route | Signal connects to `_start_ent_topic_lesson`; kinematics maps to the curated acceleration lesson. AI-generated lessons require a working provider. |
| Home | Set goal | Opens practice settings for date, target and weekly questions | Signal connected to `MainWindow.open_exam_practice`; modal captured. |
| Home | Select companion | Opens picker and persists accepted selection for the active profile | Picker/dashboard/profile-local tests pass; cancel leaves saved choice unchanged. |
| Shell / Home | Ranking and persistent avatar | Opens leaderboard and profile dialogs; avatar is visible on every route | Both dialogs captured; top-bar profile switch test passes. School ranking stays offline without an HTTPS server. |
| Topics | Search, filter, Study, Train | Filters real topics; routes selected topic | Topic search/filter/lesson test passes. |
| Practice | Mode, answer, finish/cancel, PDF | Uses current scoring and save flow | Tests cover single-answer exclusivity, full mock 50-point result, language preservation, cancellation and idempotent save. PDF export UI is present; actual export was not executed in this visual pass. |
| Progress | Empty-state practice action | Opens a training modal | Connected to existing `practice_requested` signal; empty state captured. |
| Companions | All 3×3 forms | Draws matching character and stage without cut-off | In-app `CompanionArt` rendering captured and inspected in `contact-sheet-companion-stages-4k.png`. |
| Leaderboard | Server address / update | Shows local/offline state until a real HTTPS endpoint exists | Offline state captured. `AETHERLAB_LEADERBOARD_URL` is not set here, so cross-device sync remains unverified. |

Validation: 43 targeted tests passed, including a shell test at 960×640, 1280×720, 1440×900 and 1920×1080 logical pixels in KK/RU/EN. Ruff passed for changed Python UI code and capture tools. Visually reviewed separate 4K captures of all major routes, the profile, ranking, practice setup, question, result, companion picker, and a 960×540 logical compact window rendered at 4× scale. Every platform DPI setting was not exhaustively exercised in a native Windows session; offscreen Qt captures are evidence of layout, not a complete device-compatibility guarantee.
