# PhysLab feature audit — 14 October 2026

The active objective remains: inventory every feature, derive user stories and
expected behaviour from code, maintain one canonical spreadsheet, test all
stories, document errors, fix logistical/UX defects, and retest the behaviours.
The full objective is not yet proven complete.

## Latest verified state: translation answer lock

The catalog contains **252 stories** and **219 logged bugs**. BUG-218 was
reproduced through the native UI: changing only the lesson language unlocked a
graded answer and allowed the same answer to count twice. Six locale/correctness
baseline cases failed. The fix retains the displayed attempt's choice,
confidence, translated feedback and lock only for a shared validated content
snapshot; a genuinely new content snapshot and explicit same-language restart
remain fresh attempts. Profile changes remain isolated.

The focused UI/storage/route group completed **67 passed**, exit 0, in 339.85
seconds (`tmp/language-answer-postfix-20261014.log`). The later two fresh-attempt
boundary tests are included in the new full run, not retroactively counted in
that focused result. Native post-fix acceptance also passed KK → RU → EN with
result 1/1, selected locked answer and localized feedback throughout. Progress
bytes were identical at all observations in
`tmp/native-translation-postfix-20261014.json`. The owned window was closed;
other app windows and user data remain intact. This does not prove human
listening, a complete watch, every failure path or camera acceptance.

BUG-219 records the missing tracker source for the new shared locale dictionary.
Adding its actual module to F247 makes **91/91 current surfaces** covered.

The preceding full regression completed **625 passed**, exit 0, with one upstream
warning; a new acceptance tool changed during that run. The preceding full
catalog completed **250/252**, exit 1: F164 omitted that source declaration;
F251 returned a blank AssertionError. A direct isolated F251 retry passed;
the original failure remains recorded without an invented diagnosis.

The new source-bound suite completed **633 passed**, exit 0, one upstream
warning, in 1103.61 seconds with no recorded source/resource changes during
the run (`tmp/translation-lock-final-full-20261014-evidence.json`). This includes
the two added fresh-attempt boundaries. It does not erase the separate F133
source-audit failure or establish complete story acceptance.
`tmp/catalog-translation-lock-final-20261014.log` is still active. The canonical workbook now
shows **84 FIXED / 159 PASS / 7 PARTIAL / 2 REGRESSED** scoped software checks;
the last failed F251 catalog check is retained while its new retest runs.
F133 now also retains the newly detected BUG-193 encoding regression in the
added acceptance tool: two text subprocess captures omit UTF-8/error handling.
That tool is preserved during the current frozen-source runs and needs a
targeted repair/retest afterward.
Complete behaviour acceptance is **250 PARTIAL / 2 FAIL**, not a global pass.
All required remaining acceptance stays open and the overall goal is active.

## Canonical tracking

`AetherLab_Feature_Tracker.xlsx` is the canonical spreadsheet. Its CSV is a
generated mirror; `build_feature_tracker.py` owns the catalog and consumes
`feature_test_results.json` as test evidence. Do not maintain a parallel status
workbook. Artifact tooling may apply the exact generated matrix while preserving
formatting; the integrity gate compares all rows and columns after export.

The catalog now contains 252 features/stories, including F232–F250 for topic
exercise volume, partial practice, local profiles, profile editing, daily AI
allowance, weekly mocks, resume, optional camera hints, teacher review, local and
shared school rankings, server CLI, companions, confidence/search, localization,
startup quality persistence, media validation and acceleration follow-up practice.
F251/F252 cover the prepared five-minute route and attached lesson PDF/review provenance.

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

## Profile, study-plan and newly added lesson actions (2026-10-13)

This goal cycle made progress: native profile/goals acceptance, eight
localized/status/calendar repairs (BUG-176–183), two new catalog stories,
and a complete regression of the current source version. The full objective
remains active. Software passes do not establish complete user acceptance.

### Profile and study-plan repairs

- **BUG-176 / F235:** Kazakh username labels/errors and accessible profile/photo
  hints now follow kk/ru/en and preserve the learner's name.
