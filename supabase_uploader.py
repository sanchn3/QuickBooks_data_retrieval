"""
supabase_uploader.py — Upsert parsed report data into the financials schema.

Uses the Supabase Python client with the service_role key so RLS is bypassed
for all write operations.
"""

import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Module-level singleton client (initialised on first use)
_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# Generic upsert helper
# ─────────────────────────────────────────────────────────────────────────────

def _upsert(table: str, rows: list[dict], on_conflict: str) -> int:
    """
    Upsert a list of rows into a financials.* table.
    Returns the number of rows processed (not necessarily inserted vs updated).
    """
    if not rows:
        return 0
    schema = "financials"
    client = _get_client()

    # Supabase client sends upsert via POST with Prefer: resolution=merge-duplicates
    result = (
        client.schema(schema)
        .table(table)
        .upsert(rows, on_conflict=on_conflict)
        .execute()
    )
    count = len(result.data) if result.data else len(rows)
    logger.info("Upserted %d rows into financials.%s", count, table)
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Per-report upsert functions
# ─────────────────────────────────────────────────────────────────────────────

def upsert_profit_loss(rows: list[dict]) -> int:
    # Remove balance_sheet-only keys if accidentally present
    clean = [{k: v for k, v in r.items() if k != "report_date"} for r in rows]
    return _upsert("profit_loss", clean, "report_week,account_name,account_type")


def upsert_balance_sheet(rows: list[dict]) -> int:
    # Remove profit_loss-only keys if accidentally present
    clean = [{k: v for k, v in r.items() if k not in ("report_week", "period_start", "period_end")} for r in rows]
    return _upsert("balance_sheet", clean, "report_date,account_name,account_type")


def upsert_cash_flow(rows: list[dict]) -> int:
    return _upsert("cash_flow", rows, "report_week,activity_type,account_name")


def upsert_ar_aging(rows: list[dict]) -> int:
    return _upsert("ar_aging", rows, "report_date,customer_name")


def upsert_expense_by_vendor(rows: list[dict]) -> int:
    return _upsert("expense_by_vendor", rows, "report_week,vendor_name")


# ─────────────────────────────────────────────────────────────────────────────
# Sync log
# ─────────────────────────────────────────────────────────────────────────────

def log_sync_result(
    report_name: str,
    report_week: date,
    status: str,          # "success" | "error"
    rows_upserted: int = 0,
    error_message: str | None = None,
    duration_seconds: float = 0.0,
) -> None:
    client = _get_client()
    record = {
        "run_at":           datetime.now(tz=timezone.utc).isoformat(),
        "report_name":      report_name,
        "report_week":      report_week.isoformat() if report_week else None,
        "status":           status,
        "rows_upserted":    rows_upserted,
        "error_message":    error_message,
        "duration_seconds": round(duration_seconds, 2),
    }
    try:
        client.schema("financials").table("report_sync_log").insert(record).execute()
        logger.info(
            "Logged sync result: %s | %s | %d rows | %.2fs",
            report_name, status, rows_upserted, duration_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write sync log: %s", exc)
