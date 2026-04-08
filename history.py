"""Track previously scraped entities to avoid duplicates across runs."""

import logging
from datetime import date
from pathlib import Path
from typing import Set

from config import BASE_DIR

logger = logging.getLogger(__name__)

HISTORY_FILE = BASE_DIR / "scraped_history.txt"


def load_seen_ids(target_date: date) -> Set[str]:
    """Load entity keys scraped on previous dates only — not the target date itself.
    This allows re-running the same date without getting an empty CSV."""
    if not HISTORY_FILE.exists():
        return set()
    seen = set()
    target_str = target_date.isoformat()
    with open(HISTORY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Format: state|entity_number|filing_date
            parts = line.split("|")
            if len(parts) == 3 and parts[2] == target_str:
                # Same target date — don't skip, allow re-scrape
                continue
            seen.add(f"{parts[0]}|{parts[1]}")
    logger.info(f"Loaded {len(seen)} previously scraped entities from history (excluding {target_str})")
    return seen


def save_new_ids(new_ids: Set[str], target_date: date) -> None:
    """Append newly scraped entity keys with their filing date to the history file."""
    if not new_ids:
        return
    # Remove existing entries for this date first to avoid duplicates in history file
    date_str = target_date.isoformat()
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            existing = [l.strip() for l in f if l.strip() and not l.strip().endswith(f"|{date_str}")]
    else:
        existing = []

    with open(HISTORY_FILE, "w") as f:
        for line in existing:
            f.write(line + "\n")
        for key in sorted(new_ids):
            f.write(f"{key}|{date_str}\n")
    logger.info(f"Saved {len(new_ids)} entities to history for {date_str}")


def make_key(source_state: str, entity_number: str) -> str:
    """Create a unique key for dedup tracking."""
    return f"{source_state}|{entity_number}"
