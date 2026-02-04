"""Consolidated initial schema

Revision ID: 20260204_consolidated
Revises:
Create Date: 2026-02-04 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260204_consolidated'
down_revision = None
branch_labels = None
depends_on = None

# Use explicit PostgreSQL ENUMs with create_type disabled so we can guard creation manually
attendance_status_enum = postgresql.ENUM('present', 'absent', 'late', name='attendance_status', create_type=False)
term_enum = postgresql.ENUM('1st semester', '2nd semester', 'summer', name='term_enum', create_type=False)


def upgrade():
    bind = op.get_bind()

    # Create enums idempotently to avoid duplicate type errors if they already exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attendance_status') THEN
                CREATE TYPE attendance_status AS ENUM ('present', 'absent', 'late');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'term_enum') THEN
                CREATE TYPE term_enum AS ENUM ('1st semester', '2nd semester', 'summer');
            END IF;
        END$$;
    """)

    op.create_table(
        'courses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=20), nullable=False, unique=True),
        sa.Column('description', sa.String(length=500), nullable=False, server_default='No description'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False, unique=True),
        sa.Column('email', sa.String(length=120), nullable=True, unique=True),
        sa.Column('password_hash', sa.String(length=256), nullable=True),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('middle_name', sa.String(length=50), nullable=True),
        sa.Column('last_name', sa.String(length=50), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('department', sa.String(length=50), nullable=True),
        sa.Column('profile_picture', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'students',
        sa.Column('id', sa.String(length=20), primary_key=True),
        sa.Column('first_name', sa.String(length=64), nullable=False),
        sa.Column('middle_name', sa.String(length=64), nullable=True),
        sa.Column('last_name', sa.String(length=64), nullable=False),
        sa.Column('year_level', sa.String(length=20), nullable=False),
        sa.Column('department', sa.String(length=32), nullable=False, server_default='BSIT'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_students_first_name'), 'students', ['first_name'], unique=False)
    op.create_index(op.f('ix_students_last_name'), 'students', ['last_name'], unique=False)
    op.create_index(op.f('ix_students_year_level'), 'students', ['year_level'], unique=False)

    op.create_table(
        'classes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('class_code', sa.String(length=20), nullable=False, unique=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('substitute_instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('schedule', sa.String(length=100), nullable=True),
        sa.Column('room_number', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('term', term_enum, nullable=True),
        sa.Column('school_year', sa.String(length=9), nullable=True),
    )

    op.create_table(
        'class_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('scheduled_start_time', sa.DateTime(), nullable=True),
        sa.Column('scheduled_end_time', sa.DateTime(), nullable=True),
        sa.Column('is_attendance_processed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('session_room_number', sa.String(length=50), nullable=True),
        sa.Column('view_lock_owner', sa.String(length=128), nullable=True),
        sa.Column('view_lock_acquired_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'attendance_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('check_in_time', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'enrollments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'face_encodings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('encoding_data', sa.LargeBinary(), nullable=False),
        sa.Column('image_path', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'instructor_face_encodings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('encoding', sa.LargeBinary(), nullable=False),
        sa.Column('image_path', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('code', sa.String(length=128), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('purpose', sa.String(length=64), nullable=True),
    )

    op.create_table(
        'attendance_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('class_session_id', sa.Integer(), sa.ForeignKey('class_sessions.id'), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('status', attendance_status_enum, nullable=True),
        sa.Column('time_in', sa.DateTime(), nullable=True),
        sa.Column('time_out', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('marked_at', sa.DateTime(), nullable=True),
        sa.Column('marked_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )

    op.create_table(
        'instructor_attendance',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('time_in', sa.DateTime(), nullable=True),
        sa.Column('time_out', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=50), nullable=False, unique=True),
        sa.Column('value', sa.String(length=100), nullable=False),
    )


def downgrade():
    op.drop_table('system_settings')
    op.drop_table('instructor_attendance')
    op.drop_table('attendance_records')
    op.drop_table('verification_codes')
    op.drop_table('instructor_face_encodings')
    op.drop_table('face_encodings')
    op.drop_table('enrollments')
    op.drop_table('attendance_logs')
    op.drop_table('class_sessions')
    op.drop_table('classes')
    op.drop_index(op.f('ix_students_year_level'), table_name='students')
    op.drop_index(op.f('ix_students_last_name'), table_name='students')
    op.drop_index(op.f('ix_students_first_name'), table_name='students')
    op.drop_table('students')
    op.drop_table('users')
    op.drop_table('courses')

    bind = op.get_bind()
    term_enum.drop(bind, checkfirst=True)
    attendance_status_enum.drop(bind, checkfirst=True)
