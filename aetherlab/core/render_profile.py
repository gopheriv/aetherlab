"""Single source of truth for Manim render profiles.

One validated configuration shared by local/cloud/segmented/previews/assembly/
exports/cache. Presets:

- ``preview``   — practical fast preview (480p/30, cairo)
- ``standard``  — default balanced output (720p/30, cairo)
- ``cinematic`` — full-quality output (1080p/60, cairo)
- ``unt`` — deterministic UNT study output (1080p/30, cairo)
- ``unt_vertical`` — UNT portrait cut (1080x1920/30, cairo)

API stability contract (other agents import this):
- ``RenderProfile(width, height, fps, renderer, preset, adaptive,
  resource_limits)``
- ``get_effective_profile(settings) -> RenderProfile``
- ``describe_fallback(reason) -> str``
- ``RenderProfile.identity_key()`` for cache keys (Agent3 uses this without
  editing this file).

Precedence (highest first):
1. Explicit function arguments (e.g. quality flag passed by the caller)
2. Environment overrides (``AETHERLAB_*`` / legacy ``MANIM_*`` / ``RENDER_TIER``)
3. ``AppSettings`` render fields (loaded from env > saved settings.json > default)
4. Preset defaults

Never silently downgrade: any adaptive fallback must be reported via
``describe_fallback`` and appended to diagnostics / logs by the caller.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field, replace

log = logging.getLogger(__name__)

VALID_PRESETS = ("preview", "standard", "cinematic", "unt", "unt_vertical")
VALID_RENDERERS = ("cairo", "opengl")
VALID_QUALITY_FLAGS = ("l", "m", "h", "p", "k")

# Pinned-Manim (0.21.0) output dimensions per quality flag. Single source of
# truth — render_backend.CLOUD_QUALITY_DIMS re-exports this.
QUALITY_DIMS: dict[str, tuple[int, int]] = {
    "l": (854, 480),
    "m": (1280, 720),
    "h": (1920, 1080),
    "p": (2560, 1440),
    "k": (3840, 2160),
}

# Quality flag per preset. Cinematic is 1080p/60 (flag "h"); 4K ("k") stays
# available only as an explicit quality-flag override, never as a preset, so
# the shared default never wedges a laptop on a 4K/60 encode.
# UNT presets use "h" for crisp 1080p text; unt_vertical still needs explicit
# -r 1080,1920 because -q flags are landscape-only (see resolve_resolution).
PRESET_QUALITY: dict[str, str] = {
    "preview": "l",
    "standard": "m",
    "cinematic": "h",
    "unt": "h",
    "unt_vertical": "h",
}

# Manim default fps per quality flag when no explicit --fps is passed. Manim
# silently produces 15 fps at low quality, which is why every render path must
# pass an explicit --fps (see manim_runtime._manim_render_command).
MANIM_DEFAULT_FPS: dict[str, int] = {"l": 15, "m": 30, "h": 60, "p": 60, "k": 60}

# Duration-contract tolerances: UNT exam pacing is tighter than cinematic.
CINEMATIC_DURATION_TOLERANCE = 0.20
UNT_DURATION_TOLERANCE = 0.10
UNT_PRESETS = ("unt", "unt_vertical")


@dataclass(frozen=True)
class ResourceLimits:
    """Machine-facing guardrails (never affect output pixels, only scheduling)."""

    max_local_renders: int = 0  # 0 = auto (cpu_count//2, clamped 1..4)
    below_normal_priority: bool = False
    render_timeout_scale: float = 1.0

    def effective_max_local_renders(self) -> int:
        if self.max_local_renders > 0:
            return max(1, min(8, int(self.max_local_renders)))
        try:
            cpu = int(os.cpu_count() or 4)
        except Exception:
            cpu = 4
        return max(1, min(4, cpu // 2 or 1))


@dataclass(frozen=True)
class RenderProfile:
    """Validated render configuration. Immutable; use ``dataclasses.replace``."""

    width: int = 1280
    height: int = 720
    fps: int = 30
    renderer: str = "cairo"
    preset: str = "standard"
    adaptive: bool = True
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    quality: str = "m"  # Manim -q flag backing this profile
    # Human-readable provenance, e.g. "preset=cinematic env:AETHERLAB_MANIM_FPS=30".
    source: str = "preset:standard"

    def validated(self) -> "RenderProfile":
        """Clamp to sane ranges; never raise on user input."""
        width = _clamp_int(self.width, 320, 3840, 1280)
        height = _clamp_int(self.height, 240, 2160, 720)
        fps = _clamp_int(self.fps, 15, 120, 30)
        source = self.source
        even_width, even_height = width - width % 2, height - height % 2
        if (even_width, even_height) != (width, height):
            note = f"normalized even video canvas {width}x{height}→{even_width}x{even_height}"
            log.warning("%s", note)
            source = f"{source};{note}"
            width, height = even_width, even_height
        renderer = str(self.renderer or "cairo").strip().lower()
        if renderer not in VALID_RENDERERS:
            renderer = "cairo"
        preset = str(self.preset or "standard").strip().lower()
        if preset not in VALID_PRESETS:
            preset = "standard"
        quality = str(self.quality or "m").strip().lower()
        if quality not in VALID_QUALITY_FLAGS:
            quality = PRESET_QUALITY.get(preset, "m")
        return replace(
            self,
            width=width,
            height=height,
            fps=fps,
            renderer=renderer,
            preset=preset,
            quality=quality,
            source=source,
        )

    def identity_key(self) -> str:
        """Short stable key for lesson/audio/segment caches.

        Includes every pixel-affecting field so a preset change invalidates
        cached media. Machine-only limits are excluded on purpose.
        """
        payload = (f"{self.width}x{self.height}@{self.fps}|{self.renderer}|{self.quality}|"
                   f"{self.preset}|adaptive:{int(bool(self.adaptive))}")
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def manim_args(self) -> list[str]:
        """Explicit CLI flags so Manim can never silently pick 15 fps."""
        return ["-q" + self.quality, "--fps", str(int(self.fps))]

    def canvas_filter(self) -> str:
        """ffmpeg scale/pad/fps filter normalizing any clip to this canvas."""
        return (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps={self.fps},format=yuv420p"
        )

    def describe(self) -> str:
        return (
            f"{self.preset} {self.width}x{self.height}@{self.fps} "
            f"{self.renderer} (q={self.quality})"
        )


PRESETS: dict[str, RenderProfile] = {
    "preview": RenderProfile(
        width=854, height=480, fps=30, renderer="cairo",
        preset="preview", adaptive=True, quality="l",
        source="preset:preview",
    ),
    "standard": RenderProfile(
        width=1280, height=720, fps=30, renderer="cairo",
        preset="standard", adaptive=True, quality="m",
        source="preset:standard",
    ),
    "cinematic": RenderProfile(
        width=1920, height=1080, fps=60, renderer="cairo",
        preset="cinematic", adaptive=False, quality="h",
        source="preset:cinematic",
    ),
    "unt": RenderProfile(
        width=1920, height=1080, fps=30, renderer="cairo",
        preset="unt", adaptive=False, quality="h",
        source="preset:unt",
    ),
    "unt_vertical": RenderProfile(
        width=1080, height=1920, fps=30, renderer="cairo",
        preset="unt_vertical", adaptive=False, quality="h",
        source="preset:unt_vertical",
    ),
}


def describe_fallback(reason: str) -> str:
    """Human-readable fallback notice. Callers append this to diagnostics."""
    text = str(reason or "unknown reason").strip()
    return f"Render fallback: {text} (explicit quality preserved where possible; see profile source)."


def _clamp_int(value: object, lo: int, hi: int, default: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    return max(lo, min(hi, number))


def _env_int(*names: str, default: int = 0) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None or not str(value).strip():
            continue
        try:
            return int(str(value).strip())
        except ValueError:
            continue
    return default


def _env_str(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def resolve_preset_name(settings: object | None = None) -> tuple[str, str]:
    """Resolve preset name + provenance. Never raises; defaults to standard."""
    env = _env_str("AETHERLAB_RENDER_PRESET", "AETHERLAB_RENDER_TIER", "RENDER_TIER")
    env_norm = env.strip().lower()
    # Legacy tier names map onto presets; cloud_cinematic is a location, not a
    # look — it renders cinematic pixels on the cloud backend.
    tier_map = {
        "cinematic": "cinematic",
        "cloud_cinematic": "cinematic",
        "standard": "standard",
        "constrained": "standard",
        "preview": "preview",
        "draft": "preview",
        "low": "preview",
        "high": "cinematic",
        "unt": "unt",
        "unt_vertical": "unt_vertical",
        "ent": "unt",
    }
    if env_norm in tier_map:
        return tier_map[env_norm], f"env:{env_norm}"
    if env_norm and env_norm not in {"auto", ""}:
        log.warning("Unknown AETHERLAB_RENDER_PRESET=%r; ignoring.", env)
    raw = str(getattr(settings, "render_preset", "") or "").strip().lower()
    if raw in VALID_PRESETS:
        return raw, "settings:render_preset"
    if raw in tier_map:
        return tier_map[raw], "settings:render_preset(legacy)"
    if raw:
        log.warning("Unknown settings render_preset=%r; using standard.", raw)
    return "standard", "default"


def resolve_renderer(settings: object | None = None) -> tuple[str, str]:
    env = _env_str("AETHERLAB_MANIM_RENDERER").strip().lower()
    if env in VALID_RENDERERS:
        return env, "env:AETHERLAB_MANIM_RENDERER"
    if env:
        log.warning("Unknown AETHERLAB_MANIM_RENDERER=%r; using cairo.", env)
        return "cairo", "env:AETHERLAB_MANIM_RENDERER(invalid→cairo)"
    raw = str(getattr(settings, "render_renderer", "") or getattr(settings, "renderer", "") or "").strip().lower()
    if raw in VALID_RENDERERS:
        return raw, "settings:renderer"
    if raw:
        log.warning("Unknown settings renderer=%r; using cairo.", raw)
    return "cairo", "default"


def resolve_fps(settings: object | None, preset: str) -> tuple[int, str]:
    """Explicit --fps provenance: env override > settings > preset default."""
    override = _env_int("AETHERLAB_MANIM_FPS", "MANIM_FPS", default=0)
    if override > 0:
        return _clamp_int(override, 15, 120, 30), "env:AETHERLAB_MANIM_FPS"
    raw = getattr(settings, "render_fps", None)
    try:
        number = int(str(raw).strip()) if raw is not None and str(raw).strip() else 0
    except (TypeError, ValueError, AttributeError):
        number = 0
    if number > 0:
        return _clamp_int(number, 15, 120, 30), "settings:render_fps"
    return PRESETS[preset].fps, f"preset:{preset}"


def resolve_resolution(
    settings: object | None, preset: str, quality: str
) -> tuple[int, int, str]:
    """Explicit resolution provenance: env > settings > quality dims > preset."""
    env_w = _env_int("AETHERLAB_RENDER_WIDTH", default=0)
    env_h = _env_int("AETHERLAB_RENDER_HEIGHT", default=0)
    if env_w > 0 and env_h > 0:
        return (
            _clamp_int(env_w, 320, 3840, 1280),
            _clamp_int(env_h, 240, 2160, 720),
            "env:AETHERLAB_RENDER_WIDTH/HEIGHT",
        )
    raw_w = getattr(settings, "render_width", None)
    raw_h = getattr(settings, "render_height", None)
    try:
        number_w = int(str(raw_w).strip()) if raw_w is not None and str(raw_w).strip() else 0
        number_h = int(str(raw_h).strip()) if raw_h is not None and str(raw_h).strip() else 0
    except (TypeError, ValueError, AttributeError):
        number_w, number_h = 0, 0
    if number_w > 0 and number_h > 0:
        return (
            _clamp_int(number_w, 320, 3840, 1280),
            _clamp_int(number_h, 240, 2160, 720),
            "settings:render_width/height",
        )
    if preset == "unt_vertical":
        # Manim -q flags are landscape-only; portrait must use preset dims
        # (1080x1920) instead of QUALITY_DIMS, with explicit -r W,H downstream.
        base = PRESETS[preset]
        return base.width, base.height, f"preset:{preset}"
    dims = QUALITY_DIMS.get(quality)
    if dims:
        return dims[0], dims[1], f"quality:{quality}"
    base = PRESETS[preset]
    return base.width, base.height, f"preset:{preset}"


def resolve_quality(settings: object | None, preset: str, quality: str = "") -> tuple[str, str]:
    """Resolve Manim -q flag: explicit arg > env > settings > preset default."""
    explicit = str(quality or "").strip().lower().lstrip("-q")
    if explicit in VALID_QUALITY_FLAGS:
        return explicit, "arg:quality"
    env = _env_str("AETHERLAB_MANIM_QUALITY", "MANIM_QUALITY").strip().lower().lstrip("-q")
    if env in VALID_QUALITY_FLAGS:
        return env, "env:AETHERLAB_MANIM_QUALITY"
    raw = str(getattr(settings, "render_quality", "") or "").strip().lower().lstrip("-q")
    if raw in VALID_QUALITY_FLAGS:
        return raw, "settings:render_quality"
    return PRESET_QUALITY.get(preset, "m"), f"preset:{preset}"


def resolve_adaptive(settings: object | None, preset: str) -> tuple[bool, str]:
    for name in ("AETHERLAB_ADAPTIVE_QUALITY", "AETHERLAB_RENDER_ADAPTIVE"):
        env = os.getenv(name)
        if env is None or not env.strip():
            continue
        lowered = env.strip().lower()
        if lowered in {"0", "false", "no", "off"}:
            return False, f"env:{name}=off"
        if lowered in {"1", "true", "yes", "on"}:
            return True, f"env:{name}=on"
        log.warning("Invalid adaptive render policy in %s; ignoring it.", name)
    raw = getattr(settings, "adaptive_quality", None)
    if raw is not None:
        if isinstance(raw, bool):
            return raw, "settings:adaptive_quality"
        lowered = str(raw).strip().lower()
        if lowered in {"0", "false", "no", "off"}:
            return False, "settings:adaptive_quality=off"
        if lowered in {"1", "true", "yes", "on"}:
            return True, "settings:adaptive_quality=on"
    return PRESETS[preset].adaptive, f"preset:{preset}"


def _coerce_unt_flag(value: object) -> bool | None:
    """Parse an explicit UNT flag; None means unset/invalid."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"0", "false", "no", "off"}:
        return False
    if text in {"1", "true", "yes", "on", "unt"}:
        return True
    return None


