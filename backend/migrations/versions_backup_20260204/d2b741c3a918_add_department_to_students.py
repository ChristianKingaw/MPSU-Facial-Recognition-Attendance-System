"""Add department column to students

Revision ID: d2b741c3a918
Revises: c7f43fbe8c2a
Create Date: 2025-12-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2b741c3a918'
down_revision = 'c7f43fbe8c2a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department', sa.String(length=32), nullable=False, server_default='BSIT'))

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.alter_column('department', server_default=None)


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('department')
