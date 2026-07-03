"""Library ingestion utilities for the ChromaDB textbook store.

Ingestion streams per file (large PDFs never materialize all chunks at once),
reports progress per batch, honors cancellation between batches, and keeps a
manifest so unchanged files are skipped on re-runs (incremental by default).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aetherlab.core.settings import AppSettings

TEXT_SUFFIXES = {".txt", ".md", ".tex"}
PDF_SUFFIXES = {".pdf"}

# progress(file_name, files_done, files_total, detail)
ProgressCb = Callable[[str, int, int, str], None]


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    text: str
    metadata: dict[str, str | int]


def chunk_text(text: str, *, max_chars: int = 1400, overlap: int = 180) -> list[str]:
    compact = " ".join(text.split())
    if not compact:
        return []
    if len(compact) <= max_chars:
        return [compact]

    chunks: list[str] = []
    start = 0
    while start < len(compact):
        end = min(start + max_chars, len(compact))
        if end < len(compact):
            boundary = max(
                compact.rfind(". ", start + max_chars // 2, end),
                compact.rfind("; ", start + max_chars // 2, end),
                compact.rfind("\n", start + max_chars // 2, end),
            )
            if boundary > start:
                end = boundary + 1
        chunks.append(compact[start:end].strip())
        if end >= len(compact):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


class LibraryIngestor:
    def __init__(self, settings: AppSettings, collection_name: str = "textbooks") -> None:
        self.settings = settings
        self.collection_name = collection_name

    def iter_chunks(self) -> list[TextChunk]:
        root = self.settings.library_path
        if not root.exists():
            return []

        chunks: list[TextChunk] = []
        for path in sorted(root.rglob("*")):
            suffix = path.suffix.lower()
            if suffix in TEXT_SUFFIXES:
                chunks.extend(self._chunks_from_text_file(path))
            elif suffix in PDF_SUFFIXES:
                chunks.extend(self._chunks_from_pdf(path))
        return chunks

    # ── manifest (incremental ingestion state) ──

    def manifest_path(self) -> Path:
        return self.settings.data_dir / "ingest_manifest.json"

    def _load_manifest(self) -> dict[str, dict]:
        path = self.manifest_path()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_manifest(self, manifest: dict[str, dict]) -> None:
        path = self.manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _file_signature(path: Path) -> dict:
        stat = path.stat()
        return {"mtime": stat.st_mtime, "size": stat.st_size}

    def _library_files(self) -> list[Path]:
        root = self.settings.library_path
        if not root.exists():
            return []
        return sorted(
            p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in (TEXT_SUFFIXES | PDF_SUFFIXES)
        )

    def pending_files(self) -> list[Path]:
        """Files new or changed since the last ingest (per the manifest)."""
        manifest = self._load_manifest()
        pending = []
        for path in self._library_files():
            entry = manifest.get(str(path))
            sig = self._file_signature(path)
            if not entry or entry.get("mtime") != sig["mtime"] or entry.get("size") != sig["size"]:
                pending.append(path)
        return pending

    def ingest(
        self,
        *,
        reset: bool = False,
        progress: ProgressCb | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> int:
        """Ingest the library per file. Incremental unless reset=True.

        Returns the number of chunks upserted this run (0 when everything was
        already up to date). Cancellation between batches returns the partial
        count; the manifest is updated after each completed file, so a
        cancelled run resumes where it left off.
        """
        try:
            import chromadb
        except Exception as exc:
            raise RuntimeError(
                "ChromaDB is not installed. Install the rag extra with: "
                "python -m pip install -e .[rag]"
            ) from exc

        self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
        if reset:
            try:
                client.delete_collection(self.collection_name)
            except Exception:
                pass
            try:
                self.manifest_path().unlink()
            except OSError:
                pass
        collection = client.get_or_create_collection(self.collection_name)

        manifest = self._load_manifest()
        files = self._library_files()
        todo = [p for p in files if self._needs_ingest(manifest, p)]
        total_files = len(todo)
        batch_size = 96
        upserted = 0

        for file_index, path in enumerate(todo):
            if should_cancel and should_cancel():
                return upserted
            if progress:
                progress(path.name, file_index, total_files, "reading")

            chunks = self._chunks_for_file(path)
            file_chunks = 0
            cancelled = False
            for start in range(0, len(chunks), batch_size):
                if should_cancel and should_cancel():
                    cancelled = True
                    break
                batch = chunks[start : start + batch_size]
                collection.upsert(
                    ids=[chunk.chunk_id for chunk in batch],
                    documents=[chunk.text for chunk in batch],
                    metadatas=[chunk.metadata for chunk in batch],
                )
                file_chunks += len(batch)
                upserted += len(batch)
                if progress:
                    progress(
                        path.name, file_index, total_files,
                        f"{start + len(batch):,} / {len(chunks):,} chunks",
                    )

            if cancelled:
                # Chunk ids are deterministic, so the partially-upserted file is
                # simply re-processed on the next run (not in the manifest yet).
                return upserted

            manifest[str(path)] = {**self._file_signature(path), "chunks": len(chunks)}
            self._save_manifest(manifest)

        return upserted

    def _needs_ingest(self, manifest: dict[str, dict], path: Path) -> bool:
        entry = manifest.get(str(path))
        if not entry:
            return True
        sig = self._file_signature(path)
        return entry.get("mtime") != sig["mtime"] or entry.get("size") != sig["size"]

    def _chunks_for_file(self, path: Path) -> list[TextChunk]:
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            return self._chunks_from_text_file(path)
        if suffix in PDF_SUFFIXES:
            return self._chunks_from_pdf(path)
        return []

    def _chunks_from_text_file(self, path: Path) -> list[TextChunk]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        return [
            TextChunk(
                chunk_id=_chunk_id(path, index),
                text=chunk,
                metadata={"path": str(path), "chunk": index, "kind": "text"},
            )
            for index, chunk in enumerate(chunk_text(text), start=1)
        ]

    def _chunks_from_pdf(self, path: Path) -> list[TextChunk]:
        try:
            import fitz
        except Exception:
            return []

        chunks: list[TextChunk] = []
        try:
            document = fitz.open(path)
        except Exception:
            return []

        try:
            for page_index in range(document.page_count):
                text = document.load_page(page_index).get_text("text")
                for chunk_index, chunk in enumerate(chunk_text(text), start=1):
                    chunks.append(
                        TextChunk(
                            chunk_id=_chunk_id(path, page_index + 1, chunk_index),
                            text=chunk,
                            metadata={
                                "path": str(path),
                                "page": page_index + 1,
                                "chunk": chunk_index,
                                "kind": "pdf",
                            },
                        )
                    )
        finally:
            document.close()
        return chunks


def _chunk_id(path: Path, *parts: int) -> str:
    safe_path = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(path.resolve()))
    suffix = "_".join(str(part) for part in parts)
    return f"{safe_path}_{suffix}"
