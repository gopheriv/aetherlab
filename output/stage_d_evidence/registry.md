# Stage D — evidence registry: Равноускоренное прямолинейное движение

Date: 2026-10-12. Topic: uniformly accelerated rectilinear motion, beginner 10–11 grade.
Rule: facts + short term-level quotes only. No textbook passages, figures, or
end-of-chapter exercises are reproduced (see docs/ENT_PHYSICS_SOURCES.md).

## Sources

| id | title | lang | file (C:\Users\sunak\Projects\References\) | sha16 | pdf pp. | printed pp. | role | status |
|----|-------|------|--------------------------------------------|-------|---------|-------------|------|--------|
| zak9 | Физика, Закирова, 9 сынып | kk | Физика Закирова 9.pdf | 1a903a3c6ea8f8a7 | 19–29 | 19–29 | definitions, derivations, sign rules, problem algorithm | used |
| zak10 | Физика, Закирова, 10 ЖМ | kk | Физика Закирова 10 ЖМ.pdf | cc39b02f972aff31 | 15–18, 20 | 15–18, 20 | formula table, graph table, area proofs, 1:3:5 rule | used |
| zak11 | Физика, Закирова, 11 ЖМ | kk | Физика Закирова 11 ЖМ.pdf | 839d5fe4bdfc9cc1 | 8–10 | 8–10 | notation cross-check only (harmonic oscillations; no § on this topic) | notation-only |
| fbs | Sailaubaev formula collection | kk | FBS (1).pdf | 2e2bdf3e229aa280 | 6–7 | 6–7 | formula-set + kk-term cross-check | used |
| f369 | 369 формула | kk | 369 формула.pdf | 0a8f1493abc7959a | 6–7 | 6–7 | cross-check ONLY — redistribution prohibited, no excerpts | restricted |
| tc3 | Testcenter sample collection 3 | kk | Testcenter -3.pdf | 966d33a26005cb58 | 1–2, 37 | n/a (scan) | ENT-format provenance: Q1 v–t stem + key | used, adapted-only |
| nct-ru | NCT official physics sample variant (web) | ru | https://new.testcenter.kz/wp-content/uploads/2024/12/obr_var_test_02.pdf | fetched 2026-10-12 | n/a | n/a | ru term grounding | used |
| nct-en | NCT official physics sample variant (web) | en | https://new.testcenter.kz/wp-content/uploads/2025/06/PHYSICS.pdf | fetched 2026-10-12 | n/a | n/a | en term grounding | used |

Page numbers verified: printed headers match pdf indices for all cited pages
(e.g. header "15" on pdf-p15 of zak10, "19" on pdf-p19 of zak9).

## Canonical facts (all present in zak9 + zak10, cross-checked fbs/f369)

Definitions (kk terms verbatim, short):
- теңайнымалы қозғалыс — motion with velocity changing by equal amounts in
  equal time intervals (umbrella term; zak9 p.19, zak10 p.15).
- теңүдемелі қозғалыс (ТҮҚ) — a vector aligned with v, |a| = const (zak9 p.21).
- теңкемімелі қозғалыс (ТКҚ) — a vector opposite to v, |a| = const (zak9 p.21).
- үдеу — vector quantity of velocity-change rate, a = Δv/Δt (zak9 p.20).
- лездік жылдамдық — limit of Δs/Δt as Δt → 0 (zak9 pp.19–20).
- орташа жылдамдық — arithmetic mean of v0 and v when direction is unchanged
  (zak9 pp.23, 26).
- орын ауыстыру vs жүрілген жол — directed segment vs travelled path;
  distinct quantities (zak10 p.15, fbs p.6).
- қозғалыс заңы/теңдеуі — x(t), position at any instant (zak9 p.28, zak10 p.16).

Formulas (rectilinear, projection form):
- a = (v − v0)/t; v = v0 ± at (ТҮҚ +, ТКҚ −); s = v0·t ± a·t²/2;
  s = (v + v0)·t/2; v² = v0² ± 2as; x = x0 + v0·t + a·t²/2 (zak9 p.29 table,
  zak10 p.16 table, fbs p.6, f369 p.6 set-match).
- v0 = 0 from rest; v = 0 at stop / max height (fbs p.6, f369 p.6).
- v0 = 0 special case: v = at, s = at²/2 (zak9 p.22, zak10 p.17).
- Free fall is a special case with a → g (zak10 p.16) — lesson mentions only.

Graph rules:
- v–t slope (tan α) equals acceleration; steeper → larger |a| (zak10 p.17,
  zak9 p.23). a = const is a horizontal line (zak9 p.22).
- Area under v–t numerically equals displacement: triangle at²/2 (v0 = 0),
  trapezoid v0·t + at²/2 (zak10 p.17, zak9 p.22).
- Area under a–t numerically equals velocity (zak9 p.22).
- s–t is a parabola branch; shape follows the sign of ax (zak9 p.29).
- v–t crossing the t-axis marks the stopping instant (zak9 p.23).

Number rules and method:
- Equal-interval displacements from rest: s1 : s12 : s23 … = 1 : 3 : 5 …
  (zak10 p.17).
