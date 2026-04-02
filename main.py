"""
main.py — Orchestrates the QuickBooks → Supabase weekly sync.

Usage:
    python main.py                  # full sync (last week's data)
    python main.py --dry-run        # connect to QB, print XML, skip upload
    python main.py --test-connection # verify QB COM connection only
"""

import argparse
import logging
import sys
import time
from datetime import date
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────────────────
_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
LOG_DIR = _BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

_log_file = LOG_DIR / f"sync_{date.today().isoformat()}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")

# ── Local imports (after logging is configured) ───────────────────────────────
from config import get_report_week, QB_COMPANY_FILE, QB_APP_NAME
from qb_connector import QBConnector, test_connection
from qb_reports import (
    build_profit_loss_request,
    build_balance_sheet_request,
    build_cash_flow_request,
    build_ar_aging_request,
    build_expense_by_vendor_request,
)
from qb_parser import (
    parse_general_summary_report,
    parse_cash_flow_report,
    derive_cash_flow_from_balance_sheet,
    parse_aging_report,
)
from supabase_uploader import (
    upsert_profit_loss,
    upsert_balance_sheet,
    upsert_cash_flow,
    upsert_ar_aging,
    upsert_expense_by_vendor,
    log_sync_result,
)


# ─────────────────────────────────────────────────────────────────────────────
# Per-report runners
# ─────────────────────────────────────────────────────────────────────────────

def run_profit_loss(connector: QBConnector, report_week, period_start, period_end, dry_run: bool) -> tuple[int, list[dict]]:
    xml_req = build_profit_loss_request(period_start, period_end)
    xml_resp = connector.send_request(xml_req)
    if dry_run:
        print("\n--- Profit & Loss XML Response (first 2000 chars) ---")
        print(xml_resp[:2000])
        return 0, []
    rows = parse_general_summary_report(xml_resp, report_week, period_start, period_end, "profit_loss")
    count = upsert_profit_loss(rows)
    return count, rows


def run_balance_sheet(connector: QBConnector, report_week, period_start, period_end, report_date_sunday, dry_run: bool) -> tuple[int, list[dict]]:
    xml_req = build_balance_sheet_request(report_date_sunday)
    xml_resp = connector.send_request(xml_req)
    if dry_run:
        print("\n--- Balance Sheet XML Response (first 2000 chars) ---")
        print(xml_resp[:2000])
        return 0, []
    rows = parse_general_summary_report(xml_resp, report_week, period_start, period_end, "balance_sheet")
    count = upsert_balance_sheet(rows)
    return count, rows


def run_cash_flow(
    connector: QBConnector,
    report_week, period_start, period_end,
    pl_rows: list[dict],
    bs_rows: list[dict],
    dry_run: bool,
) -> int:
    xml_req = build_cash_flow_request(period_start, period_end)
    xml_resp = connector.send_request(xml_req)
    if dry_run:
        print("\n--- Cash Flow XML Response (first 2000 chars) ---")
        print(xml_resp[:2000])
        return 0

    # Try direct parse; fall back to derivation on empty result
    rows = parse_cash_flow_report(xml_resp, report_week, period_start, period_end)
    if not rows:
        logger.warning("Cash flow direct parse returned 0 rows — falling back to derived method")
        rows = derive_cash_flow_from_balance_sheet(pl_rows, bs_rows, report_week, period_start, period_end)

    count = upsert_cash_flow(rows)
    return count


def run_ar_aging(connector: QBConnector, report_week, period_start, period_end, report_date_sunday, dry_run: bool) -> int:
    xml_req = build_ar_aging_request(report_date_sunday)
    xml_resp = connector.send_request(xml_req)
    if dry_run:
        print("\n--- AR Aging XML Response (first 2000 chars) ---")
        print(xml_resp[:2000])
        return 0
    rows = parse_aging_report(xml_resp, report_date_sunday)
    return upsert_ar_aging(rows)


