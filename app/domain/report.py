"""
Report-building logic: turns classified ledgers into the numbers each
screen needs (dashboard totals, category breakdowns, monthly trends).

build_report(), fetch_monthly_ledgers(), build_monthly_pl() and
build_cashflow_sheet() are ported from the original script, largely
unchanged -- note that fetch_monthly_ledgers/build_monthly_pl still call
Tally directly (same as the original), since month-wise data needs one
Tally call per calendar month regardless of app vs script. cache.py is
what will stop the app from re-doing this on every click -- it wraps
these functions and stores the result per (company, from_date, to_date).

Adjustment from the original: cfg: Config is replaced by plain
company / from_date / to_date args, since the app doesn't have one fixed
Config for the whole run anymore.
"""

from __future__ import annotations

import re

from app.domain.classify import build_parent_map, classify_ledgers
from app.domain.dates import month_windows
from app.tally.client import fetch_xml
from app.tally.parsers import parse_ledgers, parse_pnl_stock
from app.tally.tdl_requests import build_ledgers_request_for_range, build_pnl_request

_PEOPLE_COST_KEYWORDS = re.compile(
    r"salar|wage|staff|payroll|incentive|welfare|bonus|commission|hr\b|manpower",
    re.IGNORECASE,
)


def build_report(groups: list[dict], ledgers: list[dict], stock: dict[str, float]) -> dict[str, list[dict]]:
    """Annual P&L: Sales, Purchases, COGS, Gross Profit, Net Profit, GST,
    optional Segment P&L. This is the dashboard totals screen's data."""
    from app.domain.classify import guess_segment

    parent_map = build_parent_map(groups)
    buckets, gst_totals = classify_ledgers(ledgers, parent_map)

    segment_totals: dict[str, dict[str, float]] = {}
    for bucket_name, rows in buckets.items():
        for r in rows:
            seg = guess_segment(r["Ledger"])
            if seg:
                segment_totals.setdefault(seg, {v: 0.0 for v in buckets})
                segment_totals[seg][bucket_name] += r["Amount"]

    for b in buckets:
        buckets[b].sort(key=lambda r: -r["Amount"])

    def total(rows: list[dict]) -> float:
        return round(sum(r["Amount"] for r in rows), 2)

    sales = total(buckets["Sales"])
    direct_income = total(buckets["Direct Income"])
    purchases = total(buckets["Purchase"])
    direct_expense = total(buckets["Direct Expense"])
    indirect_income = total(buckets["Indirect Income"])
    indirect_expense = total(buckets["Indirect Expense"])

    opening_stock = stock.get("opening_stock", 0.0)
    closing_stock = stock.get("closing_stock", 0.0)

    cogs = round(opening_stock + purchases + direct_expense - closing_stock, 2)
    gross_profit = round(sales + direct_income - cogs, 2)
    net_profit = round(gross_profit + indirect_income - indirect_expense, 2)

    net_cgst = round(gst_totals["output_cgst"] - gst_totals["input_cgst"], 2)
    net_sgst = round(gst_totals["output_sgst"] - gst_totals["input_sgst"], 2)
    net_igst = round(gst_totals["output_igst"] - gst_totals["input_igst"], 2)

    pl_summary = [
        {"Particulars": "Sales Accounts", "Amount": sales},
        {"Particulars": "Direct Incomes", "Amount": direct_income},
        {"Particulars": "Opening Stock", "Amount": opening_stock},
        {"Particulars": "Purchase Accounts", "Amount": purchases},
        {"Particulars": "Direct Expenses", "Amount": direct_expense},
        {"Particulars": "Less: Closing Stock", "Amount": -closing_stock},
        {"Particulars": "Cost of Goods Sold", "Amount": cogs},
        {"Particulars": "Gross Profit", "Amount": gross_profit},
        {"Particulars": "Indirect Incomes", "Amount": indirect_income},
        {"Particulars": "Indirect Expenses", "Amount": indirect_expense},
        {"Particulars": "Net Profit", "Amount": net_profit},
    ]

    gst_summary = [
        {"Tax": "CGST", "Output": round(gst_totals["output_cgst"], 2), "Input": round(gst_totals["input_cgst"], 2), "Net Payable": net_cgst},
        {"Tax": "SGST", "Output": round(gst_totals["output_sgst"], 2), "Input": round(gst_totals["input_sgst"], 2), "Net Payable": net_sgst},
        {"Tax": "IGST", "Output": round(gst_totals["output_igst"], 2), "Input": round(gst_totals["input_igst"], 2), "Net Payable": net_igst},
        {"Tax": "TOTAL", "Output": round(sum(v for k, v in gst_totals.items() if k.startswith("output")), 2),
         "Input": round(sum(v for k, v in gst_totals.items() if k.startswith("input")), 2),
         "Net Payable": round(net_cgst + net_sgst + net_igst, 2)},
    ]

    segment_rows = []
    for seg, vals in sorted(segment_totals.items()):
        seg_sales = vals["Sales"] + vals["Direct Income"]
        seg_direct_cost = vals["Purchase"] + vals["Direct Expense"]
        seg_gp = seg_sales - seg_direct_cost
        seg_np = seg_gp + vals["Indirect Income"] - vals["Indirect Expense"]
        segment_rows.append({
            "Segment": seg, "Revenue": round(seg_sales, 2), "Direct Cost": round(seg_direct_cost, 2),
            "Gross Profit": round(seg_gp, 2), "Indirect Expense": round(vals["Indirect Expense"], 2),
            "Net Profit": round(seg_np, 2),
        })

    dashboard = [
        {"Metric": "Revenue (Sales + Direct Income)", "Value": round(sales + direct_income, 2)},
        {"Metric": "Cost of Goods Sold", "Value": cogs},
        {"Metric": "Gross Profit", "Value": gross_profit},
        {"Metric": "Indirect Expenses", "Value": indirect_expense},
        {"Metric": "Net Profit", "Value": net_profit},
        {"Metric": "Net GST Payable", "Value": round(net_cgst + net_sgst + net_igst, 2)},
    ]

    report = {
        "MIS_Dashboard": dashboard,
        "PL_Summary": pl_summary,
        "Data_Sales": buckets["Sales"],
        "Data_Direct_Income": buckets["Direct Income"],
        "Data_Purchases": buckets["Purchase"],
        "Data_Direct_Expenses": buckets["Direct Expense"],
        "Data_Indirect_Income": buckets["Indirect Income"],
        "Data_Indirect_Expenses": buckets["Indirect Expense"],
        "GST_Summary": gst_summary,
    }
    if segment_rows:
        report["Segment_PL"] = segment_rows
    return report


