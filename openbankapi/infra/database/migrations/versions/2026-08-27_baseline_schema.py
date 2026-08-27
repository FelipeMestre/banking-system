"""baseline schema

Ported from the retired `infra/postgres/init.sql` (spec §3), byte-for-byte in
intent: same tables, same column types/defaults, and — critically — the same
UNNAMED unique/foreign-key/check constraints. Leaving them unnamed lets
Postgres apply its own default names (`<table>_<column>_key`,
`<table>_<column>_fkey`, `<table>_<column>_check`), which is exactly what
`infra/database/errors.py` hardcodes and matches on. Naming any of these here
would silently break that translation.

Revision ID: de1fe24cd145
Revises:
Create Date: 2026-08-27 15:05:48.108344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID


# revision identifiers, used by Alembic.
revision: str = 'de1fe24cd145'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The system/fees account (spec §5's example value, and FEES_ACCOUNT's default).
# Its row must exist before any transfer, or the fee credit Flink emits has
# nowhere to land in the read model.
_SYSTEM_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Parent-first: branches references locations, accounts references both
    # customers and branches.

    op.create_table(
        "locations",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "branches",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("location_id", PgUUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code"),
    )

    # No `age` column, by design (spec §3.4): an age is computed from
    # date_of_birth at read time. date_of_birth/gender are personal data and
    # must never reach an application log.
    op.create_table(
        "customers",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("identification_number", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("identification_number"),
    )

    # account_number is not just an identifier: it is the Kafka partition key
    # (spec §4), and CHAR(16) means leading zeros survive. balance is a
    # read-model projection — Flink's keyed state is the source of truth; the
    # only writer here is the account-balances consumer (spec §3.6).
    op.create_table(
        "accounts",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_number", sa.CHAR(16), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("customer_id", PgUUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("branch_id", PgUUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("balance", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("account_number"),
        sa.CheckConstraint(r"account_number ~ '^[0-9]{16}$'"),
    )

    # Postgres does not index the referencing side of a foreign key on its
    # own; without these, listing a customer's accounts is a sequential scan.
    op.create_index("idx_branches_location_id", "branches", ["location_id"])
    op.create_index("idx_accounts_customer_id", "accounts", ["customer_id"])
    op.create_index("idx_accounts_branch_id", "accounts", ["branch_id"])

    # Every list endpoint pages with ORDER BY created_at DESC, id DESC — the
    # tie-break on id is what makes an offset page stable when two rows share
    # a timestamp. These indexes are that exact ordering.
    op.create_index("idx_locations_created_at", "locations", [sa.text("created_at DESC"), sa.text("id DESC")])
    op.create_index("idx_branches_created_at", "branches", [sa.text("created_at DESC"), sa.text("id DESC")])
    op.create_index("idx_customers_created_at", "customers", [sa.text("created_at DESC"), sa.text("id DESC")])
    op.create_index("idx_accounts_created_at", "accounts", [sa.text("created_at DESC"), sa.text("id DESC")])

    op.execute(
        f"INSERT INTO locations (id, name) VALUES ('{_SYSTEM_ID}', 'SYSTEM')"
    )
    op.execute(
        f"INSERT INTO branches (id, code, name, location_id) "
        f"VALUES ('{_SYSTEM_ID}', 'SYS', 'System branch', '{_SYSTEM_ID}')"
    )
    op.execute(
        f"INSERT INTO customers (id, identification_number, first_name, last_name, date_of_birth) "
        f"VALUES ('{_SYSTEM_ID}', 'SYSTEM', 'System', 'Account', DATE '1970-01-01')"
    )
    op.execute(
        f"INSERT INTO accounts (account_number, currency, customer_id, branch_id) "
        f"VALUES ('0000000000000001', 'USD', '{_SYSTEM_ID}', '{_SYSTEM_ID}')"
    )


def downgrade() -> None:
    op.drop_table("accounts")
    op.drop_table("customers")
    op.drop_table("branches")
    op.drop_table("locations")
