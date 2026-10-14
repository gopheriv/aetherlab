"""Build one five-minute, trilingual UNT lesson with cloud-rendered visuals.

Only Manim scenes are dispatched to GitHub Actions. Local work is limited to
voice synthesis, muxing the returned cloud MP4 clips, subtitles, and validation.
Cloud mode is explicit: this tool never falls back to a local Manim render.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aetherlab.core.console import configure_utf8_stdio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTENT_PATH = ROOT / "content" / "ent" / "constant_acceleration_cloud_5min.json"
OUTPUT_DIR = ROOT / "output" / "video"
TMP_DIR = ROOT / "tmp" / "ent_acceleration_cloud_5min"
OUTPUT_PATH = OUTPUT_DIR / "physlab_ent_constant_acceleration_5min_trilingual.mp4"
LANGUAGES = ("kk", "ru", "en")
SEGMENT_SECONDS = (43, 43, 43, 43, 43, 43, 42)
QUALITY = "m"  # 720p on the GitHub render worker
FPS = 30

PALETTE = {
    "background": "#071923",
    "panel": "#102B3A",
    "teal": "#35D8C2",
    "amber": "#FFC857",
    "light": "#EDF4F7",
    "muted": "#91AAB8",
    "rose": "#FF7A90",
    "violet": "#A78BFA",
}


def _load_content() -> dict[str, Any]:
    payload = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    if int(payload.get("duration_seconds", 0)) != sum(SEGMENT_SECONDS):
        raise ValueError("The lesson content and video timeline must both total 300 seconds.")
    for language in LANGUAGES:
        sections = payload["languages"][language]["sections"]
        if len(sections) != len(SEGMENT_SECONDS):
            raise ValueError(f"{language} narration does not have one chunk per visual segment.")
    return payload


def _header_code(title: str) -> list[str]:
    return [
        'self.camera.background_color = "#071923"',
        'header = Text("PHYSLAB  |  UNT PHYSICS  |  KZ / RU / EN", font_size=18, color="#91AAB8")',
        'header.to_edge(UP, buff=0.3)',
        'rule = Line(LEFT * 6.5, RIGHT * 6.5, color="#25445A", stroke_width=2).shift(UP * 2.75)',
        'title = Text("' + title + '", font_size=34, color="#EDF4F7", weight="BOLD")',
        'title.next_to(rule, DOWN, buff=0.35)',
        'self.add(header, rule)',
        'self.play(FadeIn(title, shift=DOWN * 0.15), run_time=1)',
    ]


def _scene_actions() -> list[tuple[str, list[str]]]:
    """Hand-authored visual beats; all spoken content comes from the JSON."""
    teal, amber, light, muted, rose, violet = (
        PALETTE["teal"], PALETTE["amber"], PALETTE["light"],
        PALETTE["muted"], PALETTE["rose"], PALETTE["violet"],
    )
    return [
        ("ACCELERATION: A CHANGE IN SPEED", [
            f'road = Line(LEFT * 5.5 + DOWN * 0.65, RIGHT * 5.5 + DOWN * 0.65, color="{muted}", stroke_width=4)',
            f'bus = RoundedRectangle(width=1.3, height=0.58, corner_radius=0.12, fill_color="{teal}", fill_opacity=1, stroke_color="{teal}").move_to(LEFT * 4 + DOWN * 0.22)',
            f'wheel1 = Circle(radius=0.13, color="{light}", fill_opacity=1).move_to(bus.get_center() + LEFT * 0.35 + DOWN * 0.3)',
            f'wheel2 = Circle(radius=0.13, color="{light}", fill_opacity=1).move_to(bus.get_center() + RIGHT * 0.35 + DOWN * 0.3)',
            'speed = Text("v: 0  →  2  →  4  →  6 m/s", font_size=30, color="' + amber + '").shift(UP * 0.45)',
            'ticks = VGroup(*[Text(f"{i} s", font_size=20, color="' + muted + '").move_to(LEFT * 4.4 + RIGHT * (i * 1.8) + DOWN * 1.15) for i in range(4)])',
            f'accel = Text("same increase each second  →  constant a", font_size=25, color="{light}").shift(DOWN * 1.9)',
            'self.play(Write(speed), run_time=1)',
            'self.play(Create(road), FadeIn(bus), FadeIn(wheel1), FadeIn(wheel2), run_time=1)',
            'self.play(FadeIn(ticks), run_time=1)',
            'self.play(bus.animate.shift(RIGHT * 2), wheel1.animate.shift(RIGHT * 2), wheel2.animate.shift(RIGHT * 2), run_time=1)',
            'self.play(bus.animate.shift(RIGHT * 2), wheel1.animate.shift(RIGHT * 2), wheel2.animate.shift(RIGHT * 2), run_time=1)',
            'self.play(FadeIn(accel, shift=UP * 0.1), run_time=1)',
        ]),
        ("NAME THE QUANTITIES", [
            f'v0 = Text("v0  initial velocity", font_size=29, color="{teal}").move_to(UP * 1.2 + LEFT * 2.5)',
            f'v = Text("v  final velocity", font_size=29, color="{amber}").move_to(UP * 0.4 + LEFT * 2.5)',
            f'a = Text("a  үдеу (acceleration)", font_size=26, color="{rose}").move_to(DOWN * 0.4 + LEFT * 2.2)',
            f't = Text("t  time", font_size=29, color="{violet}").move_to(DOWN * 1.2 + LEFT * 2.5)',
            f's = Text("s  displacement (орын ауыстыру)", font_size=25, color="{light}").move_to(DOWN * 2.15 + LEFT * 0.5)',
            'axis = Arrow(RIGHT * 2.55 + UP * 1.35, RIGHT * 5.4 + UP * 1.35, color="' + teal + '", buff=0, stroke_width=4)',
            'marker = Dot(RIGHT * 2.55 + UP * 1.35, radius=0.09, color="' + amber + '")',
            'axis_label = Text("chosen positive direction", font_size=18, color="' + muted + '").move_to(RIGHT * 3.95 + UP * 0.98)',
            'units = Text("v: m/s   a: m/s²\\nt: s   s: m", font_size=23, color="' + amber + '").move_to(RIGHT * 3.8 + DOWN * 0.35)',
            'distance = Text("distance = full path", font_size=21, color="' + light + '").move_to(RIGHT * 3.7 + DOWN * 1.55)',
            'self.play(Write(v0), Write(axis_label), run_time=1)',
            'self.play(Write(v), Create(axis), marker.animate.move_to(axis.get_end()), run_time=1)',
            'self.play(Write(a), FadeIn(units), run_time=1)',
            'self.play(Write(t), FadeIn(distance), run_time=1)',
            'self.play(Write(s), run_time=1)',
        ]),
        ("CHOOSE THE MODEL", [
            f'condition = Text("straight line  +  constant acceleration", font_size=27, color="{teal}").shift(UP * 1.4)',
            f'eq1 = Text("v = v0 + a t", font_size=48, color="{light}").move_to(UP * 0.25)',
            f'eq2 = Text("s = v0 t + ½ a t²", font_size=43, color="{amber}").move_to(DOWN * 0.85)',
            f'axis = Text("a is signed along your chosen axis", font_size=25, color="{rose}").move_to(DOWN * 1.9)',
            'plus = Text("a > 0: velocity rises", font_size=19, color="' + muted + '").move_to(LEFT * 4.0 + UP * 0.35)',
            'minus = Text("a < 0: velocity falls", font_size=19, color="' + muted + '").move_to(RIGHT * 4.0 + UP * 0.35)',
            'self.play(FadeIn(condition), Write(eq1), run_time=1)',
            'self.play(eq1.animate.scale(1.06), run_time=1)',
            'self.play(Write(eq2), run_time=1)',
            'self.play(FadeIn(axis), run_time=1)',
            'self.play(FadeIn(plus), FadeIn(minus), run_time=1)',
        ]),
        ("WORKED EXAMPLE  |  KEEP ONE DATA SET", [
            f'given = Text("v0 = 2 m/s     a = 1.5 m/s²     t = 4 s", font_size=28, color="{muted}").shift(UP * 1.6)',
            f'vcalc = Text("v = 2 + 1.5 × 4", font_size=41, color="{light}").move_to(UP * 0.6)',
            f'vans = Text("v = 8 m/s", font_size=45, color="{teal}").move_to(DOWN * 0.15)',
            f'scalc = Text("s = 2 × 4 + ½ × 1.5 × 4²", font_size=34, color="{light}").move_to(DOWN * 1.05)',
            f'sans = Text("s = 8 + 12 = 20 m", font_size=41, color="{amber}").move_to(DOWN * 1.95)',
            'check = Text("check: average v = 5 m/s; 5 × 4 = 20 m", font_size=23, color="' + violet + '").move_to(DOWN * 2.65)',
            'self.play(FadeIn(given), run_time=1)',
            'self.play(Write(vcalc), run_time=1)',
            'self.play(TransformFromCopy(vcalc, vans), run_time=1)',
            'self.play(Write(scalc), run_time=1)',
            'self.play(Write(sans), run_time=1)',
            'self.play(FadeIn(check), run_time=1)',
        ]),
        ("READ A VELOCITY–TIME GRAPH", [
            f'axes = Axes(x_range=[0, 4, 1], y_range=[0, 10, 2], x_length=6.4, y_length=4.0, tips=False, axis_config={{"color": "{muted}", "include_numbers": True, "font_size": 20}}).shift(LEFT * 2.0 + DOWN * 0.1)',
            f'graph = Line(axes.c2p(0, 2), axes.c2p(4, 8), color="{teal}", stroke_width=5)',
            f'marker = Dot(axes.c2p(0, 2), radius=0.09, color="{rose}")',
            f'area_box = Polygon(axes.c2p(0, 0), axes.c2p(4, 0), axes.c2p(4, 2), axes.c2p(0, 2), fill_color="{amber}", fill_opacity=0.6, stroke_width=0)',
            f'area_tri = Polygon(axes.c2p(0, 2), axes.c2p(4, 2), axes.c2p(4, 8), fill_color="{teal}", fill_opacity=0.55, stroke_width=0)',
            f'slope = Text("slope = (8 − 2) / 4 = 1.5 m/s²", font_size=24, color="{light}").move_to(RIGHT * 3.4 + UP * 1.4)',
            f'areas = Text("area = 8 + 12 = 20 m", font_size=27, color="{amber}").move_to(RIGHT * 3.4 + DOWN * 0.1)',
            f'labels = Text("slope → a     area → displacement", font_size=21, color="{muted}").move_to(RIGHT * 3.1 + DOWN * 2.75)',
            'self.play(Create(axes), FadeIn(marker), run_time=1)',
            'self.play(FadeIn(area_box), Create(graph), marker.animate.move_to(graph.get_end()), run_time=1)',
            'self.play(FadeIn(area_tri), run_time=1)',
            'self.play(FadeIn(slope), run_time=1)',
            'self.play(FadeIn(areas), run_time=1)',
            'self.play(FadeIn(labels), run_time=1)',
        ]),
        ("UNT-STYLE GRAPH QUESTION", [
            f'axes = Axes(x_range=[0, 4, 1], y_range=[0, 5, 1], x_length=6.0, y_length=3.8, tips=False, axis_config={{"color": "{muted}", "include_numbers": True, "font_size": 18}}).shift(LEFT * 2.0 + DOWN * 0.15)',
            f'line1 = Line(axes.c2p(0, 0), axes.c2p(1, 4), color="{light}", stroke_width=5)',
            f'line2 = Line(axes.c2p(1, 4), axes.c2p(3, 4), color="{light}", stroke_width=5)',
            f'line3 = Line(axes.c2p(3, 4), axes.c2p(4, 0), color="{light}", stroke_width=5)',
            f'motion_path = VMobject().set_points_as_corners([axes.c2p(0, 0), axes.c2p(1, 4), axes.c2p(3, 4), axes.c2p(4, 0)])',
            f'marker = Dot(axes.c2p(0, 0), radius=0.09, color="{rose}")',
            f'tri1 = Polygon(axes.c2p(0, 0), axes.c2p(1, 0), axes.c2p(1, 4), fill_color="{amber}", fill_opacity=0.7, stroke_width=0)',
            f'rect = Polygon(axes.c2p(1, 0), axes.c2p(3, 0), axes.c2p(3, 4), axes.c2p(1, 4), fill_color="{teal}", fill_opacity=0.65, stroke_width=0)',
            f'tri2 = Polygon(axes.c2p(3, 0), axes.c2p(4, 0), axes.c2p(3, 4), fill_color="{violet}", fill_opacity=0.7, stroke_width=0)',
            f'ask = Text("Find distance during 0–4 s", font_size=25, color="{light}").move_to(RIGHT * 3.5 + UP * 1.5)',
            f'areas = Text("2 m  +  8 m  +  2 m", font_size=31, color="{amber}").move_to(RIGHT * 3.5 + UP * 0.45)',
            f'answer = Text("B  |  12 m", font_size=44, color="{teal}").move_to(RIGHT * 3.5 + DOWN * 0.6)',
            f'source = Text("Testcenter-3  •  task 1, p.2  •  key p.37", font_size=17, color="{muted}").move_to(DOWN * 3.1)',
            'self.play(Create(axes), FadeIn(ask), FadeIn(marker), run_time=1)',
            'self.play(FadeIn(tri1), Create(line1), run_time=1)',
            'self.play(FadeIn(rect), Create(line2), run_time=1)',
            'self.play(FadeIn(tri2), Create(line3), Succession(marker.animate.move_to(axes.c2p(1, 4)), marker.animate.move_to(axes.c2p(3, 4)), marker.animate.move_to(axes.c2p(4, 0))), run_time=1)',
            'self.play(Write(areas), run_time=1)',
            'self.play(Write(answer), FadeIn(source), run_time=1)',
        ]),
        ("YOUR TURN  |  THEN CHECK", [
            f'question = Text("18 m/s  →  6 m/s   in   4 s", font_size=39, color="{light}").shift(UP * 1.25)',
            f'prompt = Text("Find a and displacement s", font_size=28, color="{muted}").shift(UP * 0.35)',
            f'a_calc = Text("a = (6 − 18) / 4 = −3 m/s²", font_size=35, color="{rose}").move_to(DOWN * 0.55)',
            f's_calc = Text("average v = 12 m/s  →  s = 48 m", font_size=32, color="{teal}").move_to(DOWN * 1.5)',
            f'recap = Text("v = v0 + a t     |     s = v0 t + ½ a t²", font_size=30, color="{amber}").move_to(DOWN * 2.5)',
            f'check = Text("constant a  •  one axis  •  SI units", font_size=20, color="{muted}").move_to(DOWN * 3.1)',
            f'velocity_drop = Line(RIGHT * 4.7 + UP * 1.35, RIGHT * 4.7 + DOWN * 0.15, color="{rose}", stroke_width=5)',
            f'velocity_marker = Dot(RIGHT * 4.7 + UP * 1.35, radius=0.1, color="{amber}")',
            'self.play(FadeIn(question), Write(prompt), Create(velocity_drop), FadeIn(velocity_marker), run_time=1)',
            'self.play(velocity_marker.animate.move_to(velocity_drop.get_end()), Write(a_calc), run_time=1)',
            'self.play(Write(s_calc), run_time=1)',
            'self.play(Write(recap), run_time=1)',
            'self.play(FadeIn(check), run_time=1)',
        ]),
    ]


def _scene_code(index: int, seconds: int) -> str:
    title, lines = _scene_actions()[index]
    prelude = _header_code(title)
    play_lines = [line for line in lines if line.strip().startswith("self.play(")]
    if not play_lines:
        raise ValueError(f"Visual segment {index + 1} has no motion")
    # All animations are explicitly one second; the remaining duration is a
    # deliberate reading/thinking hold, keeping each cloud job below its budget.
    wait_seconds = seconds - sum(1 for line in [*prelude, *play_lines] if "self.play(" in line)
    if wait_seconds <= 0:
        raise ValueError(f"Visual segment {index + 1} has no hold time")
    actions = [line for line in lines if not line.strip().startswith("self.play(")]
    code = ["from manim import *", "", "class AetherLabScene(Scene):", "    def construct(self):"]
    code.extend("        " + line for line in prelude)
    # Definitions precede actions to keep the generated source easy to audit.
    definitions = [line for line in actions]
    code.extend("        " + line for line in definitions)
    code.extend("        " + line for line in play_lines)
    code.append(f"        self.wait({wait_seconds:.1f})")
    return "\n".join(code) + "\n"


def _estimated_word_marks(text: str, duration: float) -> list[dict]:
    """Make sentence-readable, duration-weighted caption timings for cached TTS."""
    words = text.split()
    weights = [max(1, len(word.strip(".,!?;:()\"'“”«»"))) for word in words]
    total = sum(weights) or 1
    cursor = 0.0
    marks = []
    for word, weight in zip(words, weights):
        span = duration * weight / total
        marks.append({"text": word, "start": cursor, "duration": span})
        cursor += span
    return marks


async def _synthesize_chunk(text: str, voice: str, output: Path, seconds: int) -> tuple[list[dict], float, int]:
    import av
    import edge_tts

    output.parent.mkdir(parents=True, exist_ok=True)
    # Reuse complete audio from an interrupted build. This avoids repeating
    # successful remote TTS requests if a later language/chapter loses DNS.
    if output.is_file():
        try:
            with av.open(str(output)) as container:
                cached_duration = (container.duration or 0) / 1_000_000
            if seconds * 0.65 <= cached_duration <= seconds - 0.35:
                return _estimated_word_marks(text, cached_duration), cached_duration, 0
        except Exception:  # noqa: BLE001 — discard unreadable cache and synthesize again
            pass

    for rate in (0, 5, 10, 15, 20, 25, 30):
        rate_text = f"+{rate}%"
        for attempt in range(3):
            parts: list[bytes] = []
            marks: list[dict] = []
            try:
                communicator = edge_tts.Communicate(
                    text, voice, rate=rate_text, boundary="WordBoundary"
                )
                async for event in communicator.stream():
                    if event.get("type") == "audio":
                        parts.append(event["data"])
                    elif event.get("type") == "WordBoundary":
                        marks.append({
                            "text": str(event.get("text", "")).strip(),
                            "start": int(event.get("offset", 0)) / 10_000_000,
                            "duration": int(event.get("duration", 0)) / 10_000_000,
                        })
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1 + attempt * 2)
                continue
            minimum_marks = max(8, int(len(text.split()) * 0.7))
            if not parts or len(marks) < minimum_marks:
                if attempt < 2:
                    await asyncio.sleep(1 + attempt * 2)
                    continue
                break
            candidate = output.with_suffix(".candidate.mp3")
            candidate.write_bytes(b"".join(parts))
            try:
                with av.open(str(candidate)) as container:
                    duration = (container.duration or 0) / 1_000_000
                if seconds * 0.65 <= duration <= seconds - 0.35:
                    candidate.replace(output)
                    return marks, duration, rate
            except Exception:
                candidate.unlink(missing_ok=True)
                raise
            candidate.unlink(missing_ok=True)
            break
    raise RuntimeError(
        f"Narration chunk could not be completed within its {seconds}s segment or returned incomplete word timings."
    )


def _write_srt(chunks: list[tuple[list[dict], float, float]], path: Path) -> int:
    rows: list[str] = []
    cue = 1
    for marks, duration, offset in chunks:
        valid = [m for m in marks if m["text"] and 0 <= m["start"] < duration]
        for start in range(0, len(valid), 7):
            group = valid[start:start + 7]
            if not group:
                continue
            begin = max(0.0, group[0]["start"])
            end = min(duration, max(begin + 0.25, group[-1]["start"] + group[-1]["duration"]))
            rows.extend([
                str(cue),
                f"{_clock(offset + begin)} --> {_clock(offset + end)}",
                " ".join(item["text"] for item in group),
                "",
            ])
            cue += 1
    if not rows:
        raise RuntimeError(f"No timed subtitle cues were generated for {path.name}")
    path.write_text("\ufeff" + "\n".join(rows), encoding="utf-8")
    return cue - 1


def _clock(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, left = divmod(milliseconds, 3_600_000)
    minutes, left = divmod(left, 60_000)
    whole, ms = divmod(left, 1000)
    return f"{hours:02}:{minutes:02}:{whole:02},{ms:03}"


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg command failed")[-3000:])


def _assemble_visuals(ffmpeg: str, videos: list[Path], target: Path) -> None:
    listing = TMP_DIR / "cloud-visuals.txt"
    listing.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in videos) + "\n",
        encoding="utf-8",
    )
    _run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-map", "0:v:0", "-c:v", "copy", "-an", "-movflags", "+faststart", str(target),
    ])


def _make_audio_track(ffmpeg: str, paths: list[Path], durations: tuple[int, ...], target: Path) -> None:
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for path in paths:
        args.extend(["-i", str(path)])
    filters = []
    refs = []
    for i, seconds in enumerate(durations):
        filters.append(
            f"[{i}:a]aresample=48000,apad=pad_dur={seconds},"
            f"atrim=duration={seconds},asetpts=PTS-STARTPTS[a{i}]"
        )
        refs.append(f"[a{i}]")
    filters.append("".join(refs) + f"concat=n={len(paths)}:v=0:a=1[aout]")
    args.extend([
        "-filter_complex", ";".join(filters), "-map", "[aout]",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(target),
    ])
    _run(args)


def _mux_multilingual(
    ffmpeg: str,
    visual: Path,
    audio_tracks: dict[str, Path],
    subtitles: dict[str, Path],
    target: Path,
) -> None:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(visual)]
    for lang in LANGUAGES:
        cmd.extend(["-i", str(audio_tracks[lang])])
    for lang in LANGUAGES:
        cmd.extend(["-i", str(subtitles[lang])])
    cmd.extend(["-map", "0:v:0"])
    cmd.extend(["-map", "1:a:0", "-map", "2:a:0", "-map", "3:a:0"])
    cmd.extend(["-map", "4:s:0", "-map", "5:s:0", "-map", "6:s:0"])
    cmd.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", "-movflags", "+faststart"])
    lang_codes = {"kk": "kaz", "ru": "rus", "en": "eng"}
    names = {"kk": "Kazakh", "ru": "Russian", "en": "English"}
    for i, lang in enumerate(LANGUAGES):
        cmd.extend([f"-metadata:s:a:{i}", f"language={lang_codes[lang]}"])
        cmd.extend([f"-metadata:s:a:{i}", f"title={names[lang]} voice"])
        cmd.extend(["-disposition:a:" + str(i), "default" if lang == "ru" else "0"])
        cmd.extend([f"-metadata:s:s:{i}", f"language={lang_codes[lang]}"])
        cmd.extend([f"-metadata:s:s:{i}", f"title={names[lang]} subtitles"])
        cmd.extend(["-disposition:s:" + str(i), "default" if lang == "ru" else "0"])
    cmd.extend(["-metadata", "title=PhysLab ENT Physics: Constant Acceleration", "-metadata", "comment=5-minute lesson with Kazakh, Russian, and English voice tracks"])
    # Do not use -shortest: SRT cues end before the padded audio/video tracks,
    # and FFmpeg would truncate the lesson to the last subtitle cue.
    cmd.extend([str(target)])
    _run(cmd)


def _verify_output(path: Path, subtitle_paths: dict[str, Path]) -> dict[str, Any]:
    import av

    expected = sum(SEGMENT_SECONDS)
    with av.open(str(path)) as container:
        video = container.streams.video
        audio = container.streams.audio
        subtitles = [s for s in container.streams if s.type == "subtitle"]
        if len(video) != 1 or len(audio) != 3 or len(subtitles) != 3:
            raise RuntimeError(
                f"Expected one video, three audio, and three subtitle streams; got "
                f"{len(video)}, {len(audio)}, and {len(subtitles)}."
            )
        duration = (container.duration or 0) / 1_000_000
        if abs(duration - expected) > 1.5:
            raise RuntimeError(f"Final duration {duration:.2f}s differs from the {expected}s target.")
        dimensions = (video[0].width, video[0].height)
        if dimensions != (1280, 720):
            raise RuntimeError(f"Expected 1280x720 cloud video, received {dimensions}.")
        audio_langs = [str(s.metadata.get("language", "")) for s in audio]
        if audio_langs != ["kaz", "rus", "eng"]:
            raise RuntimeError(f"Unexpected audio language metadata: {audio_langs}")
        default_audio = [
            i for i, s in enumerate(audio)
            if int(getattr(s.disposition, "value", s.disposition)) & 1
        ]
        if default_audio != [1]:
            raise RuntimeError(f"Russian should be the default audio track; got {default_audio}")
        default_subtitles = [
            i for i, s in enumerate(subtitles)
            if int(getattr(s.disposition, "value", s.disposition)) & 1
        ]
        if default_subtitles != [1]:
            raise RuntimeError(f"Russian should be the default subtitle track; got {default_subtitles}")
    cue_counts = {}
    for lang, srt in subtitle_paths.items():
        text = srt.read_text(encoding="utf-8-sig")
        cue_counts[lang] = text.count(" --> ")
        if cue_counts[lang] < 30:
            raise RuntimeError(f"Too few timed {lang} subtitles: {cue_counts[lang]}")
        if not text.endswith("\n"):
            raise RuntimeError(f"Subtitle file {srt.name} is missing a final newline.")
    if path.stat().st_size < 5_000_000:
        raise RuntimeError(f"Suspiciously small final MP4: {path.stat().st_size} bytes")
    return {
        "duration_seconds": duration,
        "resolution": f"{dimensions[0]}x{dimensions[1]}",
        "video_tracks": len(video),
        "audio_tracks": len(audio),
        "subtitle_tracks": len(subtitles),
        "audio_language_order": audio_langs,
        "default_audio": "ru",
        "subtitle_cues": cue_counts,
        "file_bytes": path.stat().st_size,
    }


async def build() -> Path:
    from aetherlab.core.models import SceneBundle
    from aetherlab.core.settings import load_settings
    from aetherlab.services.code_safety import validate_code_safety
    from aetherlab.services.manim_runtime import (
        _cloud_render_admission_issues,
        _estimate_render_cost,
    )
    from aetherlab.services.render_backend import (
        CloudRenderBackend,
        cloud_job_id,
        render_fps_for,
        render_timeout_for,
    )
    from aetherlab.services.scene_validation import validate_scene

    content = _load_content()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    settings = replace(load_settings(), render_mode="cloud", narration_enabled=False, vision_model=None)
    backend = CloudRenderBackend(settings)
    available, reason = backend.available()
    if not available:
        raise RuntimeError(f"Cloud rendering is required but unavailable: {reason}")
    print("Cloud-only renderer ready; local Manim fallback is disabled.", flush=True)

    voice_files: dict[str, list[Path]] = {lang: [] for lang in LANGUAGES}
    subtitle_files: dict[str, Path] = {}
    cue_counts: dict[str, int] = {}
    for lang in LANGUAGES:
        narration = content["languages"][lang]
        marks_by_chunk: list[tuple[list[dict], float, float]] = []
        offset = 0.0
        rates: list[int] = []
        for index, (text, seconds) in enumerate(zip(narration["sections"], SEGMENT_SECONDS)):
            audio = TMP_DIR / "voice" / lang / f"chapter-{index + 1:02}.mp3"
            marks, duration, rate = await _synthesize_chunk(text, narration["voice"], audio, seconds)
            voice_files[lang].append(audio)
            marks_by_chunk.append((marks, duration, offset))
            offset += seconds
            rates.append(rate)
        srt = OUTPUT_DIR / f"physlab_ent_constant_acceleration_5min_{lang}.srt"
        cue_counts[lang] = _write_srt(marks_by_chunk, srt)
        subtitle_files[lang] = srt
        print(f"Voice {lang}: {len(voice_files[lang])} timed chunks; speech rates={rates}; subtitles={cue_counts[lang]} cues.", flush=True)

    rendered_segments: list[Path] = []
    job_ids: list[str] = []
    for index, seconds in enumerate(SEGMENT_SECONDS):
        code = _scene_code(index, seconds)
        compile(code, f"<ent-acceleration-cloud-segment-{index + 1}>", "exec")
        safe, safety_issues = validate_code_safety(code)
        if not safe:
            raise RuntimeError(f"Scene {index + 1} failed cloud safety check: {safety_issues[:4]}")
        lint_ok, lint_issues = validate_scene(code, require_motion=True)
        if not lint_ok:
            raise RuntimeError(f"Scene {index + 1} failed static Manim checks: {lint_issues[:5]}")
        budget_issues = _cloud_render_admission_issues(code, settings, float(seconds))
        if budget_issues:
            raise RuntimeError(f"Scene {index + 1} exceeded cloud admission: {budget_issues}")
        cost = _estimate_render_cost(code)
        scene = SceneBundle(
            class_name="AetherLabScene", code=code, engine="manim-community",
            status="compiled", storyboard={"title": content["segments"][index]["id"]},
        )
        fps = render_fps_for(code, QUALITY)
        variant = f"ent-acceleration-5min-seg{index + 1:02}"
        job_id = cloud_job_id(scene, quality=QUALITY, fps=fps, variant=variant)
        target = TMP_DIR / "cloud-segments" / f"segment-{index + 1:02}.mp4"
        cache_marker = target.with_suffix(".jobid")
        cache_matches = cache_marker.is_file() and cache_marker.read_text(encoding="utf-8").strip() == job_id
        if cache_matches and target.is_file() and target.stat().st_size >= 20_000:
            import av
            with av.open(str(target)) as container:
                cached_duration = (container.duration or 0) / 1_000_000
                cached_video = container.streams.video
                cached_dimensions = (cached_video[0].width, cached_video[0].height) if cached_video else None
            if abs(cached_duration - seconds) <= 1.5 and cached_dimensions == (1280, 720):
                print(f"Reusing verified cloud segment {index + 1}/7, job {job_id}.", flush=True)
                rendered_segments.append(target)
                job_ids.append(job_id)
                continue
        print(f"Cloud render {index + 1}/7: {seconds}s, 720p, cost {cost:.2f}, job {job_id}.", flush=True)
        result = await backend.render(
            scene, quality=QUALITY, settings=settings,
            timeout=render_timeout_for(code, QUALITY, settings), variant=variant,
            progress=lambda message: print(f"  {message}", flush=True),
        )
        if result.status != "rendered" or not result.video_path:
            detail = result.diagnostics[-1] if result.diagnostics else result.status
            raise RuntimeError(f"Cloud segment {index + 1} did not render: {detail}")
        source = Path(result.video_path)
        if not source.is_file() or source.stat().st_size < 20_000:
            raise RuntimeError(f"Cloud artifact for segment {index + 1} is missing or too small.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        cache_marker.write_text(job_id + "\n", encoding="utf-8")
        rendered_segments.append(target)
        job_ids.append(job_id)

    ffmpeg = _ffmpeg()
    visuals = TMP_DIR / "cloud-visuals-5min.mp4"
    _assemble_visuals(ffmpeg, rendered_segments, visuals)

    # A longer narration must never conceal a short or truncated visual render.
    import av
    with av.open(str(visuals)) as container:
        visual_duration = (container.duration or 0) / 1_000_000
    if abs(visual_duration - sum(SEGMENT_SECONDS)) > 1.5:
        raise RuntimeError(
            f"Cloud visuals total {visual_duration:.2f}s; expected {sum(SEGMENT_SECONDS)}s before audio mux."
        )

    full_audio: dict[str, Path] = {}
    for lang in LANGUAGES:
        target = TMP_DIR / "audio" / f"full-{lang}.m4a"
        target.parent.mkdir(parents=True, exist_ok=True)
        _make_audio_track(ffmpeg, voice_files[lang], SEGMENT_SECONDS, target)
        full_audio[lang] = target
    _mux_multilingual(ffmpeg, visuals, full_audio, subtitle_files, OUTPUT_PATH)
    media_check = _verify_output(OUTPUT_PATH, subtitle_files)
    print(f"Verified multilingual cloud video: {media_check}", flush=True)

    manifest = {
        "video": OUTPUT_PATH.name,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "render_backend": "github-actions-cloud-only",
        "cloud_jobs": job_ids,
        "quality": "720p",
        "fps": FPS,
        "visual_duration_seconds": visual_duration,
        "duration_target_seconds": sum(SEGMENT_SECONDS),
        "content_version": content["version"],
        "media_check": media_check,
        "sources": content["sources"],
        "official_exam_alignment": content["official_exam_alignment"],
        "calculation_keys": {
            "worked_example": {"v0_mps": 2, "a_mps2": 1.5, "t_s": 4, "v_mps": 8, "s_m": 20},
            "provided_nct_graph": {"points": [[0, 0], [1, 4], [3, 4], [4, 0]], "areas_m": [2, 8, 2], "answer": "B", "distance_m": 12},
            "self_check": {"v0_mps": 18, "v_mps": 6, "t_s": 4, "a_mps2": -3, "s_m": 48},
        },
        "local_video_rendering": False,
    }
    manifest_path = OUTPUT_DIR / "physlab_ent_constant_acceleration_5min_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}", flush=True)
    return OUTPUT_PATH


def main() -> int:
    configure_utf8_stdio()
    try:
        asyncio.run(build())
    except Exception as exc:  # noqa: BLE001
        print(f"Cloud lesson build failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