def fetch_monthly_ledgers(company: str, from_date: str, to_date: str) -> list[tuple[str, str, str, list[dict]]]:
    """Fetch the Ledger List once per calendar month in the period."""
    result = []
    for label, win_from, win_to in month_windows(from_date, to_date):
        month_ledgers = parse_ledgers(fetch_xml(build_ledgers_request_for_range(company, win_from, win_to)))
        result.append((label, win_from, win_to, month_ledgers))
    return result


def build_monthly_pl(company: str, groups: list[dict], monthly_ledgers: list[tuple[str, str, str, list[dict]]]) -> list[dict]:
    """Month-wise accrual P&L -- the ledger-detail page's monthly trend."""
    parent_map = build_parent_map(groups)
    rows = []
    for label, win_from, win_to, month_ledgers in monthly_ledgers:
        buckets, _ = classify_ledgers(month_ledgers, parent_map)
        totals = {k: round(sum(r["Amount"] for r in v), 2) for k, v in buckets.items()}

        month_pnl_xml = fetch_xml(build_pnl_request(company, win_from, win_to))
        month_stock = parse_pnl_stock(month_pnl_xml)

        cogs = round(month_stock["opening_stock"] + totals["Purchase"] + totals["Direct Expense"] - month_stock["closing_stock"], 2)
        gross_profit = round(totals["Sales"] + totals["Direct Income"] - cogs, 2)
        net_profit = round(gross_profit + totals["Indirect Income"] - totals["Indirect Expense"], 2)

        rows.append({
            "Month": label,
            "Sales": totals["Sales"],
            "Purchases": totals["Purchase"],
            "Gross Profit": gross_profit,
            "Indirect Expenses": totals["Indirect Expense"],
            "Net Profit": net_profit,
        })
    return rows


