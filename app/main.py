"""
Entrypoint.
"""

from nicegui import app as nicegui_app
from nicegui import ui

from app.config import settings
from app.exports import EXPORTS_DIR
from app.ui import company_select, dashboard, category, segment, ledger_detail  # noqa: F401  (registers routes)

nicegui_app.add_static_files("/exports", str(EXPORTS_DIR))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(port=settings.ui_port, title="Tally MIS")