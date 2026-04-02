"""
test_qb_parser.py — Unit tests for qb_parser.py.

Uses synthetic QBXML strings that mimic real QB responses.
No QB connection or .env required.
"""

from datetime import date

import pytest

from qb_parser import (
    _parse_amount,
    _infer_account_type,
    _classify_activity,
    parse_general_summary_report,
    parse_cash_flow_report,
    parse_aging_report,
    derive_cash_flow_from_balance_sheet,
)

WEEK  = date(2026, 3, 30)
START = date(2026, 3, 30)
END   = date(2026, 4, 5)


# ── Synthetic QBXML fixtures ──────────────────────────────────────────────────

MOCK_PL_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<QBXML><QBXMLMsgsRs>
  <GeneralSummaryReportRs requestID="1" statusCode="0" statusSeverity="Info" statusMessage="Status OK">
    <StatusCode>0</StatusCode>
    <ReportData>
      <RowData rowType="Section"  indent="0"><Label>Income</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Services Revenue</Label><ColData>50000.00</ColData></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Product Sales</Label><ColData>10000.00</ColData></RowData>
      <RowData rowType="Subtotal" indent="0"><Label>Total Income</Label><ColData>60000.00</ColData></RowData>
      <RowData rowType="Section"  indent="0"><Label>Expense</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Office Supplies</Label><ColData>1500.00</ColData></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Rent</Label><ColData>2000.00</ColData></RowData>
      <RowData rowType="Subtotal" indent="0"><Label>Total Expense</Label><ColData>3500.00</ColData></RowData>
      <RowData rowType="GrandTotal" indent="0"><Label>Net Income</Label><ColData>56500.00</ColData></RowData>
    </ReportData>
  </GeneralSummaryReportRs>
</QBXMLMsgsRs></QBXML>"""

MOCK_BS_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<QBXML><QBXMLMsgsRs>
  <GeneralSummaryReportRs requestID="2" statusCode="0" statusSeverity="Info" statusMessage="Status OK">
    <StatusCode>0</StatusCode>
    <ReportData>
      <RowData rowType="Section"  indent="0"><Label>ASSETS</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Checking Account</Label><ColData>10000.00</ColData></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Accounts Receivable</Label><ColData>5000.00</ColData></RowData>
      <RowData rowType="Subtotal" indent="0"><Label>Total ASSETS</Label><ColData>15000.00</ColData></RowData>
      <RowData rowType="Section"  indent="0"><Label>LIABILITIES</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Accounts Payable</Label><ColData>3000.00</ColData></RowData>
      <RowData rowType="Subtotal" indent="0"><Label>Total LIABILITIES</Label><ColData>3000.00</ColData></RowData>
      <RowData rowType="Section"  indent="0"><Label>EQUITY</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Retained Earnings</Label><ColData>12000.00</ColData></RowData>
      <RowData rowType="GrandTotal" indent="0"><Label>Total EQUITY</Label><ColData>12000.00</ColData></RowData>
    </ReportData>
  </GeneralSummaryReportRs>
</QBXMLMsgsRs></QBXML>"""

MOCK_CASH_FLOW_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<QBXML><QBXMLMsgsRs>
  <GeneralDetailReportRs requestID="3" statusCode="0" statusSeverity="Info" statusMessage="Status OK">
    <StatusCode>0</StatusCode>
    <ReportData>
      <RowData rowType="Section"  indent="0"><Label>Operating Activities</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Net Income</Label><ColData>56500.00</ColData></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Depreciation</Label><ColData>500.00</ColData></RowData>
      <RowData rowType="Subtotal" indent="0"><Label>Net Cash from Operating Activities</Label><ColData>57000.00</ColData></RowData>
      <RowData rowType="Section"  indent="0"><Label>Investing Activities</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Equipment Purchase</Label><ColData>-5000.00</ColData></RowData>
      <RowData rowType="Subtotal" indent="0"><Label>Net Cash from Investing Activities</Label><ColData>-5000.00</ColData></RowData>
      <RowData rowType="Section"  indent="0"><Label>Financing Activities</Label></RowData>
      <RowData rowType="DataRow"  indent="1"><Label>Loan Repayment</Label><ColData>-1000.00</ColData></RowData>
      <RowData rowType="Subtotal" indent="0"><Label>Net Cash from Financing Activities</Label><ColData>-1000.00</ColData></RowData>
      <RowData rowType="GrandTotal" indent="0"><Label>Net Increase in Cash</Label><ColData>51000.00</ColData></RowData>
    </ReportData>
  </GeneralDetailReportRs>
