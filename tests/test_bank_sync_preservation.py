"""Exercise SQLite preservation with real owned databases, not SQL text checks."""
import hashlib
import importlib.util
import json
import os
import sqlite3
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sync_case(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("owned_sync_case", ROOT / "tools/sync_ent_practice_bank.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "library.sqlite3"
    monkeypatch.setattr(module, "_database_path", lambda: path)
    return module, path


def initialize(module, path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE physics_pages (filename TEXT,source_path TEXT,unit_number INTEGER,label TEXT,confidence REAL,topic TEXT)")
    assert module.main() == 0


def test_sync_preserves_an_unmanaged_custom_question(sync_case):
    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        row = dict(db.execute("SELECT * FROM ent_practice_questions LIMIT 1").fetchone())
        row.update(question_id="teacher-custom-001", author="Teacher", reuse_status="teacher_item")
        db.execute(f"INSERT INTO ent_practice_questions ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT author FROM ent_practice_questions WHERE question_id='teacher-custom-001'").fetchone() == ("Teacher",)


def test_sync_keeps_additional_annotations(sync_case):
    module, path = sync_case
    initialize(module, path)
    question_id = module.EXERCISES[0].id
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE ent_practice_questions ADD COLUMN personal_note TEXT DEFAULT ''")
        db.execute("UPDATE ent_practice_questions SET personal_note='Keep this explanation' WHERE question_id=?", (question_id,))
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT personal_note FROM ent_practice_questions WHERE question_id=?", (question_id,)).fetchone() == ("Keep this explanation",)


def test_sync_keeps_child_rows_instead_of_delete_insert(sync_case):
    module, path = sync_case
    initialize(module, path)
    question_id = module.EXERCISES[0].id
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE learner_notes(question_id TEXT REFERENCES ent_practice_questions(question_id) ON DELETE CASCADE,note TEXT)")
        db.execute("INSERT INTO learner_notes VALUES (?,?)", (question_id, "Keep my note"))
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM learner_notes").fetchall() == [(question_id, "Keep my note")]


def test_sync_works_before_any_books_are_indexed(sync_case):
    module, path = sync_case
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM ent_practice_questions").fetchone() == (2500,)


def database_hash(path):
    digest = hashlib.sha256()
    with sqlite3.connect(path) as db:
        for line in db.iterdump():
            digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def clone_question(db, source_id, new_id, **updates):
    db.row_factory = sqlite3.Row
    row = dict(db.execute("SELECT * FROM ent_practice_questions WHERE question_id=?", (source_id,)).fetchone())
    row.update(question_id=new_id, **updates)
    db.execute(f"INSERT INTO ent_practice_questions ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))


def test_updates_keep_question_and_metadata_row_identity(sync_case):
    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        before = db.execute("SELECT question_id,rowid FROM ent_practice_questions ORDER BY question_id").fetchall()
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE metadata_notes(key TEXT REFERENCES metadata(key) ON DELETE CASCADE,note TEXT)")
        db.execute("INSERT INTO metadata_notes VALUES ('ent_practice_bank_count','Keep metadata note')")
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT question_id,rowid FROM ent_practice_questions ORDER BY question_id").fetchall() == before
        assert db.execute("SELECT note FROM metadata_notes").fetchall() == [("Keep metadata note",)]


def test_foreign_question_collision_aborts_without_any_changes(sync_case):
    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE ent_practice_questions SET author='Teacher' WHERE question_id=?", (module.EXERCISES[0].id,))
    before = database_hash(path)
    with pytest.raises(ValueError, match="non-bank question"):
        module.main()
    assert database_hash(path) == before


@pytest.mark.parametrize("raw", (
    pytest.param("broken-json", id="invalid-json"), pytest.param("{}", id="object"),
    pytest.param('"string"', id="string"), pytest.param("[null]", id="null-id"),
    pytest.param('["teacher-custom-001"]', id="foreign-namespace"),
    pytest.param('["topic-kinematics-001","topic-kinematics-001"]', id="duplicate-id"),
    pytest.param(None, id="null-value"), pytest.param(b"\xff", id="invalid-utf8"),
))
def test_corrupt_manifest_is_not_guessed_or_overwritten(raw, sync_case):
    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        if raw is None:
            # The current schema refuses SQL NULL itself. Exercise the
            # defensive reader against an older nullable metadata schema.
            db.execute("ALTER TABLE metadata RENAME TO previous_metadata")
            db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)")
            db.execute("INSERT INTO metadata SELECT * FROM previous_metadata")
            db.execute("DROP TABLE previous_metadata")
        db.execute("UPDATE metadata SET value=? WHERE key=?", (raw, module._MANAGED_IDS_KEY))
    before = database_hash(path)
    with pytest.raises(ValueError, match="manifest"):
        module.main()
    assert database_hash(path) == before


@pytest.mark.parametrize("mode", ("empty", "duplicate", "foreign-id"))
def test_invalid_versioned_bank_cannot_clear_existing_data(mode, sync_case, monkeypatch):
    module, path = sync_case
    initialize(module, path)
    first = module.EXERCISES[0]
    bad = {"empty": (), "duplicate": (first, first), "foreign-id": (replace(first, id="foreign"),)}[mode]
    before = database_hash(path)
    monkeypatch.setattr(module, "EXERCISES", bad)
    with pytest.raises(ValueError, match="versioned question IDs"):
        module.main()
    assert database_hash(path) == before


def test_previously_managed_removed_question_is_retired_with_its_notes(sync_case):
    module, path = sync_case
    initialize(module, path)
    stale = "topic-kinematics-999"
    with sqlite3.connect(path) as db:
        clone_question(db, module.EXERCISES[0].id, stale)
        ids = json.loads(db.execute("SELECT value FROM metadata WHERE key=?", (module._MANAGED_IDS_KEY,)).fetchone()[0])
        db.execute("UPDATE metadata SET value=? WHERE key=?", (json.dumps(ids + [stale]), module._MANAGED_IDS_KEY))
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE archived_notes(question_id TEXT REFERENCES ent_practice_questions(question_id) ON DELETE CASCADE,note TEXT)")
        db.execute("INSERT INTO archived_notes VALUES (?,?)", (stale, "Keep retired work"))
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT bank_kind FROM ent_practice_questions WHERE question_id=?", (stale,)).fetchone() == ("retired_practice",)
        assert db.execute("SELECT note FROM archived_notes").fetchall() == [("Keep retired work",)]
        manifest = json.loads(db.execute("SELECT value FROM metadata WHERE key=?", (module._MANAGED_IDS_KEY,)).fetchone()[0])
        assert stale not in manifest and len(manifest) == 2500


@pytest.mark.parametrize("had_manifest", (False, True))
def test_unknown_or_repurposed_old_rows_remain_untouched(had_manifest, sync_case):
    module, path = sync_case
    initialize(module, path)
    stale = "topic-kinematics-999"
    with sqlite3.connect(path) as db:
        clone_question(db, module.EXERCISES[0].id, stale, author="Teacher" if had_manifest else "PhysLab")
        if had_manifest:
            ids = json.loads(db.execute("SELECT value FROM metadata WHERE key=?", (module._MANAGED_IDS_KEY,)).fetchone()[0])
            db.execute("UPDATE metadata SET value=? WHERE key=?", (json.dumps(ids + [stale]), module._MANAGED_IDS_KEY))
        else:
            db.execute("DELETE FROM metadata WHERE key=?", (module._MANAGED_IDS_KEY,))
        before = tuple(db.execute("SELECT * FROM ent_practice_questions WHERE question_id=?", (stale,)).fetchone())
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM ent_practice_questions WHERE question_id=?", (stale,)).fetchone() == before


def test_current_bank_can_reactivate_an_archived_record_without_losing_notes(sync_case):
    module, path = sync_case
    initialize(module, path)
    question_id = module.EXERCISES[0].id
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE ent_practice_questions ADD COLUMN personal_note TEXT DEFAULT ''")
        db.execute("UPDATE ent_practice_questions SET bank_kind='retired_practice',personal_note='Retained' WHERE question_id=?", (question_id,))
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT bank_kind,personal_note FROM ent_practice_questions WHERE question_id=?", (question_id,)).fetchone() == ("practice", "Retained")


def test_legacy_schema_migrates_without_deleting_data(sync_case):
    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        columns = [row for row in db.execute("PRAGMA table_info(ent_practice_questions)")
                   if row[1] not in {"solution_latex_json", "source_pages_json", "bank_kind"}]
        names = ",".join(row[1] for row in columns)
        definitions = ",".join(row[1] + " " + row[2] + (" PRIMARY KEY" if row[5] else "") for row in columns)
        db.execute("ALTER TABLE ent_practice_questions RENAME TO previous_questions")
        db.execute(f"CREATE TABLE ent_practice_questions({definitions})")
        db.execute(f"INSERT INTO ent_practice_questions SELECT {names} FROM previous_questions")
        db.execute("DROP TABLE previous_questions")
        db.execute("DELETE FROM metadata WHERE key=?", (module._MANAGED_IDS_KEY,))
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        assert len(list(db.execute("PRAGMA table_info(ent_practice_questions)"))) == 21
        assert db.execute("SELECT COUNT(*) FROM ent_practice_questions").fetchone() == (2500,)


def test_page_candidates_keep_source_identity_limits_and_unreviewed_status(sync_case):
    module, path = sync_case
    initialize(module, path)
    filename = "Физика Закирова 10.pdf"
    with sqlite3.connect(path) as db:
        db.executemany("INSERT INTO physics_pages VALUES (?,?,?,?,?,?)", [
            (filename, "/owned/a/book.pdf", 12, "page 12", 1, "Механика"),
            (filename, "/owned/a/book.pdf", 12, "duplicate", 1, "Механика"),
            (filename, "/owned/b/book.pdf", 12, "page 12", 1, "Механика"),
            (filename, "/owned/c/book.pdf", 13, "page 13", 1, "Механика"),
            (filename, "/owned/d/book.pdf", 14, "page 14", 1, "Механика"),
        ])
        candidates = module._reference_pages(db)["kinematics"]
        assert len(candidates) == 3
        assert {row["source_path"] for row in candidates} == {"/owned/a/book.pdf", "/owned/b/book.pdf", "/owned/c/book.pdf"}
        assert all(row["status"] == "topic_bucket_candidate_unreviewed" for row in candidates)
    assert module.main() == 0
    with sqlite3.connect(path) as db:
        actual = json.loads(db.execute("SELECT source_pages_json FROM ent_practice_questions WHERE question_id=?", (module.EXERCISES[0].id,)).fetchone()[0])
        assert actual == candidates


def test_broken_existing_page_view_aborts_without_partial_changes(sync_case):
    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE physics_pages")
        db.execute("CREATE VIEW physics_pages AS SELECT missing_column FROM missing_table")
    before = database_hash(path)
    with pytest.raises(sqlite3.OperationalError):
        module.main()
    assert database_hash(path) == before


def test_mid_write_database_failure_rolls_back_questions_and_metadata(sync_case):
    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE ent_practice_questions SET prompt_json='old prompt' WHERE question_id=?", (module.EXERCISES[0].id,))
        db.execute("CREATE TRIGGER owned_failure BEFORE INSERT ON ent_practice_questions WHEN NEW.question_id='topic-dynamics-005' BEGIN SELECT RAISE(ABORT,'owned write failure'); END")
    before = database_hash(path)
    with pytest.raises(sqlite3.IntegrityError, match="owned write failure"):
        module.main()
    assert database_hash(path) == before


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows read-only file semantics")
def test_read_only_database_refuses_and_then_retries_without_data_loss(sync_case):
    module, path = sync_case
    initialize(module, path)
    before = database_hash(path)
    path.chmod(stat.S_IREAD)
    try:
        with pytest.raises(sqlite3.OperationalError):
            module.main()
    finally:
        path.chmod(stat.S_IREAD | stat.S_IWRITE)
    assert database_hash(path) == before
    assert module.main() == 0


def test_sync_works_with_a_low_sqlite_bind_variable_limit(sync_case, monkeypatch):
    module, path = sync_case
    initialize(module, path)
    original_connect = sqlite3.connect

    def limited(*args, **kwargs):
        db = original_connect(*args, **kwargs)
        db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 100)
        return db

    monkeypatch.setattr(module.sqlite3, "connect", limited)
    assert module.main() == 0


def test_actual_cli_from_foreign_directory_mirrors_the_public_bank(tmp_path):
    from aetherlab.core.proc import subprocess_kwargs
    from aetherlab.services.ent_physics_bank import EXERCISES

    profile = tmp_path / "данные Ә"
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "GPT_", "MANIM_"))}
    env.update(AETHERLAB_DATA_DIR=str(profile), AETHERLAB_DISABLE_LEGACY_ENV="1", AETHERLAB_QWEN_AUTOLOAD="0")
    result = subprocess.run([sys.executable, str(ROOT / "tools/sync_ent_practice_bank.py")], cwd=tmp_path,
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, **subprocess_kwargs())
    assert result.returncode == 0, result.stderr
    assert "Synchronized 2500 bank questions" in result.stdout
    with sqlite3.connect(profile / "physlab_reference_library.sqlite3") as db:
        actual = {row[0]: row[1:] for row in db.execute("SELECT question_id,prompt_json,choices_json,correct_indices_json,solution_latex_json,reviewer,source_pages_json FROM ent_practice_questions")}
        assert len(actual) == 2500
        for question in EXERCISES:
            row = actual[question.id]
            assert json.loads(row[0]) == question.prompt
            assert {key: tuple(value) for key, value in json.loads(row[1]).items()} == question.choices
            assert tuple(json.loads(row[2])) == question.correct_indices
            assert tuple(json.loads(row[3])) == question.solution_latex
            assert row[4] == "pending_kazakhstan_physics_teacher" and json.loads(row[5]) == []


