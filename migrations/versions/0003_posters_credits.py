"""Carátulas locales y personas; conserva obras y valoraciones existentes."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "posters",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.Column("media_type", sa.String(30), nullable=False),
        sa.Column("source_url", sa.String, nullable=False),
        sa.Column("fetched_at", sa.String, nullable=False),
    )
    # SQLite accepts a nullable REFERENCES column without rebuilding the works table.
    op.execute("ALTER TABLE works ADD COLUMN poster_id VARCHAR(64) REFERENCES posters(id)")
    op.create_index("ix_works_poster_id", "works", ["poster_id"])
    op.create_table(
        "people",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(200), nullable=False),
        sa.Column("identity_key", sa.String(220), nullable=False, unique=True),
        sa.Column("fa_id", sa.String(16), unique=True),
    )
    op.create_index("ix_people_name_key", "people", ["name_key"])
    op.create_table(
        "credits",
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("person_id", sa.Integer, sa.ForeignKey("people.id"), primary_key=True),
        sa.Column("role", sa.String(10), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.CheckConstraint("role IN ('director','actor')"),
    )
    op.create_index("ix_credits_person_id", "credits", ["person_id"])
    # Keep old payloads, but expire previews that predate the new metadata fields.
    op.execute("UPDATE metadata_cache SET expires_at = 0")


def downgrade():
    raise RuntimeError("Detén la aplicación y restaura la copia anterior para volver al esquema previo.")
