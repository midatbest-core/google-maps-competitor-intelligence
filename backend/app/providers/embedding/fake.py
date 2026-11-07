from .base import EmbeddingProvider
from typing import List
import hashlib
import math

class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 768, should_fail: bool = False):
        self._dimension = dimension
        self._should_fail = should_fail
        
    @property
    def provider_name(self) -> str:
        return "fake_provider"
        
    @property
    def model_name(self) -> str:
        return "fake_embedding_model"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def generate_embedding(self, text: str) -> List[float]:
        if self._should_fail:
            raise ValueError("Fake embedding failure simulated.")
        
        # Deterministic pseudo-random normalized unit vector from sha256 hash of text
        seed = int(hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:8], 16)
        vec = []
        for _ in range(self._dimension):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            vec.append((seed / 0x7FFFFFFF) * 2.0 - 1.0)
            
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
