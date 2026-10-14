"""Build and search a resumable SQLite index of the user's ENT reference files.

Original books and archives remain read-only. The database stores extracted
text with file/member/page provenance, OCR confidence, hashes, and extraction
status; it does not copy the source PDFs or images into the database.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile

from aetherlab.core.console import configure_utf8_stdio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUPPORTED = {".pdf", ".doc", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"}
COMPLETED_STATUSES = {"indexed", "indexed_partial", "unsupported", "archive_container", "container_member"}
OCR_LANGUAGES = ("kaz", "rus", "eng")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def _database_path() -> Path:
    from aetherlab.core.settings import load_settings

    return Path(load_settings().data_dir) / "physlab_reference_library.sqlite3"


def _source_id(path: Path, member: str | None) -> str:
    key = f"{path.resolve()}\0{member or ''}"
    return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=60)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_files (
            source_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            archive_member TEXT,
            filename TEXT NOT NULL,
            extension TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            sha256 TEXT,
            status TEXT NOT NULL,
            unit_count INTEGER NOT NULL DEFAULT 0,
            text_units INTEGER NOT NULL DEFAULT 0,
            ocr_units INTEGER NOT NULL DEFAULT 0,
            empty_units INTEGER NOT NULL DEFAULT 0,
            confidence REAL,
            error TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(source_path, archive_member)
        );
        CREATE TABLE IF NOT EXISTS content_units (
            unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL REFERENCES source_files(source_id) ON DELETE CASCADE,
            unit_number INTEGER NOT NULL,
            unit_type TEXT NOT NULL,
            label TEXT NOT NULL,
            text TEXT NOT NULL,
            extraction_method TEXT NOT NULL,
            confidence REAL,
            status TEXT NOT NULL,
            UNIQUE(source_id, unit_number, unit_type)
        );
        CREATE INDEX IF NOT EXISTS content_units_source ON content_units(source_id, unit_number);
        CREATE VIRTUAL TABLE IF NOT EXISTS reference_fts USING fts5(
            source_id UNINDEXED,
            unit_number UNINDEXED,
            unit_type UNINDEXED,
            title,
            label,
            text,
            tokenize='unicode61'
        );
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version','1')"
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key,value) VALUES('source_root',?)",
        (str(Path.home() / "Projects" / "References"),),
    )
    connection.commit()
    return connection


def _ocr_image(image: Any) -> tuple[str, float | None, str]:
    """OCR one image with Kazakh, Russian, and English trained data."""
    from PIL import Image

    if hasattr(image, "convert"):
        pil_image = image.convert("RGB")
    else:
        pil_image = Image.fromarray(image).convert("RGB")
    png = io.BytesIO()
    pil_image.save(png, format="PNG")
    completed = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", "+".join(OCR_LANGUAGES), "--psm", "3", "tsv"],
        input=png.getvalue(), capture_output=True, check=True,
        env={**os.environ, "OMP_THREAD_LIMIT": "1"},
    )
    lines: dict[tuple[str, str, str], list[tuple[int, str]]] = {}
    confidences: list[float] = []
    rows = csv.DictReader(
        io.StringIO(completed.stdout.decode("utf-8", errors="replace")), delimiter="\t"
    )
    for row in rows:
        word = (row.get("text") or "").strip()
        if not word or row.get("level") != "5":
            continue
        try:
            word_confidence = float(row.get("conf", "-1"))
        except ValueError:
            word_confidence = -1
        if word_confidence >= 0:
            confidences.append(word_confidence / 100.0)
        key = (row.get("block_num", "0"), row.get("par_num", "0"), row.get("line_num", "0"))
        try:
            word_index = int(row.get("word_num", "0"))
        except ValueError:
            word_index = 0
        lines.setdefault(key, []).append((word_index, word))
    text = "\n".join(
        " ".join(word for _, word in sorted(words))
        for _, words in sorted(lines.items())
    )
    confidence = sum(confidences) / len(confidences) if confidences else None
    status = "ocr_low_confidence" if confidence is not None and confidence < 0.55 else "indexed"
    return text, confidence, status


def _pdf_units(path: Path, display_name: str = "PDF") -> tuple[list[dict[str, Any]], dict[str, int]]:
    import fitz

    units: list[dict[str, Any]] = []
    counts = {"unit_count": 0, "text_units": 0, "ocr_units": 0, "empty_units": 0}
    with fitz.open(path) as document:
        counts["unit_count"] = document.page_count
        pending: list[int] = []
        def finish_ocr(position: int) -> None:
            unit = units[position]
            future: Future = unit.pop("_future")
            counts["ocr_units"] += 1
            try:
                text, confidence, status = future.result()
                unit.update(text=text, confidence=confidence, status=status)
                if not text:
                    unit["status"] = "empty_or_unreadable_scan"
                    counts["empty_units"] += 1
            except Exception as exc:  # noqa: BLE001 — preserve page/status, keep indexing
                unit.update(extraction_method="ocr_error", confidence=None,
                            status=f"ocr_error:{type(exc).__name__}")
                counts["empty_units"] += 1

        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="tesseract-page") as pool:
            for index, page in enumerate(document):
                if (index + 1) % 10 == 0:
                    print(f"  {display_name}: page {index + 1}/{document.page_count}", flush=True)
                text = (page.get_text("text", sort=True) or "").strip()
                unit = {
                    "unit_number": index + 1,
                    "unit_type": "page",
                    "label": f"PDF page {index + 1}",
                    "text": text,
                    "extraction_method": "pdf_text" if text else "tesseract_kaz_rus_eng",
                    "confidence": None,
                    "status": "indexed" if text else "ocr_pending",
                }
                units.append(unit)
                if text:
                    counts["text_units"] += 1
                    continue
                pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
                import numpy as np
                image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )
                unit["_future"] = pool.submit(_ocr_image, image)
                pending.append(index)
                if len(pending) >= 6:
                    finish_ocr(pending.pop(0))
        for position in pending:
            finish_ocr(position)
    return units, counts


def _xml_text(blob: bytes) -> str:
    try:
        root = ET.fromstring(blob)
        return " ".join(value.strip() for value in root.itertext() if value.strip())
    except ET.ParseError:
        return ""


def _docx_units(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    from docx import Document

    document = Document(str(path))
    sections: list[tuple[str, list[str]]] = [("Document", [])]
    for paragraph in document.paragraphs:
        value = paragraph.text.strip()
        if not value:
            continue
        style = (paragraph.style.name if paragraph.style else "").casefold()
        if style.startswith("heading") and sections[-1][1]:
            sections.append((value[:200], []))
        else:
            sections[-1][1].append(value)
    for table_index, table in enumerate(document.tables, 1):
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " / ") for cell in row.cells]
            if any(cells):
                sections[0][1].append(f"[Table {table_index}] " + " | ".join(cells))
    for section_index, section in enumerate(document.sections, 1):
        for part_name, part in (("Header", section.header), ("Footer", section.footer)):
            for paragraph in part.paragraphs:
                if paragraph.text.strip():
                    sections[0][1].append(f"[{part_name} {section_index}] {paragraph.text.strip()}")
    units = [
        {"unit_number": i, "unit_type": "section", "label": heading,
         "text": "\n".join(paragraphs), "extraction_method": "python_docx",
         "confidence": None, "status": "indexed"}
        for i, (heading, paragraphs) in enumerate(sections, 1) if paragraphs
    ]
    counts = {"unit_count": len(units), "text_units": len(units), "ocr_units": 0, "empty_units": 0}
    return units, counts


def _pptx_units(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    slide_pattern = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
    notes_pattern = re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$")
    units: list[dict[str, Any]] = []
    with ZipFile(path) as package:
        by_slide: dict[int, dict[str, list[str]]] = {}
        for name in package.namelist():
            match = slide_pattern.match(name)
            if match:
                number = int(match.group(1))
                by_slide.setdefault(number, {"slide": [], "notes": []})["slide"].append(
                    _xml_text(package.read(name))
                )
                continue
            match = notes_pattern.match(name)
            if match:
                number = int(match.group(1))
                by_slide.setdefault(number, {"slide": [], "notes": []})["notes"].append(
                    _xml_text(package.read(name))
                )
        for number, pieces in sorted(by_slide.items()):
            text = "\n".join(value for value in [*pieces["slide"], *pieces["notes"]] if value)
            units.append({
                "unit_number": number, "unit_type": "slide", "label": f"Slide {number}",
                "text": text, "extraction_method": "pptx_xml_text_and_notes",
                "confidence": None, "status": "indexed" if text else "empty_slide",
            })
    counts = {"unit_count": len(units), "text_units": sum(bool(x["text"]) for x in units), "ocr_units": 0, "empty_units": sum(not bool(x["text"]) for x in units)}
    return units, counts


def _doc_units(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = None
    document = None
    try:
        app = win32com.client.DispatchEx("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        app.AutomationSecurity = 3  # Disable macros when opening untrusted source files.
        document = app.Documents.Open(
            str(path.resolve()), ReadOnly=True, AddToRecentFiles=False,
            ConfirmConversions=False, Visible=False,
        )
        text = str(document.Content.Text or "").strip()
        # Also capture headers and footers that are separate from document body.
        for section_number in range(1, document.Sections.Count + 1):
            section = document.Sections(section_number)
            for kind in (1, 2, 3):
                try:
                    header_text = str(section.Headers(kind).Range.Text or "").strip()
                    footer_text = str(section.Footers(kind).Range.Text or "").strip()
                    if header_text:
                        text += f"\n[Header {section_number}] {header_text}"
                    if footer_text:
                        text += f"\n[Footer {section_number}] {footer_text}"
                except Exception:
                    pass
        units = [{"unit_number": 1, "unit_type": "document", "label": "Word document",
                  "text": text, "extraction_method": "Microsoft Word COM",
                  "confidence": None, "status": "indexed" if text else "empty_document"}]
        counts = {"unit_count": 1, "text_units": int(bool(text)), "ocr_units": 0, "empty_units": int(not bool(text))}
        return units, counts
    finally:
        if document is not None:
            document.Close(SaveChanges=0)
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def _text_units(path: Path, display_name: str = "") -> tuple[list[dict[str, Any]], dict[str, int]]:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return _pdf_units(path, display_name or path.name)
    if extension == ".docx":
        return _docx_units(path)
    if extension == ".pptx":
        return _pptx_units(path)
    if extension == ".doc":
        return _doc_units(path)
    if extension in {".png", ".jpg", ".jpeg"}:
        from PIL import Image

        text, confidence, status = _ocr_image(Image.open(path))
        units = [{"unit_number": 1, "unit_type": "image", "label": path.name,
                  "text": text, "extraction_method": "tesseract_kaz_rus_eng",
                  "confidence": confidence, "status": status if text else "image_no_readable_text"}]
        counts = {"unit_count": 1, "text_units": 0, "ocr_units": 1, "empty_units": int(not bool(text))}
        return units, counts
    if extension in {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        units = [{"unit_number": 1, "unit_type": "document", "label": path.name,
                  "text": text, "extraction_method": "utf8_text",
                  "confidence": None, "status": "indexed" if text.strip() else "empty_document"}]
        counts = {"unit_count": 1, "text_units": int(bool(text.strip())), "ocr_units": 0, "empty_units": int(not bool(text.strip()))}
        return units, counts
    return [], {"unit_count": 0, "text_units": 0, "ocr_units": 0, "empty_units": 0}


def _save_source(
    db: sqlite3.Connection,
    *, path: Path,
    member: str | None,
    extension: str,
    filename: str,
    size: int,
    digest: str | None,
    status: str,
    units: Iterable[dict[str, Any]] = (),
    counts: dict[str, int] | None = None,
    error: str | None = None,
) -> None:
    source_id = _source_id(path, member)
    counts = counts or {}
    values = list(units)
    confidences = [float(x["confidence"]) for x in values if x.get("confidence") is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None
    with db:
        db.execute("DELETE FROM reference_fts WHERE source_id=?", (source_id,))
        db.execute("DELETE FROM content_units WHERE source_id=?", (source_id,))
        db.execute(
            """INSERT INTO source_files(source_id,source_path,archive_member,filename,extension,
               size_bytes,sha256,status,unit_count,text_units,ocr_units,empty_units,confidence,error,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source_id) DO UPDATE SET source_path=excluded.source_path,
               archive_member=excluded.archive_member,filename=excluded.filename,extension=excluded.extension,
               size_bytes=excluded.size_bytes,sha256=excluded.sha256,status=excluded.status,
               unit_count=excluded.unit_count,text_units=excluded.text_units,ocr_units=excluded.ocr_units,
               empty_units=excluded.empty_units,confidence=excluded.confidence,error=excluded.error,
               updated_at=excluded.updated_at""",
            (source_id, str(path.resolve()), member, filename, extension, size, digest, status,
             counts.get("unit_count", len(values)), counts.get("text_units", 0), counts.get("ocr_units", 0),
             counts.get("empty_units", 0), avg_confidence, error, _now()),
        )
        for unit in values:
            cursor = db.execute(
                """INSERT INTO content_units(source_id,unit_number,unit_type,label,text,
                   extraction_method,confidence,status) VALUES(?,?,?,?,?,?,?,?)""",
                (source_id, unit["unit_number"], unit["unit_type"], unit["label"], unit["text"],
                 unit["extraction_method"], unit.get("confidence"), unit["status"]),
            )
            if unit["text"].strip():
                db.execute(
                    """INSERT INTO reference_fts(rowid,source_id,unit_number,unit_type,title,label,text)
                       VALUES(?,?,?,?,?,?,?)""",
                    (cursor.lastrowid, source_id, unit["unit_number"], unit["unit_type"], filename,
                     unit["label"], unit["text"]),
                )


def _already_indexed(db: sqlite3.Connection, source_id: str, digest: str) -> bool:
    row = db.execute("SELECT sha256,status FROM source_files WHERE source_id=?", (source_id,)).fetchone()
    return bool(row and row[0] == digest and row[1] in COMPLETED_STATUSES)


def _ingest_path(db: sqlite3.Connection, path: Path, member: str | None = None) -> tuple[str, str]:
    extension = Path(member or path.name).suffix.lower()
    filename = Path(member or path.name).name
    temp_path: Path | None = None
    try:
        if member is None:
            physical_path = path
            digest, size = _hash_file(physical_path)
        else:
            temporary_root = _database_path().parent / "reference_ingest_tmp"
            temporary_root.mkdir(parents=True, exist_ok=True)
            import uuid

            temp_path = temporary_root / f"{uuid.uuid4().hex}{extension}"
            digest_obj = hashlib.sha256()
            size = 0
            with ZipFile(path) as archive, archive.open(member) as source, temp_path.open("wb") as out:
                while chunk := source.read(1024 * 1024):
                    out.write(chunk)
                    digest_obj.update(chunk)
                    size += len(chunk)
            physical_path = temp_path
            digest = digest_obj.hexdigest()
        source_id = _source_id(path, member)
        if _already_indexed(db, source_id, digest):
            return "skipped", "unchanged"
        if extension == ".zip":
            status = "archive_container"
            _save_source(db, path=path, member=member, extension=extension, filename=filename,
                         size=size, digest=digest, status=status)
            return status, ""
        if extension not in SUPPORTED:
            _save_source(db, path=path, member=member, extension=extension, filename=filename,
                         size=size, digest=digest, status="unsupported")
            return "unsupported", ""
        try:
            units, counts = _text_units(physical_path, filename)
            needs_review = any(
                unit["status"] != "indexed" and unit["text"].strip()
                or not unit["text"].strip()
                for unit in units
            )
            status = "indexed_partial" if needs_review else "indexed"
            _save_source(db, path=path, member=member, extension=extension, filename=filename,
                         size=size, digest=digest, status=status, units=units, counts=counts)
            detail = f"units={counts['unit_count']} text={counts['text_units']} OCR={counts['ocr_units']} empty={counts['empty_units']}"
            return status, detail
        except Exception as exc:  # noqa: BLE001 — retain file record and continue
            message = f"{type(exc).__name__}: {exc}"[:1000]
            _save_source(db, path=path, member=member, extension=extension, filename=filename,
                         size=size, digest=digest, status="error", error=message)
            return "error", message
    except Exception as exc:  # noqa: BLE001 — unreadable/encrypted archive member
        message = f"{type(exc).__name__}: {exc}"[:500]
        try:
            size = path.stat().st_size if member is None else ZipFile(path).getinfo(member).file_size
            _save_source(db, path=path, member=member, extension=extension, filename=filename,
                         size=size, digest=None, status="error", error=message)
        except Exception:
            pass
        return "error", message
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _iter_sources(root: Path) -> Iterable[tuple[Path, str | None, bool]]:
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file():
            continue
        yield path, None, path.suffix.lower() == ".zip"
        if path.suffix.lower() != ".zip":
            continue
        try:
            with ZipFile(path) as archive:
                for info in archive.infolist():
                    if not info.is_dir():
                        yield path, info.filename, False
        except (BadZipFile, OSError):
            continue


def build_index() -> int:
    root = Path.home() / "Projects" / "References"
    if not root.is_dir():
        raise FileNotFoundError(f"Reference folder not found: {root}")
    database = _database_path()
    db = _connect(database)
    totals = {"indexed": 0, "indexed_partial": 0, "skipped": 0, "unsupported": 0, "error": 0}
    members = 0
    started = time.monotonic()
    print(f"Database: {database}", flush=True)
    print(f"Reference root: {root}", flush=True)
    print(f"OCR: Tesseract {','.join(OCR_LANGUAGES)}", flush=True)
    for path, member, is_archive in _iter_sources(root):
        if member is not None:
            members += 1
        status, detail = _ingest_path(db, path, member)
        totals[status] = totals.get(status, 0) + 1
        if status in {"error", "indexed_partial", "unsupported"}:
            label = path.name + (f" :: {member}" if member else "")
            print(f"[{status}] {label}{(': ' + detail) if detail else ''}", flush=True)
        processed = sum(totals.values())
        if processed % 25 == 0:
            print(f"Progress: {processed} entries; archive members seen={members}; elapsed={time.monotonic()-started:.0f}s", flush=True)
    db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('last_completed_at',?)", (_now(),))
    db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('last_run_counts',?)", (json.dumps(totals),))
    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    stats = db.execute(
        """SELECT COUNT(*),SUM(unit_count),SUM(text_units),SUM(ocr_units),SUM(empty_units)
           FROM source_files"""
    ).fetchone()
    print(f"DONE: {json.dumps(totals,ensure_ascii=False)}", flush=True)
    print(f"DB totals: files={stats[0]} units={stats[1] or 0} text_units={stats[2] or 0} OCR_units={stats[3] or 0} empty_units={stats[4] or 0}", flush=True)
    print(f"Elapsed: {time.monotonic()-started:.1f}s; database_bytes={database.stat().st_size}", flush=True)
    db.close()
    return 0


def search_index(query: str, limit: int) -> int:
    database = _database_path()
    if not database.is_file():
        raise FileNotFoundError(f"Index not built yet: {database}")
    db = sqlite3.connect(database)
    try:
        rows = db.execute(
            """SELECT f.title,f.label,f.unit_type,f.unit_number,
                      snippet(reference_fts,5,'[',']',' … ',18),s.source_path,s.archive_member
               FROM reference_fts f JOIN source_files s ON s.source_id=f.source_id
               WHERE reference_fts MATCH ? ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
    finally:
        db.close()
    for title, label, unit_type, number, excerpt, path, member in rows:
        location = path + (f" :: {member}" if member else "")
        print(f"{title} — {label} ({unit_type} {number})\n{location}\n{excerpt}\n")
    print(f"Results: {len(rows)}")
    return 0


def show_stats() -> int:
    db_path = _database_path()
    if not db_path.is_file():
        print(f"No database at {db_path}")
        return 1
    db = sqlite3.connect(db_path)
    rows = db.execute("SELECT status,COUNT(*),SUM(unit_count),SUM(empty_units) FROM source_files GROUP BY status ORDER BY status").fetchall()
    print(f"Database: {db_path}")
    for status, files, units, empty in rows:
        print(f"{status}: files={files}, units={units or 0}, empty_or_unread={empty or 0}")
    return 0


def main() -> int:
    configure_utf8_stdio()
    _safe_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", metavar="QUERY", help="Search indexed source text using SQLite FTS5")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--stats", action="store_true", help="Show current database coverage")
    args = parser.parse_args()
    if args.search:
        return search_index(args.search, max(1, args.limit))
    if args.stats:
        return show_stats()
    return build_index()


if __name__ == "__main__":
    raise SystemExit(main())


