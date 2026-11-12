"""Vercel serverless entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qvote.api import app  # noqa: E402,F401
