"""merge card_accounts.used_credit and transactions.description heads

Revision ID: d4e5f6a7b8c9
Revises: f1a2b3c4d5e6, b1c2d3e4f5a6
Create Date: 2026-09-07 00:00:00.000000

"""

from collections.abc import Sequence

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = ("f1a2b3c4d5e6", "b1c2d3e4f5a6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Pure merge point: `card_accounts.used_credit` (f1a2b3c4d5e6) and
    # `transactions.description` (b1c2d3e4f5a6) both branched off the same
    # parent (9a8b7c6d5e4f, add_deposits_table) and never touched each
    # other's tables, so there is no DDL to reconcile here.
    pass


def downgrade() -> None:
    pass
