# Tally MIS drill-down app

## Prerequisites
- Python 3.10+
- Tally Prime/ERP9 running locally, with the XML server enabled:
  F1 (Help) > Settings > Connectivity > Client/Server configuration,
  turn on TCP/IP server, note the port (default 9000).
- This machine must be able to reach that Tally instance (same machine,
  or same LAN if Tally is on another PC).

## Setup
    cd tally-mis-app
    python -m venv .venv
    source .venv/bin/activate      # Windows: .venv\Scripts\activate
    pip install -r requirements.txt

## Run
    python app/main.py
    python -m app.main

Then open http://localhost:8080 in a browser.

## Layout
- app/tally/     -- talks to Tally's XML server (HTTP + TDL requests + parsing)
- app/domain/     -- pure business logic (classification, report/period math)
- app/cache.py    -- per (company, year) cache so clicks don't re-hit Tally
- app/ui/         -- NiceGUI pages, one per screen
- app/main.py     -- entrypoint
- legacy/         -- the original standalone Excel-export script, kept as-is
