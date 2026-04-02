"""
config.py — Environment loading and date helpers.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
load_dotenv(_BASE / ".env")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]  # service_role key

# ── QuickBooks ────────────────────────────────────────────────────────────────
QB_COMPANY_FILE: str = os.getenv("QB_COMPANY_FILE", "")  # "" = currently open file
QB_APP_NAME: str = os.getenv("QB_APP_NAME", "QB Data Transfer")


def get_report_week(reference_date: date | None = None) -> tuple[date, date, date, date]:
    """
    Returns (report_week_monday, period_start, period_end, report_date_sunday)
    for the most recently completed Monday-Sunday week.

    By default uses today's date.  Pass a specific date for testing.

    Example: if today is Tuesday 2026-04-07, last week was Mon 2026-03-30 – Sun 2026-04-05.
      report_week_monday = 2026-03-30
      period_start       = 2026-03-30
      period_end         = 2026-04-05
      report_date_sunday = 2026-04-05
    """
    ref = reference_date or date.today()
    # weekday(): Mon=0, Sun=6
    days_since_monday = ref.weekday()
    last_monday = ref - timedelta(days=days_since_monday + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_monday, last_sunday, last_sunday