def resolve_unt_mode(
    settings: object | None = None,
    override: object = None,
    preset: str = "",
) -> tuple[bool, str]:
    """Resolve UNT exam mode. Never raises; None auto-enables on UNT presets.

    Precedence: explicit ``override`` arg > ``AETHERLAB_UNT_MODE`` env >
    ``settings.unt_mode`` > auto from preset (``unt``/``unt_vertical`` on,
    everything else off). Legacy ``ent`` maps to ``unt``.
    """
    try:
        coerced = _coerce_unt_flag(override)
        if coerced is not None:
            return coerced, f"arg:unt_mode={'on' if coerced else 'off'}"
        if override is not None and str(override).strip():
            log.warning("Invalid unt_mode override %r; ignoring it.", override)
        env = os.getenv("AETHERLAB_UNT_MODE")
        if env is not None and env.strip():
            coerced = _coerce_unt_flag(env)
            if coerced is not None:
                return coerced, f"env:AETHERLAB_UNT_MODE={'on' if coerced else 'off'}"
            log.warning("Invalid adaptive render policy in AETHERLAB_UNT_MODE; ignoring it.")
        raw = getattr(settings, "unt_mode", None)
        coerced = _coerce_unt_flag(raw)
        if coerced is not None:
            if isinstance(raw, bool):
                return coerced, "settings:unt_mode"
            return coerced, f"settings:unt_mode={'on' if coerced else 'off'}"
        preset_name = str(preset or "").strip().lower()
        if preset_name == "ent":
            preset_name = "unt"
        if not preset_name or preset_name not in VALID_PRESETS:
            try:
                preset_name, _ = resolve_preset_name(settings)
            except Exception:  # noqa: BLE001 — resolver never raises
                preset_name = "standard"
        if preset_name == "ent":
            preset_name = "unt"
        return preset_name in UNT_PRESETS, f"preset:{preset_name}"
    except Exception:  # noqa: BLE001 — resolver never raises
        return False, "default"


