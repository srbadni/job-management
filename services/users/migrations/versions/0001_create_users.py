"""Create users with a unique, canonical lowercase email.

Revision ID: 0001_create_users
Revises: None
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )


def downgrade() -> None:
    op.drop_table("users")