def test_process_crash_recovers_the_previous_committed_bank(sync_case, tmp_path):
    from aetherlab.core.proc import subprocess_kwargs

    module, path = sync_case
    initialize(module, path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE ent_practice_questions SET prompt_json='old prompt' WHERE question_id=?", (module.EXERCISES[0].id,))
        db.execute("CREATE TRIGGER owned_crash BEFORE INSERT ON ent_practice_questions WHEN NEW.question_id='topic-dynamics-005' BEGIN SELECT owned_crash(); END")
    before = database_hash(path)
    program = '''
import importlib.util,os,sqlite3,sys
from pathlib import Path
root=Path(sys.argv[1]); sys.path.insert(0,str(root/'tools')); sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location('owned_crashing_sync',root/'tools/sync_ent_practice_bank.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
module._database_path=lambda:Path(sys.argv[2])
connect=sqlite3.connect
def interrupted(*args,**kwargs):
    db=connect(*args,**kwargs); db.create_function('owned_crash',0,lambda:os._exit(7)); return db
module.sqlite3.connect=interrupted
module.main()
'''
    result = subprocess.run([sys.executable, "-c", program, str(ROOT), str(path)], cwd=tmp_path,
        capture_output=True, timeout=30, **subprocess_kwargs())
    assert result.returncode == 7
    assert database_hash(path) == before
