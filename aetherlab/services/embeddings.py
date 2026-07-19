"""Local, offline, fail-soft text embeddings — the semantic-similarity leaf.

An embedding model maps text to a fixed-length unit vector where semantically
similar text lands nearby, so "nearness" (cosine similarity == dot product of
unit vectors) means "similar meaning". This module reuses ChromaDB's bundled
sentence model (all-MiniLM-L6-v2, ONNX, CPU) — already a dependency of the
``[rag]`` extra — so it adds NO new hard dependency.

Everything degrades to "unavailable" (``None``/``-1``) when Chroma or the model
is absent, so every caller keeps working with its non-semantic fallback (keyword
matching, exact-key caches). NumPy is the only hard requirement; the model is
loaded lazily on first use, never at import.
"""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

_EMBED_FN = None
_TRIED = False


def _fn():
    """Lazily construct the embedding function; None if unavailable (once)."""
    global _EMBED_FN, _TRIED
    if _EMBED_FN is None and not _TRIED:
        _TRIED = True
        try:
            from chromadb.utils import embedding_functions as ef

            _EMBED_FN = ef.DefaultEmbeddingFunction()
        except Exception as exc:  # noqa: BLE001 — semantic features are a bonus
            log.info("Local embedder unavailable (%s); semantic features stay off.", exc)
            _EMBED_FN = None
    return _EMBED_FN


def available() -> bool:
    """True when a local embedding model can be used offline."""
    return _fn() is not None


def embed(texts: list[str]) -> np.ndarray | None:
    """Embed strings into an ``(n, d)`` array of L2-normalized (unit) vectors.

    Unit vectors mean a plain dot product equals cosine similarity. Returns
    ``None`` on any failure (no model, empty input, runtime error) so callers
    fall back to their non-semantic path.
    """
    fn = _fn()
    cleaned = [str(t) for t in (texts or []) if str(t).strip()]
    if fn is None or not cleaned:
        return None
    try:
        vecs = np.asarray(fn(cleaned), dtype=np.float32)
        if vecs.ndim != 2 or vecs.shape[0] != len(cleaned):
            return None
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms
    except Exception as exc:  # noqa: BLE001 — never break a caller
        log.info("Embedding failed (%s).", exc)
        return None


def embed_one(text: str) -> np.ndarray | None:
    """Embed a single string into a unit vector, or ``None``."""
    matrix = embed([text])
    return None if matrix is None else matrix[0]


def cosine(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """Cosine similarity of two vectors (assumed unit-length); 0.0 if either is None."""
    if a is None or b is None:
        return 0.0
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / denom) if denom else 0.0


def nearest(query: np.ndarray | None, matrix) -> tuple[int, float]:
    """Return ``(index, cosine)`` of the row in ``matrix`` closest to ``query``.

    ``matrix`` is an ``(n, d)`` array/list of unit vectors. Returns ``(-1, -1.0)``
    when either side is missing/empty.
    """
    if query is None or matrix is None or len(matrix) == 0:
        return -1, -1.0
    mat = np.asarray(matrix, dtype=np.float32)
    q = np.asarray(query, dtype=np.float32)
    if mat.ndim != 2 or mat.shape[1] != q.shape[-1]:
        return -1, -1.0
    sims = mat @ q
    idx = int(sims.argmax())
    return idx, float(sims[idx])
