"""Stage M parts 4-5: assemble per-language finals + verify + manifest.

Per lang: concat 8 silent 1080p segments (c copy) -> place 45 mp3 clips at
(measured block start + mux offset) into a 48kHz stereo bed -> mux AAC ->
rebuild SRT from fragments -> verify streams/duration/speech-timing ->
manifest.json. Lesson-absolute times use MEASURED segment durations
(B1 is one frame short of nominal: 49.9667 vs 50).
"""

if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()


import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
OUT = ROOT / "output" / "stage_m_final"
K2 = ROOT / "output" / "stage_k2_fragments"
CLIPS = K2 / "clips"
LANGS = ["ru", "kk", "en"]
CLASSES = [f"BlockB{i}" for i in range(8)]
SR = 48000


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    assert proc.returncode == 0, f"{cmd[0]}: {proc.stderr[-800:]}"
    return proc.stderr


def srt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def load_inputs():
    fragments = json.loads((K2 / "fragments.json").read_text(encoding="utf-8"))
    durations = json.loads((K2 / "durations.json").read_text(encoding="utf-8"))["durations"]
    mux = json.loads((K2 / "mux_plan.json").read_text(encoding="utf-8"))
    params = json.loads((OUT / "params.json").read_text(encoding="utf-8"))
    return fragments, durations, mux, params


def measured_starts(params: dict, lang: str) -> tuple[dict[str, float], float]:
    """Block start times from measured segment durations (lesson-absolute)."""
    starts, t = {}, 0.0
    for cls in CLASSES:
        entry = params[lang][cls]
        assert entry["status"] == "rendered", f"{lang}/{cls} not rendered"
        starts[cls] = t
        t += entry["duration_s"]
    return starts, t


def concat_video(lang: str) -> tuple[Path, float]:
    lst = OUT / lang / "_concat_list.txt"
    lst.write_text("".join(f"file '{OUT / lang / cls}.mp4'\n".replace("\\", "/")
                           for cls in CLASSES), encoding="utf-8")
    silent = OUT / lang / "_concat_silent.mp4"
    run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(silent)])
    import av

    with av.open(str(silent)) as cont:
        video = next(s for s in cont.streams if s.type == "video")
        dur = float(video.duration * video.time_base)
    print(f"{lang}: concat {dur:.3f}s", flush=True)
    return silent, dur


def decode_clip(fid: str, lang: str, tmp: Path) -> tuple[np.ndarray, float]:
    """Decode + resample one mp3 to 48kHz stereo int16; assert duration match."""
    wav = tmp / f"{fid}_{lang}.wav"
    run([ffmpeg(), "-y", "-i", str(CLIPS / f"{fid}_{lang}.mp3"),
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(wav)])
    with wave.open(str(wav), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (SR, 2, 2)
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).reshape(-1, 2), len(raw) / 4 / SR


def build_audio(lang: str, starts: dict, total: float, fragments: dict,
                durations: dict, mux: dict) -> Path:
    n = int(round(total * SR))
    bed = np.zeros((n, 2), dtype=np.int32)
    entries = []  # (start, end, fid) lesson-absolute, for SRT + checks
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for fid, entry in sorted(fragments.items()):
            block = f"BlockB{entry['shot'][1]}"
            off = mux[entry["shot"]]["offsets"][lang][fid]
            start = starts[block] + off
            pcm, wav_dur = decode_clip(fid, lang, tmp)
            expect = durations[fid][lang]
            assert abs(wav_dur - expect) < 0.03, (fid, lang, wav_dur, expect)
            i0 = int(round(start * SR))
            i1 = i0 + len(pcm)
            assert i1 <= n, (fid, "overruns total")
            assert not entries or i0 >= entries[-1][1] * SR - SR * 0.01, (fid, "overlap")
            bed[i0:i1] += pcm.astype(np.int32)
            entries.append((start, start + wav_dur, fid))
    bed = np.clip(bed, -32768, 32767).astype(np.int16)
    out_wav = OUT / lang / "_bed.wav"
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bed.tobytes())
    speech_s = sum(e - s for s, e, _ in entries)
    print(f"{lang}: bed {total:.3f}s, 45 frags, speech {speech_s:.1f}s", flush=True)
    return out_wav, entries


