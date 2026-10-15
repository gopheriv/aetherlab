"""Execute F11's complete first-launch path contract with isolated profiles."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aetherlab.core.console import configure_utf8_stdio
from tools.feature_acceptance import (
    DEFAULT_PATH_MODES, DEFAULT_PATH_SOURCES, contract_hash, requirements_for_mode,
)

configure_utf8_stdio()

CHILD = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
home = Path(sys.argv[2])
Path.home = classmethod(lambda cls: home)
from aetherlab.core.settings import load_settings, _default_data_dir, _default_chroma_path
settings = load_settings()
print(json.dumps({"data": str(settings.data_dir), "chroma": str(settings.chroma_path),
    "cache": str(settings.cache_path), "library": str(settings.library_path),
    "default_data": str(_default_data_dir()), "default_chroma": str(_default_chroma_path())}))
'''


def run_acceptance(output: Path, row: dict) -> dict:
    before = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in DEFAULT_PATH_SOURCES}
    checks = []
    with tempfile.TemporaryDirectory(prefix="f11-", dir=ROOT / "tmp") as folder:
        base = Path(folder)
        home = base / "owned home Ә"
        home.mkdir()
        for mode in DEFAULT_PATH_MODES:
            for launch in ("first", "second"):
                cwd = base / f"cwd-{launch}"
                cwd.mkdir(exist_ok=True)
                env = {name: value for name, value in os.environ.items()
                       if not name.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_"))}
                env.pop("LOCALAPPDATA", None)
                local = base / ("local Ә папка" if mode == "unicode" else "local profile")
                if mode != "absent":
                    env["LOCALAPPDATA"] = {"empty": "", "whitespace": " ", "relative": "relative-folder"}.get(mode, str(local))
                env["AETHERLAB_DISABLE_LEGACY_ENV"] = "1"
                env["AETHERLAB_QWEN_AUTOLOAD"] = "0"
                expected = local / "AetherLab" if mode in {"absolute", "unicode"} else home / ".aetherlab"
                completed = subprocess.run(
                    [sys.executable, "-c", CHILD, str(ROOT), str(home)], cwd=cwd, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                )
                assert completed.returncode == 0, f"F11 {mode}/{launch}: child exit {completed.returncode}"
                actual = json.loads(completed.stdout)
                expected_values = {"data": expected, "default_data": expected, "chroma": expected / "chroma",
                                   "default_chroma": expected / "chroma", "cache": expected / "cache.sqlite3",
                                   "library": expected / "library"}
                assert all(Path(actual[key]) == value for key, value in expected_values.items()), f"F11 path mismatch in {mode}/{launch}"
                assert not list(cwd.iterdir()), "Default resolution created working-directory state"
                checks.append({"id": f"{mode}-{launch}", "status": "PASS",
                               "covers": sorted(requirements_for_mode(mode)), "paths": actual})
    after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in DEFAULT_PATH_SOURCES}
    assert after == before, "F11 implementation changed during acceptance"
    evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": "F11", "status": "PASS",
                "exit_code": 0, "completed_at": datetime.now(UTC).isoformat(),
                "contract_sha256": contract_hash(row), "source_sha256": after, "checks": checks,
                "scope": "Executed actual load_settings/default functions in 12 fresh isolated processes; environment branches, not native packaging on another OS"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": output.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == "__main__":
    import build_feature_tracker as tracker
    tracker.apply_results({})
    row = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F11")))
    pointer = run_acceptance(ROOT / "tmp/default-path-acceptance-20261014.json", row)
    print(json.dumps(pointer))
