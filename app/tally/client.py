"""
HTTP + XML plumbing for talking to Tally's local XML server.

Ported near-verbatim from the original tally_mis_report_generic.py script --
this part doesn't change just because it's now inside an app instead of a
one-shot CLI script.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import requests

from app.config import settings

_INVALID_XML_CHARREF_RE = re.compile(r"&#(\d+);")


def _strip_invalid_charrefs(text: str) -> str:
    """Tally's XML server emits numeric character references for control
    codes (observed: &#4; right before group names like 'Primary') that
    are illegal in XML 1.0 and make every strict parser (ElementTree
    included) throw ParseError. Drop any numeric char ref that points at
    a C0 control code outside tab/CR/LF -- these carry no real data."""
    def _sub(m: re.Match) -> str:
        code = int(m.group(1))
        if code in (9, 10, 13) or code >= 32:
            return m.group(0)  # legal, keep as-is
        return ""  # illegal control char reference, drop it
    return _INVALID_XML_CHARREF_RE.sub(_sub, text)


def fetch_xml(xml_body: str, tally_url: str | None = None) -> ET.Element:
    """Send an XML/TDL request to the Tally HTTP server and return the
    parsed response root.

    tally_url defaults to settings.tally_url -- pass an explicit value in
    tests, or if you ever need to point at a different Tally instance
    (e.g. Tally running on another PC on the LAN) without touching global
    config.
    """
    url = tally_url or settings.tally_url
    resp = requests.post(
        url,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "text/xml"},
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.text
    idx = text.find("<ENVELOPE")
    if idx > 0:
        text = text[idx:]
    text = _strip_invalid_charrefs(text)
    return ET.fromstring(text)