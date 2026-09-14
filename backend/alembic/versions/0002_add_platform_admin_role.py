"""add platform_admin to user_role enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14

NOTE: downgrade() is intentionally a no-op. PostgreSQL cannot cleanly remove
a single value from an existing enum type without rebuilding it (drop +
recreate the type, then recast every dependent column) — out of scope for a
routine rollback. If this value must ever be removed, do it as its own
deliberate, reviewed migration.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run in the same transaction as anything
    # that uses the new value (a PostgreSQL restriction), and Alembic wraps
    # each migration in one transaction by default. autocommit_block()
    # isolates just this statement outside that transaction.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'platform_admin'")


def downgrade() -> None:
    # Intentionally not reversible — see module docstring.
    pass
