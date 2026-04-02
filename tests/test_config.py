"""
test_config.py — Unit tests for config.py date helpers.

No .env or Supabase credentials required.
"""

from datetime import date

import pytest

from config import get_report_week


class TestGetReportWeek:
    """get_report_week(ref) returns the last complete Mon–Sun week before ref."""

    def test_from_tuesday(self):
        # Tuesday 2026-04-07 → last full week: Mon 2026-03-30 – Sun 2026-04-05
        mon, start, end, sunday = get_report_week(date(2026, 4, 7))
        assert mon == date(2026, 3, 30)
        assert start == date(2026, 3, 30)
        assert end == date(2026, 4, 5)
        assert sunday == date(2026, 4, 5)

    def test_from_monday(self):
        # Monday 2026-04-06 → last full week: Mon 2026-03-30 – Sun 2026-04-05
        mon, start, end, sunday = get_report_week(date(2026, 4, 6))
        assert mon == date(2026, 3, 30)
        assert end == date(2026, 4, 5)

    def test_from_sunday(self):
        # Sunday 2026-04-05 is still in the current week — last full week is prior
        mon, start, end, sunday = get_report_week(date(2026, 4, 5))
        assert mon == date(2026, 3, 23)
        assert end == date(2026, 3, 29)

    def test_from_saturday(self):
        # Saturday 2026-04-04 → same prior week as Sunday
        mon, start, end, sunday = get_report_week(date(2026, 4, 4))
        assert mon == date(2026, 3, 23)
        assert end == date(2026, 3, 29)

    def test_from_wednesday(self):
        mon, start, end, sunday = get_report_week(date(2026, 4, 8))
        assert mon == date(2026, 3, 30)
        assert end == date(2026, 4, 5)

    def test_week_spans_exactly_6_days(self):
        mon, start, end, sunday = get_report_week(date(2026, 4, 7))
        assert (end - start).days == 6

    def test_report_week_is_always_monday(self):
        for ref_day in range(1, 8):  # test all 7 days of a week
            ref = date(2026, 4, ref_day)
            mon, *_ = get_report_week(ref)
            assert mon.weekday() == 0, f"Expected Monday for ref={ref}, got weekday {mon.weekday()}"

    def test_report_date_sunday_is_always_sunday(self):
        for ref_day in range(1, 8):
            ref = date(2026, 4, ref_day)
            *_, sunday = get_report_week(ref)
            assert sunday.weekday() == 6, f"Expected Sunday for ref={ref}"

    def test_period_start_equals_monday(self):
        mon, start, end, sunday = get_report_week(date(2026, 4, 7))
        assert start == mon

    def test_period_end_equals_sunday(self):
        mon, start, end, sunday = get_report_week(date(2026, 4, 7))
        assert end == sunday

    def test_returns_four_tuple(self):
        result = get_report_week(date(2026, 4, 7))
        assert len(result) == 4

    def test_all_values_are_dates(self):
        result = get_report_week(date(2026, 4, 7))
        assert all(isinstance(v, date) for v in result)

    def test_defaults_to_today_without_error(self):
        # Should not raise
        result = get_report_week()
        assert len(result) == 4

    def test_year_boundary(self):
        # Tuesday 2026-01-06 → last week: Mon 2025-12-29 – Sun 2026-01-04
        mon, start, end, sunday = get_report_week(date(2026, 1, 6))
        assert mon == date(2025, 12, 29)
        assert end == date(2026, 1, 4)
        assert mon.year == 2025
        assert end.year == 2026

    def test_consistent_across_same_week(self):
        # Tue, Wed, Thu of the same week should all return the same prior Mon–Sun
        ref_dates = [date(2026, 4, 7), date(2026, 4, 8), date(2026, 4, 9)]
        results = [get_report_week(d) for d in ref_dates]
        assert all(r == results[0] for r in results)
