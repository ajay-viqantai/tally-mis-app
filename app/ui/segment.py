"""
@ui.page('/{company}/{year_range}/{category}/segment/{segment}') --
ledger list inside one clicked segment (e.g. "Chip Manufacturing"),
each with its amount for the selected period. Same month dropdown
pattern as category.py.

Clicking a ledger goes to ledger_detail.py.
"""

from __future__ import annotations

from urllib.parse import quote, unquote

from nicegui import ui

from app import cache
from app.domain.classify import group_by_segment
from app.domain.dates import month_windows
from app.ui.dashboard import CATEGORY_SLUGS, _parse_year_range


@ui.page("/company/{company}/{year_range}/{category}/segment/{segment}")
def segment_page(company: str, year_range: str, category: str, segment: str) -> None:
    if category not in CATEGORY_SLUGS:
        ui.label(f"Unknown category '{category}'").classes("text-negative")
        ui.button("Back to dashboard", on_click=lambda: ui.navigate.to(f"/company/{company}/{year_range}"))
        return

    display_name, _report_key, bucket_key = CATEGORY_SLUGS[category]
    segment_name = unquote(segment)
    from_date, to_date = _parse_year_range(year_range)

    with ui.row().classes("items-center gap-2"):
        ui.button("< " + display_name, on_click=lambda: ui.navigate.to(f"/company/{company}/{year_range}/{category}"))
        ui.label(f"{company} - {display_name} - {segment_name}").classes("text-lg")

    try:
        month_labels = [label for label, _f, _t in month_windows(from_date, to_date)]
    except Exception as exc:
        ui.label(f"Could not compute months: {exc}").classes("text-negative")
        return

    period_options = {"": "Full year"} | {m: m for m in month_labels}
    period_select = ui.select(period_options, value="").classes("w-48 mt-2")

    @ui.refreshable
    def ledger_list() -> None:
        month_label = period_select.value or None
        try:
            all_ledgers = cache.get_category_ledgers(company, from_date, to_date, bucket_key, month_label)
        except Exception as exc:
            ui.label(f"Could not load data from Tally: {exc}").classes("text-negative")
            return

        segments = group_by_segment(all_ledgers)
        rows = segments.get(segment_name, [])
        total = round(sum(r["Amount"] for r in rows), 2)
        ui.label(f"Total: {total:,.2f}").classes("text-md mt-2")

        if not rows:
            ui.label("No ledgers found for this selection.").classes("text-sm text-secondary mt-2")
            return

        sorted_rows = sorted(rows, key=lambda r: -r["Amount"])
        chart_rows = list(reversed(sorted_rows))  # echarts draws bottom-to-top; reverse for largest-on-top

        ui.echart({
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"left": "3%", "right": "6%", "containLabel": True},
            "xAxis": {"type": "value"},
            "yAxis": {
                "type": "category",
                "data": [r["Ledger"] for r in chart_rows],
                "axisLabel": {"fontSize": 10},
            },
            "series": [{
                "type": "bar",
                "data": [r["Amount"] for r in chart_rows],
                "itemStyle": {"color": "#91cc75"},
            }],
        }).classes("w-full mt-2").style(f"height: {max(240, 32 * len(chart_rows))}px")

        with ui.column().classes("w-full mt-4 gap-1"):
            for row in sorted_rows:
                ledger_slug = quote(row["Ledger"], safe="")
                with ui.row().classes(
                    "w-full justify-between items-center cursor-pointer p-2 hover:bg-gray-100"
                ).on(
                    "click",
                    lambda s=ledger_slug: ui.navigate.to(
                        f"/company/{company}/{year_range}/{category}/segment/{segment}/{s}"
                    ),
                ):
                    ui.label(row["Ledger"])
                    ui.label(f"{row['Amount']:,.2f}")

    ledger_list()
    period_select.on("update:model-value", lambda: ledger_list.refresh())