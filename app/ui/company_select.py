"""
@ui.page('/') -- landing page.

Tries to list every company in the connected Tally instance via
parse_companies() (still unverified -- see parsers.py). If that comes
back empty, or you haven't confirmed the response shape yet, the manual
text field below it works either way -- type the exact company name as
it appears in Tally.

Picking/entering a company navigates to the dashboard page for the
current financial year (app/ui/dashboard.py, next file).
"""

from __future__ import annotations

from nicegui import ui

from app.domain.dates import current_financial_year
from app.tally.client import fetch_xml
from app.tally.parsers import parse_companies
from app.tally.tdl_requests import build_companies_request


def _go_to_dashboard(company: str) -> None:
    company = company.strip()
    if not company:
        ui.notify("Enter or select a company first", type="warning")
        return
    from_date, to_date = current_financial_year()
    ui.navigate.to(f"/company/{company}/{from_date}-{to_date}")


@ui.page("/")
def company_select_page() -> None:
    ui.label("Select company").classes("text-lg")

    companies: list[str] = []
    fetch_error: str | None = None
    try:
        companies = parse_companies(fetch_xml(build_companies_request()))
    except Exception as exc:  # Tally not running, wrong URL, unexpected response shape, etc.
        fetch_error = str(exc)

    if companies:
        selected = {"value": companies[0]}
        ui.select(companies, value=companies[0], on_change=lambda e: selected.update(value=e.value)).classes("w-80")
        ui.button("Open", on_click=lambda: _go_to_dashboard(selected["value"]))
    else:
        if fetch_error:
            ui.label(f"Could not list companies automatically ({fetch_error}).").classes("text-sm text-warning")
        else:
            ui.label("No companies returned automatically.").classes("text-sm text-warning")
        ui.label("Enter the company name exactly as it appears in Tally instead:").classes("text-sm")
        manual = ui.input("Company name").classes("w-80")
        ui.button("Open", on_click=lambda: _go_to_dashboard(manual.value or ""))