"""Add middle_name to students and users

Revision ID: a1b2c3d4e5f6
Revises: 450eb5259219
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '450eb5259219'
branch_labels = None
depends_on = None


def upgrade():
    # Add middle_name column to students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('middle_name', sa.String(length=64), nullable=True))
    
    # Add middle_name column to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('middle_name', sa.String(length=50), nullable=True))


def downgrade():
    # Remove middle_name column from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('middle_name')
    
    # Remove middle_name column from students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('middle_name')

