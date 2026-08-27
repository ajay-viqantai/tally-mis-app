"""
Parses Tally's XML responses into plain dicts.

parse_amt, parse_qty, parse_groups, parse_ledgers, parse_pnl_stock and
parse_stock_items are ported unchanged from the original script -- these
request/response shapes were already verified there.

parse_companies is NEW and currently a stub -- Tally's "List of Companies"
response shape needs to be confirmed against a live instance first (see
the TODO in tdl_requests.py).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_QTY_RE = re.compile(r"[-+]?\d*\.?\d+")


def parse_amt(v: str | None) -> float:
    """Tally amounts come formatted like '40,30,880.00' or blank/None for zero."""
    if v is None:
        return 0.0
    v = v.strip().replace(",", "")
    if not v:
        return 0.0
    try:
        return abs(float(v))
    except ValueError:
        return 0.0


def parse_qty(v: str | None) -> float:
    """Tally quantities come as '240 nos' / '515 Nos' -- strip the unit."""
    if not v:
        return 0.0
    m = _QTY_RE.search(v)
    return float(m.group()) if m else 0.0


def parse_groups(root: ET.Element) -> list[dict]:
    groups = []
    names = [e.text for e in root.findall("FLDGNAME")]
    parents = [e.text for e in root.findall("FLDPARENT")]
    for n, p in zip(names, parents):
        groups.append({"name": (n or "").strip(), "parent": (p or "").strip()})
    return groups


def parse_ledgers(root: ET.Element) -> list[dict]:
    ledgers = []
    names = [e.text for e in root.findall("FLDLNAME")]
    parents = [e.text for e in root.findall("FLDLPARENT")]
    closings = [e.text for e in root.findall("FLDCLOSING")]
    for n, p, c in zip(names, parents, closings):
        ledgers.append({
            "name": (n or "").strip(),
            "parent": (p or "").strip(),
            "closing": parse_amt(c),
        })
    return ledgers


def parse_pnl_stock(root: ET.Element) -> dict[str, float]:
    """Pull top-level figures from the native P&L export: Opening/Closing
    Stock (not ledgers at all), plus Sales, Purchases, and Indirect
    Expenses -- used as Tally's own ground truth for cross-checking."""
    names = [(e.text or "").strip() for e in root.findall(".//DSPACCNAME/DSPDISPNAME")]
    amts = root.findall(".//PLAMT")
    result = {
        "opening_stock": 0.0, "closing_stock": 0.0,
        "sales": 0.0, "purchases": 0.0, "indirect_expenses": 0.0,
    }
    for name, amt_node in zip(names, amts):
        sub = amt_node.find("PLSUBAMT")
        main = amt_node.find("BSMAINAMT")
        val = parse_amt(sub.text if sub is not None else None) or parse_amt(main.text if main is not None else None)
        low = name.lower()
        if "opening stock" in low:
            result["opening_stock"] = val
        elif "closing stock" in low:
            result["closing_stock"] = val
        elif low.startswith("sales accounts"):
            result["sales"] = val
        elif "purchase accounts" in low:
            result["purchases"] = val
        elif low.startswith("indirect expenses"):
            result["indirect_expenses"] = val
    result["net_profit"] = round(
        result["sales"] - (result["opening_stock"] + result["purchases"] - result["closing_stock"])
        - result["indirect_expenses"], 2
    )
    return result


def parse_stock_items(root: ET.Element) -> list[dict]:
    """Parse the Collection-style Stock Item export (nested <STOCKITEM>
    tags, not the flat repeated-field style used by groups/ledgers)."""
    items = []
    for node in root.findall(".//STOCKITEM"):
        name = node.get("NAME", "").strip()
        parent_el = node.find("PARENT")
        parent = (parent_el.text or "").strip() if parent_el is not None else ""
        opening_el = node.find("OPENINGBALANCE")
        opening_qty = parse_qty(opening_el.text if opening_el is not None else None)
        if name:
            items.append({"name": name, "parent": parent, "opening_qty": opening_qty})
    return items


# --------------------------------------------------------------------------
# NEW -- stub until the real "List of Companies" XML shape is confirmed.
# --------------------------------------------------------------------------

def parse_companies(root: ET.Element) -> list[str]:
    """TODO: not yet verified against a live Tally response. This is a
    best guess (looking for <COMPANY NAME="..."> elements) -- replace the
    body once we have real output to match against."""
    names = [c.get("NAME", "").strip() for c in root.findall(".//COMPANY")]
    return [n for n in names if n]