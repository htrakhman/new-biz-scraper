# Engineering Overview: New Business Entity Scraper

This document explains how the system is built, why key decisions were made, and how to extend it. Intended audience: engineers onboarding to or maintaining this codebase.

---

## What It Does

The scraper pulls newly incorporated business filings from two state databases — Florida and New York — and outputs a daily outreach-ready CSV. It runs on a weekday cron schedule, deduplicates across runs, and is designed to be extended to additional states.

Output file per run: `output/YYYY-MM-DD_new_businesses.csv`

---

## Repository Layout

```
new-biz-scraper/
├── scraper.py          # Entry point: CLI parsing, orchestration, CSV output
├── config.py           # All constants: SFTP creds, field offsets, API URLs, column list
├── normalize.py        # Maps raw state dicts → common 18-column schema
├── history.py          # File-based dedup: tracks scraped entity IDs across runs
├── states/
│   ├── __init__.py     # Registry: STATE_SCRAPERS = {"FL": ..., "NY": ...}
│   ├── base.py         # Abstract base class StateScraper
│   ├── florida.py      # SFTP download + fixed-width parser
│   └── new_york.py     # Socrata REST API client
├── requirements.txt
├── railway.toml        # Production cron config
├── run.sh              # Local venv wrapper
├── setup_cron.sh       # Installs a local crontab entry
└── .github/workflows/railway-deploy.yml
```

---

## Architecture

### Plugin Pattern for State Scrapers

Each state is an independent plugin. `states/base.py` defines the interface:

```python
class StateScraper(ABC):
    state_code: str    # e.g. "FL"
    source_name: str   # e.g. "sunbiz_sftp"

    @abstractmethod
    def fetch(self, target_date: date) -> List[Dict[str, Any]]:
        ...
```

`states/__init__.py` holds the registry:

```python
STATE_SCRAPERS = {
    "FL": FloridaScraper,
    "NY": NewYorkScraper,
}
```

The orchestrator (`scraper.py`) iterates over whichever state codes are requested, calls `fetch(date)`, and never needs to know anything about state-specific logic. Adding a new state is: write the class, register it, add field mappings in `normalize.py`.

### Data Flow

```
scraper.py
  └─ for each state code
       └─ StateScraper.fetch(date) → List[Dict]   # raw, state-specific keys
  └─ normalize_all(fl_records, ny_records)
       └─ _normalize_fl / _normalize_ny            # maps to 18-column schema
       └─ drop_duplicates(entity_number + state)
  └─ filter: keep only filing_date == target_date  # drops amendment records
  └─ filter: load_seen_ids() → drop already-scraped entities
  └─ df.to_csv(output_path)
  └─ save_new_ids() → append to scraped_history.txt
```

### No Database

Persistence is intentionally file-based:

- `scraped_history.txt` — one line per entity, format `state|entity_number|filing_date`
- `output/YYYY-MM-DD_new_businesses.csv` — per-run output
- `logs/YYYY-MM-DD.log` — per-run log

This keeps the deployment zero-dependency (no DB to provision) and the outputs trivially auditable.

---

## Florida Scraper (`states/florida.py`)

### Data Source

Florida's Division of Corporations exposes a public SFTP server at `sftp.floridados.gov`. Credentials are public (hardcoded in `config.py` — not a secret, this is a government public-access endpoint). The daily file path is `/public/doc/cor/{YYYYMMDD}c.txt`.

### Fixed-Width Format

The file is a fixed-width text file encoded in `latin-1`. Each non-empty line is one corporation record, padded to 1440 bytes. There is no header row.

All byte offsets and lengths are defined in `config.py` under `FL_FIELDS`:

| Field | Start | Length | Notes |
|---|---|---|---|
| corp_number | 0 | 12 | State entity ID |
| corp_name | 12 | 192 | Legal name |
| status | 204 | 1 | "A" = Active |
| filing_code | 205 | 4 | Entity type code (e.g. FLAL, DOMP) |
| ra_address_* | 220–345 | varies | Registered agent address block |
| princ_address_* | 346–471 | varies | Principal office address block |
| filing_date | 472 | 8 | MMDDYYYY (no delimiters) |
| fei_ein_number | 480 | 14 | Federal EIN |
| agent_name | 544 | 40 | Non-officer contact name |
| officers | 668+ | 128×6 | 6 officer slots, each 128 bytes |

Each officer slot at offset `668 + (i * 128)` contains: title (4), name (40), address (40), city (28), state (2), zip (9).

