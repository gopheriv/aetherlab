"""One-command Windows build: PyInstaller → dist smoke test → Inno installer.

Run from the repo root:  python packaging/build.py [--skip-installer]

Steps:
1. pyinstaller packaging/aetherlab.spec  →  dist/aetherlab/
2. Smoke-test the frozen app: `dist/aetherlab/aetherlab.exe --smoke` must
   exit 0 with NO provider configured (exercises the keyless fallback path,
   the domain templates, and a real Manim render inside the bundle).
3. iscc packaging/installer.iss  →  dist/AetherLab-Setup-<version>.exe
   (skipped with a warning when Inno Setup isn't installed).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "aetherlab"


def run(cmd: list[str], **kw) -> None:
    print(f"\n$ {' '.join(str(c) for c in cmd)}", flush=True)
    subprocess.run(cmd, check=True, cwd=str(ROOT), **kw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-installer", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from aetherlab import __version__

    print(f"Building AetherLab {__version__}")

    # 1 — freeze
    run([sys.executable, "-m", "PyInstaller", "packaging/aetherlab.spec", "--noconfirm"])
    exe = DIST / "aetherlab.exe"
    if not exe.exists():
        print("FATAL: PyInstaller produced no exe", file=sys.stderr)
        return 1

    # 2 — smoke test the frozen app with a clean, keyless environment
    env = dict(os.environ)
    for var in (
        "AETHERLAB_OPENAI_API_KEY", "OPENAI_API_KEY", "AETHERLAB_OPENAI_BASE_URL",
        "OPENAI_BASE_URL", "AETHERLAB_LLM_MODEL", "AETHERLAB_QWEN_AUTOLOAD",
        "AETHERLAB_PROVIDER",
    ):
        env.pop(var, None)
    env["AETHERLAB_DATA_DIR"] = str(ROOT / "dist" / "_smoke_data")
    env["AETHERLAB_CHROMA_PATH"] = str(ROOT / "dist" / "_smoke_data" / "chroma")
    print("\nSmoke-testing the frozen bundle (keyless)…", flush=True)
    result = subprocess.run(
        [str(exe), "--smoke", "Solve the simple pendulum"],
        capture_output=True, text=True, timeout=900, env=env,
    )
    print(result.stdout[-2000:])
    if result.returncode != 0:
        print(f"FATAL: frozen smoke test exited {result.returncode}", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return 1
    # Exit 0 is not enough: the pipeline degrades gracefully, so a broken
    # frozen renderer still exits cleanly with status render-error. The
    # bundle only ships if a video ACTUALLY rendered inside it.
    if "Scene status: rendered" not in result.stdout:
        print(
            "FATAL: frozen bundle did not produce a rendered video "
            "(see 'Scene status:' above) — refusing to package.",
            file=sys.stderr,
        )
        return 1
    print("Frozen smoke test PASSED (video rendered inside the bundle)")

    # 3 — installer
    if args.skip_installer:
        print("Skipping installer (--skip-installer)")
        return 0
    iscc = shutil.which("iscc") or shutil.which(
        "ISCC", path=r"C:\Program Files (x86)\Inno Setup 6"
    )
    if not iscc:
        for candidate in (
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ):
            if Path(candidate).exists():
                iscc = candidate
                break
    if not iscc:
        print(
            "WARNING: Inno Setup (iscc) not found — dist/aetherlab is ready but no "
            "Setup exe was produced. Install from jrsoftware.org and re-run."
        )
        return 0
    run([iscc, f"/DMyAppVersion={__version__}", "packaging/installer.iss"])
    setup = ROOT / "dist" / f"AetherLab-Setup-{__version__}.exe"
    print(f"\nDONE: {setup} ({setup.stat().st_size / 1e6:.0f} MB)"
          if setup.exists() else "\nWARNING: installer output not found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
