# PhysLab feature audit — 15 October 2026

The active objective remains: inventory every feature, derive user stories and
expected behaviour from code, maintain one canonical spreadsheet, test all
stories, document errors, fix logistical/UX defects, and retest the behaviours.
The full objective is not yet proven complete.

## Current 260-story checkpoint (15 October 2026)

The canonical workbook contains **260 stories**, **114 FIXED / 146 PASS
recorded software results**, **14 complete / 246 partial** source-bound story
acceptances, and **255 unique issue IDs**. The audit remains active.

The 14 complete acceptance matrices are F03–F09, F11, F27–F29, F232, F253 and
F254. The refreshed startup, settings, plot and bank evidence is in
`tmp/acceptance-refresh-stable-20261015/`; F04 was refreshed through its
source-stable story replay under `tmp/feature-acceptance/`. F11 and F253 remain
valid. No reviewed acceptance matrix is stale. These contracts have
explicit limits: F232's teacher/curriculum review is pending, and the numeric
plot contracts do not certify native canvas rendering. The other **246** story
acceptances remain partial: **8** have evidence still to gather and **238** have
no reviewed complete matrix yet.

Tracker integrity now passes for **260 features, results and tests**, with
**114 defect-linked features** and both bug-link directions checked. The
surface audit covers **107/107** detected UI/config/CLI surfaces. The canonical
XLSX has Features/Summary sheets, 260 feature rows, freeze pane D2 and updated
acceptance counts; the CSV is its generated mirror. Its Summary shows
**114 FIXED / 146 PASS** software results and **14 PASS / 246 PARTIAL** story
acceptances. The 260 result rows are recorded checks; the integrity audit
checks catalog parity, not source freshness for every feature. Only the 14
source-bound matrices above count as complete acceptance.

BUG-296 removed the hidden `AETHERLAB_SPIDER_CRAWL` launch hook. Spider stays
closed at startup and opens through its navigation action. The focused
launcher suite passed **19/19** offscreen; F259 covers five feedback/cancellation
checks and two startup/dock checks. A prior isolated native launch showed one
Kazakh dashboard, no Spider dock or scan controls, and the old English status
“PhysLab ready · No API key”: `tmp/native-spider-startup-20261015/ui-observation.json`.
BUG-297 localizes provider, settings, Ollama and explicit Spider-ready status
messages in kk/ru/en. F230's current source-stable replay passed, including the
status interaction; the focused Qt test passed **1/1**. That replay is offscreen,
so a fresh native launch has not yet verified the visual status change. The
user's existing app (PID 9224) was not restarted; the change will take effect
on its next launch.

BUG-298 records and fixes a test-isolation error found during that replay: the
test inherited the workstation's MiniMax provider variables while expecting
its synthetic Ollama model. The test now clears provider/model/endpoint
aliases only in its isolated profiles. F215's source-stable gate replay also
passes; it verifies that a red test makes the process and tracker gate fail.
Evidence: `tmp/dashboard-status-localization-final-20261015-evidence.json` and
`tmp/tracker-gate-stable-final-20261015-evidence.json`; the focused Qt test
passed **1/1**.

Current offscreen story probes also pass for F12, F14, F17, F19, F20 and F84:
submission, quality selection, stepper timing/error, duplicate-run protection,
worker cleanup and failure recovery. They were merged only after source-stable
runs. The first F13 and F15 attempts detected concurrent edits to lesson files
and were not merged; source-stable reruns now pass and are merged too. Evidence
is in `tmp/command-input-current-20261015-evidence.json`,
`tmp/command-examples-stable-final-20261015-evidence.json`,
`tmp/command-quality-current-20261015-evidence.json`,
`tmp/command-cancel-stable-final-20261015-evidence.json`,
`tmp/stepper-timeline-current-20261015-evidence.json`,
`tmp/worker-duplicate-current-20261015-evidence.json`,
`tmp/worker-cleanup-current-20261015-evidence.json` and
`tmp/stepper-error-current-20261015-evidence.json`. These eight offscreen
checks do not complete the native Windows UI acceptance.

An earlier controlled full regression passed **1727 tests** with one upstream
ChromaDB deprecation warning in 577.05 seconds:
`tmp/all-app-regression-current-20261015.log`. That run predates the latest
status/localization and lesson-source edits, so it is not a full-suite claim
for the current tree. The earlier catalog replay and F255/F259 retest remain
preserved at `tmp/all-story-catalog-current-20261015/evidence.json` and
`tmp/instance-guard-retest-current-20261015-evidence.json`.

A later direct full-catalog invocation was stopped before writing results when
its isolated process grew to about 2 GiB and left 0.4 GiB free. The pre-run and
live `feature_test_results.json` hashes match; that partial run is not counted.
Focused story replays and bounded acceptance matrices were run serially after
memory recovered.

Remaining work includes native UI navigation/layout and file-dialog journeys,
provider/cloud lesson delivery, student practice and exam journeys, camera and
school workflows, storage recovery, and teacher/language review. Spider still
needs native capture/Watch privacy, active Git-command interruption, shutdown
recovery, concurrent edits, and real Ruff failure acceptance. Full user-story
acceptance remains open for **246 stories**.

## Earlier 256-story checkpoint (superseded by the section above)

Fresh serial verification on the current source tree completed on 2026-10-15:
the full regression suite passed **1509/1509** in 371.85 s with offscreen Qt,
thread caps, one worker and isolated pytest temp
(`tmp/pytest-current-x8-20261015.log`). The post-fix code-derived feature
harness passed **256/256**, with no live provider credentials or cloud dispatch
and isolated data/reference stores (`tmp/feature-harness-postfix-final-20261015.log`).
Its explicit post-fix phase passed all 25 newer rows; five legacy acceptance
matrices were rerun against current source hashes
(`tmp/feature-legacy-acceptance-refresh-20261015.log`). The one warning remains
Chroma telemetry's deprecated `asyncio.iscoroutinefunction`; it did not affect
the result. The regression runs exposed stale test adapters: one remote-
generator fake/data fixture (BUG-267) and two scene-lint stubs (BUG-268). Their
focused tests and the final complete regression suite pass. A catalog audit
also found that a legacy row with no phase-4 field was incorrectly rejected as
PARTIAL even with passing current tests and fully verified acceptance evidence
(BUG-272). The verifier now preserves only truly absent legacy fields and
still rejects explicit `None`, `PENDING`, or failed phases; 123 acceptance-
policy tests pass. BUG-273 records the explicit-null guard, and BUG-274/275
record repaired timeout documentation and endpoint-based provider labels.
The regenerated workbook has **8 complete / 248 partial** story acceptances.
Tracker integrity reports **256 stories, 256 results, 256 tests and 104 defect-
linked features**; all **105/105** detected surfaces map to a row. This proves
current software-check coverage, not full student-facing acceptance.