**Why hard-coded offsets?** Florida provides no schema document and the file format has been stable for years. A library-based approach would add complexity with no benefit. If the format changes, the offsets in `config.py` are the only thing to update.

### Parsing

```python
# Pad to 1440 to avoid index errors on short lines
line = line.ljust(1440)

# Extract field by slice
record[field_name] = line[start:start + length].strip()

# Date conversion: MMDDYYYY → YYYY-MM-DD
mm, dd, yyyy = raw_date[:2], raw_date[2:4], raw_date[4:]
record["filing_date"] = f"{yyyy}-{mm}-{dd}"
```

Name format in the file is `LAST                FIRST       MI` (space-padded, reversed). `_parse_fl_name()` splits on whitespace and reassembles as `FIRST LAST [SUFFIX]`.

### Fallback Logic

If the target date's file doesn't exist (e.g., holiday, delay), the scraper walks backward up to 5 business days (skipping weekends), trying each. If nothing is found, it returns an empty list and logs an error. The orchestrator continues with whatever other states returned.

---

## New York Scraper (`states/new_york.py`)

### Data Source

New York exposes its entity filings via the **Socrata Open Data API** at `data.ny.gov`. No authentication is required, though setting `NY_APP_TOKEN` in `.env` raises the rate limit.

- Filings endpoint: `https://data.ny.gov/resource/k4vb-judh.json`
- Address endpoint: `https://data.ny.gov/resource/2tms-hftb.json` (currently fetched but not merged — future use)

### Query

Uses Socrata's `$where` clause to filter by filing date:

```
$where=filing_date >= '2026-04-10T00:00:00' AND filing_date < '2026-04-11T00:00:00'
$limit=50000
$order=filing_date DESC
```

Response is JSON. Fields map directly to dict keys — no parsing needed. The NY API returns `filing_date` as an ISO timestamp (`2026-04-10T00:00:00`); normalization strips the time component.

### Fallback Logic

Same 5-business-day walkback as Florida. Returns empty list on API error (logged).

---

## Normalization (`normalize.py`)

Both scrapers return `List[Dict]` with state-specific key names. `normalize_all()` maps them to the common 18-column output schema:

| Column | FL Source | NY Source |
|---|---|---|
| source_state | "FL" | "NY" |
| entity_name | corp_name | corp_name |
| entity_number | corp_number | dos_id |
| entity_type | filing_code → lookup table | entity_type (verbatim) |
| filing_date | filing_date (converted) | filing_date (truncated) |
| status | "A" → "Active" | (empty — not in NY API) |
| contact_name | agent_name, else officers[0].name | filer_name |
| contact_title | officers[0].title | (empty) |
| mail_address_line1 | princ_address_1 or ra_address_1 | filer_addr1 |
| ... | ... | ... |
| source | "sunbiz_sftp" | "data_ny_gov" |
| scraped_at | UTC ISO timestamp | UTC ISO timestamp |

**Address priority for FL**: principal office first, registered agent as fallback. FL daily files have no separate mailing address block.

**Entity type mapping for FL**: 4-char codes (e.g. `FLAL`, `DOMP`) are mapped to human-readable strings in `_fl_entity_type()`. Unknown codes pass through as-is.

