"""FX-18 structural purity guard: `account-service` must import nothing
currency-related — no `conversion_service`, no `infra.foreign_exchange_service`,
no `infra.cache.services`. `_incoming`/`_on_transfer_requested` only ever
pass through amounts and `conversion` dicts a caller already resolved; if this
package ever reaches for currency logic itself, that is the exact coupling
FX-18 exists to forbid.

`ast`-based, not regex (`test_controller_dto_alignment.py`'s style): robust
against comments/strings that merely contain one of these words, unlike a
plain grep/regex scan.
"""
from __future__ import annotations

import ast
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parents[1]
_SCANNED_FILES = ("domain.py", "job.py")

_BANNED_NAME_FRAGMENTS = (
    "conversion_service",
    "foreign_exchange",
    "applied_rate",
    "cache",
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
    return [
        name for name in names
        if any(fragment in name for fragment in _BANNED_NAME_FRAGMENTS)
    ]


def test_domain_module_imports_nothing_currency_related():
    source = (_MODULE_DIR / "domain.py").read_text()
    hits = _banned_hits(_imported_module_names(source))
    assert hits == [], f"domain.py imports banned currency-related names: {hits}"


def test_job_module_imports_nothing_currency_related():
    source = (_MODULE_DIR / "job.py").read_text()
    hits = _banned_hits(_imported_module_names(source))
    assert hits == [], f"job.py imports banned currency-related names: {hits}"


def test_the_ban_actually_detects_a_banned_import():
    """Triangulation: prove the scanner fires on a positive case, not just
    the (currently clean) real files."""
    source = "from infra.cache.services import foreign_exchange_cache_service\n"
    hits = _banned_hits(_imported_module_names(source))
    assert hits, "scanner failed to flag a genuinely banned import"
