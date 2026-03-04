from pathlib import Path
from common.config.settings import get_settings

class BotPathResolver:
    """
    Utility class to resolve paths related to a bot's data and vectorstore.
    Ensures consistent directory construction between local and deployed environments.
    """

    def __init__(self):
        settings = get_settings()
        self.bot_profile = (settings.bot_profile or "").strip()
        self.root_path = Path(settings.bot_profile_root_path or ".").expanduser().resolve()

    @property
    def documents_path(self) -> Path:
        """Return the full path where the bot's source documents live."""
        return self.root_path / self.bot_profile

    @property
    def vectorstore_path(self) -> Path:
        """Return the path where FAISS vectorstore should be stored."""
        repo_root = Path(__file__).resolve().parents[2]  # project root
        return repo_root / "vectorstores" / self.bot_profile

    def ensure_exists(self):
        """Check that the documents directory exists."""
        if not self.documents_path.exists():
            raise FileNotFoundError(f"❌ Bot documents path not found: {self.documents_path}")
        return self.documents_path
