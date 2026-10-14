"""OpenStax starter-library catalog and downloader (pure Python, no Qt).

OpenStax textbooks are CC BY 4.0 — free to download and redistribute with
attribution. URLs are resolved live from the OpenStax CMS API with hardcoded
fallbacks, so catalog drift degrades gracefully instead of breaking.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_CMS_API = (
    "https://openstax.org/apps/cms/api/v2/pages/"
    "?type=books.Book&fields=title,high_resolution_pdf_url&format=json&limit=250"
)
_CHUNK_BYTES = 256 * 1024
_SKIP_MIN_BYTES = 5 * 1024 * 1024  # existing file > 5 MB counts as downloaded
_UA = {"User-Agent": "AetherLab/1.0 (starter-library downloader)"}


@dataclass(frozen=True)
class StarterBook:
    key: str
    title: str
    filename: str
    fallback_url: str
    approx_mb: int
    default_checked: bool


# Titles MUST match the OpenStax CMS book titles exactly (case-insensitive) so
# resolve_pdf_urls() can map them to current high-resolution PDF URLs; the
# fallback_url is the CMS URL verified at authoring time. approx_mb is the real
# Content-Length (HEAD) rounded up. The calculus-based University Physics
# trilogy is the default core; astronomy + calculus + the algebra-based survey
# are opt-in extras that deepen coverage (gravitation/orbits, the calculus that
# underpins every derivation, and a broad algebra-based cross-reference).
STARTER_BOOKS: tuple[StarterBook, ...] = (
    StarterBook(
        key="university-physics-volume-1",
        title="University Physics Volume 1",
        filename="OpenStax - University Physics Vol 1.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/university-physics-volume-1_-_WEB.pdf",
        approx_mb=82,  # mechanics, oscillations, waves, gravitation, thermodynamics
        default_checked=True,
    ),
    StarterBook(
        key="university-physics-volume-2",
        title="University Physics Volume 2",
        filename="OpenStax - University Physics Vol 2.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/university-physics-volume-2_-_WEB.pdf",
        approx_mb=64,  # electricity & magnetism, circuits, electromagnetic waves, optics
        default_checked=True,
    ),
    StarterBook(
        key="university-physics-volume-3",
        title="University Physics Volume 3",
        filename="OpenStax - University Physics Vol 3.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/university-physics-volume-3_-_WEB.pdf",
        approx_mb=54,  # optics, relativity, quantum mechanics, nuclear & particle physics
        default_checked=True,
    ),
    StarterBook(
        key="astronomy-2e",
        title="Astronomy 2e",
        filename="OpenStax - Astronomy 2e.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/astronomy-2e_-_WEB.pdf",
        approx_mb=163,  # gravitation, orbital mechanics, Kepler, celestial dynamics, astrophysics
        default_checked=False,
    ),
    StarterBook(
        key="calculus-volume-1",
        title="Calculus Volume 1",
        filename="OpenStax - Calculus Vol 1.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/calculus-volume-1_-_WEB.pdf",
        approx_mb=53,  # limits, derivatives, integration — foundations of every derivation
        default_checked=False,
    ),
    StarterBook(
        key="calculus-volume-2",
        title="Calculus Volume 2",
        filename="OpenStax - Calculus Vol 2.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/calculus-volume-2_-_WEB.pdf",
        approx_mb=48,  # integration techniques, sequences & series, intro differential equations
        default_checked=False,
    ),
    StarterBook(
        key="calculus-volume-3",
        title="Calculus Volume 3",
        filename="OpenStax - Calculus Vol 3.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/calculus-volume-3_-_WEB.pdf",
        approx_mb=80,  # parametric/polar, vectors, multivariable & vector calculus
        default_checked=False,
    ),
    StarterBook(
        key="college-physics-2e",
        title="College Physics 2e",
        filename="OpenStax - College Physics 2e.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/college-physics-2e_-_WEB.pdf",
        approx_mb=264,  # broad algebra-based survey — wide cross-reference, large file
        default_checked=False,
    ),
    StarterBook(
        key="physics",
        title="Physics",
        filename="OpenStax - Physics.pdf",
        fallback_url="https://assets.openstax.org/oscms-prodcms/media/documents/Physics_-_WEB.pdf",
        approx_mb=55,  # algebra-based intro survey — plainer prose deepens retrieval recall
        default_checked=False,
    ),
)

_ATTRIBUTION = """OpenStax textbooks in this folder
=================================

These PDF textbooks were downloaded from OpenStax (https://openstax.org),
published by OpenStax, Rice University.

License: Creative Commons Attribution 4.0 International (CC BY 4.0)
         https://creativecommons.org/licenses/by/4.0/

Attribution: "Download for free at https://openstax.org."

The books are unmodified. OpenStax and Rice University do not endorse
AetherLab. Access the current editions at https://openstax.org/subjects.
"""


def resolve_pdf_urls(books: list[StarterBook]) -> dict[str, str]:
    """Map book.key -> current PDF URL via the OpenStax CMS API.

    Titles are matched case-insensitively; any miss or any exception falls
    back to the hardcoded URL. Never raises.
    """
    urls = {book.key: book.fallback_url for book in books}
    try:
        request = urllib.request.Request(_CMS_API, headers=_UA)
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        by_title = {}
        for item in payload.get("items", []):
            title = str(item.get("title", "")).strip().lower()
            url = item.get("high_resolution_pdf_url")
            if title and isinstance(url, str) and url.startswith("http"):
                by_title[title] = url
        for book in books:
            match = by_title.get(book.title.strip().lower())
            if match:
                urls[book.key] = match
    except Exception:
        pass  # fallback URLs already in place
    return urls


def download_book(
    book: StarterBook,
    url: str,
    dest_dir: Path,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> Path | None:
    """Stream a book PDF to dest_dir. Returns the final path, or None if
    cancelled. Skips (returns existing path) when already downloaded.

    Downloads to `<name>.part` and atomically renames on success, so a killed
    download never leaves a half-file that looks complete.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / book.filename
    if final.exists() and final.stat().st_size > _SKIP_MIN_BYTES:
        if progress_cb:
            size = final.stat().st_size
            progress_cb(size, size)
        return final

    part = final.with_suffix(final.suffix + ".part")
    request = urllib.request.Request(url, headers=_UA)
    response = urllib.request.urlopen(request, timeout=60)
    try:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(part, "wb") as fh:
            while True:
                if cancel_check and cancel_check():
                    fh.close()
                    part.unlink(missing_ok=True)
                    return None
                chunk = response.read(_CHUNK_BYTES)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    finally:
        response.close()

    try:
        os.replace(part, final)
    except OSError:
        # Windows AV scanners briefly lock fresh files — one short retry.
        time.sleep(1.0)
        os.replace(part, final)
    return final


def write_attribution(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "ATTRIBUTION-openstax.txt"
    path.write_text(_ATTRIBUTION, encoding="utf-8")
    return path


def free_disk_mb(path: Path) -> float:
    import shutil

    target = path
    while not target.exists() and target.parent != target:
        target = target.parent
    return shutil.disk_usage(target).free / 1e6