The canonical workbook now contains **256** code-derived stories, **104 FIXED /
152 PASS** recorded software checks and **8 complete / 248 partial** acceptances.
All **232** registered issues are linked; all **105/105** detected surfaces map
to rows. F254 inventories the existing SQLite bank-sync command; F255 covers
the new single-profile GUI launch guard. The shared tree's incoming UNT
landscape/portrait presets and unt_mode resolver are recorded in F251 without
claiming a complete exam-video workflow. F256 separately inventories the incoming
UNT directing/scaffold, codegen and textual gate policy, beyond the F251 presets.
BUG-266/267 remove fabricated scaffold values/official status and mandatory
unsupplied answer letters. The wider current UNT/segmentation/preflight/upgrade
group passed **95/95**, unchanged HEAD/sources:
`tmp/unt-policy-current-regression-20261015-evidence.json`. These tests do not
certify a model's actual final video or official-source authenticity.

BUG-259/260 repair displayed-condition answer keys (107 failures in AC,
electrostatics and relativity); BUG-261..264 repair SQLite ownership,
annotations/foreign keys, fresh databases and source-page identity; BUG-265
prevents duplicate guarded launches. The bank/policy/launch group passed
**116/116**, and startup/launch passed **60/60**. The reviewed generator/API
matrix executes 40 cases for all 2500 records in kk/ru/en; SQLite executes 29
cases including actual CLI, read-only retry and process-crash recovery.

Ten affected acceptance/startup/launch/policy stories passed again with unchanged
HEAD/sources and merged results:
`tmp/unt-bank-launch-contracts-final-20261015-evidence.json`. Earlier wider probes
were not merged because settings/render-profile or scene-generator sources
changed concurrently; their diagnostics remain preserved. An incoming renderer
edit invalidated F253's acceptance; the final serial execution renewed it with
four actual tiny CLI renders. Complete acceptance remains separate from narrow
software checks. F256 citation review also caught/fixed the existing BUG-250
field-attribution pattern; **29/29** reference/CLI/UNT cases pass with stable
sources (`tmp/unt-citation-final-20261015-evidence.json`).

Concurrent registry edits reused issue IDs and omitted a link. The colliding
fixture records now have unique BUG-269/270 IDs, BUG-268 is linked, and BUG-271
makes audit reject duplicate table definitions/literal mapping keys. All records
were preserved. The current registry/reference/voice/bugcheck group passed
**94/94**, unchanged HEAD/sources (`tmp/registry-adapters-final-20261015-evidence.json`);
four affected F106/F131/F187/F256 stories passed with stable inputs/merged results
in `tmp/registry-story-adapters-final-20261015-evidence.json`. Artifact publication
is refreshed after these new results. Earlier 224-ID counts precede reconciliation.

The configured live SQLite bank was updated only after verifying its exact
known legacy generator and making a SQLite-consistent backup. All **2500**
payloads match current source, all unrelated table hashes/schema/row identities
are unchanged and integrity/FK checks pass:
`tmp/live-bank-repair-20261015-11a9fe45/evidence.json`. The pending teacher,
language and source-candidate review labels were preserved.

Seventeen launch checks cover real lock ownership, duplicate actual CLI exit
before window import, independent/Unicode profiles, corrupt-lock/storage errors,
a release race, normal release and actual-process crash recovery. No existing user GUI was stopped,
restarted or focused. The logon task remains unchanged; existing unguarded
windows cannot retroactively adopt the new lock. Future launches use it.

Earlier simultaneous full regression/catalog replays exhausted Windows commit
resources (1450 / MemoryError / pagefile-too-small DLL load) and did not finish
successfully; their mixed-source results were not merged. The resource
transport group recorded 219 pass / 4 process-creation failures. Subsequent
sequential executions passed **165/165** bank/policy/startup/launch cases, then
**58/58** profile/transport cases, including failed render/worker paths, with
unchanged sources/HEAD (`tmp/bank-launch-serial-final-20261015-evidence.json`
and `tmp/render-profile-serial-retry-20261015-evidence.json`). Those older
partial runs have now been superseded by the fresh 1508-test and 256-feature
passes above.
The fresh controlled sequence is now running with one stage at a time and
numerical-library thread counts of one:
`tmp/bank-launch-serial-sequence-20261015.json`. Its full pytest stage started
at 09:43:37 UTC with captured HEAD/source hashes, offscreen Qt and native
acceptance disabled (`tmp/bank-launch-full-serial-20261015-started.json`).
Only a completed stable full run permits the subsequent all-story catalog and
artifact publication stages. A separate shared-project pytest printed 1508
passes/one upstream warning; it was observed headless but is not substituted
for this sequence's before/after source-bound proof.
The canonical workbook uses typed dates,
Features/Summary, filtering and freeze pane D2; the new stories/scope cells
were rendered and reviewed without opening app windows.

## Previous 253-story checkpoint

The single canonical workbook is AetherLab_Feature_Tracker.xlsx: **253**
code-derived stories, **100 FIXED / 153 PASS** last recorded software results,
and independently **6 complete / 247 partial** story acceptances. F253 covers
the incoming local encoder-budget setting; F251 includes 1440p quality `p`.
All **215** registered issue IDs are linked. The standalone integrity audit
passes, and all 104/104 identified surfaces map to tracker rows.

BUG-248/249 fix adaptive cache identity and general session/worker/runtime
profile provenance; BUG-250 fixes unrelated global-symbol citations; BUG-251
isolates the full candidate-render boundary in the catalog. The expanded
current cache/profile/critic/PDF/reference/encoder/isolation group passed
**220/220** with unchanged sources/HEAD in
`tmp/attribution-expanded-current-20261015-evidence.json`. After final reporting
refinements, **17** attribution/isolation/cache-compatibility cases passed in
`tmp/attribution-contract-final-20261015.log`.

Thirteen affected/startup stories passed and merged with unchanged sources in
`tmp/attribution-final-preartifact-20261015-evidence.json`. The final F165 check
also passed with unchanged sources and merged results:
`tmp/attribution-publication-final-20261015-evidence.json`. It checks artifact
alignment, four reference regressions and the network/preflight guard. Workbook
summaries, cache entry-point references and new encoder/profile rows were
rendered and reviewed; no native app windows were opened. An intermediate
artifact retest caught a subsecond timestamp mismatch created by the audit
metadata writer; the writer now uses the column's seconds precision and the
regenerated workbook passes.

The next full diagnostic replay exposed BUG-252: the bundled worker supported
quality `p`, while the shipped workflow choices did not. It finished **1061
passed / 1 failed**, with only the pre-repair parity failure and source changes
in the workflow/tracker map (`tmp/audit-final-full-20261015-evidence.json`). Its
catalog finished **252/253**, with artifact drift at F165, and was not merged.
The shipped choices are now l/m/h/p/k; the repaired worker/quality/reference
group passed **12/12**. F249/F251 passed with unchanged sources and merged
results (`tmp/worker-choice-current-20261015-evidence.json`); F165 also passed
with unchanged sources/merged results in
`tmp/worker-parity-artifact-20261015-evidence.json`. Final artifact integrity
passes in `tmp/worker-parity-publication-audit-20261015.json`.

