# PhysLab feature audit — 12 October 2026

The active objective remains: inventory every feature, derive user stories and
expected behaviour from code, maintain one canonical spreadsheet, test all
stories, document errors, fix logistical/UX defects, and retest the behaviours.
The full objective is not yet proven complete.

## Canonical tracking

`AetherLab_Feature_Tracker.xlsx` is the canonical spreadsheet. Its CSV is a
generated mirror; `build_feature_tracker.py` owns the catalog and consumes
`feature_test_results.json` as test evidence. Do not maintain a parallel status
workbook. Artifact tooling may apply the exact generated matrix while preserving
formatting; the integrity gate compares all rows and columns after export.

The catalog now contains 250 features/stories, including F232–F250 for topic
exercise volume, partial practice, local profiles, profile editing, daily AI
allowance, weekly mocks, resume, optional camera hints, teacher review, local and
shared school rankings, server CLI, companions, confidence/search, localization,
startup quality persistence, media validation and acceleration follow-up practice.

The worksheet adds the check time in UTC, verification scope, behaviour status
and remaining verification. Native filters and frozen ID/category/feature
columns help navigate the catalog. Software PASS/FIXED and complete user-story
acceptance are separate. The current behaviour column remains PARTIAL rather
than inferring native interaction, live cloud or camera success from automation.

## Executed evidence

| Run | Result | Evidence |
| --- | --- | --- |
| New story checks F232–F250 | 19/19 passed | `tmp/feature-new-stories-20261012.log` |
| Complete feature baseline | 248/250 passed; F154/F165 failed | `tmp/feature-goal-baseline-full-20261012.log`, `tmp/feature-goal-baseline-results-20261012.json` |
| Unit baseline | 288 passed; one invalid cloud-video fixture failed | `tmp/feature-goal-unit-native-20261012.log` |
| Complete feature rerun after fixes | 250/250 passed | `tmp/feature-goal-postfix-full-20261012.log`, `feature_test_results.json` |
| Final unit rerun, including camera recovery | 291 passed | `tmp/feature-goal-unit-final-20261012.log` |
| MP4 header memory/media gates | 5 passed | `tests/test_cloud_media_check.py`; full final unit run |
| Poll-retry fixture and media gates | 6 passed together | `tests/test_upgrade_missions.py::test_cloud_poll_retries_a_transient_read_timeout`; targeted post-fix run |
| Surface coverage | 88/88 detected surfaces, 250 rows | `python tools/feature_surface_audit.py --check` |

The full feature checks included actual local Manim output and lesson assembly,
offscreen Qt interactions, service checks and mocked cloud failure/success paths.
They do not establish a live remote render or foreground desktop journey.
The final unit run reported one upstream ChromaDB deprecation warning.

## Corrections

BUG-124–BUG-131 in `ERRORS_FOUND.md` record omitted features/stale references,
false FIXED status with no supplied check, reference/web isolation, the previously
corrected pressure-answer scale, excessive MP4 memory use, invalid test-video
fixtures, audit recovery and camera-outage timing.

MP4 header validation now reads 64 bytes and checks size from the same open file
descriptor. A sparse 128 MiB regression checks that memory use stays below 1 MiB.
The stronger media-validation gate remains enabled; cloud tests now supply real
MP4 fixtures instead of junk with an ftyp signature.

Camera downtime interrupts continuous face-count observations. After an outage,
new missing/multiple-face observations must meet the full threshold; downtime
cannot cause an immediate face flag. Review signals still do not change scores
or declare cheating.

The harness explicitly isolates references and disables web retrieval in offline
checks. Sandboxed runs could not initialize asyncio socketpair or connect to the
loopback leaderboard; a traceback established the environment restriction.
Subsequent authorized runs used isolated workspace test data outside that
restriction. This environment limitation is not recorded as an application bug.

## Outstanding acceptance work

1. Review coverage against the semantics of each story, not only surface names
   or a green feature function. Static assertions and widget construction alone
   do not prove the complete story or its failure-mode expectation.
2. Execute the foreground UI stories, including keyboard use, dialogs, avatar
   selection, persisted state and error recovery. The current Computer Use
   inventory returns the older PhysLab window, but its state capture exposes
   only a title and background content. A separately launched throwaway window
   reached `Window shown` but was not returned by that inventory. No unrelated
   background controls were clicked. Native UI acceptance stays unverified.
3. Perform the live cloud/provider journeys and validate delivered artifacts and
   playback, keeping secrets out of logs. Stubbed HTTP success/failure tests do
   not certify the configured remote service.
4. Perform actual camera start, interruption and recovery where hardware is
   available. The implemented pilot is face-count/focus hints; gaze tracking,
   screenshot prevention and automatic disqualification are not implemented.
5. Check relevant rendered media visually and aurally at the scope of each story.
   A local render's exit status and metadata are insufficient for artistic
   quality, pronunciation and complete synchronization acceptance.

Use the spreadsheet's remaining-verification cells to drive this work, retain
evidence per story, document new defects before fixes, and rerun affected stories
after each fix. Preserve the current user worktree. Do not mark the active goal
complete solely because the 250 feature checks and 291 unit tests are green.

## Continued semantic review: cloud output and media acceptance

