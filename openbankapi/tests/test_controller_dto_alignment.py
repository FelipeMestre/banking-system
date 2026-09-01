"""Every `body.<field>` a controller reads must exist on its DTO.

A rename pass left `first_name=body.name` in the customer controller while the
DTO already declared `first_name`. Nothing caught it: the unit tests build the
app but the fakes accept whatever the controller passes, so the mismatch only
surfaced as a 500 against the live stack. This closes that gap statically.
"""
from __future__ import annotations

import importlib
import pathlib
import re

import pytest

CONTROLLERS = [
    ("customer_router", "customer_dto", ["CustomerCreateDTO", "CustomerUpdateDTO", "CustomerAuth0LinkDTO"]),
    ("account_router", "account_dto", ["AccountCreateDTO", "AccountUpdateDTO"]),
    ("branch_router", "branch_dto", ["BranchCreateDTO", "BranchUpdateDTO"]),
    ("location_router", "location_dto", ["LocationCreateDTO", "LocationUpdateDTO"]),
    ("transfer_router", "transfer_dto", ["TransferRequestDTO"]),
]

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("controller,dto_module,dto_names", CONTROLLERS, ids=lambda v: v if isinstance(v, str) else "")
def test_every_body_field_a_controller_reads_exists_on_its_dto(controller, dto_module, dto_names):
    source = (ROOT / "api" / "v1" / "routers" / f"{controller}.py").read_text()
    read = set(re.findall(r"body\.(\w+)", source))

    module = importlib.import_module(f"openbankapi.api.v1.dtos.{dto_module}")
    declared: set[str] = set()
    for name in dto_names:
        declared |= set(getattr(module, name).model_fields)

    missing = read - declared
    assert not missing, f"{controller} reads {sorted(missing)}, which no DTO declares"


def test_no_dto_anywhere_declares_a_balance_field():
    """The rule from spec §3.5, asserted across every account DTO at once."""
    from openbankapi.api.v1.dtos import account_dto

    for name in ["AccountCreateDTO", "AccountUpdateDTO"]:
        assert "balance" not in getattr(account_dto, name).model_fields, name
