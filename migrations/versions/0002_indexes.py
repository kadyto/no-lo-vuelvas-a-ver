"""Índices de navegación, sin transformación ni pérdida de datos."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

INDEXES = {
    "works": ["title_key", "original_key", "kind", "created_at"],
    "reviews": ["score_half", "recommended", "watched_on"],
    "aliases": ["work_id", "title_key"],
    "sessions": ["expires_at"],
}


def upgrade():
    for table, columns in INDEXES.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index("ix_work_categories_category", "work_categories", ["category_id", "work_id"])


def downgrade():
    for table, columns in INDEXES.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
    op.drop_index("ix_work_categories_category", table_name="work_categories")
