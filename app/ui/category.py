"""
@ui.page('/{company}/{year_range}/{category}') -- segment breakdown for
one clicked category (e.g. Indirect Expenses).

Ledgers are grouped by guess_segment() -- e.g. "Chip Manufacturing -
Factory Rent" and "Chip Manufacturing - Machine Maintenance" both roll
up under a "Chip Manufacturing" tile with a combined total. A month
dropdown switches the totals between the full year and any single month.

Clicking a segment tile goes to segment.py.
"""

from __future__ import annotations

from urllib.parse import quote

from nicegui import ui

from app import cache
from app.domain.classify import group_by_segment
from app.domain.dates import month_windows
from app.ui.dashboard import CATEGORY_SLUGS, _parse_year_range


@ui.page("/company/{company}/{year_range}/{category}")
def category_page(company: str, year_range: str, category: str) -> None:
    if category not in CATEGORY_SLUGS:
        ui.label(f"Unknown category '{category}'").classes("text-negative")
        ui.button("Back to dashboard", on_click=lambda: ui.navigate.to(f"/company/{company}/{year_range}"))
        return

    display_name, _report_key, bucket_key = CATEGORY_SLUGS[category]
    from_date, to_date = _parse_year_range(year_range)

    with ui.row().classes("items-center gap-2"):
        ui.button("< Dashboard", on_click=lambda: ui.navigate.to(f"/company/{company}/{year_range}"))
        ui.label(f"{company} - {display_name}").classes("text-lg")

    try:
        month_labels = [label for label, _f, _t in month_windows(from_date, to_date)]
    except Exception as exc:
        ui.label(f"Could not compute months: {exc}").classes("text-negative")
        return

    period_options = {"": "Full year"} | {m: m for m in month_labels}
    period_select = ui.select(period_options, value="").classes("w-48 mt-2")

    @ui.refreshable
    def segment_list() -> None:
        month_label = period_select.value or None
        try:
            ledgers = cache.get_category_ledgers(company, from_date, to_date, bucket_key, month_label)
        except Exception as exc:
            ui.label(f"Could not load data from Tally: {exc}").classes("text-negative")
            return

        segments = group_by_segment(ledgers)
        total = round(sum(r["Amount"] for r in ledgers), 2)
        ui.label(f"Total: {total:,.2f}").classes("text-md mt-2")

        if not ledgers:
            ui.label("No ledgers found for this selection.").classes("text-sm text-secondary mt-2")
            return

        segment_totals = sorted(
            ((seg, round(sum(r["Amount"] for r in rows), 2)) for seg, rows in segments.items()),
            key=lambda st: -st[1],
        )

        ui.echart({
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "left": "left", "textStyle": {"fontSize": 10}},
            "series": [{
                "name": display_name,
                "type": "pie",
                "radius": "65%",
                "data": [{"name": seg, "value": seg_total} for seg, seg_total in segment_totals],
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.3)"}},
            }],
        }).classes("w-full h-80 mt-2")

        with ui.column().classes("w-full mt-4 gap-1"):
            for seg, seg_total in segment_totals:
                seg_slug = quote(seg, safe="")
                with ui.row().classes(
                    "w-full justify-between items-center cursor-pointer p-2 hover:bg-gray-100"
                ).on("click", lambda s=seg_slug: ui.navigate.to(f"/company/{company}/{year_range}/{category}/segment/{s}")):
                    ui.label(seg)
                    ui.label(f"{seg_total:,.2f}")
    segment_list()
    period_select.on("update:model-value", lambda: segment_list.refresh())