The previous turn changed the authoritative catalog and produced complete
software-run evidence, so it was progress. The user subsequently stopped
Computer Use with Escape; no further Computer Use was performed in this turn.
Independent code and test work continued toward the same full objective.

BUG-132 reproduced two accepted-invalid-media paths: missing PyAV and readable
metadata without a decoded frame. Baseline: 5 passes, 2 failures in
`tmp/media-gate-baseline-20261012.log`. Both now refuse certification; decoder
failure includes an installation/repair hint. `av` is a base dependency so
cloud-only users do not need local Manim for media validation.

BUG-133 identified a worker fallback that could publish another scene or a
partial clip. The worker now requires exactly one final class-named MP4, reports
the candidate count on failure, and never substitutes a larger file. Version 7
salts the cache key. The tests execute the exact embedded Python selection code
with temporary files for missing, unrelated, fragment-only, ambiguous and
successful output, including a directory with spaces. Initial selection gate:
5 failures / 1 parity pass in `tmp/cloud-identity-baseline-20261012.log`.

After both fixes, the media/worker/cloud-diagnosis group passed **13 tests** in
`tmp/cloud-validation-postfix-20261012.log`. Changed stories F158/F249 and the
camera-recovery story F239 passed in `tmp/cloud-story-recheck-20261012.log`;
unaffected story results retain their original timestamps rather than claiming
a fresh full 250-story run. The canonical workbook includes both new defects,
more precise F158/F249 expectations and explicit remaining live-cloud work.

These checks do not establish live GitHub execution, packaged decoder loading,
all-frame decodability, pronunciation, artistic quality or native UI acceptance.

The first complete regression run after the cloud fixes returned **295 passed /
1 failed** in `tmp/feature-goal-unit-cloudfix-20261012.log`: Windows refused one
profile-registry replacement with WinError 5. Its OS cause is not established;
the writer's lack of transient-error recovery was independently reproduced.
BUG-134 adds at most five atomic-replace attempts (375 ms total delay), only for
WinError 5/32/33, without removing the old file or claiming a lasting failure was
saved. Real/non-Windows permission errors still propagate immediately. Injected
temporary locks recover; persistent locks preserve old data and remove the
staged temporary file. Targeted profile/ranking/persistence group: **15 passed**
in `tmp/atomic-recovery-postfix-20261012.log`. The final story check includes
F158/F234/F239/F242/F249, all passed in
`tmp/cloud-story-recheck-final-20261012.log`; the temporary-recovery regression
now checks each of WinError 5, 32 and 33.

Final full regression after cloud and persistence fixes: **299 passed**, one
upstream ChromaDB deprecation warning, exit 0; evidence:
`tmp/feature-goal-unit-cloudfix-final-20261012.log`. Tracker integrity passed for
250 rows/results/test functions and 78 defect-linked features; all 134 numbered
errors are linked. Surface coverage remains 88/88. Ruff F/I checks and
compileall passed for the touched source/test files. The exported workbook
retains Features/Summary, 21 columns, 250 rows, the native PhysLabFeatures table,
freeze D2, UTC date formats and 250 PARTIAL full-behaviour statuses; its changed
evidence area and summary were rendered and inspected. No spreadsheet formula
errors were found.

Current live-cloud readiness was read directly from application settings:
GitHub token is absent, so no real remote worker was dispatched. Safe readiness
evidence without credentials is in `tmp/cloud-live-readiness-20261012.json`.
This is a configuration limitation, not proof of a cloud execution failure.
Native UI, camera, packaged playback and artistic/audio review remain open.
The active full objective is not complete.

## Profile editor acceptance: failure, rollback and boundaries

The preceding goal turn was progress: it fixed cloud identity/media gates and
Windows atomic-save recovery, updated the canonical evidence and ran 299
regressions. This continuation reviews profile-form semantics and failure paths.

`tests/test_profile_editing.py` initially returned **7 failed / 1 passed** in
`tmp/profile-editing-baseline-final-20261012.log`. BUG-135–BUG-138 document photo
overwrites before rejected profile commits, silent external-path/photo-loss
fallback, multi-commit partial creation, 40+40-character names discarded by
reload and uncaught activation errors. Cancel/discard already preserved state.

New photos are copied through QSaveFile to unique files under profile_avatars;
the old image is never overwritten. Failed registry writes remove the owned
new copy and retain the draft; failed image copies report a localized photo
error. Unchanged photos are not rewritten. Existing saved photo files are
preserved, including earlier managed versions. New-profile creation can commit
complete fields, copied-photo path and active ID with one registry replacement.
Its existing successful Save behavior (new profile becomes active) is retained.
Structured first/surname identities may total 81 display characters including
the space; legacy free-form creation keeps its 80-character limit. Activation
failure remains in the dialog without changing the active learner.

Targeted profile/form/ranking/atomic-persistence run: **26 passed** in
`tmp/profile-editing-postfix-final-20261012.log`. Eleven form regressions cover
rollback, failure/retry, source deletion, one-commit creation, maximum names,
cancel and all-language edits/photo messages. Picker cancellation/invalid
selection use injected QFileDialog return values, so these are not native
file-picker acceptance. F234/F235/F242 passed in
`tmp/profile-story-recheck-20261012.log`; other feature timestamps were retained.

Further persistence review should distinguish file-read permission failures
from intentionally recoverable malformed/missing registry data. Native picker,
keyboard/layout, real-camera and live-cloud journeys remain unverified.

