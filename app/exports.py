"""
Shared temp directory for generated Excel exports.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

EXPORTS_DIR = Path(tempfile.mkdtemp(prefix="tally_mis_exports_"))