- **BUG-177 / F227:** weekly target suffix now follows the selected language;
  language rebuilding retains the draft value.
- **BUG-178 / F227:** a blank optional exam date browses today's month without
  assigning a date. A selected date browses its saved month.
- **BUG-179 / F227:** scoped light calendar colors fix the unreadable Windows
  dates and selection. The native symptom and offscreen palette checks are
  distinct evidence: the palette baseline only failed selection color.
- **BUG-180 / F227:** actual Windows file refusal exposed an old successful
  footer below the error. Both notices now report failure; entered goals remain
  editable, old file bytes remain intact and retry recovers the success state.
- **BUG-181 / F227:** the calendar uses the selected kk_KZ/ru_RU/en_US locale
  instead of the operating-system language, including after language rebuilding.

Earlier baseline logs and test-authoring qualifications are recorded beside
the defects in `ERRORS_FOUND.md`. The final profile/recovery/calendar focused
group passed **37**. Intermediate full runs passed 428, 434, 437 and 440 on
their respective versions; they do not cover subsequent new lesson changes.

### Native acceptance and source-version boundaries

Computer Use operated only the owned `PhysLab profile audit 20261013` window
with synthetic data in `tmp/feature-native-profile-20261013`. The user's
original PhysLab windows and other work were preserved.

The native journey created **Audit Alpha**, username `audit.alpha`, class
`11 A`, synthetic school `QA-SCHOOL`. Cancelling the native photo picker kept
the draft; selecting a generated blue/green PNG copied it into app-owned avatar
storage. Editing the first name and pressing Cancel preserved exact registry
and avatar hashes. Profile activation updated the header identity and picture.

Russian goal entry saved 45/50, 80/week, Monday and no exam date. An owned
PowerShell process opened the existing isolated progress file with
`FileShare.None`. Saving draft 90 was actually refused, preserving old 80
bytes. Retry after releasing the handle saved 90. This found BUG-180.

On the final profile/calendar build, native Kazakh calendar showed a readable
**October 2026** with Kazakh month/day labels. Clicking outside left the date
blank. A second actual lock refused draft 100, retained old 90 and displayed
the localized failure in both notices. The before/after-refusal SHA256 was
`81c2260cc2ff155841e304e05c4bec3e88a67155254e13a94c7cee45e8becdcd`.
The holder's exact session ended with exit 0. Retry saved 100 without retyping;
the dashboard then showed 45/50 and 0/100.

Switching to default **Audit learner** showed no target/week goal/schedule
and default initials; Alpha's progress hash stayed unchanged. Switching back
restored Alpha's identity/avatar/targets. Final normal close and relaunch
restored Alpha, 45/50, 100/week and the Monday reminder. Owned native launches
closed normally. No exam or camera capture was started in this journey.

`tmp/native-profile-goal-acceptance-20261013.json` stores observed actions,
physical-refusal evidence, persisted values, source hashes and boundaries.
Creation/photo/cancel and initial ru entry used earlier builds before the
calendar/locale/footer repairs. Final hashes support the later calendar,
physical refusal/retry, switch and restart; they are not a claim that every
earlier path was rerun on final code. Native final layout inspection was kk;
ru/en have automated coverage and initial ru entry, not full final acceptance.

Computer Use returned stale element indexes, transient modal geometry and
screenshots of occluding foreground apps. Reobservation of the owned target
recovered them. These tool failures are not product defects. One incidental
opt-in checkbox toggle was not followed by exam/camera start; the final test
build's checkbox remained off.

### Concurrent lesson additions and PDF repairs

The current worktree gained a prebuilt five-minute v2 lesson, three-language
media/PDF and new lesson-view actions during the cycle. These changes were
preserved and inspected. **F251** tracks the prebuilt route, eight chapters,
five fixed-key questions, existing media resolution, missing-media error
bundle and separate v1/v2 progress. **F252** tracks the attached-PDF action,
review badge and export inclusion. Both have concrete steps, expected/failure
behaviour and implementation references in the same canonical workbook.

