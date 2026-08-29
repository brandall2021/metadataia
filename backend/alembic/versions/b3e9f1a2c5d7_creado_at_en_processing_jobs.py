"""creado_at_en_processing_jobs

Revision ID: b3e9f1a2c5d7
Revises: a1f3c9d2e4b6
Create Date: 2026-08-28
"""

from alembic import op
import sqlalchemy as sa

revision = "b3e9f1a2c5d7"
down_revision = "a1f3c9d2e4b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processing_jobs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("processing_jobs", "created_at")