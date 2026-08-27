"""add locations active column

Revision ID: 7e076d51d7ce
Revises: de1fe24cd145
Create Date: 2026-08-27 18:34:22.736379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e076d51d7ce'
down_revision: Union[str, Sequence[str], None] = 'de1fe24cd145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Soft delete, same shape as branches/customers/accounts: the row stays,
    # only its visibility changes. Locations can now be soft-deleted even
    # though branches still reference them by FK — nothing about that FK
    # changes, a branch can go on pointing at an inactive location.
    op.add_column(
        "locations",
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("locations", "active")
