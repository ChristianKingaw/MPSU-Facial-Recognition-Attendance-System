"""add view lock columns to class_sessions

Revision ID: c1c779d3b5f4
Revises: abc123def456
Create Date: 2025-12-07 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1c779d3b5f4'
down_revision = 'abc123def456'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('class_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('view_lock_owner', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('view_lock_acquired_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('class_sessions', schema=None) as batch_op:
        batch_op.drop_column('view_lock_acquired_at')
        batch_op.drop_column('view_lock_owner')
