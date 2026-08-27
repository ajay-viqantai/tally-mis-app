"""
App-wide configuration.

Same shape as the Config dataclass in the original tally_mis_report_generic.py
script, minus output_file (the app doesn't write Excel) and minus a fixed
company/date range -- those are now chosen at runtime in the UI, not passed
on the command line.
"""

from dataclasses import dataclass


@dataclass
class Settings:
    tally_url: str = "http://127.0.0.1:9000"
    ui_port: int = 8080


settings = Settings()