A real quality-p cloud job then produced **2560×1440/30 FPS**, with all **60**
frames decoded and measured object motion. Its repeated request returned
identical cached bytes with one total dispatch. The captured HEAD/sources stayed
unchanged (`tmp/live-1440p-5a7471e093/evidence.json`). This silent technical
probe does not certify educational content, narration or native playback.

The earlier complete replay recorded **1038 passed**, but seven source files
changed during it; the corresponding 252-story replay recorded **249/252**,
with outdated controlled render fixtures and artifact drift. Those mixed-source
results were not used to certify the current tree. The affected F108/F160
fixtures now supply successful render provenance and pass their original
assertions. Two later obsolete test processes were deliberately stopped after
final source-reference QA, not counted as completed checks; see
`tmp/attribution-current-cancelled-20261015.json`.

Those full post-repair replays completed successfully: **1062 pytest checks**
and **253/253 catalog checks**, exit 0 with unchanged HEAD/sources, and catalog
results merged. Evidence: `tmp/worker-parity-full-20261015-evidence.json` and
`tmp/catalog-worker-parity-final-20261015/evidence.json`.

## Encoder story acceptance extension

The subsequent tool extension gives F253 a reviewed 18-scenario matrix.
Eleven input classes and profile/cache/renderer arguments are checked, then
four real installed-Manim CLI renders observe effective encoder limits
1/4/8/fallback-4, drained queues and identical complete 27-frame videos.
Acceptance binds the generated scene, queue trace, process log, video bytes,
installed runtime versions/critical files and the current story/implementation.
Verification re-decodes every saved frame; file changes, queue violations,
changed runtimes, preview commands and incomplete records are refused.

Visual story review caught BUG-253: a generic Render template had added AI and
UI-retry requirements that `_manim_render_command()` does not implement. The
explicit F253 contract now describes its CLI prerequisites, integer fallback/
clamping and preserved arguments; rendering UI contracts remain on their own
stories. The corrected contract was fully executed again, with unchanged
sources and merged results (`tmp/encoder-code-contract-final-20261015-evidence.json`).
The schema/contract regression group passed **149/149** in
`tmp/encoder-contract-policy-final-20261015.log`. The final artifact/story
check passed with unchanged sources and merged results in
`tmp/encoder-code-publication-resume-20261015-evidence.json`; independent
artifact integrity passes in `tmp/encoder-contract-publication-audit-20261015.json`.
Summary and changed F253 story/scope cells were rendered and reviewed.

One earlier repeated artifact-check command was not executed because automatic
approval review could not complete after a service usage-limit error. It was
not counted as a test result. After the environment changed, the named resume
check above actually ran and passed.

The full runs after this acceptance-tool extension completed with **1087 pytest
checks** and **253/253 catalog checks**, exit 0 and unchanged HEAD/sources:
`tmp/encoder-contract-full-20261015-evidence.json` and
`tmp/catalog-encoder-contract-final-20261015/evidence.json`. Catalog results
were merged. The later answer-clear reproduction below exposes a missing
scenario in that passing suite, so those results do not certify that behaviour.
All runs use isolated data, Qt offscreen and explicitly disabled visible
acceptance. The full objective remains open: **247** acceptances are partial.

## Student answer capture and scoring

BUG-254 retained a previous multi/matching tuple after the learner cleared all
controls. Navigation, saving, closing and finishing skipped `None`, allowing
the visibly unanswered item to be restored or graded. The pre-repair matrix
failed **60/60** (`tmp/practice-clear-negative-20261015.log`). One capture
method now replaces editable responses with their actual value, including
`None`, while preserving checked, pending and finished results. Check also
retains a deliberately blank response when displaying the choose-answer hint.

The extended post-repair group passed **272/272**. It includes **183** actual
offscreen control/storage/scoring cases across kk/ru/en, two question kinds,
practice/timed/mistake-review routes, partial credit, reopened attempts and
pending-result retry. Six full 40-question/90-minute mock runs produce 48/50
after clearing one two-point response. Six actual Windows read-only active
files preserve their bytes on failure and accept the cleared answer after
permissions are restored. Evidence: `tmp/answer-capture-extended-20261015.log`.
Practice-mode multi/matching cases exercise the generic component directly;
the current generated topic exercises are single-choice, while mock items are
reachable through timed mode and mistake review.

F226/F233/F238 passed their updated catalog adapters, which execute every
parametrized case through pytest/JUnit and check that none failed or skipped
on Windows. Sources/HEAD remained unchanged and results were merged:
`tmp/answer-capture-stories-20261015-evidence.json`. Startup and encoder
acceptance were refreshed against current sources in
`tmp/answer-capture-startup-20261015-evidence.json`. Native layout, actual math
typesetting, camera and cloud behaviour are outside this answer-capture matrix.
The canonical workbook retains **6 complete / 247 partial** acceptances.

The full current-tree replay **answer-capture-full-20261015** completed with
**1270 passed**, one upstream ChromaDB deprecation warning, exit 0 and unchanged
HEAD/sources. Evidence: `tmp/answer-capture-full-20261015-evidence.json`.

An additional unchanged-app probe passed **6/6** timed expiry/PDF journeys:
`tmp/answer-expiry-pdf-20261015.log`. The real timer callback completes cleared
responses at 0/3, stops the timer and clears the active snapshot. Actual export
through `_save_pdf` produces parseable A4 reports with the same 0/3 and localized
unanswered labels in kk/ru/en. All six contain equation images. Only the file
picker and message dialogs are controlled; actual math rendering and PDF
generation run. The Kazakh multi-choice first page was visually inspected.
This is additional scoring/export coverage, not native file-picker or complete
PDF pagination acceptance. The catalog replay
**catalog-answer-capture-final-20261015** completed **253/253**, exit 0, with
unchanged HEAD/sources and merged results. Its terminal evidence is
`tmp/catalog-answer-capture-final-20261015/evidence.json`.
The six report byte hashes and executed-probe/log hashes are recorded in
`tmp/answer-expiry-pdf-20261015-evidence.json`; relevant app sources match the
unchanged full-regression snapshot.

Final publication was verified against the same unchanged sources in
`tmp/answer-capture-publication-20261015-evidence.json` and regenerated after
the check timestamp changed. The standalone gate passes in
`tmp/answer-capture-final-artifact-audit-20261015.json`: 253 rows/stories/results/
checks, all 211 issue IDs linked and no integrity errors. The heuristic surface
audit remains 104/104. Changed expectation/story/error/scope ranges and the
summary were rendered and inspected; the formula-error scan found no entries.
The workbook retains 100 FIXED / 153 PASS software results and, separately,
6 complete / 247 partial acceptances. This is a post-fix checkpoint, not overall
objective completion. No native app windows were launched or closed.

## Guarded setup actions and failed replacement

