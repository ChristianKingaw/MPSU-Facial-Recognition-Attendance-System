"""initial schema

Revision ID: ed237f83f535
Revises: 
Create Date: 2025-07-29 23:56:22.853796

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed237f83f535'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum type for attendance status used in attendance_records
    attendance_status = sa.Enum('present', 'absent', 'late', 'excused', name='attendancestatus')
    attendance_status.create(op.get_bind(), checkfirst=True)

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False, unique=True),
        sa.Column('email', sa.String(length=120), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=256)),
        sa.Column('first_name', sa.String(length=50)),
        sa.Column('last_name', sa.String(length=50)),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('profile_picture', sa.String(length=255)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # courses
    op.create_table(
        'courses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=20), nullable=False, unique=True),
        sa.Column('description', sa.String(length=500)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # students
    op.create_table(
        'students',
        sa.Column('id', sa.String(length=20), primary_key=True),
        sa.Column('first_name', sa.String(length=64), nullable=False),
        sa.Column('last_name', sa.String(length=64), nullable=False),
        sa.Column('year_level', sa.String(length=20), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # classes
    op.create_table(
        'classes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('class_code', sa.String(length=20), nullable=False, unique=True),
        sa.Column('description', sa.String(length=200)),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('schedule', sa.String(length=100)),
        sa.Column('room_number', sa.String(length=20)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # class_sessions
    op.create_table(
        'class_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('scheduled_start_time', sa.DateTime(), nullable=True),
        sa.Column('scheduled_end_time', sa.DateTime(), nullable=True),
        sa.Column('is_attendance_processed', sa.Boolean(), nullable=True),
    )

    # enrollments
    op.create_table(
        'enrollments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # attendance_logs
    op.create_table(
        'attendance_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('check_in_time', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.String(length=500)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # attendance_records
    op.create_table(
        'attendance_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('class_session_id', sa.Integer(), sa.ForeignKey('class_sessions.id'), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('status', attendance_status, nullable=False),
        sa.Column('time_in', sa.DateTime(), nullable=True),
        sa.Column('time_out', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.String(length=500)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('marked_at', sa.DateTime(), nullable=True),
        sa.Column('marked_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )

    # face_encodings
    op.create_table(
        'face_encodings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=20), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('encoding_data', sa.LargeBinary(), nullable=False),
        sa.Column('image_path', sa.String(length=255)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # instructor_attendance
    op.create_table(
        'instructor_attendance',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.String(length=500)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # instructor_face_encodings
    op.create_table(
        'instructor_face_encodings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('encoding', sa.LargeBinary(), nullable=False),
        sa.Column('image_path', sa.String(length=255)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # verification_codes (without 'purpose' for now; added in next migration)
    op.create_table(
        'verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('code', sa.String(length=128), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    # Drop in reverse dependency order
    op.drop_table('verification_codes')
    op.drop_table('instructor_face_encodings')
    op.drop_table('instructor_attendance')
    op.drop_table('face_encodings')
    op.drop_table('attendance_records')
    op.drop_table('attendance_logs')
    op.drop_table('enrollments')
    op.drop_table('class_sessions')
    op.drop_table('classes')
    op.drop_table('students')
    op.drop_table('courses')
    op.drop_table('users')

    # Drop enum type
    attendance_status = sa.Enum('present', 'absent', 'late', 'excused', name='attendancestatus')
    attendance_status.drop(op.get_bind(), checkfirst=True)
