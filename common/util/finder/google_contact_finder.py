# logic/util/google_contact_finder.py

from __future__ import annotations

import difflib
from typing import Optional, Dict, Any
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pathlib import Path
import logging

from common.util.loader.find_folder import FindFolder
from common.util.settings.env_deploy_reader import EnvDeployReader


class GoogleContactFinder:
    """
    Utility class to search Google Contacts for a person by name.
    Returns the first contact that has a WhatsApp-enabled phone number.
    """

    SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]

    def __init__(self, logger: Optional[logging.Logger] = None):
        cwd = Path.cwd()
        config_dir = FindFolder.find_config_dir(cwd)

        client_secret = Path(config_dir) / EnvDeployReader.get("GOOGLE_CLIENT_SECRET").strip()
        token_path    = Path(config_dir) / EnvDeployReader.get("GOOGLE_TOKEN_CONTACT_FILE").strip()

        self.client_secret_path = client_secret
        self.token_path = token_path

        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("[GoogleContactFinder] running OAuth flow for Contacts API")
        self.logger.info(f"[GoogleContactFinder] cwd={cwd}")
        self.logger.info(f"[GoogleContactFinder] resolved config_dir={config_dir}")
        self.logger.info(f"[GoogleContactFinder] client_secret_path={self.client_secret_path}")
        self.logger.info(f"[GoogleContactFinder] token_path={self.token_path}")

        self.service = self._build_service()

    def _get_credentials(self) -> Credentials:
        """Return credentials, always regenerating token.json if expired or invalid."""
        creds = None
        if self.token_path.exists():
            self.logger.info(f"[GoogleContactFinder] token.use path={self.token_path}")
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)

        try:
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # Try to refresh if possible
                    self.logger.info("[GoogleContactFinder] refreshing expired token")
                    creds.refresh(Request())
                else:
                    # Force regeneration if no valid token
                    raise Exception("invalid_or_missing_token")
        except Exception as ex:
            self.logger.warning(f"[GoogleContactFinder] token.invalid -> regenerating | {ex}")
            # Delete corrupted/expired token
            self.token_path.unlink(missing_ok=True)
            # Launch OAuth flow to get a new one
            flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), self.SCOPES)
            creds = flow.run_local_server(port=0)

        # Always overwrite the token with the fresh one
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")

        return creds

    def _build_service(self):
        creds = self._get_credentials()
        return build("people", "v1", credentials=creds)

    def find_contact(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Search Google Contacts for the closest match by name that has a phone number.
        Rules:
          1. If the search string appears anywhere in displayName (case-insensitive) → direct match.
          2. Otherwise fallback to fuzzy matching (difflib).
        """
        try:
            # Query Google People API for up to 10 possible matches
            results = (
                self.service.people()
                .searchContacts(query=name, pageSize=10, readMask="names,emailAddresses,phoneNumbers")
                .execute()
            )
            contacts = results.get("results", [])
            if not contacts:
                return None

            # Collect candidates
            candidates = []
            for c in contacts:
                person = c.get("person", {})
                display = person.get("names", [{}])[0].get("displayName", "")
                if display:
                    candidates.append((display, person))

            if not candidates:
                return None

            # 🔍 Step 1: direct substring match (case insensitive)
            for display, person in candidates:
                if name.lower() in display.lower():  # DNI or any partial text inside the name
                    self.logger.info(f"[GoogleContactFinder] Substring match for '{name}' -> {display}")
                    return {
                        "name": display,
                        "phone": (person.get("phoneNumbers", [{}])[0].get("value")),
                        "email": (person.get("emailAddresses", [{}])[0].get("value")),
                        "resourceName": person.get("resourceName"),
                        "match": "substring",
                    }

            # 🔍 Step 2: fallback to fuzzy match
            display_names = [c[0] for c in candidates]
            best = difflib.get_close_matches(name.lower(), [d.lower() for d in display_names], n=1, cutoff=0.5)

            if best:
                best_name = best[0]
                for display, person in candidates:
                    if display.lower() == best_name:
                        phones = person.get("phoneNumbers", [])
                        for p in phones:
                            if p.get("value"):
                                self.logger.info(f"[GoogleContactFinder] Fuzzy match for '{name}' -> {display}")
                                return {
                                    "name": display,
                                    "phone": p.get("value"),
                                    "email": (person.get("emailAddresses", [{}])[0].get("value")),
                                    "resourceName": person.get("resourceName"),
                                    "match": "fuzzy",
                                }

            return None

        except Exception as ex:
            self.logger.error(f"[GoogleContactFinder] error searching contact {name}: {ex}")
            return None



