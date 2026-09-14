"""merge transactions and applied_rates heads

Revision ID: c92d5e8a17f3
Revises: b3e7a9c1f4d0, a618b754f8ac
Create Date: 2026-09-03 09:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'c92d5e8a17f3'
down_revision: Union[str, Sequence[str], None] = ('b3e7a9c1f4d0', 'a618b754f8ac')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pure merge point: `transactions` (b3e7a9c1f4d0) and `applied_rates`
    # (a618b754f8ac) diverged off the same baseline (a1c9f3d6e21b) and never
    # touched each other's tables, so there is no DDL to reconcile here.
    pass


def downgrade() -> None:
    pass