BUG-255 allowed Review mistakes to bypass the saved-attempt prompt and replace
an interrupted practice/mock/review session. Its baseline failed **27/27** in
`tmp/review-resume-negative-20261015.log`. Both Start and Review mistakes now
use `_resolve_saved_attempt()`. Resume restores saved mode/language/identity;
Cancel preserves bytes; explicit Start again proceeds to the requested new
activity only after the interrupted snapshot is confirmed absent.

BUG-256 was independently reproduced in **6** actual Windows read-only cases:
`clear_active_session()` swallows failed unlinks for post-result cleanup, so
Start again previously entered a new session while the old snapshot remained.
Evidence: `tmp/snapshot-restart-negative-20261015.log`. A replacement now
requires verification, with separate localized restart_error feedback and
retry on unlink or verification-read failure. Best-effort completed-result
cleanup and retained-history deduplication are preserved.

The permanent matrix has **255** executed cases: 189 answer/scoring/export
cases and 66 setup-decision cases. It includes both setup controls, all three
languages, saved practice/timed/review modes, Cancel/Resume/Start again,
unavailable/empty mistakes, invalid-bank snapshots, Windows read-only failure
and retry, verification-read interruption, saved-language resume and pending
result completion once. The six actual expiry/PDF cases are now collected by
normal pytest and the F226/F227/F228/F233/F238 catalog adapters.

Eleven targeted story/startup/encoder checks passed with unchanged sources and
merged results (`tmp/session-guard-stories-20261015-evidence.json`). A prior
diagnostic group's six failures were an optional-key fixture error, corrected
to use `attempt.get`, not a product defect. One focused run was cancelled at
an old disposal test that did not answer the new second-open confirmation:
`tmp/session-guard-focused-cancellation-20261015.json`. The fixture now chooses
Resume, asserts one prompt and the same attempt identity, and keeps both
original disposal assertions. Its rerun with the full 66-case setup matrix
passed **83/83** in `tmp/session-guard-disposal-20261015.log`.

F226/F227/F238 now have explicit code-derived story steps, prerequisites and
failure expectations. The canonical workbook and CSV pass integrity in
`tmp/session-guard-artifact-audit-20261015.json`; all **213** registered issues
are linked. The three changed story/contract ranges and error cells were
rendered and inspected. Software status remains 100 FIXED / 153 PASS, separate
from 6 complete / 247 partial acceptances. Ruff F/I checks pass, including the
two previously deferred import-order fixes. The full source-frozen run
**session-guard-full-20261015** completed **1342 passed**, one upstream warning,
exit 0 and unchanged sources/HEAD; evidence is
`tmp/session-guard-full-20261015-evidence.json`. Its catalog run completed
**253/253**, exit 0, unchanged sources/HEAD and merged results:
`tmp/catalog-session-guard-final-20261015/evidence.json`. No visible/native app windows are
launched or closed; this matrix does not certify camera or cloud journeys.

A separate content probe exposed a further coverage gap while those runs were
frozen. It reports **3 failed / 9 passed** in
`tmp/topic-notation-expanded-negative-20261015.log`: f-string interpolation
removed braces from negative exponents in magnetic/photon substitutions, and
nanometre worked steps used the constant 1 nm as the unknown quantity. Actual
equation rendering succeeds even for the malformed exponent, so successful
typesetting alone cannot prove mathematical correctness. These content defects
are repaired below; the earlier passing suite/catalog did not cover them.

## Generated solution notation and independent numeric checks

BUG-257 escaped the literal negative-power braces in magnetic-force and photon
f-strings. BUG-258 gives nanometre conversion a length variable `l` instead of
reusing the constant 1 nm as the unknown. Exactly three source lines changed;
original newlines are preserved. The canonical JSON digest of every generated
field except explanation/solution_latex remains identical for all **2500**
records. Evidence: `tmp/topic-notation-preservation-20261015.json`. Prompts,
choices, correct indices, language data, IDs and pending source/review metadata
are unchanged.

The first repaired group passed **12/12**. The final permanent module has 13
checks, adding a scan of all 2500 worked sets for ungrouped negative exponents.
It independently recomputes 100 magnetic-force, 100 photon-energy and 100
nanometre-conversion answers from the supplied numbers using Decimal, checks
four-significant-digit values and units in kk/ru/en, then typesets 18 first/last
equations. Corrected magnetic and nanometre images were inspected. The expanded
notation/explanation/result/bank group passed **50/50** in
`tmp/topic-notation-final-20261015.log`.

The generator catalog executes seven non-rendering cases, preserving its pure
data API; the worked-solution catalog executes all 13. A fresh-process run with
both Qt bindings forbidden passed the seven generator/key checks and imported
neither binding (`tmp/topic-generator-no-qt-20261015.json`). Twelve targeted
story/startup/encoder checks passed with unchanged HEAD/sources and merged
results (`tmp/topic-notation-stories-20261015-evidence.json`). Shared practice
case signatures now include ent_topic_bank.py so changed generated material
cannot reuse an old in-process matrix result.

Canonical artifact integrity passes in
`tmp/topic-notation-artifact-audit-20261015.json`; all **215** registered issues
are linked. The workbook retains 253 stories and 100 FIXED / 153 PASS software
results, separately 6 complete / 247 partial acceptances. The source-frozen
**topic-notation-full-20261015** run completed **1355 passed**, exit 0, one
upstream ChromaDB warning and unchanged HEAD/sources; evidence is
`tmp/topic-notation-full-20261015-evidence.json`. The catalog run
**catalog-topic-notation-final-20261015** completed **253/253**, exit 0, unchanged
HEAD/sources and merged results; evidence is
`tmp/catalog-topic-notation-final-20261015/evidence.json`.
Mathematical checks here cover
the named three topics plus the all-bank syntax invariant; teacher/language
review and complete all-topic physical validation are not claimed.

### Final correction of non-video story boundaries

Visual review exposed the existing BUG-253 template defect on four more rows:
F190 research PDF fallback, F220 study PDF, F233 equation review and F247 language
changes described a missing/corrupt-video failure. The source-derived contract
probe failed **4/4** in `tmp/feature-failure-story-negative-20261015.log`.
These now have explicit prerequisites, steps and actual fallback expectations:
matplotlib/tex-only, deterministic document authoring/healing, readable math and
per-attempt images, and unknown-locale/source-label behaviour respectively.
The two permanent contract tests plus existing encoder/reference checks passed
**7/7** in `tmp/boundary-story-fixed-20261015.log`.

This correction changes only build_feature_tracker.py, test_features.py's F165
adapter and the new contract-test module. All application, watchdog and worker
sources match the completed 1355-pass snapshot byte for byte. The exact delta
is verified in `tmp/boundary-only-delta-20261015.json`. The new two metadata
tests are separately executed; no new 1357-case full run is claimed. The scoped
replay of the four affected stories and six startup/encoder contracts passed
with unchanged sources and merged results in
`tmp/boundary-stories-final-20261015-evidence.json`. F165 then passed its updated
artifact/reference/isolation and both new metadata contract checks, with stable
sources and merged results (`tmp/boundary-publication-final-20261015-evidence.json`).