Inspection found **BUG-182:** PDF dispatch ignored `openUrl(False)` and always
said opened. The action now reports refusal or accepted dispatch distinctly.
Accepted dispatch does not establish that the external viewer rendered a PDF.
**BUG-183:** its statuses and accessible name stayed English in kk/ru. Visible
text, accessibility and missing/refused/accepted messages now follow the UI
language. User lesson changes remain intact.

The initial PDF regression had 10 failures/2 passes; six dispatch cases failed
first on a slash-sensitive Windows path comparison. That test-authoring error
was corrected to compare Path objects. The baseline therefore did not prove
those six outcome assertions. Ignored-return evidence came from source
inspection; the other four baseline failures covered localization/accessibility.
The corrected combined profile/lesson/PDF group passed **39** in
`tmp/profile-lesson-focused2-20261013.log`. Opener results are injected and URL
fixtures are deliberately not real documents; native viewer rendering remains
unverified. New lesson tests also check ready/error bundles, measured chapter
offsets, fixed keys, shared narration, PDF/subtitle ZIP inclusion and offscreen
quiz progress; they do not certify full media quality or cloud origin.

### Final current-source checks and canonical tracker

The final complete run passed **461 tests**, one upstream ChromaDB warning,
exit 0, **173.70 seconds**, in
`tmp/current-profile-lesson-full-20261013.log`. Exact before/after hashes of
all app and test Python sources are retained in
`tmp/current-profile-lesson-full-evidence-20261013.json`; no source changed
during the run, and the final readback confirmed those hashes still matched.
This hash boundary covers Python sources, not every external media resource.

Seven catalog stories F227/F230/F234/F235/F237/F251/F252 passed in
`tmp/profile-lesson-final-stories-20261013.log`, serially merged without losing
unrelated dates, live-cloud evidence or earlier native observations.

The same canonical XLSX now contains **252 stories**, **90 FIXED / 162 PASS
scoped software checks**, and **252 PARTIAL full user behaviours**. All
**183 numbered bugs** are linked. CSV remains a generated mirror. Artifact
Tool preserved Features/Summary, 21 columns, typed UTC check dates, typed
summary date and freeze D2; the existing table was extended to **A1:U253**.
Read-only export inspection and all-row integrity passed. The formula-error
scan found no matching cells. Changed profile/goal and new-lesson story,
expectation/scope ranges were rendered and inspected.

The first surface gate reported profile localization uncovered because the
rewritten row used kk/ru/en and the heuristic matches full language names.
Restoring explicit Kazakh/Russian/English in that row resolved the diagnostic;
the gate now reports **90/90** surfaces. This is a lexical coverage guard, not
proof that all user journeys work. Ruff F/I, compileall and focused CRLF-aware
diff checks passed.

### Remaining acceptance

Next work includes native full v2 playback/seek/quiz/PDF and restart in every
language; resource packaging/hash validation and missing/corrupt-content
recovery; PDF opener refusal/inaccessible-file recovery and ZIP metadata;
all student-pane/profile isolation; physical registry/avatar/result failures
and crash recovery; remaining locale/viewport/keyboard/accessibility journeys;
camera permissions/hardware recovery; deployed school workflows; and verified
full narrated cloud delivery. Teacher/language-editor sign-off remains pending.
No new lesson or camera behaviour was marked fully accepted from automated
passes alone. The goal remains active.

## Prebuilt lesson portability and file identity (2026-10-13)

This goal turn made progress: four reproduced export/package defects were
fixed, actual ZIP structure and package identity were checked, the full
current-source regression completed, and the same workbook was updated.
Native lesson playback remains unverified; the goal remains active.

### Repairs

- **BUG-184 / F166:** ZIP metadata advertised optional assets that were not
  included, including absent/empty PDF and subtitles. References now derive
  from the actual selected PDF/SRT/VTT; unavailable optional assets are null.
  HTML PDF links agree with the entries.
- **BUG-185 / F251:** prebuilt bundles had no rendered chapter indexes.
  ZIP metadata therefore marked all eight chapters unrendered, lost their
  measured offsets and disabled every HTML seek button. Explicit indexes
  now preserve the eight starts when a video is available.
