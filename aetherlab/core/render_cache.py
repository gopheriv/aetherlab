"""Requested render provenance for reusable scene videos (never shared files)."""
from __future__ import annotations

from aetherlab.core.models import SceneBundle
from aetherlab.core.render_profile import get_effective_profile


def requested_profile_key(settings: object | None, quality: str = "l") -> str:
    profile = get_effective_profile(settings, quality=quality)
    mode = str(getattr(settings, "render_mode", "local") or "local").strip().lower()
    return f"scene-profile-v1:{mode}:{profile.identity_key()}"


def scene_profile_matches(scene: SceneBundle, settings: object | None, quality: str = "l") -> bool:
    """Legacy/unverified videos may supply code, but cannot certify a profile."""
    return bool(scene.render_profile_key) and scene.render_profile_key == requested_profile_key(settings, quality)


def record_scene_profile(scene: SceneBundle, settings: object | None, quality: str = "l") -> SceneBundle:
    if scene.status == "rendered":
        scene.render_profile_key = requested_profile_key(settings, quality)
    return scene


def invalidate_rendered_media(scene: SceneBundle, reason: str = "Cached video render profile changed or unverified; re-rendering.") -> None:
    """Retain source/analysis while detaching every output owned by the old render."""
    scene.status = "compiled"
    scene.cached = False
    scene.video_path = ""
    scene.silent_video_path = ""
    scene.subtitle_path = ""
    scene.narration_text = ""
    scene.narration_sync = {}
    scene.render_profile_key = ""
    scene.diagnostics.append(reason)