The final regenerated XLSX/CSV pass independent integrity in
`tmp/boundary-publication-final-audit-20261015.json`. All 253 stories/results/
catalog IDs align, all 215 registered issue IDs are linked, the heuristic
surface audit is 104/104, the Artifact Tool formula-error scan has no entries,
and the date column remains typed datetime. Changed contract/error ranges and
all four final boundary stories were rendered and inspected. Metadata-only
timestamp refreshes used the existing builder without re-rendering unchanged
summary/layouts. Ruff F/I and CRLF-aware whitespace checks passed.

The complete-behaviour gate still refuses completion for **247** stories in
`tmp/boundary-completion-gate-20261015.json`. The workbook retains **6 complete /
247 partial** acceptances and **100 FIXED / 153 PASS** scoped software results.
No visible application window was opened, restarted or closed. The objective
remains active; camera/native layout, wider learner journeys and complete
cloud educational/audio/playback acceptance still require work.

## Earlier profile and cloud evidence

Saved render settings and worker v8 now transport custom dimensions/FPS,
inherit adaptive policy correctly, normalize odd YUV420p canvas sizes and
validate downloaded files before replacing prior video. BUG-244–247 are
documented with negative baselines and focused successful replays.

The complete pytest replay finished with **987 passed**, one upstream warning,
exit 0. Its source snapshot changed in
`aetherlab/services/scene_components/projectile.py` during execution, so this
is a mixed-source regression result, not proof for an unchanged current tree.
Evidence: `tmp/profile-v8-full-20261015-evidence.json`.
The corresponding full catalog finished **252/252**, exit 0, but changes in
the projectile component and its tests also made that run mixed-source. Its
results were correctly not merged (`merged_into_tracker: false`):
`tmp/catalog-profile-v8-final-20261015/evidence.json`.

A separate real cloud v8 probe passed with unchanged sources/HEAD: one
dispatch, a 960×540/24 FPS MP4 with all 48 frames decoded and measured object
motion, then an identical-byte cache hit. Evidence:
`tmp/live-profile-v8-8f293f4adc/evidence.json`. This is silent technical-scene
evidence; it does not certify native playback, educational content or audio.
Visible UI acceptance remains disabled after BUG-240.

At the preceding checkpoint the canonical workbook had 252 stories, 100 FIXED / 152 PASS software
results, and independently 5 complete / 247 partial user-story acceptances.
BUG-248 and BUG-249 now cover adaptive cache identity and general session/
worker/runtime profile provenance. Their focused replay passed **36/36**;
the expanded cache/profile/segment/critic/PDF group passed **209/209**, exit 0,
unchanged sources/HEAD (`tmp/cache-expanded-final-20261015-evidence.json`).
Eleven startup/cache/render/cloud stories passed and merged with unchanged
sources in `tmp/cache-profile-focus-20261015-evidence.json`. All **206**
documented issue IDs are linked; the integrity audit and 104/104 surface audit
pass. Workbook summaries and affected profile/cloud rows were rendered and
reviewed without opening the native app.

Those complete pytest and 252-story catalog replays subsequently finished as
`cache-provenance-full-20261015` and
`catalog-cache-provenance-final-20261015` with the mixed-source results
qualified above. The separate live SQLite/pipeline
cache probe passed: initial 960×540/24 FPS render (48 decoded frames), same-
profile reuse, changed 1280×720/30 FPS render (60 decoded frames), then repeat
reuse. Exactly two renders/dispatches, distinct output paths, retained prior
file and cached solver/RAG/code are verified, with unchanged HEAD/sources.
Evidence: `tmp/live-session-cache-758685d699/evidence.json`. Its planner,
analytical result and references are controlled fixtures, preflight disabled;
it certifies actual cache/render routing and Cloud delivery, not AI generation,
audio, native UI or educational content. Twelve additional compatibility cases
passed in `tmp/cache-compatibility-acceptance-20261015.log` without opening UI.
These technical cloud probes retain their captured implementation scope.
The full objective remains incomplete.

## Historical lesson software checkpoint (before profile v8 changes)

The earlier working tree on HEAD `99e14bb` passed **932 pytest checks** and
**252/252 catalog checks**, both terminal exit 0 with unchanged HEAD/source
snapshots. The catalog evidence was merged into feature_test_results.json:

- `tmp/lesson-ui-retry-final-full-20261014-evidence.json`
- `tmp/catalog-lesson-ui-retry-final-20261014/evidence.json`

The canonical workbook remains the single status artifact, with **252**
stories, **99 FIXED / 153 PASS** software results and independently
**5 complete / 247 partial** story acceptances. The two new documented issues
are BUG-242 (lesson busy/cancellation cleanup) and BUG-243 (completion copy,
media ownership, exact retry topic and material-first navigation). All
**200** documented issue IDs are linked to their affected stories.

The 932-test run has one upstream ChromaDB deprecation warning. No visible
native UI test windows were opened. Controlled-player/owned offscreen visual
checks and the real no-key Kazakh/Russian worker probe support their recorded
scope; complete provider/cloud delivery, video/audio review, exports and the
remaining story journeys are still required. This is not overall goal
completion. Earlier checkpoints below retain their original scope/results.

## Current lesson completion checkpoint

The current worktree is based on HEAD `99e14bb`. BUG-242 retains busy controls
through real lesson-thread cleanup and prevents repeated/terminal Cancel.
Its negative baseline was **30 failed / 42 passed**; repaired module **72/72**.
The combined command-bar/Learn/policy pass was **280/280** before the media
follow-up. BUG-243 fixes misleading success notices and previous-media reuse;
its first baseline failed **35/35**, and the expanded media/result pass passed
**40/40**, including actual QMediaPlayer source clearing.

Further completion checks found missing retry topics and an empty default
Video tab for incomplete results: **28 failed / 19 passed** after strengthening
the matrix. The repaired completion suite passed **47/47**, including exact
draft recovery, newer-draft preservation, material-first navigation and refusal
of video paths on nonassembled bundles. Complete lesson generation, physical
playback/audio and exports remain separate acceptance requirements.

Thirteen affected/startup/profile/speech stories passed with unchanged inputs
and merged results in `tmp/lesson-ui-current-complete-focus-20261014-evidence.json`.
The subsequent broad freeze passed **925** tests, one upstream warning, exit 0
and stable HEAD/sources (`tmp/lesson-ui-latest-full-20261014-evidence.json`).
Both precede the final retry/Text-tab follow-up; renewed full regression and
the entire 252-story catalog follow their actual terminal results. Visible
native test windows remain disabled. Issue history contains **200** IDs.

