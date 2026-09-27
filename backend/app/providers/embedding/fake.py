from .base import EmbeddingProvider
from typing import List

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
        
        import hashlib
        # Use first 2 bytes of hash as angle factor
        h = int(hashlib.md5(text.encode()).hexdigest()[:4], 16)
        val = (h % 100) / 100.0
        
        vec = [0.0] * self._dimension
        vec[0] = 1.0
        vec[1] = val
        return vec
