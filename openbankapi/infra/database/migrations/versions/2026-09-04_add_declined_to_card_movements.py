"""add declined movement_type, request_id and decline_reason to card_movements

Revision ID: f3c8d1a5e9b7
Revises: e7a1c4f9b2d6
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID


# revision identifiers, used by Alembic.
revision: str = 'f3c8d1a5e9b7'
down_revision: Union[str, Sequence[str], None] = 'e7a1c4f9b2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Verified from Phase 1's actual migration
# (2026-09-03_add_credit_card_tables.py) rather than assumed from the
# naming-convention default.
_CHECK_NAME = "card_movements_movement_type_check"


def upgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "card_movements", type_="check")
    op.create_check_constraint(
        _CHECK_NAME,
        "card_movements",
        "movement_type IS NULL OR movement_type IN "
        "('purchase','payment','fee','interest','refund','declined')",
    )
    op.add_column(
        "card_movements", sa.Column("decline_reason", sa.String(length=50), nullable=True)
    )
    # Nullable during the add so existing (Phase 1, unwritten-to) rows are
    # unaffected; every Phase 2 writer always supplies it going forward.
    op.add_column(
        "card_movements", sa.Column("request_id", PgUUID(as_uuid=True), nullable=True)
    )
    # Makes `INSERT ... ON CONFLICT (request_id, movement_type) DO NOTHING`
    # possible — the consumer's at-least-once-delivery dedup layer (design §7.2).
    op.create_unique_constraint(
        "card_movements_request_id_movement_type_key",
        "card_movements",
        ["request_id", "movement_type"],
    )


def downgrade() -> None:
    op.drop_constraint("card_movements_request_id_movement_type_key", "card_movements", type_="unique")
    op.drop_column("card_movements", "request_id")
    op.drop_column("card_movements", "decline_reason")
    op.drop_constraint(_CHECK_NAME, "card_movements", type_="check")
    op.create_check_constraint(
        _CHECK_NAME,
        "card_movements",
        "movement_type IS NULL OR movement_type IN "
        "('purchase','payment','fee','interest','refund')",
    )
