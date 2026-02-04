"""add term to class model

Revision ID: 68b17c1e7a9b
Revises: 
Create Date: 2025-09-02 01:59:04.847587

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '68b17c1e7a9b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create the enum type first
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'term_enum') THEN
                CREATE TYPE term_enum AS ENUM ('1st semester', '2nd semester', 'summer');
            END IF;
        END$$;
    """)
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('term', sa.Enum('1st semester', '2nd semester', 'summer', name='term_enum'), nullable=False))


def downgrade():
    # Drop the column first
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.drop_column('term')
    # Then drop the enum type
    op.execute("DROP TYPE IF EXISTS term_enum;")