</QBXMLMsgsRs></QBXML>"""

MOCK_AR_AGING_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<QBXML><QBXMLMsgsRs>
  <AgingReportRs requestID="4" statusCode="0" statusSeverity="Info" statusMessage="Status OK">
    <StatusCode>0</StatusCode>
    <ReportData>
      <ColDesc><ColID>1</ColID><ColTitle>Current</ColTitle></ColDesc>
      <ColDesc><ColID>2</ColID><ColTitle>1 - 30</ColTitle></ColDesc>
      <ColDesc><ColID>3</ColID><ColTitle>31 - 60</ColTitle></ColDesc>
      <ColDesc><ColID>4</ColID><ColTitle>61 - 90</ColTitle></ColDesc>
      <ColDesc><ColID>5</ColID><ColTitle>&gt; 90</ColTitle></ColDesc>
      <ColDesc><ColID>6</ColID><ColTitle>TOTAL</ColTitle></ColDesc>
      <RowData rowType="DataRow">
        <Label>Acme Corp</Label>
        <ColData>1000.00</ColData><ColData>500.00</ColData><ColData>0.00</ColData>
        <ColData>0.00</ColData><ColData>0.00</ColData><ColData>1500.00</ColData>
      </RowData>
      <RowData rowType="DataRow">
        <Label>Big Client LLC</Label>
        <ColData>0.00</ColData><ColData>0.00</ColData><ColData>2500.00</ColData>
        <ColData>0.00</ColData><ColData>0.00</ColData><ColData>2500.00</ColData>
      </RowData>
      <RowData rowType="GrandTotal">
        <Label>TOTAL</Label>
        <ColData>1000.00</ColData><ColData>500.00</ColData><ColData>2500.00</ColData>
        <ColData>0.00</ColData><ColData>0.00</ColData><ColData>4000.00</ColData>
      </RowData>
    </ReportData>
  </AgingReportRs>
</QBXMLMsgsRs></QBXML>"""

MOCK_VENDOR_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<QBXML><QBXMLMsgsRs>
  <GeneralSummaryReportRs requestID="5" statusCode="0" statusSeverity="Info" statusMessage="Status OK">
    <StatusCode>0</StatusCode>
    <ReportData>
      <RowData rowType="DataRow"    indent="0"><Label>Office Depot</Label><ColData>500.00</ColData></RowData>
      <RowData rowType="DataRow"    indent="0"><Label>AT&amp;T</Label><ColData>150.00</ColData></RowData>
      <RowData rowType="DataRow"    indent="0"><Label>Amazon</Label><ColData>-25.00</ColData></RowData>
      <RowData rowType="GrandTotal" indent="0"><Label>TOTAL</Label><ColData>625.00</ColData></RowData>
    </ReportData>
  </GeneralSummaryReportRs>
</QBXMLMsgsRs></QBXML>"""

MOCK_ERROR_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<QBXML><QBXMLMsgsRs>
  <GeneralSummaryReportRs requestID="1" statusCode="3180" statusSeverity="Error" statusMessage="Report could not be generated.">
    <StatusCode>3180</StatusCode>
    <StatusMessage>Report could not be generated.</StatusMessage>
  </GeneralSummaryReportRs>
</QBXMLMsgsRs></QBXML>"""

MOCK_EMPTY_CASH_FLOW_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<QBXML><QBXMLMsgsRs>
  <GeneralDetailReportRs requestID="3" statusCode="0">
    <StatusCode>0</StatusCode>
  </GeneralDetailReportRs>
