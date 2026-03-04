from __future__ import annotations
from pathlib import Path
from typing import Optional, Sequence

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except Exception:  # libs missing; validated at runtime
    build = MediaFileUpload = Credentials = InstalledAppFlow = Request = None


class GoogleDriveUpload:
    """
    Google Drive uploader with explicit, verbose logging.
    - Looks up client_secret and token under ./config by default.
    - Creates/refreshes token.json if needed.
    - Uploads file to folder_id and makes it public-read.
    """

    DEFAULT_SCOPES: Sequence[str] = ("https://www.googleapis.com/auth/drive.file",)

    def __init__(
        self,
        *,
        client_secret_path: Optional[str | Path] = None,
        token_path: Optional[str | Path] = None,
        scopes: Optional[Sequence[str]] = None,
        logger=None,
    ) -> None:
        self.log = logger
        self.scopes = tuple(scopes or self.DEFAULT_SCOPES)

        repo_root = Path.cwd()
        config_dir = repo_root / "config"
        self._log("drive.init", cwd=str(repo_root), config_dir=str(config_dir))

        self.client_secret_path = Path(client_secret_path) if client_secret_path else self._find_client_secret(config_dir)
        self.token_path = Path(token_path) if token_path else (config_dir / "token.json")

        self._log("drive.paths", client_secret=str(self.client_secret_path), token=str(self.token_path))
        self._ensure_libs()

    # ---------- public ----------
    def upload_file(self, file_path: str | Path, folder_id: str) -> str:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if not folder_id:
            raise ValueError("DRIVE_FOLDER_ID is empty/missing")

        self._log("drive.upload.start",
                  file=str(p.resolve()),
                  size_bytes=p.stat().st_size,
                  folder_id=("SET" if folder_id else "<empty>"))

        creds = self._get_credentials()
        drive = build("drive", "v3", credentials=creds)

        meta = {"name": p.name, "parents": [folder_id]}
        media = MediaFileUpload(str(p), resumable=True)

        f = drive.files().create(
            body=meta, media_body=media, fields="id,webViewLink", supportsAllDrives=True
        ).execute()

        drive.permissions().create(
            fileId=f["id"], body={"role": "reader", "type": "anyone"}, supportsAllDrives=True
        ).execute()

        self._log("drive.upload.ok", file_id=f.get("id"), webViewLink=f.get("webViewLink"))
        return f["webViewLink"]

    # ---------- internals ----------
    def _get_credentials(self):
        from google.oauth2.credentials import Credentials  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore

        creds = None
        if self.token_path.exists():
            self._log("drive.token.use", path=str(self.token_path))
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self._log("drive.token.refresh")
                creds.refresh(Request())
            else:
                self._log("drive.oauth.flow", client_secret=str(self.client_secret_path))
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), self.scopes)
                creds = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
            self._log("drive.token.saved", path=str(self.token_path))

        return creds

    def _find_client_secret(self, config_dir: Path) -> Path:
        hit = next(config_dir.glob("client_secret*.json"), None)
        if not hit:
            raise FileNotFoundError(
                "client_secret*.json not found in ./config. "
                "Place it there or pass client_secret_path explicitly."
            )
        return hit

    @staticmethod
    def _ensure_libs() -> None:
        if any(x is None for x in (build, MediaFileUpload, Credentials, InstalledAppFlow, Request)):
            raise RuntimeError(
                "Google Drive libraries not available. Install: "
                "google-api-python-client google-auth google-auth-oauthlib"
            )

    def _log(self, msg: str, **kv):
        if self.log:
            self.log.info(msg + " " + " ".join(f"{k}={v}" for k, v in kv.items()))