Full regression after the profile fixes: **310 passed**, one upstream ChromaDB
deprecation warning, exit 0 in `tmp/feature-goal-unit-profilefix-20261012.log`.
The canonical workbook still has 250 stories, with 79 defect-linked features;
BUG-135–BUG-138 are linked, making 138 numbered error records. Software checks
and full user-behaviour acceptance remain distinct. The full objective stays
active; no live cloud/hardware/native-picker result is inferred from this run.

Final tracker/surface gates passed: 250 stories/results/check functions, 79
defect-linked features, 138 numbered errors linked and 88/88 detected surfaces.
The language names in F235 remain explicit (Kazakh, Russian, English), so the
surface inventory retains the localization contract rather than a vague
three-language label. Ruff F/I, compileall and the CRLF-aware diff check passed.

## Registry reads and dependent school screens

The preceding turn was progress: four profile/avatar defects were corrected and
310 regressions passed. This turn traces file-read failures through the shared
store and all its school/profile consumers, preserving the full objective.

BUG-139: an OSError was treated as empty data, allowing a default/new profile to
overwrite an unreadable existing registry. Only genuinely missing files and
malformed JSON keep the existing recovery behavior; other IO errors now
propagate without replacing the file. Regression tests preserve the exact
registry bytes and active learner after restored access. Legacy practice data
remains intact under the existing missing/malformed-file recovery.

BUG-140: profile reload now reads before changing widgets, retains choices and
drafts on failure, prevents editing/using an unconfirmed selection and offers
localized Retry. A saved profile whose list fails to reload is explicitly
reported as saved. Main-window profile opening handles failure without changing
the active views. Nine regressions cover startup of the dialog, selection,
discard, failure/retry, saved-state accuracy and all three languages. Baseline:
7 failures in `tmp/profile-read-baseline-20261012.log`; initial fix group:
35 passes in `tmp/profile-read-postfix-final-20261012.log`.

The shared-store change was then traced into teacher review and ranking.
BUG-141 adds teacher reload/error handling, retains a prior snapshot, distinguishes
unreadable data from no attempts and clears placeholder spans on recovery.
BUG-142 distinguishes endpoint file-write errors from URL/network errors and
retains the draft/saved settings without launching a worker. BUG-143 retains
local ranking snapshots on read refusal and prevents the local sync branch
from masking the failure. Their initial three regressions failed in
`tmp/school-view-io-baseline-20261012.log`.

BUG-144 addresses a separate visible history defect: a two-column empty-history
placeholder hid a later student's score after selection changed. The selection
regression failed in `tmp/ranking-history-span-baseline-20261012.log`; clearing
old spans restores the score column.

Final targeted group: **42 passed** in
`tmp/school-view-io-postfix-final-20261012.log`. F234/F235/F240/F241/F242 passed
in `tmp/read-recovery-story-final-20261012.log`; unaffected feature timestamps
were retained. Canonical expectations and source references were expanded for
these five stories. Tests are offscreen Qt and isolated file/loopback checks;
native keyboard/layout/pickers, deployed HTTPS, live cloud and camera acceptance
remain open. The full goal is not proven complete.

Final full regression after BUG-139–BUG-144: **323 passed**, one upstream
ChromaDB deprecation warning, exit 0 in
`tmp/feature-goal-unit-readfix-final-20261012.log`. An earlier 319-case full run
passed after the initial read-recovery fix; the final run adds the school-view
and history-selection regressions. Tracker integrity passed for 250
stories/results/check functions, 82 defect-linked features and all 144 numbered
errors linked. Surface coverage is 88/88. Ruff F/I and compileall passed on the
touched source/test files. The workbook retains its two tabs, 21 columns, native
table, frozen identifiers and dated scope/remaining-acceptance fields; software
status is 82 FIXED / 168 PASS, while full user behaviour remains PARTIAL.

Cloud readiness was freshly inspected in
`tmp/cloud-live-readiness-20261012.json`: no GitHub token is configured, so no
live remote job was attempted. This limitation does not prevent further local
semantic/UX review; the goal remains active. Desktop/native, real hardware,
deployed services and full media viewing are still required where their story
scope calls for them.

## Endpoint transitions and unavailable AI allowance

The prior goal turn was progress: six storage/UI defects were fixed, 323
regressions passed and the canonical workbook gained stronger expectations and
evidence. This continuation tests configuration transitions and the daily
allowance failure contract.

BUG-145: clearing the leaderboard endpoint now reloads local rows before
claiming local mode. A failed reload preserves the last loaded snapshot and a
file-error message. Tests enter remote data through the real completion/render
slot and check both the entry model and table, rather than changing one cell.

BUG-146: getter/save/sync now use the same effective environment-overridden URL,
while retaining the saved preference for later use. The address field and
localized notice explain AETHERLAB_LEADERBOARD_URL. Invalid overrides block a
worker launch with a configuration diagnosis and never echo their raw value.
Tests use a mock worker to verify destination; this is not a live HTTPS check.
Baseline mode/override group: four failures in
`tmp/leaderboard-mode-baseline-20261012.log`; two later tests also cover invalid
override and destination/display agreement.

