"""widen card_movements.movement_type CHECK to include late_fee

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-06 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Exact drop+recreate shape of 2026-09-04_add_declined_to_card_movements.py.
_CHECK_NAME = "card_movements_movement_type_check"


def upgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "card_movements", type_="check")
    op.create_check_constraint(
        _CHECK_NAME,
        "card_movements",
        "movement_type IS NULL OR movement_type IN "
        "('purchase','payment','fee','interest','refund','declined','late_fee')",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "card_movements", type_="check")
    op.create_check_constraint(
        _CHECK_NAME,
        "card_movements",
        "movement_type IS NULL OR movement_type IN "
        "('purchase','payment','fee','interest','refund','declined')",
    )