def build_cashflow_sheet(groups: list[dict], monthly_ledgers: list[tuple[str, str, str, list[dict]]]) -> list[dict]:
    """Monthly cash-flow-style view: Revenue / GST / Direct Variable Cost
    / People Cost & Operating Expenses / Cash Inflow-Outflow / Net
    Cashflow / GST payable. Reuses monthly_ledgers -- no extra Tally calls."""
    parent_map = build_parent_map(groups)
    month_labels = [label for label, *_ in monthly_ledgers]

    per_month = {}
    all_direct_cost_ledgers: set[str] = set()
    all_people_cost_ledgers: set[str] = set()
    all_opex_ledgers: set[str] = set()

    for label, _wf, _wt, month_ledgers in monthly_ledgers:
        buckets, gst_totals = classify_ledgers(month_ledgers, parent_map)

        direct_cost_rows = buckets["Purchase"] + buckets["Direct Expense"]
        people_rows, opex_rows = [], []
        for r in buckets["Indirect Expense"]:
            (people_rows if _PEOPLE_COST_KEYWORDS.search(r["Ledger"]) else opex_rows).append(r)

        revenue = round(sum(r["Amount"] for r in buckets["Sales"] + buckets["Direct Income"]), 2)
        other_income = round(sum(r["Amount"] for r in buckets["Indirect Income"]), 2)
        output_gst = round(gst_totals["output_cgst"] + gst_totals["output_sgst"] + gst_totals["output_igst"], 2)
        input_gst = round(gst_totals["input_cgst"] + gst_totals["input_sgst"] + gst_totals["input_igst"], 2)
        direct_cost_total = round(sum(r["Amount"] for r in direct_cost_rows), 2)
        people_cost_total = round(sum(r["Amount"] for r in people_rows), 2)
        opex_total = round(sum(r["Amount"] for r in opex_rows), 2)

        cash_inflow = round(revenue + output_gst + other_income, 2)
        gross_margin = round(cash_inflow - direct_cost_total, 2)
        cash_outflow = round(direct_cost_total + people_cost_total + opex_total, 2)
        net_cashflow = round(cash_inflow - cash_outflow, 2)

        per_month[label] = {
            "revenue": revenue, "output_gst": output_gst, "other_income": other_income,
            "cash_inflow": cash_inflow, "direct_cost_rows": {r["Ledger"]: r["Amount"] for r in direct_cost_rows},
            "direct_cost_total": direct_cost_total, "gross_margin": gross_margin,
            "people_rows": {r["Ledger"]: r["Amount"] for r in people_rows}, "people_cost_total": people_cost_total,
            "opex_rows": {r["Ledger"]: r["Amount"] for r in opex_rows}, "opex_total": opex_total,
            "cash_outflow": cash_outflow, "net_cashflow": net_cashflow,
            "input_gst": input_gst, "net_gst": round(output_gst - input_gst, 2),
        }
        all_direct_cost_ledgers.update(per_month[label]["direct_cost_rows"])
        all_people_cost_ledgers.update(per_month[label]["people_rows"])
        all_opex_ledgers.update(per_month[label]["opex_rows"])

    def row(label: str, key_fn, total_override=None) -> dict:
        r = {"Particulars": label}
        for m in month_labels:
            r[m] = key_fn(per_month[m])
        r["Total"] = total_override() if total_override else round(sum(r[m] for m in month_labels), 2)
        return r

    def blank() -> dict:
        r = {"Particulars": ""}
        for m in month_labels:
            r[m] = ""
        r["Total"] = ""
        return r

    def ledger_row(name: str, store_key: str) -> dict:
        return row(name, lambda pm: round(pm[store_key].get(name, 0.0), 2))

    rows = [
        row("Revenue", lambda pm: pm["revenue"]),
        row("GST on Sales (Output)", lambda pm: pm["output_gst"]),
        row("Other Operating Income", lambda pm: pm["other_income"]),
        row("Cash Inflow", lambda pm: pm["cash_inflow"]),
    ]
    mom_row = {"Particulars": "MoM Growth % (Revenue)"}
    prev = None
    for m in month_labels:
        rev = per_month[m]["revenue"]
        mom_row[m] = round(100 * (rev - prev) / prev, 2) if prev else 0.0
        prev = rev
    mom_row["Total"] = ""
    rows.append(mom_row)
    rows.append(blank())
    rows.append({"Particulars": "DIRECT VARIABLE COST", **{m: "" for m in month_labels}, "Total": ""})
    for name in sorted(all_direct_cost_ledgers):
        rows.append(ledger_row(name, "direct_cost_rows"))
    rows.append(row("Direct Variable Cost Total", lambda pm: pm["direct_cost_total"]))
    rows.append(row("Gross Margin", lambda pm: pm["gross_margin"]))
    total_cash_inflow = round(sum(per_month[m]["cash_inflow"] for m in month_labels), 2)
    total_gross_margin = round(sum(per_month[m]["gross_margin"] for m in month_labels), 2)
    rows.append(row(
        "% Margin", lambda pm: round(100 * pm["gross_margin"] / pm["cash_inflow"], 2) if pm["cash_inflow"] else 0.0,
        total_override=lambda: round(100 * total_gross_margin / total_cash_inflow, 2) if total_cash_inflow else 0.0,
    ))
    rows.append(blank())
    rows.append({"Particulars": "PEOPLE COST (name-matched)", **{m: "" for m in month_labels}, "Total": ""})
    for name in sorted(all_people_cost_ledgers):
        rows.append(ledger_row(name, "people_rows"))
    rows.append(row("People Cost Subtotal", lambda pm: pm["people_cost_total"]))
    rows.append(blank())
    rows.append({"Particulars": "OPERATING EXPENSES", **{m: "" for m in month_labels}, "Total": ""})
    for name in sorted(all_opex_ledgers):
        rows.append(ledger_row(name, "opex_rows"))
    rows.append(row("Operating Expenses Subtotal", lambda pm: pm["opex_total"]))
    rows.append(blank())
    rows.append(row("Cash Outflow", lambda pm: pm["cash_outflow"]))
    rows.append(row("Net Cashflow / Operating Profit", lambda pm: pm["net_cashflow"]))
    total_net_cashflow = round(sum(per_month[m]["net_cashflow"] for m in month_labels), 2)
    rows.append(row(
        "Net Cashflow %", lambda pm: round(100 * pm["net_cashflow"] / pm["cash_inflow"], 2) if pm["cash_inflow"] else 0.0,
        total_override=lambda: round(100 * total_net_cashflow / total_cash_inflow, 2) if total_cash_inflow else 0.0,
    ))
    rows.append(blank())
    rows.append(row("GST on Sales (Output)", lambda pm: pm["output_gst"]))
    rows.append(row("Input GST on Purchases", lambda pm: pm["input_gst"]))
    rows.append(row("Net GST Payable", lambda pm: pm["net_gst"]))
    return rows