- **BUG-186 / F166:** page and subtitle track were always marked English.
  Metadata, HTML lang and track language/name now match kk/ru/en. This fixes
  language identification; it does not claim that every exported UI label
  has been translated.
- **BUG-187 / F251:** an existing nonempty file was accepted without checking
  its recorded hash or whether it was inside the lesson package. Streaming
  SHA256 now compares the actual file with the manifest, and resolved paths
  must remain in the package. Replacement video/SRT/PDF, missing hash,
  outside-package path and unavailable reads are refused. The bundle retains
  the plan, classifies missing versus unverified files and gives localized
  guidance. An unavailable video is cleared from the player.

### Evidence and qualifications

`tests/test_lesson_share_acceptance.py` physically opens exported ZIPs and
compares asset references with included entries, optional PDF links, all eight
chapter offsets/buttons and kk/ru/en page/track metadata. Its small video/PDF
fixtures establish structure rather than valid audiovisual/PDF contents.
The prebuilt export case uses actual existing lesson assets.

The first ZIP baseline hit sandbox temporary-directory access/cleanup errors;
it is an environment failure, not the product baseline. The permitted retry
reproduced three product failures in
`tmp/share-baseline-permitted-20261013.log`. The identity baseline reproduced
five failures in `tmp/media-hash-baseline-20261013.log`.

`tests/test_prebuilt_media_integrity.py` uses isolated synthetic packages to
verify replacements, absent hash, outside path and simulated read refusal.
It checks localized missing/unverified notices and clearing of the old video.
Existing real ready-bundle checks also verify the nine packaged file hashes.
Matching a manifest does not establish file decodability, cloud origin,
physics correctness, teacher approval or language/audio quality.

Final focused group: **31 passed**, exit 0, in
`tmp/prebuilt-integrity-focused-final-20261013.log`.
Final complete regression: **471 passed**, one upstream ChromaDB warning,
exit 0, **234.45 seconds**, in `tmp/prebuilt-share-full-20261013.log`.
Exact before/after app/test Python hashes in
`tmp/prebuilt-share-full-evidence-20261013.json` showed no changes during the
run. Export readback confirmed those hashes still matched at the final gate;
this source boundary does not hash every external resource during the run.

Five catalog checks F166/F229/F247/F251/F252 passed in
`tmp/prebuilt-share-final-stories-20261013.log` and were serially merged.
Unrelated dates, previous native observations and live-cloud evidence remain
intact. F251 explicitly runs all three replacement-media cases, using the
fixture adapter without treating parametrized tests as zero-argument checks.

### Native attempt: no acceptance claim

A dedicated owned `PhysLab lesson audit 20261013` launch used isolated data
and empty provider keys. The Windows tool returned the intended window but
activation/state capture reported `no monitor found for window`. Fresh
enumeration/rehydration and a capture retry failed with the same message.
There was no displayed LockApp window; a locked desktop was not assumed.

The exact exec session was polled and remained live. Permitted process
inspection confirmed the owned Python command was responding. Its command
identity was revalidated before targeted cleanup. Only that process was
terminated; the session then ended with exit 1. This was deliberate cleanup,
not normal app closure, a product failure, a successful lesson journey or
a reason to relaunch blindly. User applications were preserved. No lesson
control, native PDF or ZIP picker, camera/auth/privacy action occurred.

`tmp/native-lesson-attempt-20261013.json` records the tool error, handle,
process identity and the absence of native acceptance. Relevant result rows
retain an unsuccessful attempt record without creating confirmed evidence.
The complete playback/PDF/portable-browser path stays open.

### Canonical workbook and remaining work

The same XLSX now has **252 stories**, **91 FIXED / 161 PASS scoped software
checks**, **252 PARTIAL full user behaviours**, and **187 linked numbered
bugs**. The generated CSV matches it. Artifact Tool preserved the two tabs,
21 columns, typed check/summary dates, freeze D2 and table **A1:U253**.
Changed export/package expectation, story and evidence ranges were rendered
and visually reviewed. Formula-error scan found no matching cells.
All-row integrity and lexical surface checks passed (**90/90** surfaces).
Ruff F/I, compileall and focused CRLF-aware diff checks passed. These guards
do not replace full user-story acceptance.

