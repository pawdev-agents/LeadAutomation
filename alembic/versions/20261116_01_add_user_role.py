"""Add user role.

Revision ID: 20261116_01
Revises:
Create Date: 2026-11-16
"""
from alembic import op
import sqlalchemy as sa

revision = "20261116_01"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=20), nullable=False, server_default="member"))

def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
