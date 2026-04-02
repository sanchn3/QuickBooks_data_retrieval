"""
test_supabase.py — Integration tests for supabase_uploader.py.

Requires real Supabase credentials in .env (SUPABASE_URL + service_role SUPABASE_KEY).
All tests are automatically skipped when .env is absent or credentials are placeholders.

Test rows use report_week/report_date = 1999-01-04 / 1999-01-10 (clearly historical/fake)
and are fully cleaned up before and after each test.
"""

import os

import pytest

# ── Credential check (runs at collection time) ────────────────────────────────
_KEY = os.environ.get("SUPABASE_KEY", "")
_HAS_REAL_CREDS = (
    len(_KEY) > 30
    and _KEY != "placeholder-key"
    and _KEY.startswith("eyJ")   # service_role JWTs start with eyJ
)


@pytest.fixture(autouse=True, scope="module")
def require_real_creds():
    """Skip the entire module when real Supabase credentials aren't available."""
    if not _HAS_REAL_CREDS:
        pytest.skip("No real Supabase credentials in .env — skipping integration tests")


# ── Imports (only evaluated when tests actually run) ──────────────────────────
from supabase_uploader import (   # noqa: E402
    _get_client,
    upsert_profit_loss,
    upsert_balance_sheet,
    upsert_cash_flow,
    upsert_ar_aging,
    upsert_expense_by_vendor,
    log_sync_result,
)
from datetime import date          # noqa: E402

_TEST_WEEK  = date(1999, 1, 4)   # Monday
_TEST_START = date(1999, 1, 4)
_TEST_END   = date(1999, 1, 10)  # Sunday
_TEST_DATE  = date(1999, 1, 10)


# ── Cleanup fixture ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup():
    """Wipe test rows before and after every test."""
    _purge()
    yield
    _purge()


def _purge():
    client = _get_client()
    for table, col in [
        ("profit_loss",       "report_week"),
        ("cash_flow",         "report_week"),
        ("expense_by_vendor", "report_week"),
        ("balance_sheet",     "report_date"),
        ("ar_aging",          "report_date"),
    ]:
        try:
            val = "1999-01-04" if col == "report_week" else "1999-01-10"
            client.schema("financials").table(table).delete().eq(col, val).execute()
        except Exception:
            pass
    try:
        client.schema("financials").table("report_sync_log").delete().eq("report_week", "1999-01-04").execute()
    except Exception:
        pass


# ── Connection ────────────────────────────────────────────────────────────────

class TestConnection:
    def test_client_initialises(self):
        assert _get_client() is not None

    def test_can_query_sync_log(self):
        result = (
            _get_client()
            .schema("financials")
            .table("report_sync_log")
            .select("id")
            .limit(1)
            .execute()
        )
        assert result is not None

    def test_service_role_can_access_private_schema(self):
        # financials schema is locked to anon/authenticated; service_role must still work
        result = (
            _get_client()
            .schema("financials")
            .table("profit_loss")
            .select("id")
            .limit(1)
            .execute()
        )
        assert result is not None


# ── Profit & Loss ─────────────────────────────────────────────────────────────

class TestUpsertProfitLoss:
    def _row(self, account_name="Test Revenue", amount=1000.0):
        return {
            "report_week":  _TEST_WEEK.isoformat(),
            "period_start": _TEST_START.isoformat(),
            "period_end":   _TEST_END.isoformat(),
            "account_name": account_name,
            "account_type": "Income",
            "parent_account": None,
            "amount":       amount,
            "is_subtotal":  False,
            "row_order":    0,
        }

    def test_upsert_returns_count(self):
        assert upsert_profit_loss([self._row()]) == 1

    def test_upsert_multiple_rows(self):
        rows = [self._row("Revenue A", 1000.0), self._row("Revenue B", 2000.0)]
        assert upsert_profit_loss(rows) == 2

    def test_upsert_is_idempotent(self):
        upsert_profit_loss([self._row(amount=1000.0)])
        count = upsert_profit_loss([self._row(amount=9999.0)])  # same conflict key
        assert count == 1

    def test_empty_input_returns_zero(self):
        assert upsert_profit_loss([]) == 0


