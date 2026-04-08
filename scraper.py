#!/usr/bin/env python3
"""
New Business Entity Scraper — pulls newly incorporated businesses from
Florida and New York state databases and outputs an outreach-ready CSV.
"""

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from config import OUTPUT_DIR, LOG_DIR, CSV_COLUMNS
from states import STATE_SCRAPERS
from normalize import normalize_all
from history import load_seen_ids, save_new_ids, make_key


def setup_logging(log_date: date) -> None:
    """Configure logging to both console and daily log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{log_date.isoformat()}.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape newly incorporated businesses from state databases."
    )
    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        help="Target date (YYYY-MM-DD). Default: yesterday.",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        type=lambda s: date.fromisoformat(s),
        help="Start of date range (YYYY-MM-DD) for backfilling.",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=lambda s: date.fromisoformat(s),
        help="End of date range (YYYY-MM-DD) for backfilling.",
    )
    parser.add_argument(
        "--states",
        type=lambda s: [x.strip().upper() for x in s.split(",")],
        default=list(STATE_SCRAPERS.keys()),
        help=f"Comma-separated state codes. Default: {','.join(STATE_SCRAPERS.keys())}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory. Default: {OUTPUT_DIR}",
    )
    return parser.parse_args()


def get_dates(args: argparse.Namespace) -> list[date]:
    """Determine the list of dates to scrape."""
    if args.date_from and args.date_to:
        dates = []
        current = args.date_from
        while current <= args.date_to:
            dates.append(current)
            current += timedelta(days=1)
        return dates
    if args.date:
        return [args.date]
    # Default: yesterday
    return [date.today() - timedelta(days=1)]


def run_for_date(
    target_date: date,
    state_codes: list[str],
    output_dir: Path,
) -> tuple[int, list[str]]:
    """Run the scraper for a single date. Returns (record_count, errors)."""
    logger = logging.getLogger(__name__)
    logger.info(f"=== Scraping for {target_date} ===")

    fl_records = []
    ny_records = []
    errors = []
    counts = {}

    for code in state_codes:
        scraper_cls = STATE_SCRAPERS.get(code)
        if not scraper_cls:
            logger.warning(f"Unknown state code: {code}")
            errors.append(f"Unknown state: {code}")
            continue

        scraper = scraper_cls()
        try:
            records = scraper.fetch(target_date)
            counts[code] = len(records)
            if code == "FL":
                fl_records = records
            elif code == "NY":
                ny_records = records
            logger.info(f"{code}: {len(records)} records")
        except Exception as e:
            logger.error(f"{code} scraper failed: {e}")
            errors.append(f"{code}: {e}")
            counts[code] = 0

    # Normalize and write CSV
    df = normalize_all(fl_records, ny_records)

    # Keep only businesses that were actually filed on the target date
    # The daily file includes old businesses filing amendments — drop those
    if not df.empty:
        target_str = target_date.isoformat()
        before_new = len(df)
        df = df[df["filing_date"] == target_str]
        old_dropped = before_new - len(df)
        if old_dropped:
            logger.info(f"Dropped {old_dropped} records (amendments/updates, not filed on {target_str})")

    # Filter out previously scraped entities
    seen_ids = load_seen_ids(target_date)
    before_filter = len(df)
    if not df.empty and seen_ids:
        df = df[
            df.apply(
                lambda r: make_key(r["source_state"], r["entity_number"]) not in seen_ids,
                axis=1,
            )
        ]
    skipped = before_filter - len(df)
    if skipped:
        logger.info(f"Skipped {skipped} previously scraped entities")

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{target_date.isoformat()}_new_businesses.csv"
    output_path = output_dir / filename
    df.to_csv(output_path, index=False, columns=CSV_COLUMNS)

    # Save newly scraped IDs to history
    new_ids = set()
    if not df.empty:
        for _, row in df.iterrows():
            new_ids.add(make_key(row["source_state"], row["entity_number"]))
    save_new_ids(new_ids, target_date)

    # Summary
    total = len(df)
    logger.info(f"--- Summary for {target_date} ---")
    for code, count in counts.items():
        logger.info(f"  {code}: {count} raw records")
    logger.info(f"  New entities (not previously scraped): {total}")
    logger.info(f"  Output: {output_path}")
    if errors:
        logger.warning(f"  Errors: {'; '.join(errors)}")

    return total, errors


def main() -> int:
    args = parse_args()
    dates = get_dates(args)

    setup_logging(dates[0])
    logger = logging.getLogger(__name__)

    total_records = 0
    all_errors = []

    for target_date in dates:
        count, errors = run_for_date(target_date, args.states, args.output)
        total_records += count
        all_errors.extend(errors)

    if len(dates) > 1:
        logger.info(
            f"=== Batch complete: {len(dates)} dates, "
            f"{total_records} total records ==="
        )

    return 1 if all_errors and total_records == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
