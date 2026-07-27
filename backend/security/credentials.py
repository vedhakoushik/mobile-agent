from pathlib import Path
from typing import Optional

import yaml

DEFAULT_SECRETS_PATH = Path(__file__).parent.parent.parent / "secrets.yaml"


class CredentialNotFoundError(KeyError):
    pass


class CredentialManager:
    """Resolves named secrets (passwords, PINs, tokens) for the type_secret action.

    Secret VALUES never enter agent state, action history, websocket broadcasts,
    or LLM prompts — only secret_id names do. executor.py's type_secret branch is
    the only place a resolved value is read; it is used once, passed straight to
    the device, and discarded.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or DEFAULT_SECRETS_PATH
        self._secrets = self._load()

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        with open(self._path) as f:
            data = yaml.safe_load(f) or {}
        secrets: dict[str, str] = {}
        for key, val in (data.get("secrets") or {}).items():
            if isinstance(val, dict):
                if val.get("enabled", True) and val.get("value"):
                    secrets[key] = str(val["value"])
            elif isinstance(val, str) and val:
                secrets[key] = val
        return secrets

    def resolve(self, secret_id: str) -> str:
        if secret_id not in self._secrets:
            raise CredentialNotFoundError(
                f"Secret '{secret_id}' not found. Available: {list(self._secrets.keys())}"
            )
        return self._secrets[secret_id]

    def keys(self) -> list[str]:
        return list(self._secrets.keys())

    def has(self, secret_id: str) -> bool:
        return secret_id in self._secrets
