"""
test_qb_reports.py — Unit tests for qb_reports.py XML request builders.

Verifies each builder produces well-formed QBXML with correct report types,
dates, and structure.  No QB connection or .env required.
"""

from datetime import date

import pytest
from lxml import etree

from qb_reports import (
    build_profit_loss_request,
    build_balance_sheet_request,
    build_cash_flow_request,
    build_ar_aging_request,
    build_expense_by_vendor_request,
)

START = date(2026, 3, 30)
END = date(2026, 4, 5)


def _parse(xml_str: str) -> etree._Element:
    """Parse XML string, raise on malformed input."""
    return etree.fromstring(xml_str.encode("utf-8"))


# ── Profit & Loss ─────────────────────────────────────────────────────────────

class TestBuildProfitLoss:
    def test_well_formed_xml(self):
        _parse(build_profit_loss_request(START, END))

    def test_report_type(self):
        assert "ProfitAndLossStandard" in build_profit_loss_request(START, END)

    def test_from_date(self):
        assert "2026-03-30" in build_profit_loss_request(START, END)

    def test_to_date(self):
        assert "2026-04-05" in build_profit_loss_request(START, END)

    def test_accrual_basis(self):
        assert "Accrual" in build_profit_loss_request(START, END)

    def test_uses_summary_request_element(self):
        assert "GeneralSummaryReportQueryRq" in build_profit_loss_request(START, END)

    def test_request_id_1(self):
        assert 'requestID="1"' in build_profit_loss_request(START, END)

    def test_total_only_columns(self):
        assert "TotalOnly" in build_profit_loss_request(START, END)


# ── Balance Sheet ─────────────────────────────────────────────────────────────

class TestBuildBalanceSheet:
    def test_well_formed_xml(self):
        _parse(build_balance_sheet_request(END))

    def test_report_type(self):
        assert "BalanceSheetStandard" in build_balance_sheet_request(END)

    def test_date_used_for_both_from_and_to(self):
        # Balance sheet uses one date for both FromReportDate and ToReportDate
        xml = build_balance_sheet_request(END)
        assert xml.count("2026-04-05") == 2

    def test_accrual_basis(self):
        assert "Accrual" in build_balance_sheet_request(END)

    def test_request_id_2(self):
        assert 'requestID="2"' in build_balance_sheet_request(END)


# ── Cash Flow ─────────────────────────────────────────────────────────────────

class TestBuildCashFlow:
    def test_well_formed_xml(self):
        _parse(build_cash_flow_request(START, END))

    def test_report_type(self):
        assert "CashFlowForecast" in build_cash_flow_request(START, END)

    def test_uses_detail_request_element(self):
        # Cash flow uses GeneralDetailReport, not GeneralSummaryReport
        xml = build_cash_flow_request(START, END)
        assert "GeneralDetailReportQueryRq" in xml
        assert "GeneralSummaryReportQueryRq" not in xml

    def test_from_date(self):
        assert "2026-03-30" in build_cash_flow_request(START, END)

    def test_to_date(self):
        assert "2026-04-05" in build_cash_flow_request(START, END)

    def test_request_id_3(self):
        assert 'requestID="3"' in build_cash_flow_request(START, END)


# ── AR Aging ──────────────────────────────────────────────────────────────────

class TestBuildArAging:
    def test_well_formed_xml(self):
        _parse(build_ar_aging_request(END))

    def test_report_type(self):
        assert "ARAgingSummary" in build_ar_aging_request(END)

    def test_uses_aging_request_element(self):
        assert "AgingReportQueryRq" in build_ar_aging_request(END)

    def test_to_report_date(self):
        assert "2026-04-05" in build_ar_aging_request(END)

    def test_ageing_period_30_days(self):
        assert "<ReportAgeingPeriod>30</ReportAgeingPeriod>" in build_ar_aging_request(END)

    def test_request_id_4(self):
        assert 'requestID="4"' in build_ar_aging_request(END)


# ── Expense by Vendor ─────────────────────────────────────────────────────────

class TestBuildExpenseByVendor:
    def test_well_formed_xml(self):
        _parse(build_expense_by_vendor_request(START, END))

    def test_report_type(self):
        assert "ExpenseByVendorSummary" in build_expense_by_vendor_request(START, END)

    def test_from_date(self):
        assert "2026-03-30" in build_expense_by_vendor_request(START, END)

    def test_to_date(self):
        assert "2026-04-05" in build_expense_by_vendor_request(START, END)

    def test_accrual_basis(self):
        assert "Accrual" in build_expense_by_vendor_request(START, END)

    def test_request_id_5(self):
        assert 'requestID="5"' in build_expense_by_vendor_request(START, END)


# ── Cross-cutting checks ──────────────────────────────────────────────────────

ALL_BUILDERS = [
    ("profit_loss",        lambda: build_profit_loss_request(START, END)),
    ("balance_sheet",      lambda: build_balance_sheet_request(END)),
    ("cash_flow",          lambda: build_cash_flow_request(START, END)),
    ("ar_aging",           lambda: build_ar_aging_request(END)),
    ("expense_by_vendor",  lambda: build_expense_by_vendor_request(START, END)),
]


@pytest.mark.parametrize("name,builder", ALL_BUILDERS)
def test_all_builders_produce_valid_xml(name, builder):
    root = _parse(builder())
    assert root is not None


@pytest.mark.parametrize("name,builder", ALL_BUILDERS)
def test_all_builders_have_qbxml_root(name, builder):
    assert "<QBXML>" in builder()


@pytest.mark.parametrize("name,builder", ALL_BUILDERS)
def test_all_builders_have_qbxml_version_13(name, builder):
    assert 'version="13.0"' in builder()


@pytest.mark.parametrize("name,builder", ALL_BUILDERS)
def test_all_builders_have_msgs_rq_wrapper(name, builder):
    assert "QBXMLMsgsRq" in builder()