BUG-147/BUG-148: a denied allowance read no longer resets usage or grants fresh
attempts. Read/write failures preserve stored bytes and do not start AI work.
The —/10 state means unknown, disables AI actions, keeps practice available and
has translated explanatory text. Startup, profile switch, request admission and
the existing refresh timer use one guarded updater. Recovery restores the
confirmed count and removes its own stale error without erasing another status.
Missing/malformed counter recovery and daily/concurrent limits remain unchanged.
The five initial regressions failed in `tmp/ai-quota-io-baseline-20261012.log`.

The full application regression run passed **334 tests**, one upstream ChromaDB
deprecation warning, exit 0 (`tmp/feature-goal-unit-mode-quota-20261012.log`).
The subsequently strengthened remote-snapshot fixtures and all affected quota,
ranking and mode checks passed **27 tests** in
`tmp/mode-quota-postfix-final-20261012.log`. Product source did not change between
these runs. F236/F241/F242 passed their final catalog checks in
`tmp/mode-quota-story-final-20261012.log`; other stories' timestamps were retained.
All tests used isolated/offscreen data;
native UI, deployed services, real cameras and complete media review remain open.

Final tracker checks passed: 250 stories/results/functions, 83 defect-linked
features, all 148 numbered errors linked and 88/88 detected surfaces. The
canonical workbook was exported and its updated summary inspected; software
status is 83 FIXED / 167 PASS, with full-behaviour status still PARTIAL for all
stories pending scope-specific acceptance. Ruff F/I, compileall and the
CRLF-aware diff check passed. Fresh cloud-readiness evidence still reports no
GitHub token. The goal remains active, with further semantic review of stored
exam/practice data and full UI/provider/hardware journeys outstanding.

## Progress writes, close-time answers and pending result recovery

The prior goal turn was progress: endpoint/quota fixes changed authoritative
code and strengthened 250-story evidence. This continuation found five more
storage/UI defects (BUG-149–BUG-153). Seven initial regressions failed in
`tmp/progress-recovery-baseline-20261012.log`.

Updates now use a strict read of existing progress before changing goals,
companion choice or attempts. An IO failure cannot replace the old history,
mistakes, preferences or lifetime points. Missing/malformed-JSON recovery keeps
its previous contract. Read-only progress loaders still substitute empty
snapshots on IO failure; diagnosing that condition in every dashboard/consumer
is outstanding and is explicitly recorded in F227's remaining acceptance.

Goal write errors retain the entered draft and show translated guidance.
Result errors no longer mark the attempt finished before the history commit.
Answers freeze, the timer stops, and a translated retry action persists the
same result. This includes automatic completion at zero seconds. Active-session
errors appear in a persistent notice; close/reject saves the current selected
answer and stays open if the save fails. Inaccessible resume data blocks a new
attempt instead of being mistaken for an absent file.

Pending completion and a UUID survive reopening. The completed active snapshot
is saved **before** committing history, so failed cleanup cannot reopen an
editable attempt or duplicate points/history. Deduplication uses the retained
100-attempt history; it is not a cross-device or unlimited-history guarantee.
This additional successful-commit/failed-cleanup case failed independently in
`tmp/progress-cleanup-baseline-20261012.log` before the final ordering fix.

The first fix passed 27 focused checks and 342 full regressions. After the final
ordering fix, F227/F238/F244 passed the catalog checks in
`tmp/progress-recovery-final-stories-20261012.log`, including all nine new
regressions. Other feature evidence timestamps were retained. The canonical
workbook was exported with 250 stories, 85 software FIXED / 165 PASS and
250 full-behaviour PARTIAL. Its summary was rendered and inspected. Integrity
checks passed and surface coverage is 89/89; the surface count is a heuristic,
not proof of every user journey. Ruff F/I and compileall passed.

Native layouts/keyboard/OS dialogs, physical file interruption, real camera
and deployed/cloud journeys still require their own acceptance. No remote
render or external message was sent in this continuation. The goal remains
active.

Final source regression: **343 passed**, one upstream ChromaDB deprecation
warning, exit 0 (`tmp/feature-progress-final-unit-20261012.log`). No product
source was changed after that run began. Integrity confirms 250
stories/results/functions and all 153 numbered errors linked; software status
is 85 FIXED / 165 PASS. These are automated/offscreen checks and do not upgrade
the separate full user-behaviour status. CRLF-aware diff checks passed.

## Read-only progress and snapshot recovery (2026-10-13)

The previous goal turn was progress: five persistence defects were fixed and
343 regressions passed. This continuation closes the known read-only failure
gap with BUG-154–BUG-157. Initial evidence reproduced five application
failures; fixture-only errors in interim school tests were corrected and were
not counted as defects.

Every public progress getter now distinguishes missing/malformed JSON (prior
recovery contract) from real IO errors. Student screens use one normalized file
snapshot per refresh. On denied read, confirmed data stays with a translated
stale notice; initial failure shows unknown values and Reload. Snapshot caches
are keyed by progress-file path, so profile switches cannot show a previous
student's results. Topic search and lesson/practice actions work with unknown
progress, while confidence filtering and unknown goal/mistake controls do not
pretend data is available. Practice setup retry restores confirmed goals and
does not overwrite a draft that the student already edited.