The final retry/media/navigation implementation passed **932** tests,
one upstream ChromaDB deprecation warning, terminal exit 0 and unchanged
HEAD/source snapshots in
`tmp/lesson-ui-retry-final-full-20261014-evidence.json`. The later full catalog
passed **252/252** with unchanged sources and merged evidence. The real no-key
Kazakh/Russian worker probe also passed with unchanged
sources (`tmp/actual-offline-lesson-20261014/evidence.json`). It does not certify
English template rendering, a configured AI provider, cloud delivery or audio.

## Previous published checkpoint

The canonical workbook has **252** stories: **99 FIXED / 153 PASS** software
checks and **5 complete / 247 partial** story acceptances. Structural audit
and code-surface reconciliation pass; the surface guard covers **104/104**.
Issue history contains **198** distinct documented IDs, each linked to a story.

The current source-bound focus passed F03/F04/F05/F09/F11/F13/F55/F251/F252,
exit 0, with no source changes and merged evidence:
`tmp/tier-profile-current-focus-20261014-evidence.json`. It includes **29**
profile checks, **34** speech/routing checks and two actual runtime tier cases.
The final profile/menu/visible-test guard group separately passed **39** cases
in `tmp/tier-final-20261014.log`. Native UI tests remain opt-in and were not run.

The earlier broad freeze passed **856** tests with one upstream warning.
The later full catalog checked all 252 entries but returned **251/252**, with
F55 still expecting the retired hardware-tier contract. Its snapshot changed
externally in `manim_runtime.py`, `render_backend.py`, `scene_preflight.py` and
`voiceover.py`, so that run was not merged. BUG-241 corrects F55's inventory and
checks while preserving application code; the current focused renewal passes.
The 856-test result predates those later rendering edits and is not presented
as a complete regression of the newest worktree. A new stable broad pass,
complete remaining story journeys, native layout/focus and cloud/media review
are still required. No completion claim is made for the overall objective.

## Visible test windows stopped

The user reported repeatedly opening PhysLab windows. The owned catalog process
13380 and its native pytest child 25528 were confirmed by their exact command
lines and stopped together with their child process. A subsequent process check
found no matching catalog/native-test process. These windows came from the UI
acceptance runner, which forced Windows Qt during ordinary catalog checks.
Successive native runs also had different source hashes (`settings.py`, then
`models.py`), so the source-bound cache could not reuse the initial result.

Ordinary catalog checks now leave visible Windows UI acceptance pending. Both
the catalog entry and native runner require the explicit environment flag
`PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE=1` before launching visible test windows.
No further native UI tests were launched after the user's report. Seven
process-free guard cases now pass, including explicit opt-in routing with a
controlled runner. The interrupted catalog run is
partial and must not be reported as a completed retest or merged as one.

## Localized school examples checkpoint

BUG-239 replaces the ten English/university/mathematics examples with ten
authored school-physics prompts in kk/ru/en. Every menu open reads the current
language; the three versions preserve physical conditions and numerical data.
They are example questions, with no official UNT provenance claim. F13's user
story and reviewed acceptance matrix now require this content/language scope.

The old content failed all three new locale cases. The final focused group
passed **10/10** offscreen: three actual menu/action checks plus seven visible
test opt-in guards (`tmp/examples-localization-fixed2-20261014.log`). A prior
retry had three temp-directory fixture setup errors, retained in its log.
The current code still requires broader post-fix regression and catalog
renewal. Native visual/layout acceptance remains pending; no visible test
windows will be opened by an ordinary catalog run. Issue history: **197** IDs.

## Current inventory and broader replay

The canonical workbook now contains **252** stories. Added F251 for validated
render profiles/presets/overrides and F252 for formula speech normalization,
language/voice/cache routing and localized narration diagnostics. Their
executed focus passed **27** render-profile checks and **34** speech/routing
checks; F13's expanded menu story also passed with unchanged source hashes in
`tmp/examples-profile-speech-focus-20261014-evidence.json`. Surface discovery
now accounts for **104/104** settings, labels, CLI and localized-copy surfaces.
This word/source mapping guards inventory coverage; it is not runtime proof.

The first broad run finished **852 passed / 4 failed**. Three source files
changed externally during it, so its recorded snapshot invalidates a single-
revision acceptance claim. All four failure cases passed on replay with
installed compiler access (`tmp/latex-owned-probe-20261014.log`). A segmented-
cache fixture now matches solver/config model metadata and forbids provider
access; its focused group passed **133** checks. Historical failures and the
environment/source distinctions remain in ERRORS_FOUND.md.

At that checkpoint reconciliation passed with **98 FIXED**
and **154 PASS** software checks. Five complete headless startup/settings
contracts (F03/F04/F05/F09/F11) were renewed with unchanged inputs, exit 0 and
merged evidence in `tmp/startup-headless-renewal-20261014-evidence.json`.
The workbook therefore shows **5 complete / 247 partial** behaviours. Former
native proofs are stale after source changes. The final broad regression
passed **856** checks, one upstream ChromaDB deprecation warning, exit 0 and
unchanged source/HEAD snapshots in
`tmp/examples-headless-final-full-20261014-evidence.json`. No visible Qt
windows were launched. The subsequent 252-story catalog result and current
F55 correction are recorded in the latest published checkpoint above.

Independent arithmetic also checked the ten authored example conditions and
the exact numerical data across translations:
`tmp/example-physics-arithmetic-20261014.json`. Expected results include
10 m/s and 25 m for acceleration, 6 N, 100 J, 2 m/s after the inelastic
collision, 400 Pa, 16800 J, 2 A, 6 ohms/2 A, 10 m/s for the wave and a real
image 60 cm from the lens. This verifies the authored inputs/derivations,
not future generated AI responses or official exam provenance.

## Latest Learn checkpoint

The command-bar layout follow-up completed **719 pytest cases**, one upstream
warning, exit 0 with unchanged sources:
`tmp/commandbar-acceptance-final-full-20261014-evidence.json`. Its native Qt
matrix passed **86** cases, including styled label fit. The full 250-story
catalog completed as 170 saved passes plus 80 resumed passes after PID 19332
was confirmed absent. Aggregate evidence retains `phase1_exit_code: null` in
`tmp/catalog-ui-acceptance-final-20261014/evidence.json`. It does not claim a
known successful exit for the interrupted original process.

The next negative UI pass found BUG-235/236. Baseline: **12 failed / 12 passed**;
first repaired Learn group: **24 passed**. Exact lesson topics now survive quota
storage refusal, failure and cancellation without restoring an older Solve draft
or overwriting newer input. Empty cancellation preserves a previous lesson or
returns to Empty; partial-video cancellation keeps its route. The current
expanded group also covers duplicate rejection/allowance and deleted Solve
wrappers. F145/F150 still need their complete lesson behaviour acceptance.

These new application/runner changes invalidate the earlier eight native UI
acceptances until renewed. The native runner now includes the Learn module and
binds actual Learn failure/draft cases to F84 as well as Solve failures. The
719/86/250 checkpoint is historical for those later changes. Issue history now
contains **193** distinct IDs. Final renewed runs and canonical counts follow
after their actual terminal results.

