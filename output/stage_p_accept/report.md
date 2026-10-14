# Stage P — acceptance matrix (§15), automatic part

- **settings**: passed — load->reload identical (render_mode=auto, tts_voice=en-US-AndrewMultilingualNeural, narration=False)
- **cloud**: passed — 24/24 unique cloud job_ids (workflow v7), all 1080p30 h264, drift<0.6, attempts=1; manifest<->params job match
- **isolation**: passed — 23/24 distinct segment hashes + 24 distinct job_ids + per-segment frames; identical pairs [['ru/B2', 'kk/B2']] have identical source texts (deterministic renders)
- **cache**: passed — versions.json fingerprints reproduce from current inputs (canonical/shots/fragments/durations/mux_plan); 135/135 clips present
- **resume**: passed — stage_m_final reuses ready mp4s (no re-render of finished segments); M2/M3 ran 24/24 first-attempt so no interrupt occurred in M (LIMIT: no controlled interrupt/continue drill was executed in M)
- **physics**: passed — verify_g (v=14, s=32, pause s=25, 3-way recompute) + verify_h (H1-H5 keys, decoy formulas) both rc=0 on current inputs
- **sources**: passed — registry cites real files with cited pages inside counts: {'zak9': 272, 'zak10': 336, 'fbs': 59, 'tc3': 37}; zak9/zak10/fbs/tc3/nct-ru/nct-en evidence ids present
- **translations**: passed — verify_i rc=0 (caption digit parity, unit parity, sense anchors, practice closed number set, no ASCII digits in voiceovers) (LIMIT: pending_teacher_review: kk/ru/en wording not teacher-reviewed)
- **sync**: passed — 45 frags x3 langs inside block windows, no overlaps; SRT 45/45 cues per lang, last-cue ends {'ru': (45, 298), 'kk': (45, 299), 'en': (45, 298)}; M5 per-fragment speech presence was 45/45 x3 (stage_m_assemble gate)
- **video**: passed — 3 lessons 1920x1080@30 h264 + aac, full decode clean: {'ru': '300.0s vframes=8999 aframes=14061', 'kk': '300.0s vframes=8999 aframes=14061', 'en': '300.0s vframes=8999 aframes=14061'} (LIMIT: human full-viewing of each lesson still pending)
- **audio**: passed — aac stream decodes to end in all 3 lessons; M5 first-speech 0.33s, presence 45/45 per lang (stage_m_assemble gate) (LIMIT: human listening (pronunciation/clarity) still pending)
- **pdf**: passed — 3 PDFs 4pp each, extractable text+figures+version stamp: {'ru': '4pp 4643ch figs=2', 'kk': '4pp 4650ch figs=2', 'en': '4pp 4706ch figs=2'}; xelatex logs rc=0 (verify_report.md) (LIMIT: human page viewing + teacher wording review still pending)
- **app**: passed — frozen v2 content matches canonical v2 (8ch/5q x3), media 9/9 present, offsets == measured cumsum; UI route re-verified by O tests + E2E rerun below