Teacher review and local ranking now receive failures from individual progress
files as well as the registry, retain their confirmed entries and avoid empty
result claims. Sync cannot construct/upload a submission from unreadable
history, and its trusted error key produces a local-file diagnosis rather than
a network failure. No remote upload was performed in these tests.

Final focused evidence: **37 passed** in
`tmp/progress-read-confirmed-20261013.log`. Final full regression: **353 passed**,
one upstream ChromaDB deprecation warning, exit 0 in
`tmp/feature-read-progress-unit-20261013.log`. Product source did not change
after the full run began. All ten affected catalog stories (F227/F230/F234/
F238/F240/F241/F242/F244/F245/F246) passed in
`tmp/progress-read-stories-20261013.log`; unrelated timestamps were retained.
New checks cover all three languages, initial and repeated read failures,
profile isolation, saved-goal/draft recovery, one-read consistency, unknown
topic actions, school snapshots and a worker's no-request/local-error path.

The goal remains active. These are automated/offscreen checks; native layout,
keyboard, OS file failures, physical camera, deployed HTTPS and live-cloud
render/playback still need scope-matched acceptance. Broader semantic review
of the remaining features continues beyond the structural surface catalog.

Canonical workbook update and readback passed: 250 feature/story/result/check
entries, 86 software FIXED / 164 PASS and full behaviour PARTIAL for all 250.
All 157 numbered errors are linked. The summary was rendered and inspected;
tabs/table/frozen identifiers and unrelated evidence dates were preserved.
Surface coverage is 90/90 (heuristic only). The first surface check exposed
an omitted explicit language list in F240's revised wording; restoring its
actual Kazakh/Russian/English contract resolved that catalog gap. Ruff F/I,
compileall and CRLF-aware diff checks passed on the touched code.

## Practice report consistency, safe export and live cloud evidence (2026-10-13)

The previous goal turn was progress: it changed scoring/numeric/PDF behaviour
and produced evidence of an order-dependent PDF font failure. This
continuation reproduced that failure, fixed its Qt lifetime cause and closed
the remaining report-export gap. BUG-158–BUG-165 are now documented and linked
to the same canonical feature workbook.

### Behaviour changed

- Early-finished practice uses the same answered-question subset for screen,
  history and PDF score/count. Unattempted questions stay in the study key with
  an explicit excluded label; timed unanswered questions still count.
- Unusable numeric preferences, nonfinite points and invalid attempt
  aggregates no longer crash views. Reads preserve source bytes, calculate
  from valid records and disclose recovered values. Lifetime-point updates
  recover from valid historical scores.
- Worked PDF reports display the shared LaTeX solution steps as equation
  images. Formula questions and sources have explicit page boundaries;
  progress columns are aligned. Ordinary prose remains searchable; equation
  images are not selectable text.
- Font registration belongs to the QApplication instance. Recreating Qt
  reinstalls bundled fonts; repeated calls preserve a later custom font.
  Calls before an application exists do not touch the font database.
- Export writes a fresh sibling stage, validates a real readable PDF and its
  title, fsyncs with a writable Windows file handle and atomically replaces
  the destination. Missing/partial/invalid print output, missing text or a
  denied replacement preserves old bytes and removes the stage. The UI
  reports failure and permits retry without changing saved practice history.
- Cloud worker selection failures now retain their actual missing/ambiguous
  output diagnosis instead of dependency-banner FFmpeg noise. Missing uploads
  and invalid downloaded media have separate failure kinds. Missing output
  includes a timed-animation/wait and retry hint.

### Verification evidence

Initial report baselines failed five checks; the shortened font sequence
failed one of eleven checks and both lifetime cases failed before repair.
All three printer-transaction baselines failed. The first transaction repair
then exposed a Windows fsync error, which was fixed by opening the stage with
write access. These intermediate failures were retained, not counted as
passing evidence.

Focused report/font/transaction checks: **18 passed** in
`tmp/pdf-transaction-confirm.log`. The new font subprocess checks the three
localized report headers and source text after recreating Qt; equations are
covered by separate report/template checks. This removes unrelated math
initialization from the lifetime case. The first concurrent catalog run had a
90-second subprocess timeout; the final serially merged catalog evidence is
the successful recheck, not that run.

Cloud diagnosis baseline: **5 failed, 3 passed** in
`tmp/cloud-diagnosis-baseline.log`. After repair: **64 passed** across diagnosis,
worker-selection, media and established bug regressions in
`tmp/cloud-diagnosis-postfix.log`.

Final full source regression: **376 passed**, one upstream ChromaDB
deprecation warning, exit 0, 246.04 seconds in
`tmp/feature-complete-confirm-unit-20261013.log`. Product source did not change
after this full run began. An earlier full run passed 371 before the cloud
diagnosis repair. Eleven practice/progress/school stories passed in
`tmp/pdf-export-stories-confirm-20261013.log`; F136/F154/F158/F249 passed in
`tmp/cloud-acceptance-merge-20261013.log`. Their results were merged serially
into `feature_test_results.json`, preserving unrelated evidence timestamps.

Three final isolated ten-question reports were regenerated through the UI
export slot with an injected file picker. Poppler previews of all **36 pages**
were inspected: readable ru/kk/en prose, score 2/2, explicit excluded labels,
complete worked questions/formulas and complete source sections. Each sample
also passed text and page-boundary checks. The first exercise's three formula
templates render for all 25 topics; this does not certify all 2500 numerical
variants, matching/multiple-choice layouts or long-set pagination.

