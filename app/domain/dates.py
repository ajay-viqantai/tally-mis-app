"""
Date/period helpers.

month_windows() is ported unchanged from the original script.

current_financial_year(), previous_financial_year() and
financial_year_label() are NEW -- the original script took --from-date
and --to-date directly on the command line. Here the year dropdown needs
to compute the current Apr-Mar Indian financial year itself and offer
prior years without the user typing dates.
"""

from __future__ import annotations

import calendar
from datetime import date


def month_windows(from_date: str, to_date: str) -> list[tuple[str, str, str]]:
    """Split a YYYYMMDD..YYYYMMDD range into calendar-month (label, from, to)
    windows, e.g. ('Apr-26', '20260401', '20260430')."""
    start = date(int(from_date[:4]), int(from_date[4:6]), int(from_date[6:8]))
    end = date(int(to_date[:4]), int(to_date[4:6]), int(to_date[6:8]))

    windows = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        first_day = date(y, m, 1)
        last_day_num = calendar.monthrange(y, m)[1]
        last_day = date(y, m, last_day_num)
        win_start = max(first_day, start)
        win_end = min(last_day, end)
        label = f"{calendar.month_abbr[m]}-{str(y)[2:]}"
        windows.append((label, win_start.strftime("%Y%m%d"), win_end.strftime("%Y%m%d")))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return windows


def current_financial_year() -> tuple[str, str]:
    """Indian financial year: 1 Apr - 31 Mar. If today is Jan-Mar, the
    current FY started last calendar year; otherwise it started this
    calendar year."""
    today = date.today()
    if today.month >= 4:
        start = date(today.year, 4, 1)
        end = date(today.year + 1, 3, 31)
    else:
        start = date(today.year - 1, 4, 1)
        end = date(today.year, 3, 31)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def previous_financial_year(from_date: str, to_date: str) -> tuple[str, str]:
    """Given one FY's (from_date, to_date), return the prior FY's -- used
    to populate the year dropdown's earlier options."""
    start = date(int(from_date[:4]), int(from_date[4:6]), int(from_date[6:8]))
    end = date(int(to_date[:4]), int(to_date[4:6]), int(to_date[6:8]))
    prev_start = date(start.year - 1, start.month, start.day)
    prev_end = date(end.year - 1, end.month, end.day)
    return prev_start.strftime("%Y%m%d"), prev_end.strftime("%Y%m%d")


def financial_year_label(from_date: str) -> str:
    """'20260401' -> 'FY 2026-27' -- for the dropdown display text."""
    y = int(from_date[:4])
    return f"FY {y}-{str(y + 1)[2:]}"