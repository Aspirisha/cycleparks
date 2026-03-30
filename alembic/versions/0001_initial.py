"""Initial schema.

Revision ID: 000000000001
Revises:
Create Date: 2026-03-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
    )

    op.create_table(
        "command_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )

    op.create_table(
        "send_failures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("message_type", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )

    op.create_table(
        "errors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exception_type", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("update_str", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("errors")
    op.drop_table("send_failures")
    op.drop_table("command_stats")
    op.drop_table("requests")
