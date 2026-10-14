# PhysLab UI bug audit — 9 October 2026

The supplied screenshot showed a small blank PhysLab window above the topic catalogue, an inconsistent page breadcrumb, and a patterned scrollbar track.

## Fixes

- **Unexpected floating windows:** topic cards were shown while still parentless. A Qt event trace recorded 25 top-level card show events per catalogue rebuild. Cards now belong to their scroll content from construction, and enter the layout before becoming visible. Deferred deletion retains widget ownership instead of detaching widgets into windows.
- **Practice navigation:** opening the modal leaves the underlying page breadcrumb and selected destination consistent. Duplicate practice dialogs are prevented. Redundant catalogue and dashboard rebuilds were removed.
- **Dialog lifetime:** finished practice dialogs are disposed of after their modal run. Closing a timed attempt stops its timer and does not save a result later.
- **Results:** repeated completion events cannot save the same attempt twice.
- **Mistake review:** the progress-page action starts the saved mistake set directly.
- **Practice settings:** changing language preserves topic, difficulty, mode and unsaved goal controls. Unavailable difficulty levels are disabled; changing topic clears an unsupported level and displays the available question count.
- **Scrollbars:** page tracks have an explicit transparent style, removing the native patterned fill.
- **Narrow tutor:** connection and library controls stack, local-AI labels have concise text with full tooltips, and Russian examples use compact full-width rows. Headline, spacing and minimum row heights prevent clipped text. Reflow clears obsolete column stretches.

## Verification

- 27 focused UI, practice, routing and integration checks passed.
- The audit traced navigation and refreshes in Kazakh, Russian and English without unexpected top-level widget shows.
- All 40 question views were checked in all three languages at 640×580 without horizontal overflow.
- Tutor content, including local-AI controls, fits 558×466 in all three languages. Example-button width and height checks use the bundled fonts.
- Python compilation and Git whitespace checks passed.
- The running Windows app was restarted and its topic catalogue and practice open/close flow inspected.

These checks cover the reviewed UI and practice workflows; they are not a claim that every backend feature has been exhaustively tested.
