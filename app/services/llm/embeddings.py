"""Embedding service and similarity computation."""
import hashlib
import math
from typing import List, Optional
import httpx
from app.config.settings import settings
from app.config.logging_config import logger

EMBEDDING_DIM = 256


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def generate_deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Generates a deterministic, normalized vector embedding for testing and fallback.
    Uses MD5/SHA256 sliding seed to construct pseudo-dense semantic space.
    """
    vec = [0.0] * dim
    words = text.lower().split()
    if not words:
        return vec

    for word in words:
        hash_val = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = hash_val % dim
        vec[idx] += 1.0

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        vec = [x / norm for x in vec]
    return vec


class EmbeddingService:
    """Async embedding generator with remote NVIDIA API and local fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or settings.NVIDIA_API_KEY
        self.base_url = base_url or settings.NVIDIA_BASE_URL
        self.model_name = model_name or "nvidia/embed-qa-4"

    async def get_embedding(self, text: str) -> List[float]:
        """Fetches vector embedding for text string."""
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        if self.api_key and not settings.DRY_RUN:
            try:
                url = f"{self.base_url}/embeddings"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "input": [text[:1000]],
                    "model": self.model_name,
                    "encoding_format": "float",
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["data"][0]["embedding"]
            except Exception as e:
                logger.warning("Remote embedding call failed, using deterministic fallback", error=str(e))

        # Fallback
        return generate_deterministic_embedding(text)


embedding_service = EmbeddingService()
