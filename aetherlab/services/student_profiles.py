"""Local student profiles with isolated practice and review data."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from aetherlab.core.atomic_json import atomic_write_json, path_lock

_PROFILE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,29}$")
_MAX_PROFILE_NAME = 81  # 40-character first + space + 40-character surname


@dataclass(frozen=True)
class StudentProfile:
    id: str
    name: str
    storage_dir: Path
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    class_name: str = ""
    school_id: str = ""
    avatar_path: str = ""

    @property
    def email(self) -> str:
        return f"{self.username}@gmail.com" if self.username else ""

    @property
    def progress_path(self) -> Path:
        return self.storage_dir / "ent_practice_progress.json"

    @property
    def course_progress_path(self) -> Path:
        return self.storage_dir / "course_progress.json"

    @property
    def ai_help_quota_path(self) -> Path:
        return self.storage_dir / "ai_help_quota.json"


class StudentProfileStore:
    """Persist profile names and the selected learner on this device."""

    def __init__(self, data_dir: Path, default_name: str = "Learner 1") -> None:
        self.data_dir = Path(data_dir)
        self.registry_path = self.data_dir / "student_profiles.json"
        self.default_name = self._clean_name(default_name)
        self._ensure_registry()

    @staticmethod
    def _clean_name(name: str) -> str:
        return str(name or "").strip()

    def _read_registry(self) -> dict:
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            payload = {}
        # An inaccessible existing file is not an empty registry. Propagating
        # other IO failures prevents recovery/create from replacing its data.
        if not isinstance(payload, dict):
            payload = {}

        raw_profiles = payload.get("profiles", [])
        if not isinstance(raw_profiles, list):
            raw_profiles = []
        profiles = []
        seen_ids: set[str] = set()
        for raw in raw_profiles:
            if not isinstance(raw, dict):
                continue
            profile_id = str(raw.get("id", ""))
            name = self._clean_name(raw.get("name", ""))
            if (
                not _PROFILE_ID.fullmatch(profile_id)
                or profile_id in seen_ids
                or not name
                or len(name) > _MAX_PROFILE_NAME
            ):
                continue
            seen_ids.add(profile_id)
            username = str(raw.get("username", "") or "").strip().lower()
            if not _USERNAME.fullmatch(username):
                username = "student1" if profile_id == "default" else f"student{profile_id[-8:]}"
            first_name = self._clean_name(raw.get("first_name", "")) or name
            profiles.append({
                "id": profile_id,
                "name": name,
                "first_name": first_name[:40],
                "last_name": self._clean_name(raw.get("last_name", ""))[:40],
                "username": username,
                "class_name": self._clean_name(raw.get("class_name", ""))[:24],
                "school_id": self._clean_name(raw.get("school_id", ""))[:40],
                "avatar_path": str(raw.get("avatar_path", "") or "")[:1024],
            })

        active_id = str(payload.get("active_profile_id", ""))
        if active_id not in seen_ids and profiles:
            active_id = profiles[0]["id"]
        return {
            "version": 1,
            "active_profile_id": active_id,
            "profiles": profiles,
        }

    def _write_registry(self, payload: dict) -> None:
        atomic_write_json(self.registry_path, payload)

    def _ensure_registry(self) -> None:
        with path_lock(self.registry_path):
            payload = self._read_registry()
            if not payload["profiles"]:
                # The first profile owns the legacy progress file so existing
                # learners keep their saved results after this migration.
                payload["profiles"] = [{
                    "id": "default",
                    "name": self.default_name,
                    "first_name": self.default_name,
                    "last_name": "",
                    "username": "student1",
                    "class_name": "",
                    "school_id": "",
                    "avatar_path": "",
                }]
                payload["active_profile_id"] = "default"
                self._write_registry(payload)
            elif not payload["active_profile_id"]:
                payload["active_profile_id"] = payload["profiles"][0]["id"]
                self._write_registry(payload)

    def _profile(self, item: dict) -> StudentProfile:
        profile_id = item["id"]
        storage_dir = (
            self.data_dir
            if profile_id == "default"
            else self.data_dir / "student_profiles" / profile_id
        )
        return StudentProfile(
            id=profile_id,
            name=item["name"],
            storage_dir=storage_dir,
            first_name=item.get("first_name", item["name"]),
            last_name=item.get("last_name", ""),
            username=item.get("username", ""),
            class_name=item.get("class_name", ""),
            school_id=item.get("school_id", ""),
            avatar_path=item.get("avatar_path", ""),
        )

    def list_profiles(self) -> list[StudentProfile]:
        with path_lock(self.registry_path):
            payload = self._read_registry()
        return [self._profile(item) for item in payload["profiles"]]

    def get_profile(self, profile_id: str) -> StudentProfile | None:
        return next((profile for profile in self.list_profiles() if profile.id == profile_id), None)

    def active_profile(self) -> StudentProfile:
        with path_lock(self.registry_path):
            payload = self._read_registry()
        for item in payload["profiles"]:
            if item["id"] == payload["active_profile_id"]:
                return self._profile(item)
        # _ensure_registry guarantees this in normal use; recover cleanly if
        # the registry is edited or truncated while PhysLab is running.
        self._ensure_registry()
        return self.active_profile()

    def create_profile(
        self,
        name: str,
        *,
        first_name: str = "",
        last_name: str = "",
        username: str = "",
        class_name: str = "",
        school_id: str = "",
        avatar_path: str = "",
        make_active: bool = False,
    ) -> StudentProfile:
        cleaned = self._clean_name(name)
        if not cleaned:
            raise ValueError("empty")
        first = self._clean_name(first_name)
        last = self._clean_name(last_name)
        structured_name = bool(first and last and cleaned == f"{first} {last}")
        name_limit = _MAX_PROFILE_NAME if structured_name else 80
        if len(cleaned) > name_limit or (structured_name and (len(first) > 40 or len(last) > 40)):
            raise ValueError("too_long")
        profile_id = uuid.uuid4().hex[:16]
        safe_username = str(username or f"student{profile_id[-8:]}").strip().lower()
        if not _USERNAME.fullmatch(safe_username):
            raise ValueError("invalid_username")
        with path_lock(self.registry_path):
            payload = self._read_registry()
            if any(item["name"].casefold() == cleaned.casefold() for item in payload["profiles"]):
                raise ValueError("duplicate")
            if any(item["username"].casefold() == safe_username for item in payload["profiles"]):
                raise ValueError("duplicate_username")
            item = {
                "id": profile_id,
                "name": cleaned,
                "first_name": self._clean_name(first_name)[:40] or cleaned[:40],
                "last_name": self._clean_name(last_name)[:40],
                "username": safe_username,
                "class_name": self._clean_name(class_name)[:24],
                "school_id": self._clean_name(school_id)[:40],
                "avatar_path": str(avatar_path or "")[:1024],
            }
            payload["profiles"].append(item)
            if make_active:
                payload["active_profile_id"] = profile_id
            self._write_registry(payload)
        return self._profile(item)

    def update_profile(
        self,
        profile_id: str,
        *,
        first_name: str,
        last_name: str,
        username: str,
        class_name: str = "",
        school_id: str = "",
        avatar_path: str = "",
    ) -> StudentProfile:
        first = self._clean_name(first_name)
        last = self._clean_name(last_name)
        safe_username = str(username or "").strip().lower()
        if not first or not last:
            raise ValueError("empty_name")
        if len(first) > 40 or len(last) > 40:
            raise ValueError("too_long")
        if not _USERNAME.fullmatch(safe_username):
            raise ValueError("invalid_username")
        cleaned_class = self._clean_name(class_name)
        cleaned_school_id = self._clean_name(school_id)
        if len(cleaned_class) > 24 or len(cleaned_school_id) > 40:
            raise ValueError("too_long")
        full_name = f"{first} {last}"
        with path_lock(self.registry_path):
            payload = self._read_registry()
            item = next(
                (entry for entry in payload["profiles"] if entry["id"] == profile_id),
                None,
            )
            if item is None:
                raise ValueError("unknown_profile")
            if any(
                entry["id"] != profile_id and entry["name"].casefold() == full_name.casefold()
                for entry in payload["profiles"]
            ):
                raise ValueError("duplicate")
            if any(
                entry["id"] != profile_id and entry["username"].casefold() == safe_username
                for entry in payload["profiles"]
            ):
                raise ValueError("duplicate_username")
            item.update({
                "name": full_name,
                "first_name": first,
                "last_name": last,
                "username": safe_username,
                "class_name": cleaned_class,
                "school_id": cleaned_school_id,
                "avatar_path": str(avatar_path or "")[:1024],
            })
            self._write_registry(payload)
        return self._profile(item)

    def set_active_profile(self, profile_id: str) -> StudentProfile:
        with path_lock(self.registry_path):
            payload = self._read_registry()
            item = next(
                (entry for entry in payload["profiles"] if entry["id"] == profile_id),
                None,
            )
            if item is None:
                raise ValueError("unknown_profile")
            payload["active_profile_id"] = profile_id
            self._write_registry(payload)
        return self._profile(item)
