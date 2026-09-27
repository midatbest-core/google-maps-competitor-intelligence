import os
import shutil
from typing import Optional
from pathlib import Path

class StorageProvider:
    def save(self, content: bytes, key: str) -> str:
        """Save content to storage and return the storage key/reference."""
        raise NotImplementedError
        
    def exists(self, key: str) -> bool:
        """Check if the given key exists in storage."""
        raise NotImplementedError
        
    def delete(self, key: str):
        """Delete the file from storage."""
        raise NotImplementedError
        
    def get_reference(self, key: str) -> str:
        """Return a string reference (e.g. URL or local path) to the stored item."""
        raise NotImplementedError

class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir).resolve()
        
    def _get_path(self, key: str) -> Path:
        # Prevent path traversal
        normalized_key = key.lstrip("/")
        full_path = (self.base_dir / normalized_key).resolve()
        
        if not str(full_path).startswith(str(self.base_dir)):
            raise ValueError(f"Invalid storage key path traversal: {key}")
            
        return full_path

    def save(self, content: bytes, key: str) -> str:
        path = self._get_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to a temporary file first, then replace for atomicity
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with open(temp_path, "wb") as f:
            f.write(content)
            
        temp_path.replace(path)
        return key
        
    def exists(self, key: str) -> bool:
        try:
            path = self._get_path(key)
            return path.exists() and path.is_file()
        except ValueError:
            return False
            
    def delete(self, key: str):
        try:
            path = self._get_path(key)
            if path.exists() and path.is_file():
                path.unlink()
        except ValueError:
            pass
            
    def get_reference(self, key: str) -> str:
        # For local storage, we just return the local file path URI or the key
        return f"file://{self._get_path(key)}"
