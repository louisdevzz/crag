"""Convenience launcher for Legal CRAG Assistant System Initialization.

Usage:
    python init_system.py [--check-models] [--reset] [--quiet]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.init_system import main

if __name__ == "__main__":
    main()
