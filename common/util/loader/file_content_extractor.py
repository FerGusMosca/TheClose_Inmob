import os
from pathlib import Path
from typing import Optional
from common.config.settings import get_settings


class FileContentExtractor:
    """
    Utility class to read file content given a relative path.
    """

    MAX_LENGTH = 8000  # safety limit to avoid token overflow

    @staticmethod
    def get_file_content(relative_path: str) -> Optional[str]:
        """
        Returns the text content of the file located under:
        {index_files_root_path}/data/documents/{bot_profile}/{relative_path}
        """
        try:
            base_root = (
                Path(get_settings().index_files_root_path)
                / get_settings().bot_profile
            )
            full_path = base_root / relative_path

            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {full_path}")

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            if len(content) > FileContentExtractor.MAX_LENGTH:
                content = content[: FileContentExtractor.MAX_LENGTH] + "\n...[truncated]..."

            return content
        except Exception as e:
            print(f"[FileContentExtractor] ❌ Error reading {relative_path}: {e}")
            return None
