"""Local textbook retrieval through ChromaDB with filesystem fallback."""

from __future__ import annotations

import math
import re
from pathlib import Path

from aetherlab.core.models import RagHit, RagResult
from aetherlab.core.settings import AppSettings

TEXT_SUFFIXES = {".txt", ".md", ".tex"}
PDF_SUFFIXES = {".pdf"}


class LocalVectorRag:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    async def search(self, keywords: list[str], limit: int = 5) -> RagResult:
        clean_keywords = [keyword for keyword in keywords if keyword.strip()]
        if not clean_keywords:
            return RagResult(keywords=[], hits=[], backend="none")

        chroma = self._try_chromadb(clean_keywords, limit)
        if chroma is not None:
            return chroma

        return self._filesystem_search(clean_keywords, limit)

    def _try_chromadb(self, keywords: list[str], limit: int) -> RagResult | None:
        try:
            import chromadb
        except Exception:
            return None

        if not self.settings.chroma_path.exists():
            return None

        try:
            client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
            collection = client.get_collection("textbooks")
            result = collection.query(query_texts=[" ".join(keywords)], n_results=limit)
        except Exception:
            return None

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[RagHit] = []
        for document, metadata, distance in zip(documents, metadatas, distances, strict=False):
            metadata = metadata or {}
            hits.append(
                RagHit(
                    source_path=str(metadata.get("path", "chromadb:textbooks")),
                    page_number=_coerce_page(metadata.get("page")),
                    score=float(1.0 / (1.0 + float(distance or 0.0))),
                    excerpt=_trim(str(document)),
                )
            )
        return RagResult(keywords=keywords, hits=hits, backend="chromadb")

    def _filesystem_search(self, keywords: list[str], limit: int) -> RagResult:
        root = self.settings.library_path
        if not root.exists():
            return RagResult(keywords=keywords, hits=[], backend="filesystem-missing-library")

        hits: list[RagHit] = []
        for path in sorted(root.rglob("*")):
            if len(hits) >= limit * 3:
                break
            if path.suffix.lower() in TEXT_SUFFIXES:
                hit = self._score_text_file(path, keywords)
                if hit:
                    hits.append(hit)
            elif path.suffix.lower() in PDF_SUFFIXES:
                hit = self._score_pdf(path, keywords)
                if hit:
                    hits.append(hit)

        hits.sort(key=lambda item: item.score, reverse=True)
        top = hits[:limit]
        # Raw scores are keyword counts (unbounded). Normalize to [0,1] against
        # the strongest hit so the UI's score pill/label — which assume a 0-1
        # relevance like the ChromaDB backend — stay meaningful and comparable.
        best = top[0].score if top else 0.0
        if best > 0:
            for hit in top:
                hit.score = hit.score / best
        return RagResult(keywords=keywords, hits=top, backend="filesystem")

    def _score_text_file(self, path: Path, keywords: list[str]) -> RagHit | None:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        return _score_text(path, text, None, keywords)

    def _score_pdf(self, path: Path, keywords: list[str]) -> RagHit | None:
        try:
            import fitz
        except Exception:
            return None

        try:
            document = fitz.open(path)
        except Exception:
            return None

        best: RagHit | None = None
        try:
            # Strided sampling: cover the whole book at a fixed cost ceiling
            # (<= 40 pages). Small documents are read page-by-page as before;
            # a 1500-page textbook is sampled every ~38th page instead of only
            # its front matter.
            page_count = document.page_count
            stride = max(1, math.ceil(page_count / 40))
            for index in range(0, page_count, stride):
                text = document.load_page(index).get_text("text")
                hit = _score_text(path, text, index + 1, keywords)
                if hit and (best is None or hit.score > best.score):
                    best = hit
        finally:
            document.close()
        return best


def _coerce_page(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _score_text(path: Path, text: str, page: int | None, keywords: list[str]) -> RagHit | None:
    if not text.strip():
        return None
    lower = text.lower()
    score = sum(lower.count(keyword.lower()) for keyword in keywords)
    if score <= 0:
        return None

    first_keyword = next((keyword for keyword in keywords if keyword.lower() in lower), keywords[0])
    match = re.search(re.escape(first_keyword), text, re.IGNORECASE)
    start = max((match.start() if match else 0) - 180, 0)
    excerpt = _trim(text[start : start + 520])
    return RagHit(source_path=str(path), page_number=page, score=float(score), excerpt=excerpt)


def _trim(text: str, limit: int = 420) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
