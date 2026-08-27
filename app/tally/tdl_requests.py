"""
TDL request templates and builders sent to Tally.

The four *_TDL templates and their builders below are ported unchanged
from the original script -- they were verified against real Tally output.

_COMPANIES_TDL is NEW (the original script took --company as a fixed CLI
argument, so it never needed to list companies). It uses Tally's built-in
"List of Companies" report. I have not been able to test this against a
live Tally instance -- when you wire up parsers.py, run this one first by
itself and check the raw XML it returns before trusting the parser.
"""

_GROUPS_TDL = """<ENVELOPE>
 <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>GroupList</ID></HEADER>
 <BODY><DESC>
  <STATICVARIABLES>
   <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
   <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  </STATICVARIABLES>
  <TDL><TDLMESSAGE>
   <REPORT NAME="GroupList"><FORMS>GroupForm</FORMS></REPORT>
   <FORM NAME="GroupForm"><TOPPARTS>GroupPart</TOPPARTS></FORM>
   <PART NAME="GroupPart">
    <LINES>GroupLine</LINES>
    <REPEAT>GroupLine : GroupColl</REPEAT>
    <SCROLLED>Vertical</SCROLLED>
   </PART>
   <LINE NAME="GroupLine"><FIELDS>FldGName,FldParent,FldIsDeemedPositive</FIELDS></LINE>
   <FIELD NAME="FldGName"><SET>$Name</SET></FIELD>
   <FIELD NAME="FldParent"><SET>$Parent</SET></FIELD>
   <FIELD NAME="FldIsDeemedPositive"><SET>$IsDeemedPositive</SET></FIELD>
   <COLLECTION NAME="GroupColl" ISMODIFY="No">
    <TYPE>Group</TYPE>
    <FETCH>NAME,PARENT,ISDEEMEDPOSITIVE</FETCH>
   </COLLECTION>
  </TDLMESSAGE></TDL>
 </DESC></BODY>
</ENVELOPE>"""

_LEDGERS_TDL = """<ENVELOPE>
 <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>LedgerList</ID></HEADER>
 <BODY><DESC>
  <STATICVARIABLES>
   <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
   <SVFROMDATE>{from_date}</SVFROMDATE>
   <SVTODATE>{to_date}</SVTODATE>
   <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  </STATICVARIABLES>
  <TDL><TDLMESSAGE>
   <REPORT NAME="LedgerList"><FORMS>LedgerForm</FORMS></REPORT>
   <FORM NAME="LedgerForm"><TOPPARTS>LedgerPart</TOPPARTS></FORM>
   <PART NAME="LedgerPart">
    <LINES>LedgerLine</LINES>
    <REPEAT>LedgerLine : LedgerColl</REPEAT>
    <SCROLLED>Vertical</SCROLLED>
   </PART>
   <LINE NAME="LedgerLine"><FIELDS>FldLName,FldLParent,FldOpening,FldClosing</FIELDS></LINE>
   <FIELD NAME="FldLName"><SET>$Name</SET></FIELD>
   <FIELD NAME="FldLParent"><SET>$Parent</SET></FIELD>
   <FIELD NAME="FldOpening"><SET>$OpeningBalance</SET></FIELD>
   <FIELD NAME="FldClosing"><SET>$ClosingBalance</SET></FIELD>
   <COLLECTION NAME="LedgerColl" ISMODIFY="No">
    <TYPE>Ledger</TYPE>
    <FETCH>NAME,PARENT,OPENINGBALANCE,CLOSINGBALANCE</FETCH>
   </COLLECTION>
  </TDLMESSAGE></TDL>
 </DESC></BODY>
</ENVELOPE>"""

_PNL_TDL = """<ENVELOPE>
 <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>Profit and Loss</ID></HEADER>
 <BODY><DESC>
  <STATICVARIABLES>
   <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
   <SVFROMDATE>{from_date}</SVFROMDATE>
   <SVTODATE>{to_date}</SVTODATE>
   <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
   <SVISSIMPLEPROFITLOSS>No</SVISSIMPLEPROFITLOSS>
  </STATICVARIABLES>
 </DESC></BODY>
</ENVELOPE>"""

# Stock Items: OPENINGBALANCE and CLOSINGBALANCE, no date variables --
# any date-scoped quantity/value field triggers Tally's costing engine and
# can hang the whole application on a company with heavy stock movement --
# verified live. Do not add SVFROMDATE here.
_STOCK_ITEMS_TDL = """<ENVELOPE>
 <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>StockItems</ID></HEADER>
 <BODY><DESC>
  <STATICVARIABLES>
   <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
   <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  </STATICVARIABLES>
  <TDL><TDLMESSAGE>
   <COLLECTION NAME="StockItems" ISINITIALIZE="Yes">
    <TYPE>Stock Item</TYPE>
    <FETCH>NAME, PARENT, OPENINGBALANCE, CLOSINGBALANCE</FETCH>
   </COLLECTION>
  </TDLMESSAGE></TDL>
 </DESC></BODY>
</ENVELOPE>"""


def build_groups_request(company: str) -> str:
    return _GROUPS_TDL.format(company=company)


def build_ledgers_request(company: str, from_date: str, to_date: str) -> str:
    return _LEDGERS_TDL.format(company=company, from_date=from_date, to_date=to_date)


def build_ledgers_request_for_range(company: str, from_date: str, to_date: str) -> str:
    """Same request as build_ledgers_request, for an arbitrary date window --
    used to build month-wise figures by calling this once per month."""
    return _LEDGERS_TDL.format(company=company, from_date=from_date, to_date=to_date)


def build_pnl_request(company: str, from_date: str, to_date: str) -> str:
    return _PNL_TDL.format(company=company, from_date=from_date, to_date=to_date)


def build_stock_items_request(company: str) -> str:
    return _STOCK_ITEMS_TDL.format(company=company)


# --------------------------------------------------------------------------
# NEW -- not in the original script. Needs verification against a live
# Tally instance before parsers.py is written to match it.
# --------------------------------------------------------------------------

_COMPANIES_TDL = """<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Export</TALLYREQUEST>
 </HEADER>
 <BODY>
  <EXPORTDATA>
   <REQUESTDESC>
    <REPORTNAME>List of Companies</REPORTNAME>
    <STATICVARIABLES>
     <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
    </STATICVARIABLES>
   </REQUESTDESC>
  </EXPORTDATA>
 </BODY>
</ENVELOPE>"""


def build_companies_request() -> str:
    """No {company} placeholder -- this is Tally's global company list,
    not scoped to one company. TODO: confirm the actual response shape
    against your Tally before trusting parse_companies() in parsers.py."""
    return _COMPANIES_TDL