The related signal/overlap pass added BUG-237/238. Its baseline failed all
**15** cases: late/cancelled/queued old-lesson events, a deleted lesson wrapper,
and Solve overlapping lesson cleanup. The repaired Learn module passed **45**
cases; combined with the acceptance-policy guards it passed **167**. Native
F84 acceptance now covers actual Learn failure and late data as well as Solve;
F19 additionally covers Solve refusing unfinished lesson cleanup. Current issue
history has **195** distinct IDs. The final source freeze follows these fixes.

## Command-bar lifecycle checkpoint

### Reviewed native acceptance and layout follow-up

The earlier shared-host popup problem is resolved by running the actual owned
QMenu scenario in a fresh Qt process. Its complete broad regression finished
with **617 passed**, one upstream warning, exit 0 and unchanged source hashes:
`tmp/commandbar-final3-full-20261014-evidence.json`. The final published nine-story
focus also passed. These runs precede the acceptance/layout follow-up below.

Eight reviewed matrices now exist for F12/F13/F14/F15/F17/F19/F20/F84. They bind
the current story contract, implementation/runner hashes, native Windows Qt
platform and actual JUnit report. The first **83-case native matrix passed** in
`tmp/feature-acceptance/commandbar-f2e016f5ef/pytest.log`; fourteen catalog stories,
including renewal of the five startup matrices, passed with unchanged inputs in
`tmp/commandbar-acceptance-focus-20261014-evidence.json`. The acceptance-policy
group passed **122** synthetic guard tests. Synthetic policy fixtures never
become application acceptance evidence.

This strengthens all ten menu selections/dismissal/focus, saved l/m/h quality
on a new window, all known/unknown failure contexts in three languages, actual
Details/retry paths with and without an existing result, frozen terminal elapsed
time, localized running stages, three-language duplicate quota/progress guards,
independent signal disconnection and real QThread cleanup. UI fixtures have no
API key and stub only background Ollama discovery and pipeline data; actual
widgets and the cancellation QThread execute. No solver/provider/cloud result
is inferred.

Visual inspection then found **BUG-234**, clipped quality captions. Native
measurements showed 61 logical pixels of text inside a 60-pixel edit field;
offscreen label-fit tests failed two of three locale cases. AdjustToContents
alone still failed; the final minimum width 120 with content adjustment passed
all three cases. The stronger native matrix now includes those three cases and
explicit error-banner content assertions. Prior eight-story acceptance is
automatically invalidated by the changed source/contract until renewed.

The full current runs are `commandbar-acceptance-final-full-20261014` and
`catalog-ui-acceptance-final-20261014`. Their terminal results must be recorded
before the renewed eight stories can be published as accepted. The workbook
currently retains five complete startup stories and 245 open behaviours while
that renewal executes. Current issue history contains **191** distinct IDs.

The 250-story catalog before this follow-up completed as 248 saved successful
checks plus an owned F249/F250 continuation after the original PID was confirmed
absent. Its aggregate evidence preserves `phase1_exit_code: null`; it is not
claimed as one uninterrupted process with exit 0.

### Earlier lifecycle investigation

The next batch exercises F12–F20 and F84 through real Qt controls and worker
connections. Actual baseline: 9 failed / 14 passed. BUG-229 preserves the exact
question on quota storage refusal/cancellation/failure; BUG-230 freezes cancelled
timeline state and rejects late worker data; BUG-231 repairs partial disconnect
and deleted-QThread restart. BUG-232 corrects inventory expectations for quality
fallback and cancellation cleanup. Native observation also exposed BUG-233:
English failure context in Russian/Kazakh UI. Its separate baseline failed 8 of
9 cases before localization; original technical diagnostics remain unchanged.

The expanded command-bar matrix now has 48 cases: Return/Run/Ctrl+Return and
quality handoff in kk/ru/en; real QThread cleanup through Cancel, Escape and the
stepper hit target; error/draft recovery; timeline reset; duplicate quota guard;
signal ownership; actual popup selection/dismissal; localized failure context.
The combined legacy batch and command-bar group passed **85**, one upstream
warning, in `tmp/commandbar-shared-stable-20261014.log` (exit 0).

Failed repeats are retained. The first broad run was **1 failed / 599 passed**:
a popup observation failed under the shared QApplication. The test now targets
its owned QMenu and keeps the test QApplication alive across window closes,
retaining the actual nested menu event loop and keyboard actions. A long-TEMP
helper render failed separately; compact-TEMP repeated the unchanged render test
successfully. Neither helper failure is presented as an application fix.

Final runs are tracked as `commandbar-final2-full-20261014`,
`catalog-commandbar-final-20261014` and `commandbar-native-final-proof-20261014`.
Their actual terminal results will be recorded below after completion. During
publication, acceptance is re-evaluated against current sources; the earlier
569/250 checkpoint does not certify these UI changes. Current documented issue
history contains **190** distinct IDs. No complete user-story acceptance is
inferred from controlled pipeline output or screenshots alone.

## Latest startup checkpoint

Current worktree: HEAD c4ffb34 plus the preserved changes below. BUG-227 fixes
the misleading diagnosis for a broken Qt runtime. BUG-228 rejects invalid Qwen
roots/field types rather than inventing string model/URL values. Baseline:
6 failed / 25 passed. Expanded startup matrix: 46 passed. The startup, settings,
watchdog, fixture, CLI and acceptance-policy group passed **144**.

Eleven related catalog checks then passed with unchanged recorded inputs in
`tmp/startup-contract-final-focus-20261014-evidence.json`. Five stories now have
reviewed complete matrices: F03 prompt routing, F04 watchdog control, F05 optional
Qt diagnostics, F09 Qwen opt-in and F11 default paths. The remaining **245**
stories are still open. F03 uses actual CLI/main/smoke request construction with
controlled pipeline results; this is not solver or cloud acceptance. F05 executes
the actual module entry point with missing/broken Qt imports. Qwen uses owned
configuration and credentials in 33 fresh processes.

The current canonical publication has 250 stories, 92 software FIXED and 158
PASS, with five full behaviours and 245 PARTIAL. Its pre-run integrity check
passed. The full post-fix regression and catalog are recorded separately as
`tmp/startup-contracts-full-20261014` and
`tmp/catalog-startup-contracts-20261014/`. The historical checkpoints below keep
their original counts; they do not certify these later changes.

The first broad startup runs are terminal: **569 pytest cases passed** (one
upstream ChromaDB deprecation warning, 241.96 seconds) and **250/250 catalog
checks passed**. Both returned exit 0 with unchanged HEAD/source hashes; the
catalog merged its actual results. Current error history has **185** distinct
IDs. These software results do not close the remaining 245 user behaviours.

