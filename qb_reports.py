"""
qb_reports.py — Build QBXML request strings for each of the 5 reports.

All requests use explicit FromReportDate/ToReportDate (no QB macros)
so the date range is deterministic regardless of when the script runs.
"""

from datetime import date

QBXML_HEADER = """<?xml version="1.0" encoding="utf-8"?>
<?qbxml version="13.0"?>
<QBXML>
  <QBXMLMsgsRq onError="stopOnError">"""

QBXML_FOOTER = """  </QBXMLMsgsRq>
</QBXML>"""


def _fmt(d: date) -> str:
    """Format a date as YYYY-MM-DD for QB."""
    return d.strftime("%Y-%m-%d")


# ── 1. Profit & Loss ──────────────────────────────────────────────────────────

def build_profit_loss_request(period_start: date, period_end: date) -> str:
    body = f"""
    <GeneralSummaryReportQueryRq requestID="1">
      <GeneralSummaryReportType>ProfitAndLossStandard</GeneralSummaryReportType>
      <DisplayColumnsBy>TotalOnly</DisplayColumnsBy>
      <FromReportDate>{_fmt(period_start)}</FromReportDate>
      <ToReportDate>{_fmt(period_end)}</ToReportDate>
      <ReportBasis>Accrual</ReportBasis>
    </GeneralSummaryReportQueryRq>"""
    return QBXML_HEADER + body + QBXML_FOOTER


# ── 2. Balance Sheet ─────────────────────────────────────────────────────────

def build_balance_sheet_request(report_date: date) -> str:
    body = f"""
    <GeneralSummaryReportQueryRq requestID="2">
      <GeneralSummaryReportType>BalanceSheetStandard</GeneralSummaryReportType>
      <DisplayColumnsBy>TotalOnly</DisplayColumnsBy>
      <FromReportDate>{_fmt(report_date)}</FromReportDate>
      <ToReportDate>{_fmt(report_date)}</ToReportDate>
      <ReportBasis>Accrual</ReportBasis>
    </GeneralSummaryReportQueryRq>"""
    return QBXML_HEADER + body + QBXML_FOOTER


# ── 3. Cash Flow ─────────────────────────────────────────────────────────────

def build_cash_flow_request(period_start: date, period_end: date) -> str:
    """
    Attempts CashFlowForecast via GeneralDetailReportQueryRq.
    Falls back in parser if unavailable.
    """
    body = f"""
    <GeneralDetailReportQueryRq requestID="3">
      <GeneralDetailReportType>CashFlowForecast</GeneralDetailReportType>
      <FromReportDate>{_fmt(period_start)}</FromReportDate>
      <ToReportDate>{_fmt(period_end)}</ToReportDate>
    </GeneralDetailReportQueryRq>"""
    return QBXML_HEADER + body + QBXML_FOOTER


# ── 4. AR Aging Summary ───────────────────────────────────────────────────────

def build_ar_aging_request(report_date: date) -> str:
    body = f"""
    <AgingReportQueryRq requestID="4">
      <AgingReportType>ARAgingSummary</AgingReportType>
      <ToReportDate>{_fmt(report_date)}</ToReportDate>
      <ReportAgeingPeriod>30</ReportAgeingPeriod>
    </AgingReportQueryRq>"""
    return QBXML_HEADER + body + QBXML_FOOTER


# ── 5. Expense by Vendor ──────────────────────────────────────────────────────

def build_expense_by_vendor_request(period_start: date, period_end: date) -> str:
    body = f"""
    <GeneralSummaryReportQueryRq requestID="5">
      <GeneralSummaryReportType>ExpenseByVendorSummary</GeneralSummaryReportType>
      <DisplayColumnsBy>TotalOnly</DisplayColumnsBy>
      <FromReportDate>{_fmt(period_start)}</FromReportDate>
      <ToReportDate>{_fmt(period_end)}</ToReportDate>
      <ReportBasis>Accrual</ReportBasis>
    </GeneralSummaryReportQueryRq>"""
    return QBXML_HEADER + body + QBXML_FOOTER