- 9-step kinematics problem algorithm: SI units → sketch with vectors →
  projection equations → axis choice → modulus form with signs → solve →
  units → answer (zak9 p.28). Shapes Stage F/H pedagogy.
- Units: м/с, м/с², м, с (zak9 p.21: [a] = 1 м/с² derivation task).

## Terminology kk / ru / en

kk from zak9/zak10/fbs (page-cited); ru grounded in nct-ru where present,
else standard school term (†); en grounded in nct-en where present, else
standard (†). Teacher review still required before exam-ready claims.

| kk (source) | ru | en |
|-------------|----|----|
| теңайнымалы қозғалыс (zak9 p.19) | равнопеременное движение † | uniformly varied motion † |
| теңүдемелі қозғалыс (zak9 p.21) | равноускоренное движение † | uniformly accelerated motion / "accelerates uniformly" (nct-en Q26–30) |
| теңкемімелі қозғалыс (zak9 p.21) | равнозамедленное движение † | uniformly decelerated motion † |
| үдеу (zak9 p.20) | ускорение (nct-ru Q1) | acceleration (nct-en Q16, Q26) |
| жылдамдық (zak9 p.19) | скорость (nct-ru Q1, Q36) | velocity (nct-en Q26–30); speed for modulus (nct-en Q8) |
| лездік жылдамдық (zak9 p.19) | мгновенная скорость † | instantaneous velocity † |
| орташа жылдамдық (zak9 p.19) | средняя скорость † | average velocity † |
| бастапқы жылдамдық (fbs p.6) | начальная скорость † | initial velocity † |
| соңғы жылдамдық (fbs p.6) | конечная скорость † | final velocity † |
| орын ауыстыру (zak10 p.15) | перемещение (nct-ru Q36) | displacement † |
| жүрілген жол (zak10 p.15) | пройденный путь † | distance of travel (nct-en Q28) |
| координата (zak9 p.25) | координата (nct-ru Q36) | coordinate † |
| қозғалыс заңы (zak9 p.28) | уравнение движения † | equation of motion † |
| еркін түсу / еркін түсу үдеуі (fbs p.7) | свободное падение † | free fall † |
| уақыт (fbs p.6) | время † | time † |

## Testcenter-3 Q1 provenance chain (closed)

- File p.1 header OCR: «Ұлттық тестілеу орталығының нұсқалық тест
  жинақтары-3» (collection claims NCT-sample status; official NCT status of
  this PDF itself is UNCHECKED → lesson uses adapted practice only, never
  presents items as official).
- Q1 stem OCR (tc3_p2.png, kaz, high confidence on text):
  «Суретте материялық нүктенің қозғалыс графигі берілген.
  Материялық нүктенің 4 с-тағы жолы» + options А) 13 м / В) 12 м / С) 9 м /
  D) 15 м.
- Graph type: v–t confirmed — vertical axis «м/с», horizontal ticks
  0 1 2 3 4 (300 dpi OCR, tc3_p2_q1.png); top tick «6».
- Key: p.37 letters row y=1230–1314 (2x coords). Q1 cell glyph correlates
  0.933 / 0.926 with two confident same-row В cells (conf 65/82), ≤0.20 with
  А/С cells → key letter В. Full-page OCR read Б (Б/В shape confusion);
  isolated psm-8 read РІ (tesseract split noise on one blob — column profile
  shows a single ink run). Evidence: key_q1_cell.png (+q2, q3),
  tc3_p37.png, scripts .qwen/tmp/key_cell.py, diag_cell.py, glyph_match.py.
- Physics cross-check: keyed answer 12 м is consistent with a v–t area over
  4 s (e.g. triangle ½·4·6); exact polyline shape NOT machine-verified —
  needs one human glance at tc3_p2.png before any pixel-level claim.
- Graph-points tiebreak (2026-10-12): the reference route's human visual check
  (content/ent/constant_acceleration_cloud_5min.json + ent_lesson_catalog
  verified_question_visual, both predating this stage) records polyline
  (0,0)-(1,4)-(3,4)-(4,0) with areas 2+8+2 = 12 = B. The 300dpi OCR top tick
  «6» is low-confidence noise: peak 6 gives 18 under a trapezoidal reading,
  which is not among the options; a triangle-peak-6 reading also yields 12,
  so the tiebreak rests on the human check. Residual: one human glance at
  tc3_p2.png to confirm peak 4.

## Coverage vs lesson needs

- Definitions, formulas, graph rules, units, sign conventions: covered by
  zak9 §3–4 + zak10 §3 (two independent textbooks) + fbs/f369 set-match.
- ENT format anchor: tc3 Q1 (v–t area problem with Kazakh stem) — format
  reference only; Stage H writes 5 ORIGINAL app exercises.
- Gaps: no Russian-language textbook in References (ru terms via nct-ru +
  standard, flagged †); official NCT status of tc3 unchecked; graph
  polyline pixels unverified; kk/en lesson wording needs teacher review
  (Stage I).
- Master-data note: lesson uses v0 = 2 м/с, a = 3 м/с², t = 4 с
  (v = 14, s = 32) per master prompt; reference route a = 1.5 stays out.
