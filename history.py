"""Track previously scraped entities to avoid duplicates across runs."""

import logging
from pathlib import Path

from config import BASE_DIR

logger = logging.getLogger(__name__)

HISTORY_FILE = BASE_DIR / "scraped_history.txt"


def load_seen_ids() -> set[str]:
    """Load the set of previously scraped entity keys (state|entity_number)."""
    if not HISTORY_FILE.exists():
        return set()
    seen = set()
    with open(HISTORY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                seen.add(line)
    logger.info(f"Loaded {len(seen)} previously scraped entities from history")
    return seen


def save_new_ids(new_ids: set[str]) -> None:
    """Append newly scraped entity keys to the history file."""
    if not new_ids:
        return
    with open(HISTORY_FILE, "a") as f:
        for key in sorted(new_ids):
            f.write(key + "\n")
    logger.info(f"Added {len(new_ids)} new entities to history")


def make_key(source_state: str, entity_number: str) -> str:
    """Create a unique key for dedup tracking."""
    return f"{source_state}|{entity_number}"
