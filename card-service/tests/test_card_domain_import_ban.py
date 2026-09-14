"""Structural purity guard, mirrors `account-service`'s own: `domain.py`
must import nothing currency-related or PyFlink-related — no
`conversion_service`, no `infra.foreign_exchange_service`, no
`ForeignExchangeCacheService`, no `pyflink`. All currency math happens in
OpenBankAPI before the event is produced; `domain.py` only ever reads
`event["amount_usd"]`, already correct.
"""
from __future__ import annotations

import ast
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parents[1]

_BANNED_NAME_FRAGMENTS = (
    "conversion_service",
    "foreign_exchange",
    "cache_service",
    "pyflink",
)


def _imported_module_names(source: str) -> list[str]:
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
            names.extend(alias.name for alias in node.names)
    return names


def _banned_hits(names: list[str]) -> list[str]:
    return [name for name in names if any(fragment in name for fragment in _BANNED_NAME_FRAGMENTS)]


def test_domain_module_imports_nothing_currency_or_pyflink_related():
    source = (_MODULE_DIR / "domain.py").read_text()
    hits = _banned_hits(_imported_module_names(source))
    assert hits == [], f"domain.py imports banned names: {hits}"


def test_the_ban_actually_detects_a_banned_import():
    source = "from openbankapi.domain.service import conversion_service\n"
    hits = _banned_hits(_imported_module_names(source))
    assert hits, "scanner failed to flag a genuinely banned import"