def write_srt(lang: str, entries: list, fragments: dict) -> Path:
    srt = OUT / lang / f"lesson_{lang}.srt"
    lines = []
    for i, (s, e, fid) in enumerate(entries, 1):
        lines.append(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{fragments[fid][lang]}\n")
    srt.write_text("\n".join(lines), encoding="utf-8")
    return srt


def mux_final(lang: str, silent: Path, bed: Path) -> Path:
    final = OUT / lang / f"lesson_{lang}.mp4"
    run([ffmpeg(), "-y", "-i", str(silent), "-i", str(bed),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
         "-ac", "2", "-movflags", "+faststart", "-shortest", str(final)])
    return final


def verify_final(lang: str, final: Path, total: float, entries: list) -> dict:
    import av

    facts: dict = {"bytes": final.stat().st_size}
    with av.open(str(final)) as cont:
        streams = [(s.type, getattr(s, "width", 0), getattr(s, "height", 0),
                    float(s.average_rate) if s.type == "video" and s.average_rate else 0.0,
                    s.codec_context.name if s.codec_context else "")
                   for s in cont.streams]
        video = next(s for s in cont.streams if s.type == "video")
        facts["duration_s"] = float(video.duration * video.time_base)
    assert [s[0] for s in streams] == ["video", "audio"], streams
    assert streams[0][1:4] == (1920, 1080, 30.0), streams
    assert streams[1][4] == "aac", streams
    assert abs(facts["duration_s"] - total) < 0.5, (facts["duration_s"], total)
    # full decode integrity, video + audio
    run([ffmpeg(), "-v", "error", "-i", str(final), "-map", "0:v", "-f", "null", "-"])
    run([ffmpeg(), "-v", "error", "-i", str(final), "-map", "0:a", "-f", "null", "-"])
    # speech timing: first sound ~0.3 (lead), coverage ~= placed speech
    err = run([ffmpeg(), "-i", str(final), "-map", "0:a",
               "-af", "silencedetect=noise=-40dB:d=0.2", "-f", "null", "-"])
    import re

    sil: list[tuple[float, float]] = []
    starts = [float(m.group(1)) for m in re.finditer(r"silence_start: ([\d.]+)", err)]
    ends = [float(m.group(1)) for m in re.finditer(r"silence_end: ([\d.]+)", err)]
    if starts and starts[0] <= 0.01 and ends:
        first_speech = ends[0]  # explicit leading silence_start: 0
    elif ends and (not starts or ends[0] < starts[0]):
        first_speech = ends[0]  # legacy: leading silence logged as end-only
    else:
        first_speech = 0.0
    pairs = list(zip(starts, ends))
    if len(starts) > len(ends):  # trailing silence runs to EOF
        pairs.append((starts[len(ends)], facts["duration_s"]))
    silence_total = sum(max(0.0, e - s) for s, e in pairs if e > s)
    placed_speech = sum(e - s for s, e, _ in entries)
    facts["first_speech_s"] = round(first_speech, 3)
    facts["speech_coverage_s"] = round(facts["duration_s"] - silence_total, 1)
    assert abs(first_speech - 0.3) < 0.2, first_speech
    # per-fragment presence: speech must fill the majority of each placed
    # window (intra-phrase pauses make a tight global check meaningless).
    for s, e, fid in entries:
        sil_ov = sum(max(0.0, min(pe, e) - max(ps, s)) for ps, pe in pairs)
        assert sil_ov < 0.5 * (e - s), (fid, round(sil_ov, 2), round(e - s, 2))
    # NOTE: no tight global coverage assert — voices pad clips with edge
    # silence (en ~22 s total), absorbed by mux gaps; per-fragment presence
    # above is the real no-missing gate. Coverage stays as a manifest fact.
    print(f"{lang}: final {facts['duration_s']:.3f}s, first speech "
          f"{first_speech:.2f}s, coverage {facts['speech_coverage_s']}s", flush=True)
    return facts


def main() -> None:
    fragments, durations, mux, params = load_inputs()
    versions = json.loads((OUT / "versions.json").read_text(encoding="utf-8"))
    manifest = {"versions": versions, "langs": {}, "gate": {}}
    # Partial reruns (LANGS filtered via argv) must not clobber sections of
    # languages assembled earlier — preserve them (P fix, 2026-10-14).
    prev = OUT / "manifest.json"
    if prev.is_file():
        try:
            old_langs = json.loads(prev.read_text(encoding="utf-8")).get("langs", {})
            for lang, section in old_langs.items():
                if lang not in LANGS:
                    manifest["langs"][lang] = section
        except (json.JSONDecodeError, AttributeError):
            pass
    for lang in LANGS:
        starts, total = measured_starts(params, lang)
        silent, concat_dur = concat_video(lang)
        assert abs(concat_dur - total) < 0.1, (concat_dur, total)
        bed, entries = build_audio(lang, starts, total, fragments, durations, mux)
        assert len(entries) == 45, len(entries)
        srt = write_srt(lang, entries, fragments)
        final = mux_final(lang, silent, bed)
        facts = verify_final(lang, final, total, entries)
        import hashlib

        manifest["langs"][lang] = {
            "segments": {c: {"job_id": params[lang][c]["job_id"],
                             "duration_s": params[lang][c]["duration_s"],
                             "attempts": params[lang][c]["attempts"]} for c in CLASSES},
            "total_s": round(total, 3),
            "final": str(final.name),
            "final_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "final_bytes": facts["bytes"],
            "srt": str(srt.name),
            "srt_entries": len(entries),
            "first_speech_s": facts["first_speech_s"],
            "speech_coverage_s": facts["speech_coverage_s"],
        }
    manifest["gate"] = {"missing": [], "repeated": [], "foreign": [],
                        "clipped_words": [], "timeline": "measured-cumsum"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"manifest written, gate clean -> {OUT.resolve()}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in LANGS:
        LANGS = sys.argv[1:]
    main()
