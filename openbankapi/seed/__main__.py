"""Preserve `python -m openbankapi.seed 1234=500` after package migration."""
from __future__ import annotations

import sys

from openbankapi.seed import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
