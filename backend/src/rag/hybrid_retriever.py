import re
import math
from typing import List, Dict, Any, Optional
import numpy as np

from src.models import PolicyCitation, AccessTier
from integrations.m365_adapter import SHAREPOINT_POLICY_DOCUMENTS


def compute_char_ngram_vector(text: str, n: int = 3, dim: int = 128) -> np.ndarray:
    """Generate deterministic dense normalized embedding vector via n-gram hashing."""
    vec = np.zeros(dim, dtype=np.float32)
    clean = re.sub(r"[^\w\s]", "", text.lower())
    if len(clean) < n:
        clean = clean.ljust(n)

    for i in range(len(clean) - n + 1):
        ngram = clean[i:i+n]
        h = hash(ngram) % dim
        vec[h] += 1.0

    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def compute_cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    dot = float(np.dot(v1, v2))
    return max(0.0, min(1.0, dot))


def compute_bm25_lexical_score(query_tokens: List[str], doc_tokens: List[str]) -> float:
    """Lightweight BM25-style lexical keyword overlap calculation."""
    if not query_tokens or not doc_tokens:
        return 0.0

    score = 0.0
    doc_len = len(doc_tokens)
    avg_len = 25.0
    k1 = 1.5
    b = 0.75

    doc_token_counts = {}
    for t in doc_tokens:
        doc_token_counts[t] = doc_token_counts.get(t, 0) + 1

    for q in query_tokens:
        if q in doc_token_counts:
            freq = doc_token_counts[q]
            tf = (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * (doc_len / avg_len)))
            score += tf

    max_possible = len(query_tokens) * (k1 + 1)
    return min(1.0, score / max_possible if max_possible > 0 else 0.0)


class HybridPolicyRetriever:
    """Hybrid RAG retriever combining BM25 lexical token match and dense cosine vector similarity."""

    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: List[np.ndarray] = []
        self.init_index()

    def init_index(self):
        """Index all pre-seeded SharePoint enterprise policy documents."""
        self.documents = []
        self.embeddings = []

        for doc in SHAREPOINT_POLICY_DOCUMENTS:
            for sec in doc["sections"]:
                chunk = {
                    "doc_id": doc["id"],
                    "document_id": doc["id"],
                    "title": doc["title"],
                    "document_title": doc["title"],
                    "version": doc["version"],
                    "section": sec["section"],
                    "content": sec["content"],
                    "text": sec["content"],
                    "access_tier": doc["access_tier"],
                    "source_url": doc["source_url"]
                }
                self.documents.append(chunk)
                full_text = f"{doc['title']} {sec['section']} {sec['content']}"
                self.embeddings.append(compute_char_ngram_vector(full_text))

    async def initialize(self):
        self.init_index()

    def _tier_permits(self, user_access_tier: AccessTier, doc_access_tier: AccessTier) -> bool:
        tier_hierarchy = {
            AccessTier.PUBLIC: 1,
            AccessTier.INTERNAL: 2,
            AccessTier.RESTRICTED: 3
        }
        user_level = tier_hierarchy.get(user_access_tier, 1)
        doc_level = tier_hierarchy.get(doc_access_tier, 2)
        return user_level >= doc_level

    def retrieve(
        self,
        query: str,
        user_access_tier: AccessTier = AccessTier.INTERNAL,
        top_k: int = 3,
        threshold: float = 0.15
    ) -> List[PolicyCitation]:
        """Perform authorized hybrid retrieval with role-based access tier pre-filtering."""
        if not self.documents:
            return []

        q_vec = compute_char_ngram_vector(query)
        q_tokens = [w for w in re.sub(r"[^\w\s]", "", query.lower()).split() if len(w) > 2]

        scored_candidates = []

        for idx, doc in enumerate(self.documents):
            # 1. Pre-filter by access tier
            if not self._tier_permits(user_access_tier, doc["access_tier"]):
                continue

            # 2. Dense vector cosine score
            dense_score = compute_cosine_similarity(q_vec, self.embeddings[idx])

            # 3. Lexical BM25 score
            doc_tokens = re.sub(r"[^\w\s]", "", doc["content"].lower()).split()
            lexical_score = compute_bm25_lexical_score(q_tokens, doc_tokens)

            # 4. Hybrid score fusion
            hybrid_score = round((0.4 * lexical_score) + (0.6 * dense_score), 4)

            if hybrid_score >= threshold or lexical_score > 0.2:
                scored_candidates.append((hybrid_score, doc))

        # Sort descending by fused score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        citations = []
        for score, doc in scored_candidates[:top_k]:
            citations.append(PolicyCitation(
                document_id=doc["document_id"],
                document_title=doc["document_title"],
                version=doc["version"],
                section=doc["section"],
                excerpt=doc["content"],
                relevance_score=score,
                access_tier=doc["access_tier"]
            ))

        return citations


policy_retriever = HybridPolicyRetriever()
