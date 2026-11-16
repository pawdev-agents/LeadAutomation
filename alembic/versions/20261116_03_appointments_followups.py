"""Appointment state, follow-up content, and team settings."""
from alembic import op
import sqlalchemy as sa
revision="20261116_03"; down_revision="20261116_02"; branch_labels=None; depends_on=None
def upgrade():
    with op.batch_alter_table("appointments") as b:
        b.add_column(sa.Column("status",sa.String(20),nullable=False,server_default="scheduled"));b.add_column(sa.Column("cancelled_at",sa.DateTime(timezone=True),nullable=True))
    with op.batch_alter_table("followups") as b:
        b.add_column(sa.Column("subject",sa.String(255),nullable=True));b.add_column(sa.Column("body",sa.Text(),nullable=True))
    with op.batch_alter_table("teams") as b:b.add_column(sa.Column("settings",sa.JSON(),nullable=True))
def downgrade():
    with op.batch_alter_table("teams") as b:b.drop_column("settings")
    with op.batch_alter_table("followups") as b:b.drop_column("body");b.drop_column("subject")
    with op.batch_alter_table("appointments") as b:b.drop_column("cancelled_at");b.drop_column("status")
