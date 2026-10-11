"""Biblioteca y acceso. Esquema congelado; no depende de modelos futuros."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "works",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uid", sa.String(36), nullable=False, unique=True),
        sa.Column("fa_id", sa.String(16), unique=True),
        sa.Column("fa_url", sa.String),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("title_key", sa.String(300), nullable=False),
        sa.Column("original_title", sa.String(300)),
        sa.Column("original_key", sa.String(300), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("year", sa.Integer),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("updated_at", sa.String, nullable=False),
        sa.Column("metadata_source", sa.String),
        sa.Column("metadata_fetched_at", sa.String),
        sa.Column("metadata_snapshot", sa.Text),
        sa.CheckConstraint("kind IN ('movie','series')"),
    )
    op.create_table(
        "reviews",
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score_half", sa.Integer),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("recommended", sa.Boolean, nullable=False),
        sa.Column("watched_on", sa.String(10)),
        sa.CheckConstraint("score_half IS NULL OR score_half BETWEEN 2 AND 20"),
    )
    op.create_table(
        "aliases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("title_key", sa.String(300), nullable=False),
        sa.Column("language", sa.String(30)),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_key", sa.String(80), unique=True, nullable=False),
    )
    op.create_table(
        "work_categories",
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "category_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_table(
        "admin",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String, nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String, primary_key=True),
        sa.Column("csrf", sa.String, nullable=False),
        sa.Column("authenticated", sa.Boolean, nullable=False),
        sa.Column("expires_at", sa.Integer, nullable=False),
    )
    op.create_table(
        "login_limits",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("count", sa.Integer, nullable=False),
        sa.Column("reset_at", sa.Integer, nullable=False),
    )
    op.create_table(
        "metadata_cache",
        sa.Column("fa_id", sa.String, primary_key=True),
        sa.Column("payload", sa.String, nullable=False),
        sa.Column("fetched_at", sa.String, nullable=False),
        sa.Column("expires_at", sa.Integer, nullable=False),
    )
    op.create_table(
        "import_previews",
        sa.Column("token", sa.String, primary_key=True),
        sa.Column("session_hash", sa.String, nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("expires_at", sa.Integer, nullable=False),
    )


def downgrade():
    raise RuntimeError(
        "Restaurar la copia previa con la aplicación detenida; no se borran tablas automáticamente."
    )