After normalization, `drop_duplicates(subset=["entity_number", "source_state"])` removes any within-run duplicates (shouldn't happen, but defensive).

---

## Deduplication (`history.py`)

The history file (`scraped_history.txt`) has one entry per scraped entity:

```
FL|L12345678901|2026-04-09
NY|6789012|2026-04-09
```

**On load** (`load_seen_ids`): reads all entries *except* those matching the current target date. This means re-running the same date produces a fresh CSV rather than an empty one (idempotent re-runs).

**On save** (`save_new_ids`): rewrites the file, first removing any existing entries for the target date, then appending new ones. This keeps the file clean on repeated same-day runs.

**Dedup check** in `scraper.py`:
```python
df = df[df.apply(
    lambda r: make_key(r["source_state"], r["entity_number"]) not in seen_ids,
    axis=1,
)]
```

---

## Amendment Filtering

Florida's daily file contains *all* transactions for that day, not just new incorporations — it also includes amendments, registered-agent updates, etc. for older entities. The orchestrator filters these out:

```python
df = df[df["filing_date"] == target_date.isoformat()]
```

Only records whose `filing_date` matches the target date survive. Older amendment records are dropped and logged.

---

## CLI Interface

```
python scraper.py [--date YYYY-MM-DD] [--from YYYY-MM-DD --to YYYY-MM-DD]
                  [--states FL,NY] [--output ./output]
```

- No arguments → scrapes yesterday
- `--date` → single date
- `--from/--to` → date range (inclusive, for backfilling)
- `--states` → subset of states (comma-separated)
- `--output` → override output directory

Exit code: `1` if errors occurred *and* no records were written; `0` otherwise.

---

## Configuration (`config.py`)

All constants in one file. Key items:

- **FL SFTP credentials**: public government endpoint, no rotation needed
- **FL_FIELDS**: byte offset map for fixed-width parser — update here if format changes
- **NY_FILINGS_URL / NY_ADDRESS_URL**: Socrata endpoints
- **NY_API_LIMIT**: 50,000 (Socrata max per request; daily volume is well below this)
- **CSV_COLUMNS**: ordered list of output columns — source of truth for the schema

---

## Deployment

### Production: Railway

`railway.toml` configures the service:

```toml
[build]
builder = "RAILPACK"    # auto-detects Python, installs requirements.txt

[deploy]
cronSchedule = "0 13 * * 1-5"    # Weekdays at 1:00 PM UTC (8 AM Eastern)
restartPolicyType = "NEVER"       # One-shot: run and exit
```

GitHub Actions (`.github/workflows/railway-deploy.yml`) deploys on push to `main` using Railway CLI. Requires two repository secrets: `RAILWAY_TOKEN` and `RAILWAY_SERVICE`.

### Local Development

```bash
pip install -r requirements.txt
python scraper.py                        # yesterday
python scraper.py --date 2026-04-01      # specific date
python scraper.py --from 2026-03-01 --to 2026-03-31  # backfill
./run.sh                                  # creates/uses a local venv
./setup_cron.sh                           # installs local 8AM weekday crontab
```

### Environment Variables

Copy `.env.example` to `.env`. Only one optional variable:

```
NY_APP_TOKEN=your_token_here   # Socrata app token — increases rate limit, not required
```

---

## Logging

Dual output: stdout + `logs/YYYY-MM-DD.log`. Format:

```
2026-04-10 13:00:01 [INFO] __main__: === Scraping for 2026-04-10 ===
2026-04-10 13:00:03 [INFO] __main__: FL: 1247 records
2026-04-10 13:00:04 [INFO] __main__: NY: 412 records
2026-04-10 13:00:04 [INFO] __main__: Dropped 83 records (amendments/updates, not filed on 2026-04-10)
2026-04-10 13:00:04 [INFO] __main__: Skipped 0 previously scraped entities
2026-04-10 13:00:04 [INFO] __main__: --- Summary for 2026-04-10 ---
2026-04-10 13:00:04 [INFO] __main__:   FL: 1247 raw records
2026-04-10 13:00:04 [INFO] __main__:   NY: 412 raw records
2026-04-10 13:00:04 [INFO] __main__:   New entities (not previously scraped): 1576
2026-04-10 13:00:04 [INFO] __main__:   Output: /app/output/2026-04-10_new_businesses.csv
```

---

## How to Add a New State

1. **Create `states/your_state.py`**:
   ```python
   from states.base import StateScraper

   class TexasScraper(StateScraper):
       state_code = "TX"
       source_name = "texas_sos_api"

       def fetch(self, target_date: date) -> List[Dict[str, Any]]:
           # fetch and return raw records as list of dicts
           ...
   ```

2. **Register in `states/__init__.py`**:
   ```python
   from states.texas import TexasScraper
   STATE_SCRAPERS["TX"] = TexasScraper
   ```

3. **Add normalization in `normalize.py`**:
   ```python
   def _normalize_tx(rec: Dict[str, Any]) -> List:
       # map TX-specific keys to the 18-column schema
       ...
   ```
   Call it from `normalize_all()`.

4. Update `normalize_all()` to accept and process `tx_records`.

5. Update `scraper.py` `run_for_date()` to collect TX records alongside FL and NY.

---

## Dependencies

| Package | Version | Use |
|---|---|---|
| paramiko | >=3.0 | SFTP client for Florida |
| requests | >=2.28 | HTTP client for NY API |
| pandas | >=2.0 | DataFrame normalization and CSV export |
| python-dotenv | >=1.0 | `.env` loading |

No web framework, no ORM, no database driver. The dependency footprint is intentionally minimal.
