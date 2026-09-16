"""Loads `card-service/domain.py` as a uniquely-named module (`card_domain`)
instead of the bare `domain` name `account-service/tests` already registers
in `sys.modules` for its own `domain.py` — both suites run in one pytest
session, so a bare-name `import domain` here would silently resolve to the
WRONG module (account-service's), not a collection error."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_DOMAIN_PATH = Path(__file__).resolve().parents[1] / "domain.py"
_spec = importlib.util.spec_from_file_location("card_domain", _DOMAIN_PATH)
_module = importlib.util.module_from_spec(_spec)
sys.modules["card_domain"] = _module
_spec.loader.exec_module(_module)
