# New Business Entity Scraper

Pulls newly incorporated businesses from Florida and New York state databases and outputs an outreach-ready CSV for GTM teams.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Pull yesterday's filings (default)
python scraper.py

# Pull a specific date
python scraper.py --date 2026-03-20

# Pull only Florida
python scraper.py --states FL

# Backfill a date range
python scraper.py --from 2026-03-15 --to 2026-03-20

# Custom output directory
python scraper.py --output ./my_data/
```

Output goes to `./output/YYYY-MM-DD_new_businesses.csv`.

## Cron Setup

Run the installer to schedule weekday 8am pulls:

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

## Data Sources

- **Florida**: Daily SFTP bulk files from the Division of Corporations (sunbiz). Includes officer names, mailing addresses, EIN.
- **New York**: Socrata Open Data API on data.ny.gov. Entity metadata + addresses via a join dataset.

## Output CSV Columns

| Column | Description |
|---|---|
| source_state | FL or NY |
| entity_name | Business name |
| entity_number | State filing number |
| entity_type | LLC, Corporation, etc. |
| filing_date | YYYY-MM-DD |
| status | Active, etc. |
| contact_name | First officer/principal (FL only) |
| contact_title | Officer title |
| mail_address_line1 | Best mailing address |
| mail_address_line2 | Address line 2 |
| mail_city | City |
| mail_state | State |
| mail_zip | ZIP code |
| principal_address | Full principal address |
| ein | Federal EIN (FL only) |
| registered_agent_address | RA address |
| source | sunbiz_sftp or data_ny_gov |
| scraped_at | ISO timestamp |

## Adding a New State

1. Create `states/your_state.py` with a class extending `StateScraper`
2. Implement the `fetch(date)` method
3. Register it in `states/__init__.py`
