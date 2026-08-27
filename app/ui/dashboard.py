"""
@ui.page('/company/{company}/{year_range}') -- totals screen.

Routes live under /company/... (not bare /{company}/{year_range}) so
they can't collide with two-segment browser probe requests like
/.well-known/appspecific/... that Chrome/Edge send automatically -- a
fully wildcard 2-segment route would otherwise swallow those and crash
on year_range.split("-").

year_range is "{from_date}-{to_date}" (e.g. "20260401-20270331"), built
by company_select.py and read back apart here.

Shows the dashboard totals (Sales, Purchases, Indirect Expenses, Net
Profit, etc. -- from build_report via cache.get_annual_data) as cards
plus a bar chart, a year dropdown defaulting to the current FY with the
prior FY selectable, and one clickable tile per P&L category leading
into app/ui/category.py.

CATEGORY_SLUGS is shared with category.py (imported from here) so the
URL slug <-> bucket-key <-> display-name mapping only lives in one place.
"""

from __future__ import annotations

from nicegui import ui

from app import cache, excel_export
from app.domain.dates import current_financial_year, financial_year_label, previous_financial_year

# slug -> (display name, report dict key for the yearly total tile, classify_ledgers bucket key)
CATEGORY_SLUGS: dict[str, tuple[str, str, str]] = {
    "sales": ("Sales", "Data_Sales", "Sales"),
    "direct-income": ("Direct Income", "Data_Direct_Income", "Direct Income"),
    "purchase": ("Purchase", "Data_Purchases", "Purchase"),
    "direct-expense": ("Direct Expense", "Data_Direct_Expenses", "Direct Expense"),
    "indirect-income": ("Indirect Income", "Data_Indirect_Income", "Indirect Income"),
    "indirect-expense": ("Indirect Expense", "Data_Indirect_Expenses", "Indirect Expense"),
}


def _parse_year_range(year_range: str) -> tuple[str, str]:
    from_date, to_date = year_range.split("-")
    return from_date, to_date


def _category_total(report: dict, key: str) -> float:
    return round(sum(row["Amount"] for row in report.get(key, [])), 2)


@ui.page("/company/{company}/{year_range}")
def dashboard_page(company: str, year_range: str) -> None:
    from_date, to_date = _parse_year_range(year_range)

    with ui.row().classes("items-center justify-between w-full"):
        ui.label(company).classes("text-lg")

        cur_from, cur_to = current_financial_year()
        prev_from, prev_to = previous_financial_year(cur_from, cur_to)
        year_options = {
            f"{cur_from}-{cur_to}": financial_year_label(cur_from),
            f"{prev_from}-{prev_to}": financial_year_label(prev_from),
        }
        if year_range not in year_options:
            year_options[year_range] = financial_year_label(from_date)

        ui.select(
            year_options,
            value=year_range,
            on_change=lambda e: ui.navigate.to(f"/company/{company}/{e.value}"),
        ).classes("w-48")

    try:
        data = cache.get_annual_data(company, from_date, to_date)
    except Exception as exc:
        ui.label(f"Could not load data from Tally: {exc}").classes("text-negative")
        ui.button("Back", on_click=lambda: ui.navigate.to("/"))
        return

    report = data["report"]

    with ui.grid(columns=3).classes("gap-4 w-full mt-4"):
        for row in report["MIS_Dashboard"]:
            with ui.card():
                ui.label(row["Metric"]).classes("text-sm text-secondary")
                ui.label(f"{row['Value']:,.2f}").classes("text-lg")

    ui.echart({
        "tooltip": {},
        "xAxis": {
            "type": "category",
            "data": [row["Metric"] for row in report["MIS_Dashboard"]],
            "axisLabel": {"rotate": 20, "fontSize": 10},
        },
        "yAxis": {"type": "value"},
        "series": [{
            "type": "bar",
            "data": [row["Value"] for row in report["MIS_Dashboard"]],
            "itemStyle": {"color": "#5470c6"},
        }],
    }).classes("w-full h-64 mt-4")

    ui.label("Categories").classes("text-lg mt-6")
    with ui.grid(columns=3).classes("gap-4 w-full"):
        for slug, (display_name, report_key, _bucket_key) in CATEGORY_SLUGS.items():
            total = _category_total(report, report_key)
            with ui.card().classes("cursor-pointer").on(
                "click", lambda s=slug: ui.navigate.to(f"/company/{company}/{year_range}/{s}")
            ):
                ui.label(display_name).classes("text-sm text-secondary")
                ui.label(f"{total:,.2f}").classes("text-lg")

    def _download_report() -> None:
        try:
            path = excel_export.build_workbook(company, from_date, to_date)
        except Exception as exc:
            ui.notify(f"Could not generate report: {exc}", type="negative")
            return
        ui.download(f"/exports/{path.name}")

    with ui.row().classes("mt-6 gap-2"):
        ui.button("Download Excel report", on_click=_download_report)
        ui.button(
            "Refresh from Tally",
            on_click=lambda: (cache.refresh(company, from_date, to_date), ui.navigate.reload()),
        )