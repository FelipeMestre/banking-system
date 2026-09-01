"""add customer auth0_sub

Revision ID: a1c9f3d6e21b
Revises: 7e076d51d7ce
Create Date: 2026-08-31 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9f3d6e21b'
down_revision: Union[str, Sequence[str], None] = '7e076d51d7ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable and unpopulated on creation (spec §1.1): a customer is linked to
    # an Auth0 identity only through PATCH /customers/{id}/auth0-link, never by
    # a data migration or backfill — there is no signup flow to source it from.
    op.add_column(
        "customers",
        sa.Column("auth0_sub", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "customers_auth0_sub_key", "customers", ["auth0_sub"], unique=True
    )


def downgrade() -> None:
    op.drop_index("customers_auth0_sub_key", table_name="customers")
    op.drop_column("customers", "auth0_sub")
