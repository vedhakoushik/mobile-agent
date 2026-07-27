import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CARDS_DIR = Path(__file__).parent.parent.parent / "app_cards"


class AppCardProvider:
    """Resolves per-app guidance cards (markdown files) from app_cards.json.

    The mapping file (app_cards.json) maps app names to markdown filenames.
    Markdown content is loaded lazily on first request and cached for the
    lifetime of the provider.
    """

    def __init__(self, cards_dir: Optional[Path] = None):
        self._dir = cards_dir or DEFAULT_CARDS_DIR
        self._mapping: dict[str, str] = self._load()
        self._cache: dict[str, str] = {}

    def _load(self) -> dict[str, str]:
        path = self._dir / "app_cards.json"
        if not path.exists():
            return {}
        with open(path) as f:
            data = json.load(f)
        return {k.lower(): v for k, v in data.items() if isinstance(v, str)}

    def get(self, app_name: str) -> Optional[str]:
        key = app_name.lower()
        if key not in self._mapping:
            return None
        if key in self._cache:
            return self._cache[key]
        md_path = self._dir / self._mapping[key]
        if not md_path.exists():
            logger.warning("App card file missing: %s", md_path)
            return None
        content = md_path.read_text()
        self._cache[key] = content
        return content