def resolve_resource_limits(settings: object | None, preset: str) -> ResourceLimits:
    max_renders = _env_int("AETHERLAB_LOCAL_RENDER_LIMIT", default=0)
    provenance_settings = 0
    try:
        raw = getattr(settings, "render_max_local", None)
        provenance_settings = int(str(raw).strip()) if raw is not None and str(raw).strip() else 0
    except (TypeError, ValueError, AttributeError):
        provenance_settings = 0
    limit = max_renders or provenance_settings
    # Legacy constrained tier asked for below-normal priority so the UI stays
    # responsive on small machines; preserve that intent.
    tier = _env_str("AETHERLAB_RENDER_TIER", "RENDER_TIER").strip().lower()
    settings_preset = str(getattr(settings, "render_preset", "") or "").strip().lower()
    constrained = tier == "constrained" or settings_preset == "constrained"
    if constrained:
        below_normal = True
    else:
        below_normal = False
        raw_priority = getattr(settings, "render_below_normal", None)
        if isinstance(raw_priority, bool):
            below_normal = raw_priority
    scale = 1.0
    try:
        raw_scale = getattr(settings, "render_timeout_scale", None)
        if raw_scale is not None and str(raw_scale).strip():
            scale = float(str(raw_scale).strip())
    except (TypeError, ValueError):
        scale = 1.0
    if not (0.25 <= scale <= 4.0):
        scale = 1.0
    return ResourceLimits(
        max_local_renders=max(0, min(8, int(limit or 0))),
        below_normal_priority=bool(below_normal),
        render_timeout_scale=scale,
    )


