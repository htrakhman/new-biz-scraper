#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_CMD="0 8 * * 1-5 cd $SCRIPT_DIR && /usr/bin/python3 scraper.py >> ./logs/cron.log 2>&1"
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
echo "Cron job installed. Will run weekdays at 8am."
