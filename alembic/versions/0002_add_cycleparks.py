"""Add cycleparks table.

Revision ID: 000000000002
Revises: 000000000001
Create Date: 2026-03-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "000000000002"
down_revision = "000000000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cycleparks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("feature_id", sa.String(50), nullable=False, unique=True),
        sa.Column("svdate", sa.Date(), nullable=True),
        sa.Column("prk_carr", sa.Boolean(), nullable=False),
        sa.Column("prk_cover", sa.Boolean(), nullable=False),
        sa.Column("prk_secure", sa.Boolean(), nullable=False),
        sa.Column("prk_locker", sa.Boolean(), nullable=False),
        sa.Column("prk_sheff", sa.Boolean(), nullable=False),
        sa.Column("prk_mstand", sa.Boolean(), nullable=False),
        sa.Column("prk_pstand", sa.Boolean(), nullable=False),
        sa.Column("prk_hoop", sa.Boolean(), nullable=False),
        sa.Column("prk_post", sa.Boolean(), nullable=False),
        sa.Column("prk_buterf", sa.Boolean(), nullable=False),
        sa.Column("prk_wheel", sa.Boolean(), nullable=False),
        sa.Column("prk_hangar", sa.Boolean(), nullable=False),
        sa.Column("prk_tier", sa.Boolean(), nullable=False),
        sa.Column("prk_other", sa.Boolean(), nullable=False),
        sa.Column("prk_provis", sa.Integer(), nullable=True),
        sa.Column("prk_cpt", sa.Integer(), nullable=True),
        sa.Column("borough", sa.String(100), nullable=True),
        sa.Column("photo1_url", sa.Text(), nullable=True),
        sa.Column("photo2_url", sa.Text(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cycleparks")
