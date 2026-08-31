"""Embeddings as blobs with brute-force cosine — nothing else warranted (D-01)."""
from __future__ import annotations

import struct
from typing import Iterable

import numpy as np


def pack(vec: Iterable[float]) -> bytes:
    arr = np.asarray(list(vec), dtype=np.float32)
    return struct.pack("<I", arr.shape[0]) + arr.tobytes()


def unpack(blob: bytes | None) -> np.ndarray:
    if not blob:
        return np.zeros(0, dtype=np.float32)
    (n,) = struct.unpack("<I", blob[:4])
    return np.frombuffer(blob[4 : 4 + n * 4], dtype=np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.0
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def hash_embed(text: str, dim: int = 256) -> list[float]:
    """Deterministic offline embedding for fixture mode (no GPU, I-05).

    A hashed bag-of-tokens projected into `dim` dims. Not semantically rich,
    but stable and dependency-free so similarity/retrieval works with no model.
    """
    vec = np.zeros(dim, dtype=np.float32)
    toks = _tokenize(text)
    for tok in toks:
        h = hash(tok)
        vec[h % dim] += 1.0
        vec[(h // dim) % dim] += 0.5
    norm = np.linalg.norm(vec)
    if norm:
        vec /= norm
    return vec.tolist()


def _tokenize(text: str) -> list[str]:
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if t]


def ngram_overlap(a: str, b: str, n: int = 3) -> float:
    """Lexical n-gram (word) overlap for the similarity guard (P-07)."""
    ta, tb = _tokenize(a), _tokenize(b)
    if len(ta) < n or len(tb) < n:
        # fall back to token Jaccard for short texts
        sa, sb = set(ta), set(tb)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)
    ga = {tuple(ta[i : i + n]) for i in range(len(ta) - n + 1)}
    gb = {tuple(tb[i : i + n]) for i in range(len(tb) - n + 1)}
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)
