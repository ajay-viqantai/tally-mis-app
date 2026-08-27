"""
Per (company, year) in-memory cache.

NEW -- not in the original script, which only ever ran once per process.
Here the same company+year gets visited repeatedly as the user clicks
company -> dashboard -> category -> ledger -> back -> another ledger, so
without this every one of those clicks would re-hit Tally.

Two tiers, fetched lazily:
  - annual data (groups, ledgers, stock, the dashboard report) -- fetched
    once when a company+year is first opened.
  - monthly data (fetch_monthly_ledgers + the monthly P&L / cash-flow
    built from it) -- more expensive (one extra Tally call per month), so
    only fetched the first time a ledger-detail page is actually opened
    for that company+year, not up front.

This is a plain process-memory dict, cleared on restart -- fine for a
single-user local app. If this ever needs to serve multiple concurrent
users reliably, this is the file that would need to grow (e.g. a TTL, or
an explicit refresh button per company+year, since Tally data changes as
vouchers get entered).
"""

from __future__ import annotations

from app.domain.classify import build_parent_map, classify_ledgers
from app.domain.report import build_cashflow_sheet, build_monthly_pl, build_report, fetch_monthly_ledgers
from app.tally.client import fetch_xml
from app.tally.parsers import parse_groups, parse_ledgers, parse_pnl_stock
from app.tally.tdl_requests import build_groups_request, build_ledgers_request, build_pnl_request

_cache: dict[tuple[str, str, str], dict] = {}


def _key(company: str, from_date: str, to_date: str) -> tuple[str, str, str]:
    return (company, from_date, to_date)


def get_annual_data(company: str, from_date: str, to_date: str) -> dict:
    """groups, ledgers, stock/PnL, and the built dashboard report for one
    company+year. Fetched from Tally on first call, cached after that."""
    key = _key(company, from_date, to_date)
    if key not in _cache:
        groups = parse_groups(fetch_xml(build_groups_request(company)))
        ledgers = parse_ledgers(fetch_xml(build_ledgers_request(company, from_date, to_date)))
        stock = parse_pnl_stock(fetch_xml(build_pnl_request(company, from_date, to_date)))
        report = build_report(groups, ledgers, stock)
        _cache[key] = {
            "groups": groups,
            "ledgers": ledgers,
            "stock": stock,
            "report": report,
        }
    return _cache[key]


def get_monthly_pl(company: str, from_date: str, to_date: str) -> list[dict]:
    """Month-wise P&L trend for the ledger-detail page. Triggers the
    monthly Tally fetch on first call for this company+year; cached
    after that (shared with get_cashflow, see below)."""
    data = get_annual_data(company, from_date, to_date)
    _ensure_monthly_ledgers(data, company, from_date, to_date)
    if "monthly_pl" not in data:
        data["monthly_pl"] = build_monthly_pl(company, data["groups"], data["monthly_ledgers"])
    return data["monthly_pl"]


def get_cashflow(company: str, from_date: str, to_date: str) -> list[dict]:
    """Monthly cash-flow view. Reuses the same monthly ledger fetch as
    get_monthly_pl if it already ran for this company+year."""
    data = get_annual_data(company, from_date, to_date)
    _ensure_monthly_ledgers(data, company, from_date, to_date)
    if "cashflow" not in data:
        data["cashflow"] = build_cashflow_sheet(data["groups"], data["monthly_ledgers"])
    return data["cashflow"]


def _ensure_monthly_ledgers(data: dict, company: str, from_date: str, to_date: str) -> None:
    if "monthly_ledgers" not in data:
        data["monthly_ledgers"] = fetch_monthly_ledgers(company, from_date, to_date)


def refresh(company: str, from_date: str, to_date: str) -> None:
    """Drop the cached entry for one company+year so the next request
    re-fetches from Tally -- for a manual 'refresh data' action in the UI,
    since Tally figures change as new vouchers get entered."""
    _cache.pop(_key(company, from_date, to_date), None)

def get_ledger_monthly(company: str, from_date: str, to_date: str, ledger_name: str) -> list[dict]:
    """One ledger's own amount for each month -- e.g. 'what did Office
    Rent cost in each month of the year'. Reuses the same monthly ledger
    fetch as get_monthly_pl/get_cashflow if it already ran."""
    data = get_annual_data(company, from_date, to_date)
    _ensure_monthly_ledgers(data, company, from_date, to_date)
    rows = []
    for label, _wf, _wt, month_ledgers in data["monthly_ledgers"]:
        amount = next((l["closing"] for l in month_ledgers if l["name"] == ledger_name), 0.0)
        rows.append({"Month": label, "Amount": round(amount, 2)})
    return rows

def get_category_ledgers(company: str, from_date: str, to_date: str, bucket_key: str, month_label: str | None = None) -> list[dict]:
    """Ledger rows for one P&L bucket, for the full year or one month
    (pass month_label like 'Apr-26'). Powers the month dropdown on the
    category/segment pages."""
    data = get_annual_data(company, from_date, to_date)
    parent_map = build_parent_map(data["groups"])

    if month_label is None:
        buckets, _ = classify_ledgers(data["ledgers"], parent_map)
        return buckets.get(bucket_key, [])

    _ensure_monthly_ledgers(data, company, from_date, to_date)
    for label, _wf, _wt, month_ledgers in data["monthly_ledgers"]:
        if label == month_label:
            buckets, _ = classify_ledgers(month_ledgers, parent_map)
            return buckets.get(bucket_key, [])
    return []