Next acceptance includes native v2 playback/seek/quiz/PDF and restart in all
languages, extracted ZIP/browser playback and optional-asset recovery,
missing/corrupt-manifest/cache recovery, packaged runtime/resources, complete
media visual/audio review and verified full cloud delivery. Broad profile,
camera, school-service and remaining desktop journeys also remain open.
Teacher/editor sign-off is pending. The complete original goal is active.

## Prepared lesson content recovery and catalog isolation (2026-10-13)

This goal turn made progress. BUG-188–192 are logged and linked to the existing
stories F251 and F215; the full objective remains active.

### Changes and evidence

- Missing, unreadable, malformed and incomplete explicit manifests now produce
  a localized `package_error`. Stale video is cleared, no AI request or course
  progress refresh occurs, and restoring the file allows retry.
- Every request reads a fresh validated manifest. Caller mutation, path changes
  and a warmed cache cannot serve stale content after a read failure.
- A semantic content fingerprint survives plan serialization and must match
  before media assembly. A changed manifest or legacy prebuilt plan without a
  fingerprint is refused until a fresh load; existing text/progress is retained.
- Package validation covers version, duration, offsets, chapter kinds/order,
  question structure/counts and correct-answer positions across ru/kk/en.
  Structural agreement does not prove physical or linguistic correctness.
- Explicit catalog cases now have separate monkeypatch lifetimes. The first
  F251 catalog failure after passing independent tests exposed the harness leak;
  the failing log remains available instead of being overwritten.

The corrected original baseline had 13 failures. A subsequently introduced
serialization gap failed once and was repaired. Four alignment cases and one
fixture-isolation case also failed before repair. Final focused group:
**53 passed**, exit 0. Final full regression: **493 passed**, one upstream
ChromaDB warning, exit 0, **136.55 seconds**. The six scoped checks
F166/F215/F229/F247/F251/F252 passed. Logs are named in `ERRORS_FOUND.md`.
`tmp/content-recovery-final-full-evidence-20261013.json` confirms unchanged
app/test Python, root harness, lesson manifest and all nine media hashes at
both boundaries; readback confirmed the same files still matched.

### Existing media technical review

`tmp/content-media-acceptance-20261013/evidence.json` records full mapped
video/audio decode of all three existing videos, each exit 0. All are
1920×1080, 30 fps, 299.966667 seconds, H.264/AAC at 48 kHz. Measured mean/peak
audio levels in dB were ru -26.0/-6.3, kk -27.6/-6.5 and en -26.6/-5.6.
This confirms a non-silent signal, not intelligibility or natural pronunciation.

Fifteen frames at 70/80/160/180/290 seconds were inspected. The 70/160-second
samples are chapter transitions, while samples inside scenes display formulas,
localized graphs and recap text. This is sampled inspection, not a complete
visual/pedagogical review. No new render was performed. Human listening,
native playback, complete UI recovery, cloud provenance and teacher/editor
acceptance remain unconfirmed. No new native launch was attempted in this turn.

### Canonical status

Artifact Tool updated the single canonical XLSX and the generated CSV matches.
Readback and integrity gates passed: **252 stories**, **91 FIXED / 161 PASS**
scoped software checks, **252 PARTIAL** full user behaviours and **192 linked
numbered bugs**. The two tabs, 21 columns, typed dates, freeze D2 and table
**A1:U253** remain. Changed expectation/story/evidence ranges were rendered and
visually reviewed; the formula error scan matched no cells. Lexical surface
coverage passed **90/90**; it does not establish complete user acceptance.

Next work is a fresh run of all 252 existing catalog probes with preserved
historical/live/native evidence, followed by any failures and stronger native
and external-service acceptance. Full lesson/audio, profile, camera, school
service and remaining desktop journeys are still open. The goal is not complete.

## Whole-catalog retest and portable browser follow-up (2026-10-13)

