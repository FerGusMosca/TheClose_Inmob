from __future__ import annotations
from pathlib import Path
from typing import Optional, Sequence

from google.auth.exceptions import RefreshError

from common.util.loader.find_folder import FindFolder
from common.util.settings.env_deploy_reader import EnvDeployReader

try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except Exception:
    build = Credentials = InstalledAppFlow = Request = None

class GoogleDriveDownload:
    """
    Google Drive downloader.
    - Requires client_secret + token.json in ./config
    - Downloads a file from folder_id by name
    """

    DEFAULT_SCOPES: Sequence[str] = ("https://www.googleapis.com/auth/drive.readonly",)
    EXPORT_FOLDER="exports/portfolio_rotation"

    def __init__(self, *, client_secret_path=None, token_path=None, scopes=None, logger=None):
        self.log = logger
        self.scopes = tuple(scopes or self.DEFAULT_SCOPES)

        cwd = Path.cwd()
        config_dir = FindFolder.find_config_dir(cwd)

        # Build clean paths
        client_secret = Path(config_dir) / EnvDeployReader.get("GOOGLE_CLIENT_SECRET").strip()
        token_path = Path(config_dir) / EnvDeployReader.get("GOOGLE_TOKEN_DRIVE_FILE").strip()

        self.client_secret_path = client_secret
        self.token_path = token_path

        # Debug logs
        if self.log:
            self.log.info(f"[GoogleContactFinder] cwd={cwd}")
            self.log.info(f"[GoogleContactFinder] config_dir={config_dir}")
            self.log.info(f"[GoogleContactFinder] client_secret_path={self.client_secret_path}")
            self.log.info(f"[GoogleContactFinder] token_path={self.token_path}")
            self.log.info("[GoogleContactFinder] OAuth flow initialized for Drive API")

    def _get_credentials(self):
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        creds = None
        if Path(self.token_path).exists():
            self.log.info(f"drive.token.use path={self.token_path}")
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)

        # Always check and refresh/regenerate if needed
        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    self.log.info("drive.token.refresh")
                    creds.refresh(Request())
                else:
                    raise RefreshError("invalid_or_missing_token")
            except Exception as ex:
                self.log.warning(f"drive.token.invalid -> regenerating | {ex}")
                # 🚀 Always regenerate OAuth token
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secret_path), self.scopes
                )
                creds = flow.run_local_server(port=0)

        # 💾 Always overwrite token file
        Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.token_path).write_text(creds.to_json(), encoding="utf-8")

        return creds

    def download_file(self, filename: str, folder_id: str) -> Path:
        """Download a file from Google Drive by name into ./exports/tmp."""
        creds = self._get_credentials()
        drive = build("drive", "v3", credentials=creds)

        # Search file in folder
        q = f"name='{filename}' and '{folder_id}' in parents"
        res = drive.files().list(q=q, fields="files(id,name)").execute()
        files = res.get("files", [])
        if not files:
            raise FileNotFoundError(f"{filename} not found in Drive folder {folder_id}")

        file_id = files[0]["id"]

        out_path = Path(GoogleDriveDownload.EXPORT_FOLDER) / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)

        request = drive.files().get_media(fileId=file_id)
        with open(out_path, "wb") as fh:
            fh.write(request.execute())

        self.log and self.log.info(f"drive.download.ok file={filename} -> {out_path}")
        return out_path

