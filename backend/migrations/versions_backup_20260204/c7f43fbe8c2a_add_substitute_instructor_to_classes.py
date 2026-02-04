"""add substitute instructor to classes

Revision ID: c7f43fbe8c2a
Revises: 6e33e4408b2e
Create Date: 2025-12-05 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7f43fbe8c2a'
down_revision = '6e33e4408b2e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('substitute_instructor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_classes_substitute_instructor_id',
            'users',
            ['substitute_instructor_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_classes_substitute_instructor_id', type_='foreignkey')
        batch_op.drop_column('substitute_instructor_id')