This goal turn made further progress: the single canonical workbook was
aligned with recovery evidence, the entire catalog was rerun, two newly
observed defects were repaired, and both test layers were repeated.

### Complete existing catalog, before and after

The first fresh run completed **251/252 PASS**, exit 1. F133 found eight
new lesson-tool text subprocess calls without UTF-8/replacement and 39
printing scripts without console configuration. Its failed evidence remains
in `tmp/catalog-all-20261013.log` and `tmp/catalog-all-20261013/evidence.json`.
That snapshot covered app/tests/harness/generator and lesson resources, but
did not include tool sources; the subsequent snapshot includes them.

BUG-193 explicitly decodes those pipes and adds a shared bootstrap that calls
the existing app console policy in direct-file and package modes. User tool
logic and generated lesson assets were preserved. The new regression executes
the actual console prefixes of every printing lesson tool under cp1251, in
both modes; it deliberately does not execute their content/OCR/cloud jobs.

BUG-194 was observed in the real Russian portable page and reproduced by an
export regression: English controls/instructions and the internal high_school
label remained. Controls, README, school audience and fallback title now
follow ru/kk/en, including PDF and source-only paths. The language editor
status is not promoted by these technical checks.

Post-fix focused export/console tests: **5 passed**, exit 0. Seven scoped
catalog probes F133/F166/F215/F229/F247/F251/F252 passed. Then the entire
existing catalog completed **252/252 PASS**, exit 0, in
`tmp/catalog-all-postfix-20261013.log`; no app/test/tool/packaging/harness/
generator/manifest/nine-media hashes changed during the run.
`tmp/catalog-all-postfix-20261013/evidence.json` retains the exact boundary.

The final full test suite completed **495 passed**, one upstream ChromaDB
deprecation warning, exit 0, **168.52 seconds**. Evidence:
`tmp/catalog-portable-final-full-20261013.log` and
`tmp/catalog-portable-final-full-evidence-20261013.json`, again unchanged at
both source/resource boundaries. All-catalog probes still include static,
service and offscreen GUI checks; this is not all native user behaviours.

### Browser acceptance of actual extracted ZIPs

All three real prebuilt bundles were exported and safely extracted in an
isolated temporary folder, then loaded in the in-app browser from an owned
loopback server. The first SimpleHTTP server could play but had no HTTP Range
support, so seeking initially failed; this was a fixture limitation. After
Range support, all **24 chapter clicks** landed within one second of their
measured starts and started playback without a media error. Each video loaded
at 1920×1080 with duration 299.966667 seconds. Pause via the video keyboard
control worked; English End moved to the duration while paused. The End check
does not establish a complete uninterrupted watch or natural ended event.

Localized pages were observed and screenshot files inspected. Each video
exposed one subtitle track with its matching language. This establishes track
presence/language, not actual subtitle display or full speech quality.
The Russian PDF link navigated to the correct PDF URL, but repeated viewer
capture remained blank grey; PDF viewing is unconfirmed, without attributing
the cause to the application. Browser observations and source/ZIP hashes are
in `tmp/portable-browser-20261013/browser-observations.json` and `evidence.json`.
No file://, native application ZIP picker, human listening or full lesson
watch is claimed. The owned server/browser are cleaned up after verification.

### Tracker and remaining acceptance

The same canonical XLSX now tracks **252 stories**, **91 FIXED / 161 PASS**
scoped checks, **194 linked numbered bugs**, and **252 PARTIAL** full user
behaviours. The browser evidence is attached to F166 with explicit remaining
work; historical failed runs and live/native evidence are preserved.
Complete native journeys, external school service, camera, packaged runtime,
PDF viewing, full audio/visual review and teacher/editor approval still need
acceptance. The full objective remains active.

Final tracker readback confirmed typed dates, two tabs, 21 columns, freeze D2
and table A1:U253. All-row integrity and lexical surface gates passed (90/90
surfaces). The changed F133/F166 expectation and evidence ranges were rendered
and visually inspected; formula-error scan matched no cells. Ruff F/I passed
for the changed exporter, shared bootstrap, new tests and tracker generator;
compileall passed for all lesson tools, and focused CRLF-aware diff checks
passed. These checks retain their stated scope.

