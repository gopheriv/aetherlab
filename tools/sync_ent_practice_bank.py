"""Mirror the version-controlled ENT question bank into its local SQLite DB."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from index_reference_library import _database_path

from aetherlab.core.console import configure_utf8_stdio
from aetherlab.services.ent_physics_bank import EXERCISES

_MANAGED_IDS_KEY = "ent_practice_managed_ids"
_BANK_ID = re.compile(r"topic-[a-z][a-z0-9_]*-[0-9]{3,6}\Z")


def _managed_ids(db: sqlite3.Connection) -> set[str]:
    row = db.execute("SELECT value FROM metadata WHERE key=?", (_MANAGED_IDS_KEY,)).fetchone()
    if row is None:
        return set()
    try:
        ids = json.loads(row[0])
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid managed-question manifest; sync cancelled") from exc
    if (not isinstance(ids, list) or any(not isinstance(value, str) or not _BANK_ID.fullmatch(value) for value in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("Invalid managed-question manifest; sync cancelled")
    return set(ids)


def _is_bank_record(row: tuple | None) -> bool:
    return bool(row and row[0] in {"PhysLab", "AetherLab"}
                and row[1] == "original_aetherlab_item" and row[2] in {"practice", "retired_practice"})

_CATEGORY = {
    "kinematics":"Механика", "dynamics":"Механика", "statics":"Механика",
    "fluids":"Механика", "conservation":"Механика",
    "molecular_kinetic_theory":"Молекулярная физика и термодинамика",
    "gas_laws":"Молекулярная физика и термодинамика",
    "thermodynamics":"Молекулярная физика и термодинамика",
    "liquids_solids":"Молекулярная физика и термодинамика",
    "mechanical_oscillations":"Колебания и волны", "wave_motion":"Колебания и волны",
    "electromagnetic_waves":"Колебания и волны", "wave_optics":"Оптика",
    "geometric_optics":"Оптика", "electricity":"Электричество и магнетизм",
    "electrostatics":"Электричество и магнетизм", "current_media":"Электричество и магнетизм",
    "magnetic_field":"Электричество и магнетизм", "induction":"Электричество и магнетизм",
    "ac_circuits":"Электричество и магнетизм", "relativity":"Атомная и ядерная физика",
    "quantum_physics":"Атомная и ядерная физика", "nuclear_physics":"Атомная и ядерная физика",
    "nanotechnology":"Общие материалы", "cosmology":"Атомная и ядерная физика",
}


def _reference_pages(db: sqlite3.Connection) -> dict[str, list[dict]]:
    """Attach identifiable indexed textbook pages as topic-bucket references.

    The current corpus taxonomy is broader than the 25 UNT topics, so these
    are explicitly marked as candidate references rather than verified page
    citations for each generated numeric variation.
    """
    result = {}
    # A fresh question database need not have an indexed textbook corpus yet.
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='physics_pages' AND type IN ('table','view')").fetchone() is None:
        return {topic: [] for topic in _CATEGORY}
    for topic, category in _CATEGORY.items():
        rows = db.execute(
            """SELECT filename,source_path,unit_number,label,confidence
               FROM physics_pages WHERE topic=? AND filename LIKE 'Физика Закирова%'
               ORDER BY filename,source_path,unit_number""", (category,),
        ).fetchall()
        pages = []
        seen = set()
        for filename, source_path, number, label, confidence in rows:
            key = (source_path, filename, number)
            if key in seen:
                continue
            seen.add(key)
            pages.append({"filename": filename, "source_path": source_path,
                          "pdf_page": number, "label": label,
                          "confidence": confidence, "status": "topic_bucket_candidate_unreviewed"})
            if len(pages) == 3:
                break
        result[topic] = pages
    return result


def main() -> int:
    configure_utf8_stdio()
    db_path = _database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(db_path, timeout=30)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """CREATE TABLE IF NOT EXISTS ent_practice_questions (
                question_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                difficulty TEXT NOT NULL CHECK (difficulty IN ('A','B','C')),
                kind TEXT NOT NULL,
                prompt_json TEXT NOT NULL,
                choices_json TEXT NOT NULL,
                correct_indices_json TEXT NOT NULL,
                explanation_json TEXT NOT NULL,
                kazakh_term TEXT NOT NULL,
                context_json TEXT,
                matching_left_json TEXT,
                source_note TEXT NOT NULL,
                reuse_status TEXT NOT NULL,
                author TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                language_review_status TEXT NOT NULL,
                answer_verification_status TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                solution_latex_json TEXT NOT NULL DEFAULT '[]',
                source_pages_json TEXT NOT NULL DEFAULT '[]',
                bank_kind TEXT NOT NULL DEFAULT 'practice'
            )"""
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(ent_practice_questions)")}
        for column, declaration in (
            ("solution_latex_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("source_pages_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("bank_kind", "TEXT NOT NULL DEFAULT 'practice'"),
        ):
            if column not in columns:
                db.execute(f"ALTER TABLE ent_practice_questions ADD COLUMN {column} {declaration}")
        db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        previous_ids = _managed_ids(db)
        ids = [question.id for question in EXERCISES]
        if not ids or len(ids) != len(set(ids)) or any(not _BANK_ID.fullmatch(value) for value in ids):
            raise ValueError("Invalid versioned question IDs; sync cancelled")
        current_ids = set(ids)
        for question_id in ids:
            existing = db.execute(
                "SELECT author,reuse_status,bank_kind FROM ent_practice_questions WHERE question_id=?",
                (question_id,),
            ).fetchone()
            if existing is not None and not _is_bank_record(existing):
                raise ValueError(f"Refusing to overwrite a non-bank question: {question_id}")
        references = _reference_pages(db)
        rows = []
        for question in EXERCISES:
            ref_pages = references.get(question.topic, [])
            source_note = question.source_note
            if ref_pages:
                ref_label = "; ".join(f"{p['filename']} p. {p['pdf_page']} (topic candidate)" for p in ref_pages)
                source_note = f"{source_note} | Indexed reference candidates: {ref_label}"
            rows.append((
                question.id,
                question.topic,
                question.difficulty,
                question.kind,
                json.dumps(question.prompt, ensure_ascii=False),
                json.dumps(question.choices, ensure_ascii=False),
                json.dumps(question.correct_indices),
                json.dumps(question.explanation, ensure_ascii=False),
                question.kazakh_term,
                json.dumps(question.context, ensure_ascii=False) if question.context else None,
                json.dumps(question.matching_left, ensure_ascii=False) if question.matching_left else None,
                source_note,
                question.reuse_status,
                question.author,
                question.reviewer,
                question.language_review_status,
                question.answer_verification_status,
                now,
                json.dumps(question.solution_latex, ensure_ascii=False),
                json.dumps(ref_pages, ensure_ascii=False),
                "practice",
            ))
        columns = ("question_id", "topic", "difficulty", "kind", "prompt_json", "choices_json",
                   "correct_indices_json", "explanation_json", "kazakh_term", "context_json",
                   "matching_left_json", "source_note", "reuse_status", "author", "reviewer",
                   "language_review_status", "answer_verification_status", "synced_at",
                   "solution_latex_json", "source_pages_json", "bank_kind")
        updates = ",".join(f"{column}=excluded.{column}" for column in columns if column != "question_id")
        db.executemany(
            f"INSERT INTO ent_practice_questions ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) "
            f"ON CONFLICT(question_id) DO UPDATE SET {updates}", rows)
        # Retire only IDs recorded by a prior successful sync. Never infer
        # ownership of legacy/custom rows, and keep annotations/foreign keys.
        for question_id in previous_ids - current_ids:
            existing = db.execute(
                "SELECT author,reuse_status,bank_kind FROM ent_practice_questions WHERE question_id=?",
                (question_id,),
            ).fetchone()
            if _is_bank_record(existing):
                db.execute("UPDATE ent_practice_questions SET bank_kind='retired_practice' WHERE question_id=?",
                           (question_id,))
        db.execute(
            "INSERT INTO metadata(key,value) VALUES('ent_practice_bank_count',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(len(EXERCISES)),),
        )
        db.execute(
            "INSERT INTO metadata(key,value) VALUES('ent_practice_bank_synced_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (now,),
        )
        db.execute(
            "INSERT INTO metadata(key,value) VALUES('ent_practice_topics',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("25 topics x 100 practice questions",),
        )
        db.execute("INSERT INTO metadata(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (_MANAGED_IDS_KEY, json.dumps(sorted(current_ids))),)
        db.commit()
        total = db.execute("SELECT COUNT(*) FROM ent_practice_questions").fetchone()[0]
        print(f"Database: {db_path}")
        print(f"Synchronized {len(ids)} bank questions across kk/ru/en; preserved {total - len(ids)} other records.")
        print(f"Unreviewed textbook-page candidates: {sum(bool(pages) for pages in references.values())}/25 topics.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