### Real GitHub Actions checks

GitHub CLI authentication and the configured worker repository were rechecked.
The default branch had an older worker. The existing backend provisioned
version 7 on both `main` and `renders`, uploaded only a synthetic test scene
and executed it through the normal cloud path. User preferences and student
data were preserved.

- Success: job `1b03e707760e425c5eae9748`, run **38311353505**, artifact
  **11775166191**. The downloaded silent clip is 1280×720, 30 fps, four
  seconds. All 120 frames decoded; beginning/middle/end images were inspected
  for Cyrillic, Kazakh glyphs, LaTeX and motion. Both remote workflows match
  the shipped version 7.
- Cache reuse: the same job returned the same artifact hash with a cache-hit
  diagnosis and no new dispatch. Evidence is
  `tmp/live-cloud-acceptance-20261013/evidence-cache.json`.
- Missing output: an empty synthetic scene produced no final MP4. Initial run
  **38311744646** exposed the incorrect FFmpeg kind. Post-fix run
  **38312254517** returned `render-error` / `artifact_missing`; no video was
  returned and no local fallback ran. Both failures are retained as evidence.

These checks prove a short real cloud render, artifact delivery/full decode,
cache reuse and one real failure path. They do not prove a complete narrated
lesson, native playback, every renderer profile, cancellation under every
network condition or ambiguous output on a live runner. F136/F154/F158/F249
carry this additional scope in the canonical workbook; full behaviour remains
PARTIAL.

### Canonical tracking and remaining acceptance

The sole canonical workbook remains `AetherLab_Feature_Tracker.xlsx`; the CSV
is its generated mirror. It contains **250** feature/story records: **88 FIXED,
162 PASS** for scoped software checks, and **250 PARTIAL** for full user
behaviour. The workbook retains distinct expected behaviour, evidence dates,
verification scope and remaining acceptance. No broad completion claim is
made from this regression count.

Remaining work includes native UI navigation/layout/keyboard and file dialogs,
physical storage interruption, real camera opt-in/recovery, deployed HTTPS
school journeys, full cloud lesson audio/playback and broader semantic review
across the other feature stories. The goal remains active.

Final canonical export/readback passed: all 250 rows and 21 columns agree with
the CSV mirror, comparing UTC timestamps as typed dates. The Features/Summary
tabs, PhysLabFeatures table A1:U251 and D2 freeze were preserved. Summary and
changed PDF/cloud scope ranges were rendered and inspected. Integrity checks
confirm 250 features/results/check functions and all 165 numbered defects
linked; surface coverage is 90/90 (heuristic only). Ruff F/I, focused compileall
and CRLF-aware diff checks passed. No outstanding test or render process
remains from this continuation.

## Native practice acceptance and follow-up repairs (2026-10-13)

The previous audit continuation made progress through source repairs, scoped
regressions and real short cloud evidence. This continuation expanded native
practice acceptance, repaired five observed UX defects and updated the same
canonical workbook. The whole-app objective remains active.

### Changes and observed behaviour

- **BUG-166 / F233:** feedback and review prose exposed LaTeX commands beside
  correctly typeset equations. `practice_math.py` now converts only supported,
  source-matched expressions, preserving grouping, roots, scripts and the
  original question data. Unsupported input is not silently guessed.
- **BUG-167 / F230/F233:** a perfect 2/2 practice sample claimed mistakes and a
  weak topic. All three locales now report the actual sample and invite more
  practice without claiming mastery; later imperfect attempts restore review.
- **BUG-168 / F233:** the study key inherited small Cascadia Code formatting.
  The scoped PracticeReview style uses the application font at 14 pixels.
  Native Russian and Kazakh result views were inspected.
- **BUG-169 / F228:** native PDF saving opened a Windows printer-connection
  wait. Cancelling it let the old export finish. The PDF path now uses
  QPdfWriter directly and releases its file handle before validation and atomic
  replacement. A restarted native Kazakh export completed without that wait.
- **BUG-170 / F230:** after correcting the only missed item, home showed zero
  queued mistakes but still asked for mistake review based on historical 5/6.
  Home now checks pending IDs for its selected topic, retains historical counts
  and invites new practice when that topic has no pending items. An unrelated
  topic's pending mistake does not re-enable this recommendation.

All changes preserve learner history and the existing typeset solution path.
PDF validation, fsync, stage cleanup and old-file preservation remain covered.
The imperfect-sample test now records actual wrong question IDs, matching the
behaviour it expects rather than creating only aggregate error counts.

### Software evidence and harness recovery

Before BUG-166/167/168 repair, three locale cases failed in each of
`tmp/explanation-baseline-20261013.log`,
`tmp/recommend-baseline-20261013.log` and
`tmp/review-font-baseline-20261013.log`. The first formatter checks passed 12;
the pre-font combined group passed 60. A subsequent full run passed **391**
before the two follow-up repairs.

For BUG-169, the first pytest baseline and focused commands encountered a
permission error in the system pytest temporary directory. They did not reach
the tmp_path checks and are not product failure baselines. Repository-local
isolated basetemp restored execution: **34 passed** in
`tmp/native-pdf-printer-focused-recheck-20261013.log`. The new regression
forbids system-printer construction while exporting a real readable report;
existing injected missing/partial/invalid/locked-output checks retain their
old-report and cleanup assertions. A full run then passed 392 before BUG-170.

