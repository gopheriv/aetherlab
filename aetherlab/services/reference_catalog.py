"""Curated local physics sources for school-book references and ENT practice.

The user's source folder stays read-only. ZIP archives are inspected through
their central directory and a single selected member is extracted to a temp
cache only when the user opens it.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from aetherlab.core.atomic_json import path_lock

OPENABLE_SUFFIXES = {".pdf", ".doc", ".docx", ".pptx"}
_BOOK_SERIES = ("кронгарт", "башар", "закиров")
_UNT_BOOK_FILENAMES = {
    "физика кронгарт 7.pdf",
    "физика закирова 8.pdf",
    "физика закирова 9.pdf",
    "физика закирова 10 жм.pdf",
    "физика закирова 11 жм.pdf",
}
_SUPPLEMENTAL_TERMS = (
    "369 формула",
    "механика_формула",
    "физика теория чемпион",
    "fbs",
    "құпия есептер",
)
_SPEC_TERMS = ("спецификация", "кодификатор")
_NON_QUESTION_TERMS = (
    "спецификация", "кодификатор", "формула", "теория", "видеоурок",
    "видеосабақ", "кинематика видео", "сор, соч", "сор соч", "бжб, тжб",
)


@dataclass(frozen=True)
class SourceMaterial:
    title: str
    category: str
    path: Path
    detail: str
    grade: int | None = None
    archive_member: str | None = None

    @property
    def suffix(self) -> str:
        return Path(self.archive_member or self.path.name).suffix.lower()

    @property
    def is_archived(self) -> bool:
        return self.archive_member is not None


def default_reference_root() -> Path | None:
    """Resolve the explicitly configured source folder or this user's usual folder."""
    configured = os.getenv("AETHERLAB_REFERENCE_SOURCES", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_dir() else None
    usual = Path.home() / "Projects" / "References"
    return usual if usual.is_dir() else None


def _grade_from_name(name: str) -> int | None:
    match = re.search(r"(?<!\d)(7|8|9|10|11)(?!\d)", name)
    return int(match.group(1)) if match else None


def _kind_for_direct_file(path: Path) -> tuple[str, int | None] | None:
    name = path.name.casefold()
    if path.suffix.lower() not in {".pdf", ".doc", ".docx", ".pptx"}:
        return None

    if any(series in name for series in _BOOK_SERIES):
        grade = _grade_from_name(name)
        if grade is not None and name in _UNT_BOOK_FILENAMES:
            return "book", grade
        return None
    if any(term in name for term in _SUPPLEMENTAL_TERMS):
        return "reference", None
    if name.startswith("testcenter") or "ұто үлгі кітап" in name:
        return "mock", None
    if name == "10_.pdf" or any(term in name for term in _SPEC_TERMS):
        return "specification", None
    return None


def _archive_category(member: str) -> str | None:
    normalized = member.replace("\\", "/")
    folded = normalized.casefold()
    if "/ент физика/" not in f"/{folded}/":
        return None
    if any(term in folded for term in ("/сор", "/соч", "/бжб", "/тжб")):
        return None
    suffix = Path(normalized).suffix.lower()
    if suffix not in OPENABLE_SUFFIXES:
        return None
    name = Path(normalized).name.casefold()
    # Teacher qualification (NKT/OZP) and Russian entrance exams are separate
    # assessments; a filename containing "пробный" does not make them UNT.
    if any(term in name for term in ("нкт", "nkt", "озп", "ozp", "огэ", "егэ")):
        return None
    if any(term in name for term in _NON_QUESTION_TERMS):
        return "reference"
    if any(term in name for term in ("кодфикатор", "кодификатор")):
        return "reference"
    if any(term in name for term in (
        "testcenter", "пробный", "вариант", "нұсқа", "нуска", "вопрос",
        "сұрақ", "ент", "ұбт", "тест", "разбор",
    )):
        return "mock"
    # These files are in the physics-specific ENT archive folder, but their
    # names do not tell us whether they are tests, explanations, or formula sets.
    return "physics_material"


def scan_reference_catalog(root: Path | None = None) -> dict[str, list[SourceMaterial]]:
    """Return books, supplementary references, and exam materials by role."""
    source_root = root or default_reference_root()
    grouped: dict[str, list[SourceMaterial]] = {
        "book": [], "reference": [], "specification": [], "mock": [],
        "physics_material": [],
    }
    if source_root is None or not source_root.is_dir():
        return grouped

    for path in sorted(source_root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file():
            continue
        classified = _kind_for_direct_file(path)
        if classified is None:
            continue
        category, grade = classified
        detail = "PDF учебник" if category == "book" else "Материал из папки References"
        if category == "book" and grade is not None:
            detail = f"Учебник {grade} класса · источник для объяснений"
        grouped[category].append(
            SourceMaterial(path.stem, category, path, detail, grade=grade)
        )

    for archive_path in sorted(source_root.glob("*.zip"), key=lambda item: item.name.casefold()):
        try:
            with ZipFile(archive_path) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    category = _archive_category(info.filename)
                    if category is None:
                        continue
                    member_path = Path(info.filename.replace("\\", "/"))
                    group = " / ".join(member_path.parts[-3:-1])
                    label = "Материал из ZIP · физика ЕНТ"
                    if group:
                        label += f" · {group}"
                    if category == "physics_material":
                        label = "Физический материал из сборника ЕНТ · тип не указан в названии"
                    grouped[category].append(
                        SourceMaterial(
                            member_path.stem,
                            category,
                            archive_path,
                            label,
                            archive_member=info.filename,
                        )
                    )
        except (BadZipFile, OSError):
            continue

    for items in grouped.values():
        items.sort(key=lambda item: (item.grade or 99, item.title.casefold()))
    return grouped


def _has_searchable_text(path: Path) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    return _sampled_pdf_has_text(str(path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=256)
def _sampled_pdf_has_text(path_text: str, _mtime_ns: int, _size: int) -> bool:
    """Avoid indexing image-only scans by sampling pages beyond their watermark."""
    try:
        import fitz

        with fitz.open(path_text) as document:
            if document.page_count == 0:
                return False
            indices = {0, min(3, document.page_count - 1), min(8, document.page_count - 1)}
            indices.update(
                min(document.page_count - 1, max(0, round(document.page_count * portion)))
                for portion in (0.12, 0.3, 0.55, 0.8, 0.95)
            )
            readable_pages = 0
            for index in sorted(indices):
                text = document.load_page(index).get_text("text").strip()
                if len(text) >= 420:
                    readable_pages += 1
                if readable_pages >= 2:
                    return True
    except Exception:  # noqa: BLE001 - unreadable/scanned source is still openable in UI
        return False
    return False


def searchable_reference_files(root: Path | None = None) -> list[Path]:
    """Textbooks and theory/formula references that have extractable PDF text."""
    catalog = scan_reference_catalog(root)
    sources = [*catalog["book"], *catalog["reference"]]
    files: list[Path] = []
    for item in sources:
        if not item.is_archived and item.suffix == ".pdf" and _has_searchable_text(item.path):
            files.append(item.path)
    return sorted(set(files), key=lambda path: path.name.casefold())


def openable_path(item: SourceMaterial) -> Path:
    """Resolve a catalog source to a local file, extracting only one ZIP member."""
    if not item.archive_member:
        return item.path
    member = item.archive_member.replace("\\", "/")
    if member.startswith("/") or ".." in Path(member).parts:
        raise ValueError("Unsafe path inside source archive")
    with ZipFile(item.path) as archive:
        info = archive.getinfo(item.archive_member)
        if info.is_dir() or info.file_size > 160 * 1024 * 1024:
            raise ValueError("This source file is too large to open from the archive")
        if info.file_size > max(info.compress_size, 1) * 1000:
            raise ValueError("This archive member has an unsafe compression ratio")
        archive_stat = item.path.stat()
        key = hashlib.sha256(
            (
                f"{item.path.resolve()}\0{archive_stat.st_size}\0{archive_stat.st_mtime_ns}"
                f"\0{member}\0{info.CRC}\0{info.file_size}"
            ).encode("utf-8")
        ).hexdigest()[:20]
        cache_dir = Path(tempfile.gettempdir()) / "physlab-source-cache" / key
        target = cache_dir / Path(member).name
        with path_lock(target):
            if not target.is_file() or target.stat().st_size != info.file_size:
                cache_dir.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(target.suffix + ".tmp")
                try:
                    with archive.open(info) as source, temporary.open("wb") as destination:
                        shutil.copyfileobj(source, destination, length=1024 * 1024)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
        return target
