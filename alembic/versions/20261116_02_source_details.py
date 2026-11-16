"""Add lead source metadata."""
from alembic import op
import sqlalchemy as sa
revision = "20261116_02"
down_revision = "20261116_01"
branch_labels = None
depends_on = None
def upgrade():
    with op.batch_alter_table("lead_sources") as batch_op:
        batch_op.add_column(sa.Column("source_type", sa.String(50), nullable=False, server_default="other"))
        batch_op.add_column(sa.Column("utm_defaults", sa.JSON(), nullable=True))
def downgrade():
    with op.batch_alter_table("lead_sources") as batch_op:
        batch_op.drop_column("utm_defaults"); batch_op.drop_column("source_type")
