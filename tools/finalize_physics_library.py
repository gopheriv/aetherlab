"""Keep physics pages only in the persistent reference-library SQLite database."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

from index_reference_library import _database_path

from aetherlab.core.console import configure_utf8_stdio

TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Механика", (
        "механик", "кинемат", "движени", "перемещен", "скорост", "ускорен",
        "сила", "ньютон", "импульс", "работа", "мощност", "энерги", "давлен",
        "гравитац", "тартыл", "жылдамдық", "үдеу", "қозғалыс", "күш", "энергия",
        "жұмыс", "қуат", "қысым", "үйкеліс", "momentum", "velocity", "acceleration",
        "force", "newton", "work", "power", "energy", "motion", "kinematic",
    )),
    ("Молекулярная физика и термодинамика", (
        "термодинамик", "молекул", "температур", "теплот", "тепл", "газов", "газ",
        "жылу", "температура", "молекула", "ішкі энергия", "газ заң", "энтроп",
        "thermodynamic", "molecular", "temperature", "heat", "internal energy", "entropy",
    )),
    ("Электричество и магнетизм", (
        "электр", "ток", "заряд", "напряж", "сопротивлен", "ом закон", "магнит",
        "электр өріс", "электр тог", "заряд", "кернеу", "кедергі", "магнит өріс",
        "electric", "current", "charge", "voltage", "resistance", "magnetic", "coulomb",
    )),
    ("Колебания и волны", (
        "колеб", "волна", "частот", "период", "резонанс", "звук", "тербеліс",
        "толқын", "жиілік", "дыбыс", "oscillation", "wave", "frequency", "resonance", "sound",
    )),
    ("Оптика", (
        "оптик", "свет", "линз", "зеркал", "преломлен", "отражен", "жарық", "линза",
        "сыну көрсеткіш", "шағыл", "optics", "light", "lens", "mirror", "refraction", "reflection",
    )),
    ("Атомная и ядерная физика", (
        "атом", "ядр", "радиоактив", "изотоп", "квант", "фотон", "ядерн", "атомдық",
        "ядролық", "радиоактив", "изотоп", "квант", "фотон", "nuclear", "radioactive",
        "isotope", "quantum", "photon",
    )),
)
TOPIC_PATTERNS = tuple(
    (topic, re.compile("|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)), re.IGNORECASE))
    for topic, terms in TOPICS
)

PHYSICS_SOURCE = re.compile(r"физик|physics|physlab|физика", re.IGNORECASE)
# Keep generic mixed-subject UNT scans page-specific. Previous substring checks
# treated fragments such as "ом" inside "дом" and "свет" inside literary
# passages as physics. These anchors use full-word starts and physical concepts;
# short SI symbols count only when attached to a number.
PHYSICS_PAGE = re.compile(
    r"(?<!\w)(?:"
    r"кинемат\w*|механик\w*|траектор\w*|перемещен\w*|скорост\w*|ускорен\w*|"
    r"ньютон\w*|импульс\w*|гравитац\w*|трени\w*|архимед\w*|momentum|velocity|acceleration|kinematic|"
    r"термодинамик\w*|молекулярн\w*|теплоемк\w*|теплопередач\w*|плавлен\w*|кипени\w*|энтроп\w*|"
    r"термодинамик\w*|молекул\w*|температур\w*|газов\w* закон\w*|жылу\w*|молекула\w*|temperature|thermodynamic|entropy|"
    r"электрическ\w* ток\w*|электр\w* тог\w*|напряжен\w*|сопротивлен\w*|электр өріс\w*|магнит өріс\w*|"
    r"конденсатор\w*|электромагнит\w*|кулон\w*|вольт\w*|ампер\w*|кернеу\w*|кедергі\w*|electric current|voltage|resistance|magnetic field|coulomb|"
    r"колебан\w*|частот\w*|резонанс\w*|период колебан\w*|тербеліс\w*|жиілік\w*|wave\b|frequency\b|oscillation\w*|"
    r"оптик\w*|линз\w*|фокус\w*|зеркал\w*|преломлен\w*|снелл\w*|сыну көрсеткіш\w*|шағыл\w*|refraction\w*|lens\w*|mirror\w*|"
    # Avoid bare "nuclear"/"ядролық": mixed UNT archives use those words
    # in history and politics questions. Specific nuclear-physics vocabulary
    # (radioactivity, isotopes, quanta, photons) is a safer signal.
    r"радиоактив\w*|изотоп\w*|квант\w*|фотон\w*|radioactive\w*|quantum\w*|photon\w*|"
    r"\d+(?:[.,]\d+)?\s*(?:м/с(?:²|2)?|км/ч|гц|hz|ом|ohm|дж|joule|вт|watt|па|pascal|н|тл|tesla)\b"
    r")",
    re.IGNORECASE,
)
NON_PHYSICS_SOURCE = re.compile(
    r"матем|mathemat|math(?:s|sauce)?|mat_sauat|мат сауат|матграм|геометр|алгебр|"
    r"биолог|biology|\bбио\b|хими|chem|истори|istori|history|тарих|информат|informat|"
    r"географ|geograph|литератур|литература|обществозн|русский язык",
    re.IGNORECASE,
)


def classify(text: str, source_name: str, unit_type: str) -> tuple[bool, str | None]:
    # OCR pages can contain very long footers or OCR noise; the leading section
    # is enough for a topic label and keeps catalog finalization bounded.
    text = text[:6000]
    if NON_PHYSICS_SOURCE.search(source_name):
        return False, None
    if PHYSICS_SOURCE.search(source_name) and text.strip():
        topic = next((name for name, pattern in TOPIC_PATTERNS if pattern.search(text)), "Общие материалы")
        return True, topic
    # Mixed UNT compilations are only included when the page itself clearly
    # marks the Physics section or contains a specific physics concept/unit.
    if re.search(r"(?<!\w)(?:физика|physics)(?!\w)", text[:6000], re.IGNORECASE) or PHYSICS_PAGE.search(text):
        topic = next((name for name, pattern in TOPIC_PATTERNS if pattern.search(text)), "Общие материалы")
        return True, topic
    return False, None


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Remove non-physics rows and keep only classified pages")
    args = parser.parse_args()
    db_path = _database_path()
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = sqlite3.Row
    try:
        # Plan the filter in memory first, preserving provenance from each source.
        records = db.execute(
            """SELECT u.unit_id,u.source_id,u.unit_number,u.unit_type,u.label,u.text,
                      s.filename,s.source_path,s.archive_member
               FROM content_units u JOIN source_files s USING(source_id)
               ORDER BY s.filename COLLATE NOCASE,u.unit_number"""
        )
        keep: list[tuple[int, str]] = []
        for row in records:
            name = " ".join((row["filename"], row["source_path"], row["archive_member"] or ""))
            included, topic = classify(row["text"], name, row["unit_type"])
            if included and row["text"].strip():
                keep.append((row["unit_id"], topic or "Общие материалы"))
        topic_totals: dict[str, int] = {}
        for _, topic in keep:
            topic_totals[topic] = topic_totals.get(topic, 0) + 1
        selected = {unit_id: topic for unit_id, topic in keep}
        source_count = len({row["source_id"] for row in db.execute(
            "SELECT DISTINCT source_id FROM content_units"
        )})
        print(f"Database: {db_path}")
        current_units = db.execute("SELECT COUNT(*) FROM content_units").fetchone()[0]
        print(f"Current units: {current_units}; physics text pages/slides/sections selected: {len(keep)}; current source files: {source_count}")
        for topic, count in sorted(topic_totals.items()):
            print(f"{topic}: {count}")
        if not args.apply:
            print("Dry run only. Re-run with --apply to keep only physics pages.")
            return 0

        physics_errors = db.execute(
            """SELECT source_path,archive_member,filename,status,error FROM source_files
               WHERE status='error' AND (filename LIKE '%физик%' COLLATE NOCASE
                 OR filename LIKE '%physics%' COLLATE NOCASE
                 OR archive_member LIKE '%физик%' COLLATE NOCASE
                 OR archive_member LIKE '%physics%' COLLATE NOCASE)"""
        ).fetchall()
        db.execute(
            """CREATE TABLE IF NOT EXISTS catalog_issues(
               source_path TEXT NOT NULL, archive_member TEXT, filename TEXT NOT NULL,
               status TEXT NOT NULL, detail TEXT)"""
        )
        known_issues = {
            (row[0], row[1], row[2])
            for row in db.execute("SELECT source_path,archive_member,filename FROM catalog_issues")
        }
        db.executemany(
            "INSERT INTO catalog_issues(source_path,archive_member,filename,status,detail) VALUES(?,?,?,?,?)",
            (row for row in physics_errors if (row[0], row[1], row[2]) not in known_issues),
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(content_units)")}
        if "topic" not in columns:
            db.execute("ALTER TABLE content_units ADD COLUMN topic TEXT")
        else:
            # Make repeated filtering runs idempotent: prior topic labels must
            # not keep a page that the refined classifier now rejects.
            db.execute("UPDATE content_units SET topic=NULL")
        for unit_id, topic in selected.items():
            db.execute("UPDATE content_units SET topic=? WHERE unit_id=?", (topic, unit_id))
        db.execute("DELETE FROM content_units WHERE topic IS NULL OR trim(text)=''")
        db.execute(
            """UPDATE content_units SET topic='Формулы и справочник'
               WHERE topic='Общие материалы' AND source_id IN (
                 SELECT source_id FROM source_files WHERE lower(filename) LIKE '%формул%'
                   OR lower(filename) LIKE '%formula%' OR lower(filename) LIKE '%анықтамалық%')"""
        )
        db.execute("DELETE FROM reference_fts WHERE rowid NOT IN (SELECT unit_id FROM content_units)")
        db.execute("DELETE FROM source_files WHERE source_id NOT IN (SELECT DISTINCT source_id FROM content_units)")
        db.execute(
            """UPDATE source_files SET
               unit_count=(SELECT COUNT(*) FROM content_units u WHERE u.source_id=source_files.source_id),
               text_units=(SELECT COUNT(*) FROM content_units u WHERE u.source_id=source_files.source_id AND u.extraction_method NOT LIKE '%tesseract%' AND trim(u.text)<>''),
               ocr_units=(SELECT COUNT(*) FROM content_units u WHERE u.source_id=source_files.source_id AND u.extraction_method LIKE '%tesseract%'),
               empty_units=(SELECT COUNT(*) FROM content_units u WHERE u.source_id=source_files.source_id AND trim(u.text)='')"""
        )
        db.execute("CREATE INDEX IF NOT EXISTS content_units_topic_sort ON content_units(topic,source_id,unit_number)")
        db.execute("DROP VIEW IF EXISTS physics_pages")
        db.execute(
            """CREATE VIEW physics_pages AS
               SELECT u.topic,s.filename,s.source_path,s.archive_member,u.unit_type,
                      u.unit_number,u.label,u.text,u.extraction_method,u.confidence,u.status
               FROM content_units u JOIN source_files s USING(source_id)
               ORDER BY u.topic COLLATE NOCASE,s.filename COLLATE NOCASE,
                        s.source_path COLLATE NOCASE,s.archive_member COLLATE NOCASE,u.unit_number"""
        )
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('catalog_filter','physics_only')")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('catalog_sort','topic, filename, source_path, archive_member, unit_number')")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('catalog_finalized_at',datetime('now'))")
        db.commit()
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print("Applied physics-only filter and created sorted physics_pages view.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