def run_expense_by_vendor(connector: QBConnector, report_week, period_start, period_end, dry_run: bool) -> int:
    xml_req = build_expense_by_vendor_request(period_start, period_end)
    xml_resp = connector.send_request(xml_req)
    if dry_run:
        print("\n--- Expense by Vendor XML Response (first 2000 chars) ---")
        print(xml_resp[:2000])
        return 0
    rows = parse_general_summary_report(xml_resp, report_week, period_start, period_end, "expense_by_vendor")
    return upsert_expense_by_vendor(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

REPORTS = [
    "profit_loss",
    "balance_sheet",
    "cash_flow",
    "ar_aging",
    "expense_by_vendor",
]


def run_sync(dry_run: bool = False) -> None:
    report_week, period_start, period_end, report_date_sunday = get_report_week()

    logger.info(
        "Starting QB → Supabase weekly sync | week=%s | %s to %s | dry_run=%s",
        report_week, period_start, period_end, dry_run,
    )

    results: dict[str, dict] = {}
    pl_rows: list[dict] = []
    bs_rows: list[dict] = []

    with QBConnector(company_file=QB_COMPANY_FILE, app_name=QB_APP_NAME) as conn:

        # ── 1. Profit & Loss ────────────────────────────────────────────────
        _run_report(
            "profit_loss", report_week, dry_run, results,
            fn=lambda: run_profit_loss(conn, report_week, period_start, period_end, dry_run),
            capture_rows=True, rows_store=pl_rows,
        )

        # ── 2. Balance Sheet ────────────────────────────────────────────────
        _run_report(
            "balance_sheet", report_week, dry_run, results,
            fn=lambda: run_balance_sheet(conn, report_week, period_start, period_end, report_date_sunday, dry_run),
            capture_rows=True, rows_store=bs_rows,
        )

        # ── 3. Cash Flow (needs P&L + BS rows for fallback) ─────────────────
        _run_report(
            "cash_flow", report_week, dry_run, results,
            fn=lambda: (run_cash_flow(conn, report_week, period_start, period_end, pl_rows, bs_rows, dry_run), []),
        )

        # ── 4. AR Aging ─────────────────────────────────────────────────────
        _run_report(
            "ar_aging", report_week, dry_run, results,
            fn=lambda: (run_ar_aging(conn, report_week, period_start, period_end, report_date_sunday, dry_run), []),
        )

        # ── 5. Expense by Vendor ────────────────────────────────────────────
        _run_report(
            "expense_by_vendor", report_week, dry_run, results,
            fn=lambda: (run_expense_by_vendor(conn, report_week, period_start, period_end, dry_run), []),
        )

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Sync complete. Results:")
    all_success = True
    for name, info in results.items():
        status = info["status"]
        if status == "error":
            all_success = False
        logger.info("  %-25s  %s  rows=%s  %.2fs", name, status.upper(), info.get("rows", "-"), info.get("duration", 0))
    logger.info("=" * 60)

    if not all_success:
        sys.exit(1)


def _run_report(
    name: str,
    report_week: date,
    dry_run: bool,
    results: dict,
    fn,
    capture_rows: bool = False,
    rows_store: list | None = None,
) -> None:
    start = time.monotonic()
    try:
        result = fn()
        # fn returns either (count, rows) or just count
        if isinstance(result, tuple):
            count, rows = result
        else:
            count, rows = result, []

        duration = time.monotonic() - start

        if capture_rows and rows_store is not None:
            rows_store.extend(rows)

        results[name] = {"status": "success", "rows": count, "duration": duration}

        if not dry_run:
            log_sync_result(name, report_week, "success", count, None, duration)

        logger.info("[%s] SUCCESS — %d rows — %.2fs", name, count, duration)

    except Exception as exc:  # noqa: BLE001
        duration = time.monotonic() - start
        logger.exception("[%s] ERROR: %s", name, exc)
        results[name] = {"status": "error", "duration": duration}

        if not dry_run:
            log_sync_result(name, report_week, "error", 0, str(exc), duration)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="QuickBooks → Supabase weekly sync")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Connect to QB, print report XML, skip all Supabase uploads",
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Verify the QuickBooks COM connection and exit",
    )
    args = parser.parse_args()

    if args.test_connection:
        ok = test_connection(company_file=QB_COMPANY_FILE, app_name=QB_APP_NAME)
        sys.exit(0 if ok else 1)

    run_sync(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
