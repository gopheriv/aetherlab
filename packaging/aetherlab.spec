# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the AetherLab Windows distribution (onedir).

Build from the repo root:  pyinstaller packaging/aetherlab.spec --noconfirm

Notes on the awkward passengers:
- manim resolves its version/plugins via importlib.metadata -> copy_metadata,
  and ships templates/config data -> collect_all.
- chromadb carries native libs (hnswlib/sqlite bindings) and migration data.
- matplotlib is used ONLY for mathtext (services/mathtext.py); the tk backend
  and sample data are excluded to keep the bundle lean.
- av (PyAV) provides Manim's encoder and the critic's frame sampling.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = Path(SPECPATH).parent  # repo root (spec lives in packaging/)

datas = [
    (str(ROOT / "assets" / "aetherlab.ico"), "assets"),
    (str(ROOT / "assets" / "ui" / "chevron-down.svg"), "assets/ui"),
    (str(ROOT / "assets" / "ui" / "check.svg"), "assets/ui"),
    (
        str(ROOT / "assets" / "ui" / "companion-contact-sheets" / "physics-companions-overview-4k.png"),
        "assets/ui/companion-contact-sheets",
    ),
    (str(ROOT / "assets" / "ui" / "companion-contact-sheets" / "quantum-evolution-4k.png"), "assets/ui/companion-contact-sheets"),
    (str(ROOT / "assets" / "ui" / "companion-contact-sheets" / "photon-evolution-4k.png"), "assets/ui/companion-contact-sheets"),
    (str(ROOT / "assets" / "ui" / "companion-contact-sheets" / "lab-bot-evolution-4k.png"), "assets/ui/companion-contact-sheets"),
    # DejaVu fonts drive the produced-lesson title cards (services/cards.py);
    # miss them and cards fall back to PIL's tiny bitmap font.
    (str(ROOT / "assets" / "fonts" / "DejaVuSans.ttf"), "assets/fonts"),
    (str(ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"), "assets/fonts"),
]
binaries = []
hiddenimports = [
    "aetherlab",
    "PyQt6.QtSvg",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    # Manim's CLI + plugin machinery (imported lazily → not auto-detected).
    "manim.__main__",
    "manim.plugins",
    "manim.utils.commands",
    "cloup",
    "click",
]

# The Manim render subprocess needs its whole native ecosystem, not just the
# `manim` package: manimpango renders EVERY Text/MarkupText (all our fallback
# templates use Text — miss it and every render fails), skia-pathops does path
# boolean ops, moderngl backs the OpenGL renderer, av (PyAV) is the encoder.
# collect_all pulls each package's data files, compiled libs, and submodules.
_COLLECT = (
    "manim", "manimpango", "skia_pathops", "moderngl", "moderngl_window",
    "chromadb", "av", "cloup", "pygments", "imageio_ffmpeg", "edge_tts",
)
for package in _COLLECT:
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass  # optional passenger (e.g. imageio_ffmpeg) not installed — skip

# Metadata-only requirements (importlib.metadata version/entry-point lookups).
for dist in ("manim", "manimpango", "numpy", "openai", "matplotlib", "pillow",
             "chromadb", "cloup", "click"):
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "aetherlab" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib.backends.backend_tkagg",
        "matplotlib.tests",
        "PyQt5",
        "PySide6",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="aetherlab",
    icon=str(ROOT / "assets" / "aetherlab.ico"),
    debug=False,
    strip=False,
    upx=False,
    console=False,  # GUI app; --smoke still works, just without a console window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="aetherlab",
)