def get_effective_profile(
    settings: object | None = None,
    *,
    quality: str = "",
    preset: str = "",
) -> RenderProfile:
    """Resolve the validated profile. Lazy — call per render, never cache at import.

    ``settings`` may be a full AppSettings, a SimpleNamespace in tests, or None.
    Missing new fields fall back gracefully to preset defaults so old saved
    settings and old callers keep working.
    """
    if preset and preset.strip().lower() in VALID_PRESETS:
        preset_name, preset_src = preset.strip().lower(), "arg:preset"
    else:
        preset_name, preset_src = resolve_preset_name(settings)
    quality_flag, quality_src = resolve_quality(settings, preset_name, quality)
    renderer, renderer_src = resolve_renderer(settings)
    fps, fps_src = resolve_fps(settings, preset_name)
    width, height, res_src = resolve_resolution(settings, preset_name, quality_flag)
    adaptive, adaptive_src = resolve_adaptive(settings, preset_name)
    limits = resolve_resource_limits(settings, preset_name)
    source = ";".join([f"preset={preset_name}({preset_src})", quality_src, fps_src, res_src, renderer_src, adaptive_src])
    return RenderProfile(
        width=width,
        height=height,
        fps=fps,
        renderer=renderer,
        preset=preset_name,
        adaptive=adaptive,
        resource_limits=limits,
        quality=quality_flag,
        source=source,
    ).validated()


