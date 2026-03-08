"""Add performance indexes and attendance uniqueness guard

Revision ID: 20260308_performance_indexes
Revises: 20260219_drop_verification_codes
Create Date: 2026-03-08 19:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260308_performance_indexes"
down_revision = "20260219_drop_verification_codes"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name):
    return table_name in _inspector().get_table_names()


def _has_column(table_name, column_name):
    if not _has_table(table_name):
        return False
    return any(col["name"] == column_name for col in _inspector().get_columns(table_name))


def _has_index(table_name, index_name):
    if not _has_table(table_name):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table_name))


def _has_unique_constraint(table_name, constraint_name):
    if not _has_table(table_name):
        return False
    return any(cst["name"] == constraint_name for cst in _inspector().get_unique_constraints(table_name))


def _create_index_if_possible(index_name, table_name, columns, unique=False):
    if not _has_table(table_name):
        return
    if any(not _has_column(table_name, col) for col in columns):
        return
    if _has_index(table_name, index_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(index_name, table_name):
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _create_unique_if_possible(constraint_name, table_name, columns):
    if not _has_table(table_name):
        return
    if any(not _has_column(table_name, col) for col in columns):
        return
    if _has_unique_constraint(table_name, constraint_name):
        return
    op.create_unique_constraint(constraint_name, table_name, columns)


def _drop_unique_if_exists(constraint_name, table_name):
    if _has_unique_constraint(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="unique")


def _dedupe_student_attendance():
    if _has_table("StudentAttendance") and all(
        _has_column("StudentAttendance", col)
        for col in ("StudentAttendanceID", "ClassSessionID", "StudentID")
    ):
        op.execute(
            sa.text(
                """
                DELETE FROM "StudentAttendance" older
                USING "StudentAttendance" newer
                WHERE older."ClassSessionID" = newer."ClassSessionID"
                  AND older."StudentID" = newer."StudentID"
                  AND older."ClassSessionID" IS NOT NULL
                  AND older."StudentAttendanceID" < newer."StudentAttendanceID"
                """
            )
        )

    if _has_table("attendance_records") and all(
        _has_column("attendance_records", col)
        for col in ("id", "class_session_id", "student_id")
    ):
        op.execute(
            sa.text(
                """
                DELETE FROM attendance_records older
                USING attendance_records newer
                WHERE older.class_session_id = newer.class_session_id
                  AND older.student_id = newer.student_id
                  AND older.class_session_id IS NOT NULL
                  AND older.id < newer.id
                """
            )
        )


def upgrade():
    _create_index_if_possible("ix_class_instructor_id", "Class", ["InstructorID"])
    _create_index_if_possible("ix_class_substitute_instructor_id", "Class", ["SubstituteInstructorID"])

    _create_index_if_possible("ix_enrolled_class_id", "Enrolled", ["ClassID"])
    _create_index_if_possible("ix_enrolled_student_id", "Enrolled", ["StudentID"])

    _create_index_if_possible("ix_class_sessions_class_date", "class_sessions", ["class_id", "date"])
    _create_index_if_possible(
        "ix_class_sessions_date_processed",
        "class_sessions",
        ["date", "is_attendance_processed"],
    )

    _create_index_if_possible("ix_face_encodings_student_id", "face_encodings", ["student_id"])
    _create_index_if_possible(
        "ix_instructor_face_encodings_instructor_id",
        "instructor_face_encodings",
        ["instructor_id"],
    )

    _create_index_if_possible(
        "ix_student_attendance_class_session_id",
        "StudentAttendance",
        ["ClassSessionID"],
    )
    _create_index_if_possible(
        "ix_student_attendance_class_status_date",
        "StudentAttendance",
        ["ClassID", "status", "Date"],
    )

    _create_index_if_possible(
        "ix_attendance_records_class_session_id",
        "attendance_records",
        ["class_session_id"],
    )
    _create_index_if_possible(
        "ix_attendance_records_class_status_date",
        "attendance_records",
        ["class_id", "status", "date"],
    )

    _dedupe_student_attendance()
    _create_unique_if_possible(
        "uq_student_attendance_class_session_student",
        "StudentAttendance",
        ["ClassSessionID", "StudentID"],
    )
    _create_unique_if_possible(
        "uq_attendance_records_class_session_student",
        "attendance_records",
        ["class_session_id", "student_id"],
    )


def downgrade():
    _drop_unique_if_exists(
        "uq_attendance_records_class_session_student",
        "attendance_records",
    )
    _drop_unique_if_exists(
        "uq_student_attendance_class_session_student",
        "StudentAttendance",
    )

    _drop_index_if_exists("ix_attendance_records_class_status_date", "attendance_records")
    _drop_index_if_exists("ix_attendance_records_class_session_id", "attendance_records")
    _drop_index_if_exists("ix_student_attendance_class_status_date", "StudentAttendance")
    _drop_index_if_exists("ix_student_attendance_class_session_id", "StudentAttendance")
    _drop_index_if_exists("ix_instructor_face_encodings_instructor_id", "instructor_face_encodings")
    _drop_index_if_exists("ix_face_encodings_student_id", "face_encodings")
    _drop_index_if_exists("ix_class_sessions_date_processed", "class_sessions")
    _drop_index_if_exists("ix_class_sessions_class_date", "class_sessions")
    _drop_index_if_exists("ix_enrolled_student_id", "Enrolled")
    _drop_index_if_exists("ix_enrolled_class_id", "Enrolled")
    _drop_index_if_exists("ix_class_substitute_instructor_id", "Class")
    _drop_index_if_exists("ix_class_instructor_id", "Class")