BUG-170 baseline: **3 failed**, all locales, in
`tmp/native-cleared-mistakes-baseline-20261013.log`. Final focused display,
progress-read and PDF-transaction checks: **35 passed** in
`tmp/native-recommend-final-focused-20261013.log`.

The catalog adapter initially could not supply parametrized language inputs.
The explicit locale adapter then exposed its own reused fixture directory:
F230 and F233 appended to the same synthetic history. Each invocation now
gets a unique isolated directory; no assertions were removed. The failed
catalog run remains in `tmp/native-acceptance-stories-20261013.log`, followed
by a successful isolated F233 recheck and final five-story run.

Final source regression: **395 passed**, one upstream ChromaDB deprecation
warning, exit 0, **133.72 seconds**, in
`tmp/native-all-final-full-20261013.log`. Product source and regression tests
were not changed after that run began. F226/F227/F228/F230/F233 all passed in
`tmp/native-all-final-stories-20261013.log`; these results were serially merged
into `feature_test_results.json`, preserving unrelated timestamps and earlier
live-cloud evidence. This was a five-story refresh, not a new run of all 250
catalog checks.

### Native interface evidence

Computer Use controlled only `PhysLab current audit 20261013`, launched from
the current source with isolated learner data in
`tmp/feature-native-ui-20261013-current`. The user's original PhysLab window
and learner files were preserved. Native actions included Russian/Kazakh
navigation, a visible 100-question topic count, distinct answers, checking,
early finish, readable feedback, result review and restart persistence.
Russian Tab/Return activated Check Answer. The native PDF picker was first
cancelled, and later used to save a real report after the printer fix.

Initial evidence in `tmp/native-ui-acceptance-20261013.json` records three
unique attempts and four points. Follow-up evidence in
`tmp/native-ui-followup-20261013.json` records the later wrong answer, restart,
Kazakh correction of that exact item, successful PDF saving, fixed cleared-topic
recommendation and progress view. Final saved data has **five unique attempts,
six attempted questions, five points and zero queued mistakes**. Historical
topic accuracy stays **5/6**, displayed as 83%; it is not rewritten to 100%.
Each evidence record contains the relevant source hashes and real timestamp.
The older record belongs to its earlier source version; the follow-up records
the final dashboard/PDF changes.

The native post-fix Kazakh PDF is A4, three pages, with a selectable 1/1 score,
the matching condition/9 m/s answer, rendered formula steps and source links.
All three Poppler page previews were inspected. This proves that single-item
native export; broader locale/kind/large-set layout acceptance remains open.

Computer Use's stale save-dialog index/focus data were recovered with fresh
screenshot observations and keyboard input. Those tool errors were not counted
as app defects. The final isolated app was closed normally; its process was
confirmed absent. No test/render process from these final checks remains live.

### Canonical workbook and remaining work

The single canonical XLSX contains **250 stories**, **88 FIXED / 162 PASS**
scoped software statuses and **250 PARTIAL** full-user-behaviour statuses.
Five native evidence scopes and their remaining acceptance were updated.
All **170 numbered defects** are linked to story records. CSV remains the
generated mirror, not a second independently maintained tracker.

Artifact Tool exported the same workbook; integrity readback matches all 250
rows and 21 columns with typed UTC dates. Features/Summary tabs,
PhysLabFeatures table A1:U251 and freeze pane D2 were preserved. Summary and
the changed practice/home evidence ranges were rendered and inspected.
Integrity and heuristic surface checks passed (250 records/results/functions,
90/90 surfaces); heuristic coverage does not prove every user journey.
Ruff F/I, focused compileall and CRLF-aware diff checks passed. Final visual
inspection also caught a clipped Summary scope note; its cell now wraps at a
fitted row height. The summary audit date is a typed date, and the final
Artifact Tool scan found no spreadsheet formula-error cells.

Remaining acceptance includes timed/native mock journeys and other question
kinds, complete English study-key typography, native goals/profile and
filename/storage failure recovery, physical storage interruption, real camera
permissions/recovery, deployed HTTPS school workflows, full narrated cloud
lesson playback and semantic/visual checks across the remaining stories.
The full objective is not complete; continue these recorded acceptance gaps.

## Timed mock evidence recovered and reconciled — 13 October 2026

The previous goal cycle is classified as **progress**: BUG-171/172 repaired
timed setup and pending mock-topic recommendations, with native evidence and
persisted state. The canonical export from that cycle was revalidated rather
than restarted because its completion output had been interrupted. XLSX
modification time, readable output, generated matrix and integrity gate proved
that export had completed. Its counts were 89 FIXED / 161 PASS and 250 PARTIAL.

Historical regression for that source version passed **401**, one upstream
ChromaDB deprecation warning, exit 0, 376.64 seconds, in
`tmp/timed-unrestricted-final-full-20261013.log`. Five scoped stories passed in
`tmp/timed-final-stories-20261013.log`. This was not a fresh 250-story run.

