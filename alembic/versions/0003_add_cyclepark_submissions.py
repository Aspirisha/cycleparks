"""Add cyclepark_submissions table.

Revision ID: 000000000003
Revises: 000000000002
Create Date: 2026-03-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "000000000003"
down_revision = "000000000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cyclepark_submissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("photo1_file_id", sa.Text(), nullable=False),
        sa.Column("photo2_file_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cyclepark_submissions")
