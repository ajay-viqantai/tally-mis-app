"""
@ui.page('/company/{company}/{year_range}/{category}/segment/{segment}/{ledger}')
-- monthly trend for one clicked ledger, plus that month's company-wide
sales alongside it for context. Shown both as a bar+line chart (ledger
amount as bars, company sales as a line on a second axis, since the two
are usually very different scales) and as a table underneath.

`segment` and `ledger` are URL-encoded (decoded here with unquote()).
"""

from __future__ import annotations

from urllib.parse import unquote

from nicegui import ui

from app import cache
from app.ui.dashboard import CATEGORY_SLUGS, _parse_year_range


@ui.page("/company/{company}/{year_range}/{category}/segment/{segment}/{ledger}")
def ledger_detail_page(company: str, year_range: str, category: str, segment: str, ledger: str) -> None:
    if category not in CATEGORY_SLUGS:
        ui.label(f"Unknown category '{category}'").classes("text-negative")
        ui.button("Back to dashboard", on_click=lambda: ui.navigate.to(f"/company/{company}/{year_range}"))
        return

    display_name, _report_key, _bucket_key = CATEGORY_SLUGS[category]
    segment_name = unquote(segment)
    ledger_name = unquote(ledger)
    from_date, to_date = _parse_year_range(year_range)

    with ui.row().classes("items-center gap-2"):
        ui.button(
            "< " + segment_name,
            on_click=lambda: ui.navigate.to(f"/company/{company}/{year_range}/{category}/segment/{segment}"),
        )
        ui.label(f"{company} - {ledger_name}").classes("text-lg")

    try:
        ledger_monthly = cache.get_ledger_monthly(company, from_date, to_date, ledger_name)
        company_monthly_pl = cache.get_monthly_pl(company, from_date, to_date)
    except Exception as exc:
        ui.label(f"Could not load monthly data from Tally: {exc}").classes("text-negative")
        return

    sales_by_month = {row["Month"]: row["Sales"] for row in company_monthly_pl}

    year_total = round(sum(r["Amount"] for r in ledger_monthly), 2)
    ui.label(f"Year total: {year_total:,.2f}").classes("text-md mt-2")

    months = [r["Month"] for r in ledger_monthly]
    ledger_values = [r["Amount"] for r in ledger_monthly]
    sales_values = [round(sales_by_month.get(m, 0.0), 2) for m in months]

    # dual y-axis: this ledger's monthly amount is usually much smaller
    # than total company sales, so they'd flatten to nothing on one shared
    # axis -- bars for the ledger (left axis), a line for sales (right axis).
    ui.echart({
        "tooltip": {"trigger": "axis"},
        "legend": {"data": [display_name, "Company sales"]},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": {"type": "category", "data": months},
        "yAxis": [
            {"type": "value", "name": display_name, "position": "left"},
            {"type": "value", "name": "Sales", "position": "right"},
        ],
        "series": [
            {
                "name": display_name,
                "type": "bar",
                "yAxisIndex": 0,
                "data": ledger_values,
                "itemStyle": {"color": "#ee6666"},
            },
            {
                "name": "Company sales",
                "type": "line",
                "yAxisIndex": 1,
                "data": sales_values,
                "itemStyle": {"color": "#5470c6"},
                "smooth": True,
            },
        ],
    }).classes("w-full h-72 mt-2")

    columns = [
        {"name": "month", "label": "Month", "field": "month", "align": "left"},
        {"name": "amount", "label": display_name, "field": "amount", "align": "right"},
        {"name": "sales", "label": "Company sales that month", "field": "sales", "align": "right"},
    ]
    rows = [
        {
            "month": r["Month"],
            "amount": f"{r['Amount']:,.2f}",
            "sales": f"{sales_by_month.get(r['Month'], 0.0):,.2f}",
        }
        for r in ledger_monthly
    ]
    ui.table(columns=columns, rows=rows, row_key="month").classes("w-full mt-4")