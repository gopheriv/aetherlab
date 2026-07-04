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

datas = [(str(ROOT / "assets" / "aetherlab.ico"), "assets")]
binaries = []
hiddenimports = [
    "aetherlab",
    "PyQt6.QtSvg",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
]

for package in ("manim", "chromadb", "av"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

# Metadata-only requirements (version lookups at import time).
for dist in ("manim", "numpy", "openai", "matplotlib", "pillow", "chromadb"):
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