`tmp/native-timed-acceptance-20261013.json` records natural English start,
answers, Escape/close and resume. Two choices and index were retained; the
clock went from saved 88:40 to resumed 86:46. Return chose No at early finish
without creating history; explicit Yes finalized 1/50 with 38 unanswered.
An explicit reordered 40-item fixture then exercised all four control kinds
with native input, producing 4/50 and 1/2 partial credit for both multi and
matching. Already-expired and stale-completion fixtures produced 1/50 and
retained the exact committed history hash, three unique attempts and six
points. These expiry/stale scenarios used synthetic saved states, not a real
90-minute wait or physical crash. Their original version evidence is retained.

That native pass exposed empty mock solution_latex and English confirmation
buttons in Kazakh. These became the next concrete acceptance work below.

## Worked mock solutions and safe confirmation — 13 October 2026

### Repairs and checks

- **BUG-173 / F233:** all 40 authored mock items now have shared LaTeX steps
  in `ent_mock_solutions.py`. Practice and mock completed reviews add equation
  images to a fresh per-attempt QTextDocument, clearing old resources. PDF uses
  the same steps. Renderer failure keeps readable math or a localized diagnosis
  and never shows raw TeX as an equation. Question conditions, choices, grading,
  original provenance and pending teacher/language-review labels are preserved.
- **BUG-174 / F226:** resume and finish controls are explicitly localized in
  kk/ru/en. Resume offers Resume, Start again and Cancel, with a replacement
  warning. Finish defaults to Continue. The selected exam language controls
  both message and action labels, independent of the OS/Qt locale.
- **BUG-175 / F238:** Resume Escape/window dismissal now leaves saved bytes
  intact and returns to setup. Explicit Resume restores the same attempt;
  explicit Start again creates a new one. Globally valid IDs incompatible with
  the selected bank diagnose failure without replacing the attempt.

Baselines failed eight math cases and six confirmation cases. Their logs are
listed in `ERRORS_FOUND.md`. Test-authoring import, number-format/rounding and
invalid-fixture issues are recorded separately from app failures. The focused
repaired group passed 63; extended checks passed 21. Those checks cover all 40
math entries, three language views, 21 independently calculated numerical keys,
per-attempt image resources, all confirmation choices and readable fallback.

Three generated full mock PDFs passed technical checks, each 42 A4 pages and
50/50, with all equation images. A read-only image-bounds check found no image
outside any page. This is technical coverage; it is not visual inspection of
every page or a new native file-picker export.

Final full regression: **422 passed**, one upstream ChromaDB warning, exit 0,
**148.14 seconds**, in `tmp/solutions-full-final-20261013.log`. Product source
did not change after this run began. Seven final catalog checks
F225/F226/F227/F228/F230/F233/F238 passed in
`tmp/solutions-final-stories2-20261013.log` and were serially merged, preserving
unrelated check dates and earlier live/native evidence. Catalog checks now
execute the new locale/mode and full-mock PDF assertions explicitly.

### Native behaviour

Computer Use operated only `PhysLab solutions audit 20261013`, a current-source
standalone ExamPracticeDialog with isolated learner data. The original user
PhysLab windows were preserved. Kazakh full mock start showed 40 questions,
90:00 and hidden solutions. A selected 14 m/s answer survived close/reopen.
Resume's three localized buttons were inspected. Native Escape returned to
setup and preserved the exact saved SHA256. Explicit Resume restored the
original answer/attempt ID and clock 83:56, below saved 88:28.

Localized finish buttons were inspected. Return chose Continue and created no
history. Explicit Finish produced 1/50, one correct, zero incorrect and 39
unanswered. Native review displayed readable velocity and substitution,
freefall and Ohm-law fractions; scrolling was checked. One unique full mock
attempt persisted, with the original UUID and no active-session file. Both
owned native launches closed normally with exit 0. Evidence and final source
hashes are in `tmp/native-solutions-acceptance-20261013.json`.

Computer Use had stale index/geometry/screenshot-cache failures. Fresh window
observations and coordinate input recovered them; these are tool failures,
not counted as product defects. Native acceptance covers the isolated dialog
in kk and the first three review items. Complete main-window navigation,
ru/en layouts, all items/viewports and physical failure paths remain open.

### Canonical tracking and remaining work

The same canonical XLSX was exported with Artifact Tool and read back. It has
**250 stories, 89 FIXED / 161 PASS scoped software checks and 250 PARTIAL full
user behaviours**. All **175 numbered defects** are linked. CSV remains its
generated mirror. All 250 rows and 21 columns match; typed UTC dates and the
typed summary date, Features/Summary tabs, table A1:U251 and freeze pane D2 are
preserved. Changed review/resume expectations and evidence ranges were rendered
and inspected. The Artifact Tool formula-error scan found no matching cells.
Integrity and heuristic surface gates passed, including 90/90 surfaces.

Final visual review caught the acceptance writer using a new field while the
generator consumed the existing `remaining` field. The writer now updates the
existing field idempotently. Re-export, all-row integrity and surface gates
passed again; review/resume scope previews now show the updated open work.
Ruff F/I, focused compileall and CRLF-aware diff checks also passed.

The full objective remains active. Upcoming acceptance still includes native
profile/goal flows, broad review/PDF layouts, actual storage interruption and
crash recovery, camera permissions/recovery, deployed school workflows and a
complete narrated cloud lesson through playback. Teacher and language-editor
sign-off is still pending. Automated passes do not close those behaviours.