Cleanup closed only the audit-created browser tab and terminated only the
exact owned Range server command, PID 9948, after identity validation. Its exec
session became terminal with exit 1 due to deliberate cleanup, not a product
failure. Browser seek/navigation can cancel in-flight HTTP transfers; the
temporary server logged connection resets, without a browser media error in
the recorded 24 checks. No user application window or original lesson asset
was removed.

## Prepared learner routes and native entry repair (2026-10-14)

The current canonical workbook retains 252 stories, 21 columns and the
existing Features/Summary tabs. It links 209 numbered defects, with
92 FIXED / 160 PASS scoped software checks and 252 PARTIAL full behaviours.
PARTIAL remains deliberate: an offscreen or source check does not establish
the complete native story.

### Completed software work

BUG-195–205 repaired prepared-content access at zero/unknown AI quota,
unnecessary reference ingestion, cross-learner locked/revealed answers,
retired-card signals, selected language and latest pending language,
cancelled-load retention, stable v2 course identity across languages,
preserved legacy history, honest course IO errors, save retries and
idempotent operation IDs, active-profile settings ownership, both players'
audio destinations, distinct Unicode topic identities, ambiguous historical
attribution and misleading cancelled-review success.

Old-language progress is projected without a read-time rewrite; complete
source snapshots are retained on successful mutation. Changed previously
migrated aliases require review. A real Windows byte-range lock test proved
that denied history reads/writes retain old bytes. New answers keep original
time/confidence and use a stable operation ID across retry, including the
case where the write succeeded but acknowledgment failed.

The source-bound full suite completed 551 tests in 383.94 seconds, then an
updated tracker-only boundary completed 551 in 423.39 seconds. Both exited
0 with one upstream ChromaDB deprecation warning and no changed source/media
hashes. Those runs predate the later native entry repairs and remain
historical evidence, not acceptance of the new code. Nine related catalog
stories passed; the separate related test group completed 84. Existing
failure baselines, browser/native records and teacher-review states remain.

### Defects found through the actual home button

An owned isolated native Kazakh window was opened from current source, and
the real home Learn button was accepted once. It selected v1 with six chapters,
no video, internal rendering status and English completion prose. The
accessibility observation is `tmp/native-route-baseline-20261014.json`.
This established BUG-206–208 beyond direct handler tests.

The dashboard and catalog emitted the exact prepared ID, but the receiving
handler failed to recognize it and wrapped it in a generic generation prompt.
It now routes directly to the v2 package. Tests click both widgets in kk/ru/en,
at fresh/exhausted allowance, and require the exact worker topic, eight
chapters, language and unchanged quota. Ready notices and audience labels
are localized; rendering/text-only results explicitly distinguish text
availability from a finished video.

Route baseline: 12 failures. Notice/audience baseline: 9 failures. The same
21 checks passed after repair in `tmp/native-entry-postfix-20261014.log`.
The committed regressions are in `tests/test_prebuilt_student_routes.py` and
the catalog expands their cases explicitly. These use a controlled worker
and recorded video dispatch, not real playback.

### Catalog execution and state isolation

The first restricted run failed access to its own Windows temp directory and
stalled in its smoke child. The next permitted run encountered Windows path
failures in nested test fixtures/atomic staging. All logs and partial results
were retained. Only command-validated owned processes were stopped.

BUG-209 removes module/function names from fixture paths and gives each
invocation fresh UUID/index directories. Three independent regressions failed
before repair, including previous-state reuse. An initial misplaced import
was corrected; the fixture/lifetime group then passed 4. Result notes retain
test names, and skip/failure behavior is preserved. Long-path and isolated
case checks are now part of F215.