</QBXMLMsgsRs></QBXML>"""


# ── _parse_amount ─────────────────────────────────────────────────────────────

class TestParseAmount:
    def test_simple_positive(self):
        assert _parse_amount("1234.56") == pytest.approx(1234.56)

    def test_simple_negative(self):
        assert _parse_amount("-1234.56") == pytest.approx(-1234.56)

    def test_with_commas(self):
        assert _parse_amount("1,234,567.89") == pytest.approx(1234567.89)

    def test_negative_with_comma(self):
        assert _parse_amount("-1,234.56") == pytest.approx(-1234.56)

    def test_with_dollar_sign(self):
        assert _parse_amount("$500.00") == pytest.approx(500.0)

    def test_zero(self):
        assert _parse_amount("0.00") == pytest.approx(0.0)

    def test_integer_string(self):
        assert _parse_amount("500") == pytest.approx(500.0)

    def test_none_returns_none(self):
        assert _parse_amount(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_amount("") is None

    def test_whitespace_returns_none(self):
        assert _parse_amount("   ") is None

    def test_non_numeric_returns_none(self):
        assert _parse_amount("N/A") is None


# ── _infer_account_type ───────────────────────────────────────────────────────

class TestInferAccountType:
    def test_income_keyword(self):
        assert _infer_account_type("Total Income", "Subtotal", "profit_loss") == "Income"

    def test_revenue_keyword(self):
        assert _infer_account_type("Services Revenue", "DataRow", "profit_loss") == "Income"

    def test_sales_keyword(self):
        assert _infer_account_type("Product Sales", "DataRow", "profit_loss") == "Income"

    def test_net_income_label(self):
        assert _infer_account_type("Net Income", "GrandTotal", "profit_loss") == "NetIncome"

    def test_net_loss_label(self):
        assert _infer_account_type("Net Loss", "GrandTotal", "profit_loss") == "NetIncome"

    def test_grand_total_is_net_income(self):
        assert _infer_account_type("Anything", "GrandTotal", "profit_loss") == "NetIncome"

    def test_cogs_keyword(self):
        assert _infer_account_type("Cost of Goods Sold", "DataRow", "profit_loss") == "COGS"

    def test_generic_expense(self):
        assert _infer_account_type("Office Supplies", "DataRow", "profit_loss") == "Expense"

    def test_balance_sheet_asset(self):
        assert _infer_account_type("ASSETS", "Section", "balance_sheet") == "Asset"

    def test_balance_sheet_liability(self):
        assert _infer_account_type("LIABILITIES & EQUITY", "Section", "balance_sheet") == "Liability"

    def test_balance_sheet_equity(self):
        assert _infer_account_type("EQUITY", "Section", "balance_sheet") == "Equity"

    def test_balance_sheet_default_is_asset(self):
        assert _infer_account_type("Unknown Section", "DataRow", "balance_sheet") == "Asset"


# ── _classify_activity ────────────────────────────────────────────────────────

class TestClassifyActivity:
    def test_operating(self):
        assert _classify_activity("Operating Activities") == "Operating"

    def test_operations_variant(self):
        assert _classify_activity("Cash from Operations") == "Operating"

    def test_investing(self):
        assert _classify_activity("Investing Activities") == "Investing"

    def test_financing(self):
        assert _classify_activity("Financing Activities") == "Financing"

    def test_net_increase(self):
        assert _classify_activity("Net Increase in Cash") == "Net"

    def test_net_decrease(self):
        assert _classify_activity("Net Decrease in Cash") == "Net"

    def test_beginning_cash(self):
        assert _classify_activity("Beginning Cash Balance") == "Net"

    def test_ending_cash(self):
        assert _classify_activity("Ending Cash Balance") == "Net"

    def test_unknown_defaults_to_operating(self):
        assert _classify_activity("Something Unrecognised") == "Operating"


# ── P&L parsing ───────────────────────────────────────────────────────────────

class TestParseProfitLoss:
    def setup_method(self):
        self.rows = parse_general_summary_report(MOCK_PL_XML, WEEK, START, END, "profit_loss")

    def test_returns_list(self):
        assert isinstance(self.rows, list)

    def test_row_count(self):
        # 2 sections + 2+2 data rows + 2 subtotals + 1 grand total = 9
        assert len(self.rows) == 9

    def test_report_week_on_every_row(self):
        assert all(r["report_week"] == "2026-03-30" for r in self.rows)

    def test_period_dates_on_every_row(self):
        assert all(r["period_start"] == "2026-03-30" for r in self.rows)
        assert all(r["period_end"] == "2026-04-05" for r in self.rows)

    def test_net_income_row_is_subtotal(self):
        net = next(r for r in self.rows if "Net Income" in r["account_name"])
        assert net["is_subtotal"] is True

    def test_net_income_amount(self):
        net = next(r for r in self.rows if "Net Income" in r["account_name"])
        assert net["amount"] == pytest.approx(56500.0)

    def test_net_income_account_type(self):
        net = next(r for r in self.rows if "Net Income" in r["account_name"])
        assert net["account_type"] == "NetIncome"

    def test_data_rows_not_subtotal(self):
        revenue = next(r for r in self.rows if r["account_name"] == "Services Revenue")
        assert revenue["is_subtotal"] is False

    def test_parent_tracking_for_detail_rows(self):
        # "Services Revenue" (indent=1) should have parent "Income" (indent=0)
        revenue = next(r for r in self.rows if r["account_name"] == "Services Revenue")
        assert revenue["parent_account"] == "Income"

    def test_top_level_sections_have_no_parent(self):
        income_section = next(r for r in self.rows if r["account_name"] == "Income")
        assert income_section["parent_account"] is None

    def test_row_order_sequential(self):
        orders = [r["row_order"] for r in self.rows]
        assert orders == list(range(len(self.rows)))

    def test_income_account_type(self):
        income = next(r for r in self.rows if r["account_name"] == "Income")
        assert income["account_type"] == "Income"

    def test_error_xml_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="QB returned status 3180"):
            parse_general_summary_report(MOCK_ERROR_XML, WEEK, START, END, "profit_loss")


# ── Balance Sheet parsing ─────────────────────────────────────────────────────

class TestParseBalanceSheet:
    def setup_method(self):
        self.rows = parse_general_summary_report(MOCK_BS_XML, WEEK, START, END, "balance_sheet")

    def test_returns_rows(self):
        assert len(self.rows) > 0

    def test_report_date_on_every_row(self):
        assert all(r["report_date"] == "2026-04-05" for r in self.rows)

    def test_has_account_subtype_key(self):
        assert all("account_subtype" in r for r in self.rows)

    def test_asset_type_present(self):
        assert any(r["account_type"] == "Asset" for r in self.rows)

    def test_liability_type_present(self):
        assert any(r["account_type"] == "Liability" for r in self.rows)

    def test_equity_type_present(self):
        assert any(r["account_type"] == "Equity" for r in self.rows)

    def test_checking_account_row(self):
        row = next((r for r in self.rows if r["account_name"] == "Checking Account"), None)
        assert row is not None
        assert row["amount"] == pytest.approx(10000.0)
        assert row["parent_account"] == "ASSETS"

    def test_no_report_week_key_for_balance_sheet(self):
        # report_week is set to None for balance_sheet rows
        assert all(r["report_week"] is None for r in self.rows)


# ── Expense by Vendor parsing ─────────────────────────────────────────────────

class TestParseExpenseByVendor:
    def setup_method(self):
        self.rows = parse_general_summary_report(MOCK_VENDOR_XML, WEEK, START, END, "expense_by_vendor")

    def test_row_count(self):
        # 3 data rows + 1 grand total = 4
        assert len(self.rows) == 4

    def test_has_vendor_name_key(self):
        assert all("vendor_name" in r for r in self.rows)

    def test_no_account_name_key(self):
        assert all("account_name" not in r for r in self.rows)

    def test_office_depot_amount(self):
        row = next(r for r in self.rows if r["vendor_name"] == "Office Depot")
        assert row["amount"] == pytest.approx(500.0)

    def test_negative_amount(self):
        row = next(r for r in self.rows if r["vendor_name"] == "Amazon")
        assert row["amount"] == pytest.approx(-25.0)

    def test_xml_entity_decoded(self):
        # AT&amp;T in XML → AT&T in parsed output
        row = next((r for r in self.rows if "AT" in r["vendor_name"]), None)
        assert row is not None
        assert row["vendor_name"] == "AT&T"

    def test_report_week(self):
        assert all(r["report_week"] == "2026-03-30" for r in self.rows)


# ── Cash Flow parsing ─────────────────────────────────────────────────────────

class TestParseCashFlow:
    def setup_method(self):
        self.rows = parse_cash_flow_report(MOCK_CASH_FLOW_XML, WEEK, START, END)

    def test_returns_rows(self):
        assert len(self.rows) > 0

    def test_section_labels_excluded(self):
        labels = {r["account_name"] for r in self.rows}
        assert "Operating Activities" not in labels
        assert "Investing Activities" not in labels
        assert "Financing Activities" not in labels

    def test_operating_rows_present(self):
        assert any(r["activity_type"] == "Operating" for r in self.rows)

    def test_investing_rows_present(self):
        assert any(r["activity_type"] == "Investing" for r in self.rows)

    def test_financing_rows_present(self):
        assert any(r["activity_type"] == "Financing" for r in self.rows)

    def test_negative_investing_amount(self):
        row = next(r for r in self.rows if "Equipment" in r["account_name"])
        assert row["amount"] == pytest.approx(-5000.0)
        assert row["activity_type"] == "Investing"

    def test_not_derived(self):
        assert all(r["is_derived"] is False for r in self.rows)

    def test_report_week(self):
        assert all(r["report_week"] == "2026-03-30" for r in self.rows)

    def test_empty_response_returns_empty_list(self):
        assert parse_cash_flow_report(MOCK_EMPTY_CASH_FLOW_XML, WEEK, START, END) == []


# ── derive_cash_flow_from_balance_sheet ───────────────────────────────────────

class TestDeriveCashFlow:
    PL_ROWS = [
        {"account_type": "NetIncome", "is_subtotal": True,  "amount": 56500.0},
        {"account_type": "Income",    "is_subtotal": False, "amount": 60000.0},
    ]

    def test_returns_two_rows(self):
        rows = derive_cash_flow_from_balance_sheet(self.PL_ROWS, [], WEEK, START, END)
        assert len(rows) == 2

    def test_net_income_row_amount(self):
        rows = derive_cash_flow_from_balance_sheet(self.PL_ROWS, [], WEEK, START, END)
        net = next(r for r in rows if "Net Income" in r["account_name"])
        assert net["amount"] == pytest.approx(56500.0)

    def test_net_income_row_activity(self):
        rows = derive_cash_flow_from_balance_sheet(self.PL_ROWS, [], WEEK, START, END)
        net = next(r for r in rows if "Net Income" in r["account_name"])
        assert net["activity_type"] == "Operating"

    def test_estimated_net_cash_row(self):
        rows = derive_cash_flow_from_balance_sheet(self.PL_ROWS, [], WEEK, START, END)
        est = next(r for r in rows if "Estimated" in r["account_name"])
        assert est["is_subtotal"] is True
        assert est["activity_type"] == "Net"
        assert est["amount"] == pytest.approx(56500.0)

    def test_all_rows_marked_derived(self):
        rows = derive_cash_flow_from_balance_sheet(self.PL_ROWS, [], WEEK, START, END)
        assert all(r["is_derived"] is True for r in rows)

    def test_no_net_income_row_defaults_to_zero(self):
        rows = derive_cash_flow_from_balance_sheet([], [], WEEK, START, END)
        net = next(r for r in rows if "Net Income" in r["account_name"])
        assert net["amount"] == pytest.approx(0.0)

    def test_report_week_date(self):
        rows = derive_cash_flow_from_balance_sheet(self.PL_ROWS, [], WEEK, START, END)
        assert all(r["report_week"] == "2026-03-30" for r in rows)


# ── AR Aging parsing ──────────────────────────────────────────────────────────

class TestParseAgingReport:
    def setup_method(self):
        self.rows = parse_aging_report(MOCK_AR_AGING_XML, END)

    def test_grand_total_row_excluded(self):
        # GrandTotal row is skipped; only 2 customer data rows returned
        assert len(self.rows) == 2

    def test_customer_names(self):
        names = {r["customer_name"] for r in self.rows}
        assert "Acme Corp" in names
        assert "Big Client LLC" in names

    def test_current_amount(self):
        acme = next(r for r in self.rows if r["customer_name"] == "Acme Corp")
        assert acme["current_amount"] == pytest.approx(1000.0)

    def test_days_1_30(self):
        acme = next(r for r in self.rows if r["customer_name"] == "Acme Corp")
        assert acme["days_1_30"] == pytest.approx(500.0)

    def test_days_31_60(self):
        big = next(r for r in self.rows if r["customer_name"] == "Big Client LLC")
        assert big["days_31_60"] == pytest.approx(2500.0)

    def test_days_61_90_zero(self):
        acme = next(r for r in self.rows if r["customer_name"] == "Acme Corp")
        assert acme["days_61_90"] == pytest.approx(0.0)

    def test_total_balance(self):
        acme = next(r for r in self.rows if r["customer_name"] == "Acme Corp")
        assert acme["total_balance"] == pytest.approx(1500.0)

    def test_report_date(self):
        assert all(r["report_date"] == "2026-04-05" for r in self.rows)

    def test_column_detection_from_col_desc(self):
        # Verify the parser used ColDesc headers (not fallback positions)
        # by checking that Big Client's 31-60 bucket is correctly identified
        big = next(r for r in self.rows if r["customer_name"] == "Big Client LLC")
        assert big["current_amount"] == pytest.approx(0.0)
        assert big["days_31_60"] == pytest.approx(2500.0)
