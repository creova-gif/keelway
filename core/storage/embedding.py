"""
Keelway Deterministic Dense Vector Embedding & Similarity Engine.
Pure-Python, zero-dependency implementation of normalized vector hashing and hybrid relevance scoring.
"""

import math
import re
import hashlib
from typing import List, Optional, Dict, Any, Tuple


class EmbeddingProvider:
    """Computes vector embeddings using a deterministic pure-Python dense feature hasher."""

    DIMENSIONS = 128

    @classmethod
    def get_dense_embedding(cls, text: str) -> List[float]:
        """
        Generates a deterministic normalized 128-dimensional embedding vector
        using multi-hash term n-gram feature projection.
        Guarantees zero-dependency, reproducible vector generation.
        """
        vec = [0.0] * cls.DIMENSIONS
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vec

        # Project unigrams and bigrams into vector space
        terms = tokens + [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        for term in terms:
            h = int(hashlib.md5(term.encode("utf-8")).hexdigest(), 16)
            idx = h % cls.DIMENSIONS
            sign = 1.0 if (h >> 7) & 1 else -1.0
            vec[idx] += sign

        # L2 Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    sim = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, (sim + 1.0) / 2.0))  # Rescale [-1, 1] to [0, 1]


def compute_lexical_score(query: str, text: str) -> float:
    """Computes token overlap score between query and text."""
    query_tokens = set(re.findall(r"\w+", query.lower()))
    if not query_tokens:
        return 0.0
    text_tokens = set(re.findall(r"\w+", text.lower()))
    if not text_tokens:
        return 0.0

    overlap = query_tokens.intersection(text_tokens)
    return len(overlap) / len(query_tokens)
