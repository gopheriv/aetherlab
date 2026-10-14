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
        chunks: list[TextChunk] = []
        for path in self._library_files():
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
        reference_root = getattr(self.settings, "reference_sources_path", None)
        same_as_reference_root = False
        if reference_root:
            try:
                same_as_reference_root = root.resolve() == Path(reference_root).resolve()
            except OSError:
                pass
        files = (
            {
                p for p in root.rglob("*")
                if p.is_file() and p.suffix.lower() in (TEXT_SUFFIXES | PDF_SUFFIXES)
            }
            if root.exists() and not same_as_reference_root
            else set()
        )
        # The provided study books are external, read-only references. Exam
        # packs and mixed ZIP contents are intentionally excluded from RAG.
        if reference_root:
            try:
                from aetherlab.services.reference_catalog import searchable_reference_files

                files.update(searchable_reference_files(reference_root))
            except Exception:  # noqa: BLE001 - local reference discovery is fail-soft
                pass
        return sorted(files, key=lambda path: str(path).casefold())

    def pending_files(self) -> list[Path]:
        """Files new or changed since the last ingest (per the manifest)."""
        manifest = self._load_manifest()
        pending = []
        for path in self._library_files():
            entry = manifest.get(str(path))
            sig = self._file_signature(path)
            if not entry or entry.get("mtime") != sig["mtime"] or entry.get("size") != sig["size"]:
                pending.append(path)
        pending.extend(Path(key) for key in self._stale_reference_manifest_keys(manifest))
        return pending

    def _stale_reference_manifest_keys(self, manifest: dict[str, dict]) -> list[str]:
        """Find formerly indexed files in the source folder no longer in its curated catalog."""
        reference_root = getattr(self.settings, "reference_sources_path", None)
        if not reference_root:
            return []
        try:
            from aetherlab.services.reference_catalog import searchable_reference_files

            root = Path(reference_root).resolve()
            allowed = {str(path.resolve()).casefold() for path in searchable_reference_files(root)}
        except Exception:  # noqa: BLE001 - do not block the library if catalog lookup fails
            return []

        stale: list[str] = []
        for key in manifest:
            try:
                path = Path(key).resolve()
                path.relative_to(root)
            except (OSError, ValueError):
                continue
            if str(path).casefold() not in allowed:
                stale.append(key)
        return stale

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
        stale_keys = self._stale_reference_manifest_keys(manifest)
        removed = False
        for key in stale_keys:
            try:
                collection.delete(where={"path": key})
            except Exception:  # noqa: BLE001 - retain the manifest if Chroma couldn't delete
                continue
            manifest.pop(key, None)
            removed = True
        if removed:
            self._save_manifest(manifest)
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
            self._delete_existing_chunks(collection, path)
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

    @staticmethod
    def _delete_existing_chunks(collection, path: Path) -> None:
        """Drop stale chunks for a changed file before re-upserting it.

        Chroma upsert replaces matching ids but does not remove ids that no
        longer exist after a file shrinks or a PDF extraction changes shape.
        Those orphan chunks keep showing up in retrieval unless we delete by
        the stable path metadata first.
        """
        try:
            collection.delete(where={"path": str(path)})
        except Exception:
            # Older/alternate Chroma clients may reject metadata deletes; keep
            # ingestion fail-soft rather than blocking the user's library.
            pass

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
