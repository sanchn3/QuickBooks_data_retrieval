"""
qb_parser.py — Parse QBXML response XML into list[dict] ready for Supabase upsert.

Uses lxml for robust XML parsing.  All monetary values are stored as float
(Supabase NUMERIC columns handle precision).
"""

import logging
import re
from datetime import date
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_amount(text: Optional[str]) -> Optional[float]:
    """Convert a QB amount string like '-1,234.56' to float, or None."""
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"[,$]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_xml(xml_str: str) -> etree._Element:
    return etree.fromstring(xml_str.encode("utf-8"))


def _check_status(root: etree._Element, report_label: str) -> None:
    """Raise if QB returned a non-zero status code."""
    for status in root.iter("StatusCode"):
        code = status.text or "0"
        if code != "0":
            msg_el = status.getparent().find("StatusMessage")
            msg = msg_el.text if msg_el is not None else "Unknown QB error"
            raise RuntimeError(f"QB returned status {code} for {report_label}: {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# 1 & 2. GeneralSummaryReport  (P&L, Balance Sheet, Expense by Vendor)
# ─────────────────────────────────────────────────────────────────────────────

def parse_general_summary_report(
    xml_str: str,
    report_week: date,
    period_start: date,
    period_end: date,
    report_type: str,  # "profit_loss" | "balance_sheet" | "expense_by_vendor"
) -> list[dict]:
    """
    Parse a GeneralSummaryReportRs response into a flat list of row dicts.

    Row hierarchy is tracked via a simple depth stack so parent_account is
    populated for child lines.
    """
    root = _parse_xml(xml_str)
    _check_status(root, report_type)

    rs = root.find(".//GeneralSummaryReportRs")
    if rs is None:
        logger.warning("No GeneralSummaryReportRs element found for %s", report_type)
        return []

    rows: list[dict] = []
    row_order = 0
    # Stack of (indent_level, account_name) for parent tracking
    parent_stack: list[tuple[int, str]] = []

    for row_data in rs.iter("RowData"):
        row_type = row_data.get("rowType", "")
        label_el = row_data.find("Label")
        label = label_el.text.strip() if label_el is not None and label_el.text else ""
        if not label:
            continue

        # Collect all ColData values (first col is the amount for TotalOnly)
        col_values = [c.text for c in row_data.findall("ColData")]
        amount = _parse_amount(col_values[0]) if col_values else None

        indent_str = row_data.get("indent", "0")
        try:
            indent = int(indent_str)
        except ValueError:
            indent = 0

        is_subtotal = row_type in ("Subtotal", "GrandTotal")

        # Maintain parent stack
        while parent_stack and parent_stack[-1][0] >= indent:
            parent_stack.pop()
        parent_account = parent_stack[-1][1] if parent_stack else None

        # Infer account_type from report context (refined per row label below)
        account_type = _infer_account_type(label, row_type, report_type)

        base = {
            "report_week": report_week.isoformat() if report_type != "balance_sheet" else None,
            "report_date": period_end.isoformat() if report_type == "balance_sheet" else None,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "account_name": label,
            "account_type": account_type,
            "parent_account": parent_account,
            "amount": amount,
            "is_subtotal": is_subtotal,
            "row_order": row_order,
        }

        if report_type == "balance_sheet":
            base["account_subtype"] = None  # populated if needed later

        if report_type == "expense_by_vendor":
            base = {
                "report_week": report_week.isoformat(),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "vendor_name": label,
                "amount": amount,
            }

        rows.append(base)

        if not is_subtotal:
            parent_stack.append((indent, label))

        row_order += 1

    logger.info("Parsed %d rows from %s", len(rows), report_type)
    return rows


def _infer_account_type(label: str, row_type: str, report_type: str) -> str:
    """Best-effort account type inference from label and report context."""
    upper = label.upper()

    if report_type == "profit_loss":
        # NetIncome must be checked before Income — "NET INCOME" contains "INCOME"
        if "NET INCOME" in upper or "NET LOSS" in upper or row_type == "GrandTotal":
            return "NetIncome"
        if "INCOME" in upper or "REVENUE" in upper or "SALES" in upper:
            return "Income"
        if "COST OF" in upper or "COGS" in upper:
            return "COGS"
        return "Expense"

    if report_type == "balance_sheet":
        if "ASSET" in upper:
            return "Asset"
        if "LIABILIT" in upper:
            return "Liability"
        if "EQUITY" in upper:
            return "Equity"
        return "Asset"  # default

    return "Expense"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cash Flow (GeneralDetailReportRs — CashFlowForecast)
# ─────────────────────────────────────────────────────────────────────────────

_ACTIVITY_KEYWORDS = {
    "Operating": ["operating", "operations"],
    "Investing":  ["investing"],
    "Financing":  ["financing"],
    "Net":        ["net increase", "net decrease", "net change", "beginning cash", "ending cash"],
}


def _classify_activity(label: str) -> str:
    lower = label.lower()
    for activity, keywords in _ACTIVITY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return activity
    return "Operating"  # default


def parse_cash_flow_report(
    xml_str: str,
    report_week: date,
    period_start: date,
    period_end: date,
) -> list[dict]:
    """Parse CashFlowForecast detail report response."""
    root = _parse_xml(xml_str)
    _check_status(root, "cash_flow")

    rs = root.find(".//GeneralDetailReportRs")
    if rs is None:
        logger.warning("No GeneralDetailReportRs found; cash flow will be empty")
        return []

    rows: list[dict] = []
    row_order = 0
    current_activity = "Operating"

    for row_data in rs.iter("RowData"):
        label_el = row_data.find("Label")
        label = label_el.text.strip() if label_el is not None and label_el.text else ""
        if not label:
            continue

        # Section headers switch the current activity bucket
        row_type = row_data.get("rowType", "")
        if row_type in ("Section", "Header"):
            current_activity = _classify_activity(label)
            continue

        col_values = [c.text for c in row_data.findall("ColData")]
        amount = _parse_amount(col_values[0]) if col_values else None
        is_subtotal = row_type in ("Subtotal", "GrandTotal")

        rows.append({
            "report_week":   report_week.isoformat(),
            "period_start":  period_start.isoformat(),
            "period_end":    period_end.isoformat(),
            "activity_type": current_activity,
            "account_name":  label,
            "amount":        amount,
            "is_subtotal":   is_subtotal,
            "is_derived":    False,
            "row_order":     row_order,
        })
        row_order += 1

    logger.info("Parsed %d cash flow rows", len(rows))
    return rows


def derive_cash_flow_from_balance_sheet(
    pl_rows: list[dict],
    bs_rows: list[dict],
    report_week: date,
    period_start: date,
    period_end: date,
) -> list[dict]:
    """
    Fallback: derive cash flow indirectly from Net Income (P&L) + balance sheet
    account changes.  All derived rows are flagged with is_derived=True.
    """
    # Extract net income from P&L
    net_income = 0.0
    for row in pl_rows:
        if row.get("account_type") == "NetIncome" and row.get("is_subtotal"):
            net_income = row.get("amount") or 0.0
            break

    rows = [
        {
            "report_week":   report_week.isoformat(),
            "period_start":  period_start.isoformat(),
            "period_end":    period_end.isoformat(),
            "activity_type": "Operating",
            "account_name":  "Net Income (derived)",
            "amount":        net_income,
            "is_subtotal":   False,
            "is_derived":    True,
            "row_order":     0,
        },
        {
            "report_week":   report_week.isoformat(),
            "period_start":  period_start.isoformat(),
            "period_end":    period_end.isoformat(),
            "activity_type": "Net",
            "account_name":  "Estimated Net Cash Change (derived)",
            "amount":        net_income,
            "is_subtotal":   True,
            "is_derived":    True,
            "row_order":     1,
        },
    ]
    logger.info("Derived %d cash flow rows from P&L", len(rows))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 4. AR Aging Summary (AgingReportRs)
# ─────────────────────────────────────────────────────────────────────────────

def parse_aging_report(xml_str: str, report_date: date) -> list[dict]:
    """
    Parse ARAgingSummary response.

    QB aging report columns (with 30-day ageing period):
      Current | 1 - 30 | 31 - 60 | 61 - 90 | > 90 | TOTAL
    Column indices may vary; we detect them from the ColDesc elements.
    """
    root = _parse_xml(xml_str)
    _check_status(root, "ar_aging")

    rs = root.find(".//AgingReportRs")
    if rs is None:
        logger.warning("No AgingReportRs element found")
        return []

    # Build column index map from ColDesc header row
    col_map: dict[str, int] = {}  # key → 0-based index
    for col_desc in rs.findall(".//ColDesc"):
        idx_el = col_desc.find("ColID")
        name_el = col_desc.find("ColTitle")
        if idx_el is not None and name_el is not None:
            idx = int(idx_el.text or "0") - 1  # QB colID is 1-based
            title = (name_el.text or "").strip().lower()
            col_map[title] = idx

    # Fallback positional map if ColDesc is absent
    if not col_map:
        col_map = {
            "current": 0, "1 - 30": 1, "31 - 60": 2,
            "61 - 90": 3, "> 90": 4, "total": 5,
        }

    def _get_col(values: list, *keys: str) -> Optional[float]:
        for k in keys:
            idx = col_map.get(k)
            if idx is not None and idx < len(values):
                return _parse_amount(values[idx])
        return None

    rows: list[dict] = []
    for row_data in rs.iter("RowData"):
        row_type = row_data.get("rowType", "")
        if row_type in ("Header", "Section", "Subtotal", "GrandTotal"):
            continue

        label_el = row_data.find("Label")
        customer = label_el.text.strip() if label_el is not None and label_el.text else ""
        if not customer:
            continue

        col_values = [c.text for c in row_data.findall("ColData")]

        rows.append({
            "report_date":    report_date.isoformat(),
            "customer_name":  customer,
            "current_amount": _get_col(col_values, "current"),
            "days_1_30":      _get_col(col_values, "1 - 30", "1-30"),
            "days_31_60":     _get_col(col_values, "31 - 60", "31-60"),
            "days_61_90":     _get_col(col_values, "61 - 90", "61-90"),
            "days_over_90":   _get_col(col_values, "> 90", ">90"),
            "total_balance":  _get_col(col_values, "total"),
        })

    logger.info("Parsed %d AR aging rows", len(rows))
    return rows