The final source-bound suite completed **575 passed**, one upstream ChromaDB
warning, exit 0, in **511.21 seconds**. The all-catalog retry completed
**252/252 PASS**, exit 0, including all 48 prepared student route checks and
the compact fixture/lifetime checks. Logs are
`tmp/student-route-final2-full-20261014.log` and
`tmp/catalog-student-routes-final2-20261014.log`. The evidence files record
unchanged app/test/tool/packaging/harness/generator/manifest/nine-media hashes
at both boundaries; current readback rechecks these hashes.

The canonical workbook was updated after the completed catalog merge, retaining
historical cloud/browser/native/failed-run records. Integrity and lexical
coverage gates pass: 252 features/results/tests and 90/90 recognized surfaces.
The scope of that lexical gate is word coverage, not exhaustive UI acceptance.
An additional read-only audit found all 753 numbered Python source references
within existing files and line bounds; it does not prove semantic function
matching. Changed expectation/evidence ranges were rendered and visually
inspected, with no formula-error matches. Ruff F/I and CRLF-aware focused diff
checks passed for the changed route/view/tests/harness/generator.

### Limits of native and media acceptance

Post-fix startup accessibility was observed in a new owned window. An occluded
capture showed an unrelated foreground view and was excluded from PhysLab
visual evidence; activation reported no monitor. Two fresh-tree clicks were
refused by user-input detection. Post-fix native entry/playback remains
unconfirmed; `tmp/native-route-postfix-attempt-20261014.json` retains that
scope. Only the owned post-fix process was closed, PID 15044, after validating
its command. User windows/data were preserved.

The three actual packaged MP4s were loaded by Qt with audio/video streams and
the correct duration, without playback. Audio-output ownership/mute toggles
are checked. No human listening, complete native watch, PDF viewer display,
real camera flow or deployed school-service acceptance is inferred.

Pending answer drafts remain in memory. Normal close defaults to staying
unless the learner explicitly discards them, and retries avoid double counts;
forced termination before an uncommitted write has no durable outbox recovery.
Old ambiguous topic history is retained without guessed per-topic scores.
Teacher/editor review and full remaining story acceptance stay open.

## Course feedback and retest status (2026-10-14, current work)

BUG-210–217 cover overwritten empty/missed feedback, low-confidence correctness
counts, lifecycle/review localization, false save acknowledgment for removed
review targets, lost pending-card state on partial cancellation, recommendations
ignoring later objective review, generic score reset on header language change,
and historical PASS being promoted despite an incomplete current retest.
Changes preserve historical quiz totals, original choices and unknown metadata.
Self-reported recall remains separate from objective correctness.

Data/tracker regressions completed **42 passed**, exit 0, in 43.73 seconds with
unchanged recorded source hashes, in
`tmp/feedback-core-boundary-20261014-evidence.json`. UI/controller and controlled
pipeline tests completed **21 passed** in 101.46 seconds after correcting a
Kazakh word-order assumption in one assertion. Logs retain the initial
failures, two invalid fixture constructors, the intermediate metadata-only
gate repair and the final passing focused groups. No constructor mistake is
classified as an app defect.

Automatic approval review initially could not execute the elevated header
test because its usage limit was exhausted. The command did not run. After
the stated reset time, the same normal approval path accepted the test group;
no alternate tool or permission bypass was used. Only the exact owned old
probe, PID 23948, was retired after command validation; its original log has
no final test outcome. User windows and data were preserved.

The canonical workbook currently records 252 stories and 217 linked bugs.
While the new full regression/catalog run, seven affected checks are explicitly
PENDING/PARTIAL: 86 FIXED, 159 PASS, 7 PARTIAL scoped software statuses.
Historical PASS entries, dates, cloud/browser/native media evidence and failed
runs remain; the incomplete current retest is not stamped FIXED. Structural
integrity can be checked separately, but the strict gate must reject pending
current-source retests. All 252 complete story behaviours remain PARTIAL.

Active final runs are `tmp/lesson-feedback-final-full-20261014.log` and
`tmp/catalog-lesson-feedback-final-20261014.log`. Their process handles are
observed directly; silence/timeouts do not trigger a restart. They do not
establish native camera, external school deployment, full human listening or
PDF-viewer acceptance. The overall user goal remains active.
