"""configuracion_global_settings_ocr_por_tipo

Revision ID: 5a1b2c3d4e5f
Revises: c4d8e2f6a0b1
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa

revision = "5a1b2c3d4e5f"
down_revision = "c4d8e2f6a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=150), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("section", sa.String(length=100), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.add_column(
        "document_types",
        sa.Column("ocr_languages", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_types", "ocr_languages")
    op.drop_table("app_settings")