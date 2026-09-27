import os
import pytest
from pathlib import Path
from app.core.config import settings
from app.core.storage import LocalStorageProvider

def test_local_storage_initialization(tmp_path):
    """
    Focused test proving local storage initialization and basic operations work
    using the architecture's configured directory approach.
    """
    base_dir = tmp_path / "test_data"
    
    # 1. Initialization
    provider = LocalStorageProvider(base_dir=str(base_dir))
    assert provider.base_dir == base_dir.resolve()
    
    # 2. Saving content creates directories and files
    test_key = "media/test_file.txt"
    test_content = b"fake_media_content"
    
    saved_key = provider.save(test_content, test_key)
    assert saved_key == test_key
    
    # Verify file physically exists
    expected_path = base_dir / test_key
    assert expected_path.exists()
    assert expected_path.read_bytes() == test_content
    
    # 3. Exists check
    assert provider.exists(test_key) is True
    assert provider.exists("media/non_existent.txt") is False
    
    # 4. Path traversal protection
    with pytest.raises(ValueError, match="Invalid storage key path traversal"):
        provider.save(b"bad", "../bad_file.txt")

    assert provider.exists("../bad_file.txt") is False

    # 5. Delete operation
    provider.delete(test_key)
    assert not expected_path.exists()
    assert provider.exists(test_key) is False
