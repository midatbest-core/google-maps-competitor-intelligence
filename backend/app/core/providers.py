from abc import ABC, abstractmethod
from typing import Any, List, Dict
import os

class StorageProvider(ABC):
    @abstractmethod
    async def save(self, file_name: str, content: bytes) -> str:
        pass
    
    @abstractmethod
    async def get(self, file_path: str) -> bytes:
        pass

class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: str = "media"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    async def save(self, file_name: str, content: bytes) -> str:
        file_path = os.path.join(self.base_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    async def get(self, file_path: str) -> bytes:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"{file_path} not found.")
        with open(file_path, "rb") as f:
            return f.read()

class AIProvider(ABC):
    @abstractmethod
    async def analyze_post(self, text: str, image_path: str | None = None) -> Dict[str, Any]:
        """Returns structured JSON for topics, keywords, CTAs."""
        pass

    @abstractmethod
    async def generate_ideas(self, context: Dict[str, Any], count: int) -> List[Dict[str, Any]]:
        """Generates content ideas based on context."""
        pass

    @abstractmethod
    async def generate_update(self, idea: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Generates a complete post update."""
        pass
