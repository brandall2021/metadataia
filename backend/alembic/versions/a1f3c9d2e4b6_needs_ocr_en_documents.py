"""needs_ocr en documents

Revision ID: a1f3c9d2e4b6
Revises: 7ced463a45ed
Create Date: 2026-08-28

Agrega la columna needs_ocr a documents (FASE 7): el analisis del PDF
determina si el documento requiere OCR antes de extraer texto.
"""

from alembic import op
import sqlalchemy as sa

revision = "a1f3c9d2e4b6"
down_revision = "7ced463a45ed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("needs_ocr", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("documents", "needs_ocr", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "needs_ocr")