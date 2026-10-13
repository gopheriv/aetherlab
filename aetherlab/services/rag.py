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
        if chroma is not None and chroma.hits:
            return chroma

        # A collection can exist and still contain no pages relevant to this
        # language/query. An empty vector result must not suppress the local
        # textbook search, which may see files that have not been indexed yet.
        return self._filesystem_search(clean_keywords, limit)

    def _try_chromadb(self, keywords: list[str], limit: int) -> RagResult | None:
        try:
            import chromadb
        except Exception:
            return None

        if not self.settings.chroma_path.exists():
            return None

        # Over-fetch a wider candidate pool than we intend to return, so the
        # rerank + diversity pass below has room to drop near-duplicate chunks
        # (the same passage indexed twice, or five chunks off one page) and
        # still hand back `limit` distinct, on-topic citations.
        pool = max(limit * 4, limit + 8)
        try:
            client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
            collection = client.get_collection("textbooks")
            result = collection.query(query_texts=[" ".join(keywords)], n_results=pool)
        except Exception:
            return None

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        candidates: list[RagHit] = []
        for document, metadata, distance in zip(documents, metadatas, distances, strict=False):
            metadata = metadata or {}
            excerpt = _trim(str(document))
            # Vector relevance in (0, 1]; a smaller Chroma distance ranks higher.
            vector = float(1.0 / (1.0 + float(distance or 0.0)))
            # Hybrid signal: reward candidates that also contain the literal
            # query terms. Pure-vector retrieval can drift to thematically-near
            # passages that never mention the actual quantity being asked about;
            # a lexical boost pulls exact-term matches back to the top.
            boosted = vector * (1.0 + _lexical_overlap(str(document), keywords))
            candidates.append(
                RagHit(
                    source_path=str(metadata.get("path", "chromadb:textbooks")),
                    page_number=_coerce_page(metadata.get("page")),
                    score=boosted,
                    excerpt=excerpt,
                )
            )

        deduped = _dedup_hits(candidates)
        selected = _mmr_select(deduped, limit)
        _normalize_scores(selected)
        return RagResult(keywords=keywords, hits=selected, backend="chromadb")

    def _filesystem_search(self, keywords: list[str], limit: int) -> RagResult:
        root = self.settings.library_path
        paths = (
            {
                path for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in (TEXT_SUFFIXES | PDF_SUFFIXES)
            }
            if root.exists()
            else set()
        )
        reference_root = getattr(self.settings, "reference_sources_path", None)
        if reference_root:
            try:
                from aetherlab.services.reference_catalog import searchable_reference_files

                paths.update(searchable_reference_files(reference_root))
            except Exception:  # noqa: BLE001 - local fallback must remain available
                pass
        if not paths:
            return RagResult(keywords=keywords, hits=[], backend="filesystem-missing-library")

        hits: list[RagHit] = []
        for path in sorted(paths, key=lambda item: str(item).casefold()):
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
        top = _dedup_hits(hits)[:limit]
        # Raw scores are keyword counts (unbounded). Normalize to [0,1] against
        # the strongest hit so the UI's score pill/label — which assume a 0-1
        # relevance like the ChromaDB backend — stay meaningful and comparable.
        _normalize_scores(top)
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


_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    """Lowercase word tokens, dropping 1–2 char noise that inflates overlap."""
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2}


def _lexical_overlap(document: str, keywords: list[str]) -> float:
    """Fraction of query keywords the document literally contains, in [0, 1].

    Used as a multiplicative boost on top of vector relevance so exact-term
    matches outrank merely thematically-similar passages.
    """
    terms = [k.lower() for k in keywords if k.strip()]
    if not terms:
        return 0.0
    lower = document.lower()
    return sum(1 for term in terms if term in lower) / len(terms)


def _jaccard(a: set[str], b: set[str]) -> float:
    """Token-set similarity in [0, 1]; 0 when either side is empty."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


def _dedup_hits(hits: list[RagHit]) -> list[RagHit]:
    """Collapse hits that point at the same (path, page) or carry a near-
    identical excerpt, keeping the highest-scoring representative. Preserves
    input order among survivors so a prior sort is respected.
    """
    survivors: list[RagHit] = []
    seen_loc: set[tuple[str, int | None]] = set()
    kept_tokens: list[set[str]] = []
    for hit in sorted(hits, key=lambda h: h.score, reverse=True):
        loc = (hit.source_path, hit.page_number)
        if loc in seen_loc:
            continue
        tokens = _tokens(hit.excerpt)
        if any(_jaccard(tokens, prev) >= 0.85 for prev in kept_tokens):
            continue
        seen_loc.add(loc)
        kept_tokens.append(tokens)
        survivors.append(hit)
    return survivors


def _mmr_select(hits: list[RagHit], limit: int, diversity: float = 0.3) -> list[RagHit]:
    """Maximal-marginal-relevance selection: greedily pick the next hit that is
    both relevant (high score) and novel (low excerpt overlap with those already
    chosen), so the returned citations span sources instead of restating one.

    ``diversity`` (0 → pure relevance, 1 → pure novelty) is kept modest: citation
    quality still leads, diversity only breaks ties among comparably-relevant hits.
    """
    if limit <= 0 or not hits:
        return []
    ranked = sorted(hits, key=lambda h: h.score, reverse=True)
    if len(ranked) <= limit:
        return ranked
    pool = ranked[:]
    selected: list[RagHit] = [pool.pop(0)]
    selected_tokens = [_tokens(selected[0].excerpt)]
    best = ranked[0].score or 1.0
    while pool and len(selected) < limit:
        best_idx, best_mmr = 0, float("-inf")
        for idx, hit in enumerate(pool):
            relevance = (hit.score / best) if best else 0.0
            tokens = _tokens(hit.excerpt)
            redundancy = max((_jaccard(tokens, s) for s in selected_tokens), default=0.0)
            mmr = (1.0 - diversity) * relevance - diversity * redundancy
            if mmr > best_mmr:
                best_idx, best_mmr = idx, mmr
        chosen = pool.pop(best_idx)
        selected.append(chosen)
        selected_tokens.append(_tokens(chosen.excerpt))
    return selected


def _normalize_scores(hits: list[RagHit]) -> None:
    """Rescale scores in place to [0, 1] against the strongest hit, so the UI's
    relevance pill stays comparable across the chromadb and filesystem backends.
    """
    best = max((h.score for h in hits), default=0.0)
    if best > 0:
        for hit in hits:
            hit.score = hit.score / best
