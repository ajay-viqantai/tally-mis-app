"""
Ledger classification: walks each ledger's group up to one of Tally's
six reserved P&L primary groups. These names are fixed by Tally itself
in every company, which is what makes this classification generic
(no per-company ledger-naming regex needed).

Ported unchanged from the original script.
"""

from __future__ import annotations

import re

_PL_PRIMARY_GROUPS = {
    "Sales Accounts": "Sales",
    "Purchase Accounts": "Purchase",
    "Direct Incomes": "Direct Income",
    "Direct Expenses": "Direct Expense",
    "Indirect Incomes": "Indirect Income",
    "Indirect Expenses": "Indirect Expense",
}

# Used only for GST identification under Duties & Taxes -- GST is read
# from ledger balances, not back-calculated at an assumed rate.
_GST_LEDGER_PATTERNS = {
    "output_cgst": re.compile(r"output.*\bcgst\b", re.IGNORECASE),
    "output_sgst": re.compile(r"output.*\bsgst\b", re.IGNORECASE),
    "output_igst": re.compile(r"output.*\bigst\b", re.IGNORECASE),
    "input_cgst":  re.compile(r"input.*\bcgst\b", re.IGNORECASE),
    "input_sgst":  re.compile(r"input.*\bsgst\b", re.IGNORECASE),
    "input_igst":  re.compile(r"input.*\bigst\b", re.IGNORECASE),
}


def build_parent_map(groups: list[dict]) -> dict[str, str]:
    return {g["name"]: g["parent"] for g in groups}


def resolve_bucket(group_name: str, parent_map: dict[str, str]) -> str | None:
    """Walk up the group hierarchy until we hit one of the 6 reserved P&L
    primary groups, or run off the top (-> None, i.e. Balance Sheet item)."""
    seen = set()
    current = group_name
    while current and current not in seen:
        if current in _PL_PRIMARY_GROUPS:
            return _PL_PRIMARY_GROUPS[current]
        seen.add(current)
        current = parent_map.get(current)
    return None


def guess_segment(ledger_name: str) -> str | None:
    """Best-effort segment/business-line detector: many companies prefix
    ledger names with a segment tag before ' - ' (e.g. 'Chip Manufacturing
    - Factory Rent'). Heuristic bonus, not required for the core report."""
    parts = [p.strip() for p in ledger_name.split(" - ")]
    if len(parts) < 2:
        return None
    first = parts[0]
    if re.fullmatch(r"[A-Z0-9 ]{2,15}", first) and len(parts) > 2:
        return parts[1]
    return first


def classify_ledgers(ledgers: list[dict], parent_map: dict[str, str]) -> tuple[dict[str, list[dict]], dict[str, float]]:
    """Buckets P&L ledgers by the 6 reserved primary groups, and
    separately tallies GST duty ledgers found anywhere under
    Duties & Taxes. Shared by the annual report and the per-month
    cash-flow / monthly-trend views."""
    buckets: dict[str, list[dict]] = {v: [] for v in _PL_PRIMARY_GROUPS.values()}
    gst_totals = {k: 0.0 for k in _GST_LEDGER_PATTERNS}

    for l in ledgers:
        bucket = resolve_bucket(l["parent"], parent_map)
        if bucket:
            buckets[bucket].append({"Ledger": l["name"], "Group": l["parent"], "Amount": l["closing"]})
            continue
        if l["parent"]:
            cur, seen = l["parent"], set()
            under_duties = False
            while cur and cur not in seen:
                if cur == "Duties & Taxes":
                    under_duties = True
                    break
                seen.add(cur)
                cur = parent_map.get(cur)
            if under_duties:
                for key, pattern in _GST_LEDGER_PATTERNS.items():
                    if pattern.search(l["name"]):
                        gst_totals[key] += l["closing"]
                        break
    return buckets, gst_totals

def group_by_segment(ledger_rows: list[dict]) -> dict[str, list[dict]]:
    """Groups already-classified ledger rows (dicts with Ledger/Group/
    Amount, as produced by classify_ledgers) by guess_segment(), putting
    anything with no detected segment prefix into 'Other'.

    Note: for a name like "Trading - Books - Warehouse Staff Salaries",
    guess_segment() returns just "Trading" (the first ' - ' segment), not
    "Trading - Books" -- if your naming convention nests two levels like
    that, tell me and I'll adjust it to take the first two parts when the
    second part also looks like a category tag rather than a description."""
    groups: dict[str, list[dict]] = {}
    for row in ledger_rows:
        seg = guess_segment(row["Ledger"]) or "Other"
        groups.setdefault(seg, []).append(row)
    return groups