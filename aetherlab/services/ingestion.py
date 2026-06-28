"""Library ingestion utilities for the ChromaDB textbook store."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from aetherlab.core.settings import AppSettings


TEXT_SUFFIXES = {".txt", ".md", ".tex"}
PDF_SUFFIXES = {".pdf"}


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

    def ingest(self, *, reset: bool = False) -> int:
        try:
            import chromadb
        except Exception as exc:
            raise RuntimeError("ChromaDB is not installed. Install the rag extra with: python -m pip install -e .[rag]") from exc

        self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
        if reset:
            try:
                client.delete_collection(self.collection_name)
            except Exception:
                pass
        collection = client.get_or_create_collection(self.collection_name)
        chunks = self.iter_chunks()
        if not chunks:
            return 0

        batch_size = 96
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            collection.upsert(
                ids=[chunk.chunk_id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                metadatas=[chunk.metadata for chunk in batch],
            )
        return len(chunks)

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