def adapt_profile_for_cost(
    profile: RenderProfile,
    render_cost: float,
) -> tuple[RenderProfile, str | None]:
    """Apply the adaptive policy to an expensive scene, reporting any fallback.

    - Non-adaptive (cinematic default, explicit opt-out): never downgrade.
    - Adaptive + heavy hi-res scene: halve 60 fps to 30 fps and report it.
    Returns ``(effective_profile, fallback_notice_or_None)``.
    """
    try:
        cost = float(render_cost)
    except (TypeError, ValueError):
        cost = 1.0
    if not profile.adaptive:
        return profile, None
    if cost >= 3.0 and profile.quality in ("h", "p", "k") and profile.fps > 30:
        transition = f"{profile.fps}→30"
        downgraded = replace(profile, fps=30, source=profile.source + f";adaptive:fps{transition}(cost={cost:.1f})")
        return downgraded, describe_fallback(
            f"expensive scene (cost {cost:.1f}) at quality '{profile.quality}': "
            f"fps {transition} to hold the render budget"
        )
    return profile, None


def profile_for_quality(quality: str, settings: object | None = None) -> RenderProfile:
    """Resolve a profile pinned to an explicit Manim quality flag."""
    return get_effective_profile(settings, quality=quality)


def tier_compat(profile: RenderProfile) -> dict:
    """Legacy ``_RENDER_TIER`` shape for old callers: {name, fps, below_normal}."""
    return {
        "name": profile.preset,
        "fps": int(profile.fps),
        "below_normal": bool(profile.resource_limits.below_normal_priority),
    }
