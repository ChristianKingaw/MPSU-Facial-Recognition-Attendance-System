"""merge legacy head

Revision ID: 450eb5259219
Revises: c1c779d3b5f4, d2b741c3a918
Create Date: 2025-12-08 13:21:16.118391

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '450eb5259219'
down_revision = ('c1c779d3b5f4', 'd2b741c3a918')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