Subsequent negative-case review strengthened the Qwen policy: malformed explicit
model/URL types reject the complete provider tuple, rather than retaining a key
with fallback settings. Four stricter cases failed against the intermediate
per-field repair (**4 failed / 42 passed**) before correction. The repaired
combined group passed **144**; eleven focused stories passed again with unchanged
inputs. Debug-level and file logs are checked for owned credential sentinels.
Final broad validation for this stricter policy uses the separate
`startup-provider-final-full-20261014` and
`catalog-startup-provider-final-20261014` run names; the earlier 569 checkpoint
does not certify that later change.

The final stricter-policy runs are now terminal: **569 pytest cases passed**
(one upstream warning, 237.31 seconds), and **250/250 catalog checks passed**.
Both returned exit 0 with unchanged HEAD/source hashes. Evidence:
`tmp/startup-provider-final-full-20261014-evidence.json` and
`tmp/catalog-startup-provider-final-20261014/evidence.json`. Current complete
acceptance remains F03/F04/F05/F09/F11; 245 stories remain open.

Next inspection target: command-bar and worker control, F12–F20. In particular,
F15's text still says cancellation resets idle immediately, while current
`_cancel_pipeline()` deliberately keeps busy until `_on_worker_finished()`.
F14's failure text also needs to distinguish an unselected combo (Draft fallback)
from an unknown programmatic flag (preserves the selection). These are pending
inventory corrections and their UI paths still require complete acceptance.
Initial source-bound probes confirmed both conflicts in
`tmp/commandbar-inventory-probe-20261014.json`: the actual combo preserves High
for unknown text/flags and returns Draft only when unselected; actual cancel/
finished methods keep busy until completion. The latter uses owned control/
worker interfaces, not real QThread termination or native UI acceptance. A
first scratch helper incorrectly discarded PATH before importing Qt; its fixed
owned repeat passed. This is helper history, not an application failure.

## Current revision: c4ffb34

An external checkout/merge replaced the previous worktree during the audit.
The authoritative branch is `codex/stabilize-current-branch`, HEAD `c4ffb34`.
Its catalog contains 250 stories; earlier 252-story and 633-test evidence belongs
to the prior revision and cannot certify this one. Current user changes and
artifacts are preserved; deleted lesson features have not been silently restored.

BUG-220–223 address corrupt-encoding startup failures, unsafe read/modify/write
of unreadable settings, lost Settings drafts/unhandled save errors, and unstable
default paths. The current branch's baseline failed 4 data cases and 12 UI cases.
The repaired group passed **44**; 7 related catalog checks passed without changes
during the run. The source-bound result is
`tmp/current-settings-catalog-20261014/evidence.json`.

Full behaviour acceptance can now be represented explicitly. F11 uses twelve
fresh-process cases against the actual default/settings functions, with a
bound story contract, scenario/requirement coverage, implementation and runner
hashes. A changed source, missing/failed case, changed evidence or unfinished
catalog retest invalidates acceptance. Policy tests exercise these refusals.
F04 now has ten executed watchdog cases, including real owned child processes
and the actual batch entry point from a foreign Unicode/spaced directory.
Logging refusals, spawn failure, backoff growth/cap/reset and both interrupt
locations are covered. Its evidence binds the watchdog, batch file, console
helper, test implementation and catalog runner. This closes F04 and F11 only;
it does not certify the native application's GUI or crash safety. No other
story is promoted by inference.

`tools/tracker_integrity_audit.py --complete-behaviours` adds the full-goal gate:
it rejects incomplete story acceptance even when scoped software checks pass.
The canonical workbook remains the single status view; JSON files are supporting
evidence and the CSV is its generated mirror.

Current complete regression/catalog runs will be recorded separately as
`tmp/stabilize-settings-full-20261014.log` and
`tmp/catalog-stabilize-settings-20261014/`. They use isolated provider/data
environments and bind both HEAD and source hashes. A catalog whose inputs change
is retained as history and is not merged into the current tracker.

The first such runs are now terminal: pytest **470 passed / 1 failed**, catalog
**248/250**, both with unchanged source snapshots. The batch test depended on
cached video; its replacement actually renders and decodes its own MP4. The
teacher-review failure came from long reused fixture paths, now compact and
fresh. Both original scenarios pass targeted reruns. Tracker F165 read during
publication; final catalog execution will begin only after publication/parity
checks finish. A direct-CLI import issue introduced by the evidence integration
was repaired and tested from a foreign working directory.

The next permitted full run passed **476** with unchanged inputs. Its catalog
finished **248/250**: F230/F233 used a third fixture adapter still embedding
long function names. An expanded path regression reproduced the missed case;
all three adapters now have compact fresh paths. Original F230/F233 assertions
pass after that fix. These broad results precede the subsequent watchdog and
acceptance changes and are not final-current-source certification.

Watchdog baseline: **3 failed / 7 passed**, preserving the original log. The
fixes address import-time logging failures and Ctrl+C during backoff. The
watchdog/path/CLI/acceptance-policy group passed **53**. Focused F04/F133/F215/
F230/F233 all passed. F04/F11/F133/F215 were then rerun with unchanged inputs in
`tmp/watchdog-defaults-proof-20261014-evidence.json`.

Current defect history has **183 distinct IDs**. The canonical table remains
250 stories; F04 and F11 have complete acceptance, with **248** still open.
Neither scoped software success nor these two closed contracts complete the
overall goal. Broad post-fix runs are tracked separately under the final4 names.

The final4 full regression has now completed **499 passed**, one upstream
ChromaDB deprecation warning, exit 0, in 226.39 seconds. Its evidence includes
the root watchdog and batch file as well as the application/tests/tools;
HEAD and all recorded source hashes were unchanged. The separate final4 catalog
also completed **250/250**, exit 0, with no failed IDs and unchanged source
hashes; it merged its actual results into the canonical result data. Evidence:
`tmp/catalog-stabilize-settings-final4-20261014/evidence.json`. This is a scoped
software/catalog pass, not acceptance of the remaining 248 complete stories.

Initial acceptance candidates were F03/F05. Eight fresh-process CLI probes passed
in `tmp/cli-stories-initial-20261014.json`: default/Unicode parsing, exact
dispatch of default/Unicode/empty prompts, normal invalid-flag exit, and the
actual module entry point with PyQt imports blocked. Dispatch deliberately
uses a controlled async callback and does not certify the smoke pipeline.
These probes are not yet registered as complete acceptance and do not promote
either story in the workbook.

Final publication parity passed with no issues: 250 rows/stories/results/tests,
91 software FIXED and 159 PASS, two complete behaviours and 248 PARTIAL. The
full-goal gate intentionally exits 1 for those 248 open stories. The current
surface check covers 90/90 detected surfaces, including 19 locale maps; it is
an inventory check, not proof of all user behaviour. The canonical workbook
retains its Features/Summary sheets, native Features table A1:U251, D2 frozen
panes and typed UTC check dates. Changed status/acceptance ranges were rendered
and visually inspected. Final reports: `tmp/integrity-final4-20261014.json`,
`tmp/complete-behaviours-final4-20261014.json` and
`tmp/surfaces-final4-20261014.json`.

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