# ── Balance Sheet ─────────────────────────────────────────────────────────────

class TestUpsertBalanceSheet:
    def _row(self, account_name="Test Asset"):
        return {
            "report_date":    _TEST_DATE.isoformat(),
            "period_start":   _TEST_START.isoformat(),  # stripped by upsert_balance_sheet
            "period_end":     _TEST_END.isoformat(),    # stripped by upsert_balance_sheet
            "account_name":   account_name,
            "account_type":   "Asset",
            "account_subtype": None,
            "parent_account": None,
            "amount":         5000.0,
            "is_subtotal":    False,
            "row_order":      0,
        }

    def test_upsert_returns_count(self):
        assert upsert_balance_sheet([self._row()]) == 1

    def test_empty_input_returns_zero(self):
        assert upsert_balance_sheet([]) == 0


# ── Cash Flow ─────────────────────────────────────────────────────────────────

class TestUpsertCashFlow:
    def _row(self, account_name="Test Net Income", derived=False):
        return {
            "report_week":   _TEST_WEEK.isoformat(),
            "period_start":  _TEST_START.isoformat(),
            "period_end":    _TEST_END.isoformat(),
            "activity_type": "Operating",
            "account_name":  account_name,
            "amount":        5000.0,
            "is_subtotal":   False,
            "is_derived":    derived,
            "row_order":     0,
        }

    def test_upsert_returns_count(self):
        assert upsert_cash_flow([self._row()]) == 1

    def test_derived_flag_stored(self):
        upsert_cash_flow([self._row(derived=True)])
        result = (
            _get_client()
            .schema("financials")
            .table("cash_flow")
            .select("is_derived")
            .eq("report_week", _TEST_WEEK.isoformat())
            .execute()
        )
        assert result.data[0]["is_derived"] is True

    def test_empty_input_returns_zero(self):
        assert upsert_cash_flow([]) == 0


# ── AR Aging ──────────────────────────────────────────────────────────────────

class TestUpsertArAging:
    def _row(self, customer="Test Customer"):
        return {
            "report_date":    _TEST_DATE.isoformat(),
            "customer_name":  customer,
            "current_amount": 100.0,
            "days_1_30":      50.0,
            "days_31_60":     0.0,
            "days_61_90":     0.0,
            "days_over_90":   0.0,
            "total_balance":  150.0,
        }

    def test_upsert_returns_count(self):
        assert upsert_ar_aging([self._row()]) == 1

    def test_empty_input_returns_zero(self):
        assert upsert_ar_aging([]) == 0


# ── Expense by Vendor ─────────────────────────────────────────────────────────

class TestUpsertExpenseByVendor:
    def _row(self, vendor="Test Vendor"):
        return {
            "report_week":  _TEST_WEEK.isoformat(),
            "period_start": _TEST_START.isoformat(),
            "period_end":   _TEST_END.isoformat(),
            "vendor_name":  vendor,
            "amount":       500.0,
        }

    def test_upsert_returns_count(self):
        assert upsert_expense_by_vendor([self._row()]) == 1

    def test_empty_input_returns_zero(self):
        assert upsert_expense_by_vendor([]) == 0


# ── Sync Log ──────────────────────────────────────────────────────────────────

class TestLogSyncResult:
    def test_log_success_does_not_raise(self):
        log_sync_result("profit_loss", _TEST_WEEK, "success", 5, None, 1.23)

    def test_log_error_does_not_raise(self):
        log_sync_result("balance_sheet", _TEST_WEEK, "error", 0, "Test error", 0.5)

    def test_log_row_appears_in_db(self):
        log_sync_result("profit_loss", _TEST_WEEK, "success", 3, None, 0.8)
        result = (
            _get_client()
            .schema("financials")
            .table("report_sync_log")
            .select("report_name,status,rows_upserted")
            .eq("report_week", _TEST_WEEK.isoformat())
            .execute()
        )
        assert len(result.data) >= 1
        row = result.data[0]
        assert row["report_name"] == "profit_loss"
        assert row["status"] == "success"
        assert row["rows_upserted"] == 3
