from flask import Blueprint, request, jsonify, send_file
from extensions import db
from models import ClassSession, User, Class, Student, Enrollment, AttendanceRecord, InstructorAttendance, Course, FaceEncoding, InstructorFaceEncoding, AttendanceStatus, SystemSettings
from datetime import datetime, time, date, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from flask import current_app # Import current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time as time_module  # Rename to avoid conflict with datetime.time
import logging
from utils.timezone import get_pst_now, pst_now_naive
from utils.system_settings_helper import DEFAULT_ROOM_NUMBERS, load_room_numbers
from utils.attendance_manager import AttendanceTimeValidator
from utils.schedule_parser import resolve_schedule_window

from flask_login import login_required # Import login_required decorator from Flask-Login

import logging
from werkzeug.utils import secure_filename
import uuid
import os
from flask import url_for

# Create logger for this module
logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

DEFAULT_AUTO_TIMEOUT_MINUTES = 60

# Initialize rate limiter with Redis storage
from config import Config
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"],  # Default limit, will be overridden in create_app
    storage_uri=Config.RATELIMIT_STORAGE_URL
)

# Function to check for API key
def require_api_key():
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != current_app.config['API_KEY']:
        return jsonify({'error': 'Unauthorized: Missing or invalid API Key'}), 401
    return None # Return None if authorized


@api_bp.before_request
def before_request_api():
    # Apply API key protection only to routes within this blueprint
    # Exclude the instructor list endpoint and health endpoint from API key requirement
    if request.endpoint and request.endpoint.startswith('api.') and request.endpoint not in ['api.get_instructors', 'api.health_check', 'api.upload_instructor_images_api']:
        return require_api_key()

import re

# Import DeepFace only when needed to avoid startup issues
DEEPFACE_AVAILABLE = False
DEEPFACE_MODEL = "Facenet512"
DEEPFACE_DETECTOR = "opencv" 
DEEPFACE_DISTANCE_METRIC = "cosine"

def get_deepface():
    """Lazy import of DeepFace to avoid startup issues"""
    global DEEPFACE_AVAILABLE
    if not DEEPFACE_AVAILABLE:
        try:
            import deepface
            DEEPFACE_AVAILABLE = True
            return deepface
        except ImportError:
            return None
    return __import__('deepface')

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password) and user.role == 'instructor':
        return jsonify({'success': True, 'message': 'Login successful', 'user': {'id': user.id, 'username': user.username, 'role': user.role}})
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@api_bp.route('/rooms', methods=['GET'])
def get_room_numbers_api():
    """Return the configured list of room numbers for kiosk clients."""
    try:
        room_numbers_setting = SystemSettings.query.filter_by(key='room_numbers').first()
        single_room_setting = None
        if not room_numbers_setting:
            single_room_setting = SystemSettings.query.filter_by(key='room_number').first()

        raw_value = None
        if room_numbers_setting:
            raw_value = room_numbers_setting.value
        elif single_room_setting:
            raw_value = single_room_setting.value

        rooms = load_room_numbers(raw_value, fallback=DEFAULT_ROOM_NUMBERS)
        return jsonify({'success': True, 'rooms': rooms})
    except Exception as exc:
        logger.exception('Failed to load room numbers: %s', exc)
        return jsonify({'success': False, 'message': 'Unable to load room numbers'}), 500


@api_bp.route('/face-encodings', methods=['GET'])
def download_face_encodings():
    """Stream the latest face encoding cache so kiosks can stay in sync."""
    cache_path = current_app.config.get('FACE_ENCODINGS_CACHE')
    if not cache_path:
        cache_path = os.path.abspath(
            os.path.join(current_app.root_path, '..', 'cache', 'face_encodings.pkl')
        )

    if not os.path.exists(cache_path):
        return jsonify({'success': False, 'message': 'Face encoding cache not found'}), 404

    try:
        return send_file(
            cache_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='face_encodings.pkl'
        )
    except Exception as exc:
        current_app.logger.error('Failed to stream face encodings: %s', exc, exc_info=True)
        return jsonify({'success': False, 'message': 'Unable to load face encodings'}), 500


@api_bp.route('/sessions/active', methods=['GET'])
def get_active_class_sessions():
    """Return class sessions that are currently running so every kiosk stays in sync."""
    try:
        now = pst_now_naive()
        today = now.date()
        max_age_hours = current_app.config.get('SESSION_ACTIVE_WINDOW_HOURS', 6)
        min_allowed_start = now - timedelta(hours=max_age_hours)

        sessions = ClassSession.query.filter(
            ClassSession.date == today,
            ClassSession.start_time.isnot(None),
            ClassSession.is_attendance_processed == False  # noqa: E712
        ).all()

        active_sessions = []
        for session in sessions:
            if session.start_time and session.start_time < min_allowed_start:
                continue

            cls = Class.query.get(session.class_id)
            scheduled_end = session.scheduled_end_time
            if not scheduled_end and session.start_time:
                scheduled_end = session.start_time + timedelta(minutes=DEFAULT_AUTO_TIMEOUT_MINUTES)
            active_sessions.append({
                'class_session_id': session.id,
                'class_id': session.class_id,
                'start_time': session.start_time.isoformat() if session.start_time else None,
                'room_number': session.session_room_number or (cls.room_number if cls else None),
                'class_code': cls.class_code if cls else None,
                'description': cls.description if cls else None,
                'instructor_id': session.instructor_id,
                'scheduled_end_time': scheduled_end.isoformat() if scheduled_end else None,
                'timeout_deadline': scheduled_end.isoformat() if scheduled_end else None,
                'is_attendance_processed': bool(session.is_attendance_processed),
                'view_lock_owner': session.view_lock_owner,
                'view_lock_acquired_at': session.view_lock_acquired_at.isoformat() if session.view_lock_acquired_at else None,
            })

        return jsonify({'success': True, 'sessions': active_sessions}), 200
    except Exception as exc:
        current_app.logger.error(f"Error fetching active class sessions: {exc}", exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to load active class sessions'}), 500


@api_bp.route('/sessions/<int:session_id>/view-lock', methods=['POST'])
def manage_session_view_lock(session_id):
    """Allow kiosks to acquire or release exclusive view locks for a session."""
    data = request.get_json() or {}
    locker_id = (data.get('locker_id') or '').strip()
    action = (data.get('action') or 'lock').strip().lower()
    force = bool(data.get('force'))

    if not locker_id:
        return jsonify({'error': 'Missing locker_id'}), 400

    session = ClassSession.query.get(session_id)
    if not session:
        return jsonify({'error': f'Class session with ID {session_id} not found'}), 404

    if action not in {'lock', 'unlock'}:
        return jsonify({'error': 'Invalid action'}), 400

    if session.is_attendance_processed:
        session.view_lock_owner = None
        session.view_lock_acquired_at = None
        db.session.commit()
        if action == 'lock':
            return jsonify({'error': 'Class session already ended'}), 409
        return jsonify({
            'class_session_id': session.id,
            'view_lock_owner': session.view_lock_owner,
            'view_lock_acquired_at': None,
        }), 200

    now = pst_now_naive()

    if action == 'lock':
        if session.view_lock_owner and session.view_lock_owner != locker_id:
            return jsonify({
                'error': 'Session already locked by another kiosk',
                'lock_owner': session.view_lock_owner,
            }), 409
        session.view_lock_owner = locker_id
        session.view_lock_acquired_at = now
    else:  # unlock
        if session.view_lock_owner and session.view_lock_owner != locker_id and not force:
            return jsonify({
                'error': 'Unable to unlock session held by another kiosk',
                'lock_owner': session.view_lock_owner,
            }), 403
        session.view_lock_owner = None
        session.view_lock_acquired_at = None

    db.session.commit()

    return jsonify({
        'class_session_id': session.id,
        'view_lock_owner': session.view_lock_owner,
        'view_lock_acquired_at': session.view_lock_acquired_at.isoformat() if session.view_lock_acquired_at else None,
    }), 200

@api_bp.route('/instructors/<int:instructor_id>/classes', methods=['GET'])
def get_instructor_classes_api(instructor_id):
    """Return classes assigned to the instructor (API key protected)."""
    try:
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            return jsonify({'success': False, 'message': 'Instructor not found'}), 404

        classes = Class.query.filter(
            or_(
                Class.instructor_id == instructor_id,
                Class.substitute_instructor_id == instructor_id
            )
        ).all()
        class_payload = []

        for cls in classes:
            course = Course.query.get(cls.course_id) if cls.course_id else None
            enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
            substitute_name = None
            if cls.substitute_instructor_id:
                substitute = User.query.get(cls.substitute_instructor_id)
                substitute_name = f"{substitute.first_name} {substitute.last_name}" if substitute else "Unknown"
            is_substitute_assignment = cls.substitute_instructor_id == instructor_id
            
            class_payload.append({
                'id': cls.id,
                'classCode': cls.class_code,
                'description': cls.description,
                'schedule': cls.schedule,
                'roomNumber': cls.room_number,
                'courseName': course.description if course else None,
                'instructorId': cls.instructor_id,
                'substituteInstructorId': cls.substitute_instructor_id,
                'assignmentRole': 'substitute' if is_substitute_assignment else 'primary',
                'isSubstituteAssignment': is_substitute_assignment,
                'substituteInstructorName': substitute_name,
                'enrolledCount': enrolled_count
            })

        return jsonify({'success': True, 'classes': class_payload})
    except Exception as e:
        current_app.logger.error(f"Error in get_instructor_classes_api: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to load classes'}), 500

@api_bp.route('/instructors/<int:instructor_id>/students', methods=['GET'])
def get_instructor_students_api(instructor_id):
    """Return all unique students across the instructor's classes."""
    try:
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            return jsonify({'success': False, 'message': 'Instructor not found'}), 404

        classes = Class.query.filter(
            or_(
                Class.instructor_id == instructor_id,
                Class.substitute_instructor_id == instructor_id
            )
        ).all()
        class_ids = [cls.id for cls in classes]
        if not class_ids:
            return jsonify({'success': True, 'students': []})

        enrollments = Enrollment.query.filter(Enrollment.class_id.in_(class_ids)).all()
        student_ids = sorted({enrollment.student_id for enrollment in enrollments})
        if not student_ids:
            return jsonify({'success': True, 'students': []})

        students = Student.query.filter(Student.id.in_(student_ids)).all()
        face_student_ids = set(
            encoding.student_id for encoding in FaceEncoding.query.filter(FaceEncoding.student_id.in_(student_ids)).all()
        )

        student_payload = []
        for student in students:
            student_payload.append({
                'id': student.id,
                'name': f"{(student.first_name or '').strip()} {(student.last_name or '').strip()}".strip() or student.id,
                'yearLevel': student.year_level or '',
                'hasFaceImages': student.id in face_student_ids
            })

        student_payload.sort(key=lambda item: item['name'])
        return jsonify({'success': True, 'students': student_payload})
    except Exception as e:
        current_app.logger.error(f"Error in get_instructor_students_api: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to load students'}), 500

@api_bp.route('/instructors/<int:instructor_id>/classes/<int:class_id>/students', methods=['GET'])
def get_instructor_class_students_api(instructor_id, class_id):
    """Return students for a specific class taught by the instructor."""
    try:
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            return jsonify({'success': False, 'message': 'Instructor not found'}), 404

        cls = Class.query.filter(
            Class.id == class_id,
            or_(
                Class.instructor_id == instructor_id,
                Class.substitute_instructor_id == instructor_id
            )
        ).first()
        if not cls:
            return jsonify({'success': False, 'message': 'Class not found or unauthorized'}), 404

        enrollments = Enrollment.query.filter_by(class_id=class_id).all()
        student_ids = [enrollment.student_id for enrollment in enrollments]
        if not student_ids:
            return jsonify({'success': True, 'students': []})

        students = Student.query.filter(Student.id.in_(student_ids)).all()
        face_student_ids = set(
            encoding.student_id for encoding in FaceEncoding.query.filter(FaceEncoding.student_id.in_(student_ids)).all()
        )

        student_payload = []
        for student in students:
            student_payload.append({
                'id': student.id,
                'name': f"{(student.first_name or '').strip()} {(student.last_name or '').strip()}".strip() or student.id,
                'yearLevel': student.year_level or '',
                'hasFaceImages': student.id in face_student_ids,
                'classId': class_id,
                'classCode': cls.class_code,
                'className': cls.description
            })

        student_payload.sort(key=lambda item: item['name'])
        return jsonify({'success': True, 'students': student_payload})
    except Exception as e:
        current_app.logger.error(f"Error in get_instructor_class_students_api: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to load class students'}), 500

def sanitize_name_for_folder(name):
    """
    Sanitize a name to be safe for use as a folder name.
    Removes special characters and replaces spaces with underscores.
    """
    if not name:
        return 'unknown'
    
    # Replace spaces with underscores and remove special characters
    sanitized = re.sub(r'[^a-zA-Z0-9\s_-]', '', name)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    
    # Ensure it's not empty after sanitization
    if not sanitized:
        return 'unknown'
    
    return sanitized.lower()

def generate_face_embedding(image_path):
    try:
        deepface = get_deepface()
        if not deepface:
            current_app.logger.warning("DeepFace not available, skipping face embedding generation")
            return None
        
        # Generate face embedding using DeepFace
        embedding = deepface.DeepFace.represent(img_path=image_path, model_name=DEEPFACE_MODEL, detector_backend=DEEPFACE_DETECTOR, enforce_detection=False)
        
        if embedding and len(embedding) > 0:
            # Extract the embedding array
            embedding_array = embedding[0]['embedding']
            return embedding_array
        else:
            current_app.logger.warning(f"No face detected in {image_path}")
            return None
    except Exception as e:
        current_app.logger.error(f"Error generating face embedding for {image_path}: {str(e)}")
        return None

# New function to mark absent students
def mark_absent_students():
    """
    Marks students as absent for completed class sessions that haven't been processed.
    This function should be called periodically (e.g., via a cron job) to process
    attendance for completed sessions.
    """
    current_app.logger.info("Starting process to mark absent students...")
    try:
        # Get current time for processing
        current_time = get_pst_now()
        
        # Find completed class sessions that haven't been processed
        # A session is considered complete if it's more than 15 minutes past its scheduled end time
        # or if it's more than 4 hours past its scheduled start time
        completed_sessions = ClassSession.query.filter(
            ClassSession.is_attendance_processed == False,
            (
                # Either 15 minutes past scheduled end time
                (ClassSession.scheduled_end_time != None) &
                (ClassSession.scheduled_end_time + timedelta(minutes=15) < current_time)
            ) | (
                # Or 4 hours past scheduled start time
                (ClassSession.scheduled_start_time != None) &
                (ClassSession.scheduled_start_time + timedelta(hours=4) < current_time)
            )
        ).all()

        current_app.logger.info(f"Found {len(completed_sessions)} completed sessions to process")

        for session in completed_sessions:
            try:
                # Use a transaction for each session to ensure atomicity
                with db.session.begin_nested():
                    current_app.logger.info(
                        f"Processing session ID: {session.id} for class {session.class_id} "
                        f"on {session.date}"
                    )

                    # Get all enrolled students for this class
                    enrolled_students = Enrollment.query.filter_by(
                        class_id=session.class_id
                    ).all()
                    enrolled_student_ids = {enrollment.student_id for enrollment in enrolled_students}

                    # Get all students who have attendance records for this session
                    attendance_records = AttendanceRecord.query.filter_by(
                        class_session_id=session.id
                    ).all()
                    attended_student_ids = {record.student_id for record in attendance_records}

                    # Find students who are enrolled but haven't attended
                    absent_student_ids = enrolled_student_ids - attended_student_ids

                    current_app.logger.info(
                        f"Session {session.id}: {len(enrolled_student_ids)} enrolled, "
                        f"{len(attended_student_ids)} attended, {len(absent_student_ids)} absent"
                    )

                    # Create absent records for each absent student
                    for student_id in absent_student_ids:
                        absent_record = AttendanceRecord(
                            student_id=student_id,
                            class_session_id=session.id,
                            status=AttendanceStatus.ABSENT,  # Use enum instead of string
                            marked_by=None,  # Marked by system
                            marked_at=current_time
                        )
                        db.session.add(absent_record)
                        current_app.logger.info(
                            f"Marked student {student_id} as Absent for session {session.id}"
                        )

                    # Mark the session as processed
                    session.is_attendance_processed = True
                    session.view_lock_owner = None
                    session.view_lock_acquired_at = None
                    current_app.logger.info(f"Marked session {session.id} as processed")

            except Exception as e:
                current_app.logger.error(
                    f"Error processing session {session.id}: {str(e)}"
                )
                # Continue with next session instead of failing completely
                continue

        # Commit all changes
        db.session.commit()
        current_app.logger.info("Successfully completed marking absent students")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in mark_absent_students: {str(e)}")
        raise  # Re-raise to allow caller to handle the error

# Add a scheduled task endpoint (protected by API key)
@api_bp.route('/tasks/mark-absent', methods=['POST'])
@limiter.limit("1 per minute")  # Strict limit for background tasks
def trigger_mark_absent():
    """
    Endpoint to trigger the mark_absent_students function.
    This should be called by a scheduled task (e.g., cron job).
    """
    try:
        mark_absent_students()
        return jsonify({
            'message': 'Successfully processed absent students',
            'timestamp': get_pst_now().isoformat()
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error in trigger_mark_absent: {str(e)}")
        return jsonify({
            'error': 'Failed to process absent students',
            'details': str(e)
        }), 500

@api_bp.route('/instructors', methods=['GET'])
@login_required # Ensure user is logged in
def get_instructors():
    """API endpoint to get a list of all instructors."""
    try:
        # Query for users with the role 'instructor' sorted alphabetically
        instructors = User.query.filter_by(role='instructor').order_by(User.last_name, User.first_name).all()
        
        # Prepare data for JSON response
        instructor_list = []
        for instructor in instructors:
            instructor_list.append({
                'id': instructor.id,
                'username': instructor.username,
                'firstName': instructor.first_name,
                'lastName': instructor.last_name,
                'email': instructor.email
                # Include other relevant fields if needed
            })
            
        return jsonify(instructor_list), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching instructors: {str(e)}")
        return jsonify({'error': 'Failed to fetch instructors', 'details': str(e)}), 500

@api_bp.route('/checkin/instructor', methods=['POST'])
@limiter.limit("30 per minute")  # More lenient limit for instructor check-in
def instructor_checkin():
    # API key check is handled by before_request
    data = request.get_json()
    instructor_id = data.get('instructor_id')
    class_id = data.get('class_id')
    client_timestamp = data.get('timestamp')
    # Optional room number for this specific session (from scanner client)
    session_room_number = (data.get('room_number') or '').strip() if isinstance(data, dict) else None

    if not instructor_id or not class_id:
        return jsonify({'error': 'Missing instructor_id or class_id'}), 400

    try:
        # Use User model and filter by role for instructor
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        class_obj = Class.query.get(class_id)

        if not instructor:
            return jsonify({'error': f'Instructor with ID {instructor_id} not found or does not have instructor role'}), 404
        if not class_obj:
            return jsonify({'error': f'Class with ID {class_id} not found'}), 404
        if instructor_id not in (class_obj.instructor_id, class_obj.substitute_instructor_id):
            return jsonify({
                'error': 'Instructor not assigned to this class',
                'details': 'Only the primary or designated substitute may start the session'
            }), 403
        assignment_role = 'substitute' if class_obj.substitute_instructor_id == instructor_id else 'primary'

        current_time = pst_now_naive()
        if client_timestamp:
            try:
                from utils.timezone import to_pst
                client_time = datetime.fromisoformat(client_timestamp.replace('Z', '+00:00'))
                client_time_pst = to_pst(client_time).replace(tzinfo=None)
                time_diff = abs((client_time_pst - current_time).total_seconds())
                if time_diff <= 300:  # 5 minutes tolerance
                    current_time = client_time_pst
                    current_app.logger.info(
                        f"Using instructor client timestamp (converted to PST): {current_time}"
                    )
                else:
                    current_app.logger.warning(
                        f"Instructor client timestamp {client_time_pst} differs significantly from server time {current_time}. "
                        f"Using server time instead."
                    )
            except ValueError:
                current_app.logger.warning(
                    f"Invalid instructor client timestamp format: {client_timestamp}. Using server time instead."
                )

        today = current_time.date()
        schedule_window = resolve_schedule_window(class_obj.schedule or '', target_date=today)
        # Reuse only unprocessed sessions so instructors can end and restart on the same day
        current_session = (
            ClassSession.query
            .filter_by(
                class_id=class_id,
                date=today,
                is_attendance_processed=False
            )
            .order_by(ClassSession.start_time.desc())
            .first()
        )

        if not current_session:
            if schedule_window:
                scheduled_start_datetime = schedule_window['start_datetime']
                scheduled_end_datetime = schedule_window['end_datetime']
            else:
                scheduled_start_datetime = current_time
                scheduled_end_datetime = current_time + timedelta(minutes=DEFAULT_AUTO_TIMEOUT_MINUTES)

            # Create new session with proper locking
            try:
                current_session = ClassSession(
                    class_id=class_id,
                    date=today,
                    start_time=current_time,
                    scheduled_start_time=scheduled_start_datetime,
                    scheduled_end_time=scheduled_end_datetime,
                    instructor_id=instructor_id,
                    is_attendance_processed=False,
                    session_room_number=session_room_number or None
                )
                db.session.add(current_session)
                db.session.commit()
                current_app.logger.info(f"Created new class session: {current_session.id}")
                
                # Don't automatically create ABSENT records - let facial recognition/manual marking create them
                # This prevents students from being marked absent before they have a chance to check in
                
            except IntegrityError:
                # Handle race condition where another process created the session
                db.session.rollback()
                current_session = ClassSession.query.filter_by(
                    class_id=class_id,
                    date=today
                ).first()
                if current_session:
                    current_app.logger.info(f"Using existing session {current_session.id} created by another process")
                else:
                    raise  # Re-raise if session still doesn't exist
        else:
            # If a session exists, ensure the instructor is associated
            if current_session.instructor_id != instructor_id:
                current_session.instructor_id = instructor_id

            # If we receive a room number and it hasn't been set for this session yet, store it
            if session_room_number and not current_session.session_room_number:
                current_session.session_room_number = session_room_number

            if not current_session.scheduled_end_time and schedule_window:
                current_session.scheduled_end_time = schedule_window['end_datetime']

            db.session.commit()
            current_app.logger.info(
                f"Associated instructor {instructor_id} with existing session {current_session.id}"
            )

            current_app.logger.info(f"Using existing class session: {current_session.id}")

        attendance_record = InstructorAttendance.query.filter_by(
            instructor_id=instructor_id,
            class_id=class_id,
            date=today
        ).first()

        if not attendance_record:
            attendance_record = InstructorAttendance(
                instructor_id=instructor_id,
                class_id=class_id,
                date=today,
                status='Present',
                time_in=current_time
            )
            db.session.add(attendance_record)
            current_app.logger.info(
                f"Created instructor attendance record for instructor {instructor_id} in class {class_id} on {today}"
            )
        else:
            updates_applied = False
            if attendance_record.status != 'Present':
                attendance_record.status = 'Present'
                updates_applied = True
            if not attendance_record.time_in:
                attendance_record.time_in = current_time
                updates_applied = True
            if updates_applied:
                current_app.logger.info(
                    f"Updated instructor attendance record for instructor {instructor_id} in class {class_id} on {today}"
                )

        db.session.commit()

        return jsonify({
            'message': 'Instructor check-in successful',
            'class_session_id': current_session.id,
            'scheduled_start_time': current_session.scheduled_start_time.isoformat() if current_session.scheduled_start_time else None,
            'scheduled_end_time': current_session.scheduled_end_time.isoformat() if current_session.scheduled_end_time else None,
            'assignment_role': assignment_role
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during instructor check-in: {str(e)}")
        return jsonify({'error': 'An internal error occurred', 'details': str(e)}), 500

@api_bp.route('/checkout/instructor', methods=['POST'])
@limiter.limit("30 per minute")
def instructor_checkout():
    """Handle instructor checkout and mark absent students who never checked in.
    
    This marks all enrolled students who never clocked in as ABSENT for the specific class session.
    If class_id is provided, only marks absent students for that particular class.
    If class_id is not provided, marks absent students for all active class sessions of the instructor.
    Attendance status is based on the actual start time (when instructor clicked the class),
    not the scheduled class time.
    """
    data = request.get_json()
    instructor_id = data.get('instructor_id')
    class_id = data.get('class_id')  # Optional: if provided, only checkout from that specific class
    class_session_id = data.get('class_session_id')  # Optional: target a specific session explicitly

    # Whether this checkout was initiated automatically (timeout) from a kiosk or scheduler
    auto = bool(data.get('auto', False))

    if instructor_id is None:
        return jsonify({'error': 'Missing instructor_id'}), 400

    try:
        instructor_id = int(instructor_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid instructor_id'}), 400

    if class_id is not None:
        try:
            class_id = int(class_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid class_id'}), 400

    if class_session_id is not None:
        try:
            class_session_id = int(class_session_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid class_session_id'}), 400

    try:
        # Verify instructor
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            return jsonify({'error': f'Instructor with ID {instructor_id} not found'}), 404

        today = date.today()

        class_sessions = []

        if class_session_id is not None:
            class_session = ClassSession.query.get(class_session_id)
            if not class_session:
                return jsonify({'error': f'Class session with ID {class_session_id} not found'}), 404

            class_obj = Class.query.get(class_session.class_id)
            if not class_obj:
                return jsonify({'error': f'Class with ID {class_session.class_id} not found'}), 404

            if instructor_id not in (
                class_session.instructor_id,
                class_obj.instructor_id,
                class_obj.substitute_instructor_id
            ):
                return jsonify({
                    'error': 'Instructor not assigned to this session',
                    'details': 'Only the instructor who started the session or an assigned substitute may end it'
                }), 403

            if class_id and class_session.class_id != class_id:
                return jsonify({
                    'error': 'Class mismatch',
                    'details': 'Provided class_id does not match the targeted class session'
                }), 400

            if class_session.is_attendance_processed:
                return jsonify({
                    'message': 'Class session already ended',
                    'absent_students_marked': 0
                }), 200

            class_sessions = [class_session]
        else:
            # Find active class sessions for this instructor today
            # If class_id is provided, filter to only that specific class session
            query = ClassSession.query.filter_by(
                date=today,
                instructor_id=instructor_id
            ).filter(ClassSession.start_time.isnot(None))

            if class_id:
                # If class_id is provided, only checkout from that specific class session
                query = query.filter_by(class_id=class_id)
                class_obj = Class.query.get(class_id)
                if not class_obj:
                    return jsonify({'error': f'Class with ID {class_id} not found'}), 404
                if instructor_id not in (class_obj.instructor_id, class_obj.substitute_instructor_id):
                    return jsonify({
                        'error': 'Instructor not assigned to this class',
                        'details': 'Only the primary or designated substitute may end this session'
                    }), 403

            class_sessions = query.all()

        if not class_sessions:
            return jsonify({
                'message': 'No active class sessions found for checkout',
                'absent_students_marked': 0
            }), 200

        total_absent_count = 0
        session_results = []

        for class_session in class_sessions:
            session_checkout_time = pst_now_naive()
            # Get all enrolled students for this specific class
            enrollments = Enrollment.query.filter_by(class_id=class_session.class_id).all()
            enrolled_student_ids = [e.student_id for e in enrollments]

            # Get all students who have already checked in for this specific class session
            existing_attendance = AttendanceRecord.query.filter_by(
                class_session_id=class_session.id
            ).all()
            checked_in_student_ids = {record.student_id for record in existing_attendance}

            # Find students who haven't checked in for this specific class session
            absent_student_ids = [sid for sid in enrolled_student_ids if sid not in checked_in_student_ids]

            # Mark absent students for this specific class session only
            absent_count = 0
            for student_id in absent_student_ids:
                # Check if attendance record already exists for this class session (shouldn't, but just in case)
                existing_record = AttendanceRecord.query.filter_by(
                    class_session_id=class_session.id,
                    student_id=student_id
                ).first()

                if not existing_record:
                    # Create ABSENT record for this specific class session
                    absent_record = AttendanceRecord(
                        student_id=student_id,
                        class_session_id=class_session.id,  # Specific to this class session
                        status=AttendanceStatus.ABSENT,
                        date=class_session.date,
                        marked_by=None,  # System-marked
                        marked_at=get_pst_now(),
                        time_out=session_checkout_time
                    )
                    db.session.add(absent_record)
                    absent_count += 1
                    total_absent_count += 1
                    current_app.logger.info(
                        f"Marked student {student_id} as ABSENT for class session {class_session.id} "
                        f"(class {class_session.class_id}) on {today} (never checked in before checkout)"
                    )

            for attendance in existing_attendance:
                if attendance.time_out is None:
                    attendance.time_out = session_checkout_time

            attendance_record = InstructorAttendance.query.filter_by(
                instructor_id=instructor_id,
                class_id=class_session.class_id,
                date=class_session.date
            ).first()

            if attendance_record:
                if not attendance_record.time_in:
                    attendance_record.time_in = class_session.start_time or session_checkout_time
                # If this checkout was automatic (timeout), do not record an OUT timestamp for instructor
                attendance_record.time_out = session_checkout_time if not auto else None
                if attendance_record.status != 'Present':
                    attendance_record.status = 'Present'
            else:
                attendance_record = InstructorAttendance(
                    instructor_id=instructor_id,
                    class_id=class_session.class_id,
                    date=class_session.date,
                    status='Present' if class_session.start_time else 'Absent',
                    time_in=class_session.start_time,
                    time_out=(session_checkout_time if not auto else None)
                )
                db.session.add(attendance_record)

            # Get class info for response
            class_obj = Class.query.get(class_session.class_id)
            session_results.append({
                'class_session_id': class_session.id,
                'class_id': class_session.class_id,
                'class_code': class_obj.class_code if class_obj else 'Unknown',
                'absent_students_marked': absent_count,
                'total_enrolled': len(enrolled_student_ids),
                'checked_in': len(checked_in_student_ids)
            })

            # Mark the session as processed so other kiosks know it's no longer active
            class_session.is_attendance_processed = True
            class_session.view_lock_owner = None
            class_session.view_lock_acquired_at = None

        db.session.commit()

        return jsonify({
            'message': 'Instructor checkout successful',
            'total_absent_students_marked': total_absent_count,
            'sessions_processed': len(session_results),
            'session_details': session_results
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during instructor checkout: {str(e)}")
        return jsonify({'error': 'An internal error occurred', 'details': str(e)}), 500

@api_bp.route('/scan/student', methods=['POST'])
@limiter.limit("60 per minute")  # Higher limit for student scans
def student_scan():
    # API key check is handled by before_request
    data = request.get_json()
    student_id = data.get('student_id')
    class_session_id = data.get('class_session_id')
    client_timestamp = data.get('timestamp')  # Optional client timestamp

    if not student_id or not class_session_id:
        return jsonify({'error': 'Missing student_id or class_session_id'}), 400

    try:
        # Validate student
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': f'Student with ID {student_id} not found'}), 404

        # Validate class session with proper locking
        class_session = ClassSession.query.filter_by(id=class_session_id).with_for_update().first()
        if not class_session:
            return jsonify({'error': f'Class session with ID {class_session_id} not found'}), 404

        # Check if session is still active (within 4 hours of actual start)
        # Use pst_now_naive() to get Philippine time (PST) as naive datetime for consistent comparison
        current_time = pst_now_naive()
        if class_session.start_time:
            time_diff = current_time - class_session.start_time
            if time_diff > timedelta(hours=4):
                return jsonify({
                    'error': 'Class session has ended',
                    'details': 'Attendance can only be recorded within 4 hours of the actual start time'
                }), 400

        # Check if student is enrolled in this class
        enrollment = Enrollment.query.filter_by(
            student_id=student_id,
            class_id=class_session.class_id
        ).first()
        if not enrollment:
            return jsonify({
                'error': 'Student not enrolled',
                'details': f'Student {student_id} is not enrolled in class {class_session.class_id}'
            }), 403

        # Removed timeout window check - time_out functionality removed

        # Check for existing attendance record
        existing_attendance = AttendanceRecord.query.filter_by(
            student_id=student_id,
            class_session_id=class_session_id
        ).first()
        
        if existing_attendance:
            # Student already checked in - time_out functionality removed
            return jsonify({
                'error': 'Already checked in',
                'details': f'Student {student_id} is already checked in for this session'
            }), 409

        # Use pst_now_naive() to get Philippine time (PST) as naive datetime for consistent comparison
        current_time = pst_now_naive()
        
        # Handle time synchronization
        scan_datetime = current_time
        if client_timestamp:
            try:
                # Parse client timestamp if provided
                client_time = datetime.fromisoformat(client_timestamp.replace('Z', '+00:00'))
                # Convert to PST naive for comparison
                from utils.timezone import to_pst
                client_time_pst = to_pst(client_time).replace(tzinfo=None)
                # Check if client time is within reasonable bounds (e.g., ±5 minutes)
                time_diff = abs((client_time_pst - current_time).total_seconds())
                if time_diff <= 300:  # 5 minutes in seconds
                    scan_datetime = client_time_pst
                    current_app.logger.info(f"Using client timestamp (converted to PST): {scan_datetime}")
                else:
                    current_app.logger.warning(
                        f"Client timestamp {client_time_pst} differs significantly from server time {current_time}. "
                        f"Using server time instead."
                    )
            except ValueError as e:
                current_app.logger.warning(f"Invalid client timestamp format: {client_timestamp}. Using server time instead.")

        # Determine attendance status based on actual class start time (when instructor clicked the class) in Philippine time (PST)
        # Logic: If scanned within 15min after actual start → PRESENT, If scanned more than 15min but less than 45min → LATE, If scanned 45min+ → ABSENT
        # Students who never check in are marked ABSENT at instructor checkout
        status = 'Late'  # Default to Late
        if class_session.start_time:
            status = AttendanceTimeValidator.determine_attendance_status(
                class_session.start_time,
                scan_datetime
            )
            time_diff = scan_datetime - class_session.start_time
            current_app.logger.info(
                f"Student {student_id} marked as {status}. "
                f"Scan time: {scan_datetime}, Actual start: {class_session.start_time}, "
                f"Difference: {time_diff}"
            )

        # Create attendance record with retry logic
        max_retries = current_app.config.get('API_MAX_RETRIES', 3)
        retry_delay = current_app.config.get('API_RETRY_DELAY', 0.1)
        retry_count = 0
        while retry_count < max_retries:
            try:
                attendance_record = AttendanceRecord(
                    student_id=student.id,
                    class_session_id=class_session.id,
                    status=AttendanceStatus[status.upper()],  # Convert status to enum value
                    marked_by=None,  # Marked by facial recognition
                    marked_at=scan_datetime,
                    time_in=scan_datetime
                )
                db.session.add(attendance_record)
                db.session.commit()
                current_app.logger.info(
                    f"Recorded attendance for student {student.id} in session {class_session.id} "
                    f"with status: {status} at {scan_datetime}"
                )
                break
            except IntegrityError:
                retry_count += 1
                if retry_count == max_retries:
                    raise
                db.session.rollback()
                current_app.logger.warning(
                    f"Retry {retry_count}/{max_retries} for student {student.id} "
                    f"in session {class_session.id}"
                )
                time_module.sleep(retry_delay)  # Use configured delay

        return jsonify({
            'message': 'Student attendance recorded successfully',
            'status': status,
            'recorded_at': scan_datetime.isoformat(),
            'time_in': scan_datetime.isoformat(),
            'scheduled_start_time': class_session.scheduled_start_time.isoformat() if class_session.scheduled_start_time else None
        }), 201

    except IntegrityError:
        db.session.rollback()
        current_app.logger.error(
            f"Integrity error during student scan for student {student_id} "
            f"in session {class_session_id}"
        )
        return jsonify({
            'error': 'Attendance record already exists for this student and session'
        }), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during student scan: {str(e)}")
        return jsonify({'error': 'An internal error occurred', 'details': str(e)}), 500

# Add a health check endpoint (no rate limit)
@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint that returns server status and time.
    This can be used by the Raspberry Pi to verify connectivity and time sync.
    """
    try:
        server_time = get_pst_now()
        return jsonify({
            'status': 'healthy',
            'server_time': server_time.isoformat(),
            'timezone': str(server_time.tzinfo) if server_time.tzinfo else 'UTC',
            'version': current_app.config.get('VERSION', '1.0.0'),
            'api_timestamp_tolerance': current_app.config.get('API_TIMESTAMP_TOLERANCE', 300),
            'attendance_grace_period': current_app.config.get('ATTENDANCE_GRACE_PERIOD', 15),
            'attendance_absent_threshold': current_app.config.get('ATTENDANCE_ABSENT_THRESHOLD', 45),
            'attendance_timeout_window': current_app.config.get('ATTENDANCE_TIMEOUT_WINDOW', 10),
            'attendance_session_timeout': current_app.config.get('ATTENDANCE_SESSION_TIMEOUT', 240)
        }), 200
    except Exception as e:
        current_app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@api_bp.route('/class/<int:class_id>/session/<date_str>', methods=['GET'])
def get_class_session_info(class_id, date_str):
    """
    Get class session information for a specific class and date.
    Returns class and session details including room number.
    """
    try:
        # Parse the date
        try:
            session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
            
        # Get class information
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({'error': f'Class with ID {class_id} not found'}), 404
            
        # Get class session for the specific date
        class_session = ClassSession.query.filter_by(
            class_id=class_id,
            date=session_date
        ).first()
        
        response_data = {
            'class_id': class_id,
            'class_code': class_obj.class_code,
            'class_description': class_obj.description,
            'room_number': class_obj.room_number,  # Default class room
            'schedule': class_obj.schedule,
            'date': date_str
        }
        
        if class_session:
            response_data.update({
                'session_id': class_session.id,
                'session_room_number': class_session.session_room_number,
                'start_time': class_session.start_time.isoformat() if class_session.start_time else None,
                'scheduled_start_time': class_session.scheduled_start_time.isoformat() if class_session.scheduled_start_time else None,
                'scheduled_end_time': class_session.scheduled_end_time.isoformat() if class_session.scheduled_end_time else None,
                'is_attendance_processed': class_session.is_attendance_processed,
                'instructor_id': class_session.instructor_id
            })
        else:
            response_data['session_id'] = None
            
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching class session info: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@api_bp.route('/attendance', methods=['POST'])
@limiter.limit("60 per minute")
def mark_attendance():
    """Mark student attendance via facial recognition"""
    try:
        data = request.get_json()
        if not data or not all(key in data for key in ['student_id', 'class_id', 'date']):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        student_id = data['student_id']
        class_id = data['class_id']
        date_str = data['date']
        status = data.get('status', 'Present')  # Default to Present if not specified
        time_in_str = data.get('time_in')  # Optional time_in from scanner
        # Removed time_out parsing - time_out functionality removed

        # Parse date string
        try:
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # Verify student exists
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404

        # Verify class exists
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({'success': False, 'message': 'Class not found'}), 404

        # Verify student is enrolled in class
        enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
        if not enrollment:
            return jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 400

        # Find or create class session
        class_session = ClassSession.query.filter_by(
            class_id=class_id,
            date=attendance_date
        ).first()

        # If session exists but hasn't started, start it now
        if class_session and not class_session.start_time:
            class_session.start_time = pst_now_naive()
            db.session.commit()  # Commit the start_time change
            current_app.logger.info(f"Started class session {class_session.id} when first attendance was recorded")

        if not class_session:
            now = pst_now_naive()
            window = resolve_schedule_window(class_obj.schedule or '', target_date=attendance_date)
            if window:
                scheduled_start_datetime = window['start_datetime']
                scheduled_end_datetime = window['end_datetime']
            else:
                scheduled_start_datetime = now
                scheduled_end_datetime = now + timedelta(minutes=DEFAULT_AUTO_TIMEOUT_MINUTES)

            class_session = ClassSession(
                class_id=class_id,
                instructor_id=class_obj.instructor_id,
                date=attendance_date,
                start_time=now,  # Mark session as started when first attendance is recorded
                scheduled_start_time=scheduled_start_datetime,
                scheduled_end_time=scheduled_end_datetime,
                is_attendance_processed=False,
                # Fallback to class room number if defined
                session_room_number=getattr(class_obj, 'room_number', None)
            )
            db.session.add(class_session)
            db.session.flush()
            current_app.logger.info(f"Created new class session {class_session.id} and marked as started")
            
            # Don't automatically create ABSENT records - let facial recognition/manual marking create them
            # This prevents students from being marked absent before they have a chance to check in
            db.session.commit()  # Commit the new session

        # At this point, class_session should have a start_time (either from creation or from starting it above)
        # Check for existing attendance record
        existing_attendance = AttendanceRecord.query.filter_by(
            class_session_id=class_session.id,
            student_id=student_id
        ).first()

        # Use pst_now_naive() to get Philippine time (PST) as naive datetime for consistent comparison
        current_time = pst_now_naive()
        
        # Determine attendance status
        determined_status = status  # status is from data.get('status', 'Present')
        
        # Check if instructor has marked attendance for this class and date
        instructor_attendance = InstructorAttendance.query.filter_by(
            instructor_id=class_obj.instructor_id,
            date=attendance_date
        ).first()
        
        # Determine attendance status based on actual class start time (when instructor clicked the class) in Philippine time (PST)
        # Logic: If scanned within 15min after actual start → PRESENT, If scanned more than 15min but less than 45min → LATE, If scanned 45min+ → ABSENT
        # Students who never check in are marked ABSENT at instructor checkout
        if class_session.start_time:
            determined_status = AttendanceTimeValidator.determine_attendance_status(
                class_session.start_time,
                current_time
            )
            time_diff = current_time - class_session.start_time
            current_app.logger.info(
                f"Student {student_id} marked as {determined_status}. "
                f"Scan time: {current_time}, Actual start: {class_session.start_time}, "
                f"Difference: {time_diff}"
            )
        else:
            # If no actual start time (shouldn't happen if instructor checked in), use the status from the request (defaults to 'Late')
            determined_status = status if status else 'Late'
        
        # Parse time_in if provided
        time_in = None
        if time_in_str:
            try:
                time_in = datetime.strptime(time_in_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    time_in = datetime.strptime(time_in_str, '%H:%M:%S')
                    time_in = datetime.combine(attendance_date, time_in.time())
                except ValueError:
                    time_in = current_time
        else:
            time_in = current_time
        
        # If existing attendance record exists, check its status
        if existing_attendance:
            # If status is already LATE, don't allow update (already checked in)
            if existing_attendance.status == AttendanceStatus.LATE:
                return jsonify({
                    'success': False,
                    'message': 'Student already checked in for this session'
                }), 409
            # If status is ABSENT, update it to the new status
            elif existing_attendance.status == AttendanceStatus.ABSENT:
                existing_attendance.status = AttendanceStatus[determined_status.upper()]
                existing_attendance.marked_by = None
                existing_attendance.marked_at = current_time
                existing_attendance.time_in = time_in
                db.session.commit()
                return jsonify({
                    'success': True,
                    'message': 'Attendance recorded successfully',
                    'status': existing_attendance.status.value if existing_attendance.status else 'Absent',
                    'recorded_at': existing_attendance.marked_at.isoformat(),
                    'time_in': existing_attendance.time_in.isoformat()
                }), 200
        
        # Create new attendance record if none exists (shouldn't happen if defaults are created)
        attendance_record = AttendanceRecord(
            class_session_id=class_session.id,
            student_id=student_id,
            status=AttendanceStatus[determined_status.upper()],
            marked_by=None,
            marked_at=current_time,
            date=attendance_date,
            time_in=time_in
        )
        db.session.add(attendance_record)
        
        # Fallback: create new record if no default exists (shouldn't happen)
        attendance_record = AttendanceRecord(
            class_session_id=class_session.id,
            student_id=student_id,
            status=AttendanceStatus[determined_status.upper()],
            marked_by=None,
            marked_at=current_time,
            date=attendance_date,
            time_in=time_in or current_time
            # Removed time_out - time_out functionality removed
        )
        db.session.add(attendance_record)

        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Attendance recorded successfully',
                'status': attendance_record.status.value if attendance_record.status else 'Absent',
                'recorded_at': attendance_record.marked_at.isoformat(),
                'time_in': attendance_record.time_in.isoformat()
                # Removed time_out from response - time_out functionality removed
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/instructor-attendance', methods=['POST'])
@limiter.limit("60 per minute")
def mark_instructor_attendance():
    """Mark instructor attendance via facial recognition"""
    try:
        data = request.get_json()
        if not data or not all(key in data for key in ['instructor_id', 'date', 'class_id']):
            return jsonify({'success': False, 'message': 'Missing required fields: instructor_id, date, class_id'}), 400

        instructor_id = data['instructor_id']
        date_str = data['date']
        class_id = data['class_id']
        status = data.get('status', 'Present')  # Default to Present, accept status parameter

        # Convert date string to date object
        try:
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400

        # Verify instructor exists and is an instructor
        instructor = User.query.get(instructor_id)
        if not instructor or instructor.role != 'instructor':
            return jsonify({'success': False, 'message': 'Instructor not found'}), 404

        # Check if instructor is assigned to the specific class
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({'success': False, 'message': 'Class not found'}), 404
            
        is_primary_assignment = class_obj.instructor_id == instructor_id
        is_substitute_assignment = class_obj.substitute_instructor_id == instructor_id
        if not (is_primary_assignment or is_substitute_assignment):
            return jsonify({
                'success': False,
                'message': f'Instructor {instructor.username} is not assigned to this class.',
                'error_type': 'not_assigned_to_class'
            }), 403

        # Prepare class information for response
        scheduled_class_info = {
            'class_id': class_obj.id,
            'class_code': class_obj.class_code,
            'description': class_obj.description,
            'assignmentRole': 'substitute' if is_substitute_assignment else 'primary'
        }

        # Determine which instructor's record should be updated (always the primary instructor when available)
        attendance_instructor_id = class_obj.instructor_id or instructor_id
        proxy_instructor_id = None
        if attendance_instructor_id != instructor_id:
            proxy_instructor_id = instructor_id

        attendance_instructor = User.query.get(attendance_instructor_id)
        attendance_instructor_name = None
        if attendance_instructor:
            first = (attendance_instructor.first_name or '').strip()
            last = (attendance_instructor.last_name or '').strip()
            full_name = f"{first} {last}".strip()
            attendance_instructor_name = full_name or attendance_instructor.username

        # Check for existing attendance record for this class and date
        existing_attendance = InstructorAttendance.query.filter_by(
            instructor_id=attendance_instructor_id,
            class_id=class_id,
            date=attendance_date
        ).first()

        if existing_attendance:
            # Instructor already marked attendance for today - time_out functionality removed
            return jsonify({
                'success': True,
                'message': 'Instructor attendance already recorded for today',
                'status': existing_attendance.status,
                'recorded_at': existing_attendance.created_at.isoformat() if hasattr(existing_attendance, 'created_at') else None,
                'time_in': existing_attendance.time_in.isoformat() if existing_attendance.time_in else None,
                'scheduled_class': scheduled_class_info,
                'recorded_instructor_id': attendance_instructor_id,
                'recorded_instructor_name': attendance_instructor_name,
                'proxy_instructor_id': proxy_instructor_id
            }), 200

        # Create new attendance record with class information
        current_time = get_pst_now()
        attendance_record = InstructorAttendance(
            instructor_id=attendance_instructor_id,
            class_id=class_id,
            date=attendance_date,
            status=status,  # Use the provided status
            notes=(
                f'Marked by facial recognition system for {class_obj.class_code}'
                + (
                    f" via substitute instructor ID {proxy_instructor_id}"
                    if proxy_instructor_id is not None else ''
                )
            ),
            time_in=current_time
        )
        db.session.add(attendance_record)

        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Attendance recorded successfully',
                'status': status,
                'recorded_at': attendance_record.created_at.isoformat() if hasattr(attendance_record, 'created_at') else current_time.isoformat(),
                'time_in': attendance_record.time_in.isoformat(),
                'scheduled_class': scheduled_class_info,
                'recorded_instructor_id': attendance_instructor_id,
                'recorded_instructor_name': attendance_instructor_name,
                'proxy_instructor_id': proxy_instructor_id
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/student/<student_id>/classes', methods=['GET'])
@limiter.limit("60 per minute")
def get_student_classes(student_id):
    """Get all classes that a student is enrolled in"""
    try:
        # Verify student exists - use the id field directly since it's the primary key
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404

        # Get all enrollments for the student
        enrollments = Enrollment.query.filter_by(student_id=student.id).all()
        
        # Get the classes from enrollments
        classes = []
        for enrollment in enrollments:
            class_obj = Class.query.get(enrollment.class_id)
            if class_obj:
                classes.append({
                    'id': class_obj.id,
                    'class_code': class_obj.class_code,
                    'description': class_obj.description,
                    'instructor_id': class_obj.instructor_id,
                    'schedule': class_obj.schedule,
                    'room_number': class_obj.room_number
                })

        return jsonify(classes), 200

    except Exception as e:
        current_app.logger.error(f"Error getting student classes: {str(e)}")
        return jsonify({'error': 'Failed to get student classes', 'details': str(e)}), 500

@api_bp.route('/courses', methods=['GET'])
@limiter.limit("60 per minute")
def get_courses():
    """Get all courses."""
    try:
        courses = Course.query.all()
        return jsonify([{
            'id': course.id,
            'code': course.code,
            'description': course.description
        } for course in courses]), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching courses: {str(e)}")
        return jsonify({'error': 'Failed to fetch courses', 'details': str(e)}), 500

@api_bp.route('/face-encodings', methods=['GET'])
@limiter.limit("60 per minute")
def get_face_encodings():
    """Get all face encodings."""
    try:
        import numpy as np
        
        student_encodings = FaceEncoding.query.all()
        instructor_encodings = InstructorFaceEncoding.query.all()
        
        student_encodings_list = []
        for encoding in student_encodings:
            try:
                # Convert bytes to numpy array and then to list for JSON serialization
                if encoding.encoding_data:
                    embedding_array = np.frombuffer(encoding.encoding_data, dtype=np.float32)
                    embedding_data = embedding_array.tolist()
                else:
                    embedding_data = None
                
                student_encodings_list.append({
                    'id': encoding.id,
                    'student_id': encoding.student_id,
                    'embedding': embedding_data,
                    'image_path': encoding.image_path
                })
            except Exception as e:
                current_app.logger.error(f"Error processing student encoding {encoding.id}: {e}")
                continue
        
        instructor_encodings_list = []
        for encoding in instructor_encodings:
            try:
                # Convert bytes to numpy array and then to list for JSON serialization
                if encoding.encoding:
                    embedding_array = np.frombuffer(encoding.encoding, dtype=np.float32)
                    embedding_data = embedding_array.tolist()
                else:
                    embedding_data = None
                
                instructor_encodings_list.append({
                    'id': encoding.id,
                    'instructor_id': encoding.instructor_id,
                    'embedding': embedding_data,
                    'image_path': encoding.image_path
                })
            except Exception as e:
                current_app.logger.error(f"Error processing instructor encoding {encoding.id}: {e}")
                continue
        
        return jsonify({
            'student_encodings': student_encodings_list,
            'instructor_encodings': instructor_encodings_list
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching face encodings: {str(e)}")
        return jsonify({'error': 'Failed to fetch face encodings', 'details': str(e)}), 500

@api_bp.route('/instructor/<int:instructor_id>/classes', methods=['GET'])
@limiter.limit("60 per minute")
def get_instructor_classes(instructor_id):
    """Get all classes taught by an instructor"""
    try:
        # Verify instructor exists
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            return jsonify({'success': False, 'message': 'Instructor not found'}), 404

        # Get all classes taught by this instructor or ones where they serve as a substitute
        classes = Class.query.filter(
            or_(
                Class.instructor_id == instructor_id,
                Class.substitute_instructor_id == instructor_id
            )
        ).all()
        
        classes_data = []
        for class_obj in classes:
            is_substitute_assignment = class_obj.substitute_instructor_id == instructor_id
            classes_data.append({
                'id': class_obj.id,
                'class_code': class_obj.class_code,
                'description': class_obj.description,
                'instructor_id': class_obj.instructor_id,
                'substitute_instructor_id': class_obj.substitute_instructor_id,
                'assignmentRole': 'substitute' if is_substitute_assignment else 'primary',
                'schedule': class_obj.schedule,
                'room_number': class_obj.room_number,
                'term': class_obj.term,
                'school_year': class_obj.school_year
            })

        return jsonify(classes_data), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/attendance/<student_id>/<class_id>/<date>', methods=['PUT'])
@limiter.limit("60 per minute")
def update_attendance_status(student_id, class_id, date):
    """Update attendance status for a specific student, class, and date"""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'success': False, 'message': 'Missing status field'}), 400

        status = data['status']

        # Verify student exists
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404

        # Parse date from URL
        try:
            attendance_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400

        # Find the class session for this class and date
        class_session = ClassSession.query.filter_by(
            class_id=class_id,
            date=attendance_date
        ).first()

        if not class_session:
            return jsonify({'success': False, 'message': 'No class session found for this date'}), 404

        # Find existing attendance record
        existing_attendance = AttendanceRecord.query.filter_by(
            student_id=student_id,
            class_session_id=class_session.id,
            date=attendance_date
        ).first()

        if existing_attendance:
            # Update existing record
            existing_attendance.updated_at = pst_now_naive()
            
            try:
                db.session.commit()
                return jsonify({
                    'success': True,
                    'message': f'Attendance status updated to {status}',
                    'student_id': student_id,
                    'class_id': class_id,
                    'status': status,
                    'updated_at': existing_attendance.updated_at.isoformat()
                }), 200
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
        else:
            return jsonify({
                'success': False, 
                'message': 'No existing attendance record found to update'
            }), 404

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/upload-instructor-images', methods=['POST'])
@login_required
def upload_instructor_images_api():
    """Upload multiple instructor images"""
    try:
        # Get instructor_id from form
        instructor_id = request.form.get('instructor_id')
        if not instructor_id:
            return jsonify({'success': False, 'message': 'Instructor ID is required'}), 400

        try:
            instructor_id = int(instructor_id)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid instructor ID'}), 400

        current_app.logger.info(f"Upload instructor images called for instructor ID: {instructor_id}")
        current_app.logger.info(f"Request files keys: {list(request.files.keys())}")
        current_app.logger.info(f"Request form keys: {list(request.form.keys())}")
        
        if 'images' not in request.files:
            current_app.logger.warning("No image file provided in request")
            return jsonify({'success': False, 'message': 'No image file provided'}), 400
            
        # Verify instructor exists and has correct role
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            current_app.logger.warning(f"Instructor not found or not an instructor: {instructor_id}")
            return jsonify({'success': False, 'message': 'Instructor not found'}), 404
        
        current_app.logger.info(f"Found instructor: {instructor.first_name} {instructor.last_name}")
        
        # Get all files from the request
        files = request.files.getlist('images')
        if not files:
            current_app.logger.warning("No files found in request.files.getlist('images')")
            return jsonify({'success': False, 'message': 'No image files provided'}), 400
            
        current_app.logger.info(f"Processing {len(files)} files for instructor {instructor_id}")
        
        # Get instructor name for folder creation
        instructor_name = f"{instructor.first_name}_{instructor.last_name}"
        sanitized_instructor_name = sanitize_name_for_folder(instructor_name)
        
        # Check if the files are allowed
        allowed_extensions = {'png', 'jpg', 'jpeg'}
        uploaded_files = []
        errors = []
        
        for file in files:
            if not file.filename:
                errors.append('Empty filename provided')
                continue
                
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if file_ext not in allowed_extensions:
                errors.append(f'File type not allowed for {file.filename}. Please upload PNG, JPG, or JPEG')
                continue
            
            try:
                # Secure the filename and make it unique
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                
                # Create the upload directory based on instructor name
                uploads_dir = os.path.join(current_app.static_folder, 'uploads', 'instructors', sanitized_instructor_name)
                os.makedirs(uploads_dir, exist_ok=True)
                
                # Save the file
                file_path = os.path.join(uploads_dir, filename)
                file.save(file_path)
                
                # Store the relative path
                relative_image_path = os.path.join('uploads', 'instructors', sanitized_instructor_name, filename).replace('\\', '/')
                
                # Generate face embedding using DeepFace
                current_app.logger.info(f"Generating DeepFace embedding for {file.filename}")
                face_embedding = generate_face_embedding(file_path)
                
                if face_embedding is None:
                    current_app.logger.warning(f"Could not generate face embedding for {file.filename}, skipping this image")
                    errors.append(f'No face detected in {file.filename}. Please upload a clear frontal face image.')
                    # Clean up the uploaded file
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue
                
                # Create the face encoding record using InstructorFaceEncoding model
                face_encoding = InstructorFaceEncoding(
                    instructor_id=instructor_id,
                    encoding=face_embedding,
                    image_path=relative_image_path,
                    created_at=pst_now_naive()
                )
                
                # Add to session
                db.session.add(face_encoding)
                # Flush to get the ID without committing
                db.session.flush()
                uploaded_files.append({
                    'id': face_encoding.id,
                    'filename': filename,
                    'path': url_for('static', filename=relative_image_path)
                })
                
            except Exception as e:
                current_app.logger.error(f"Error processing file {file.filename}: {str(e)}", exc_info=True)
                errors.append(f'Error processing {file.filename}: {str(e)}')
                # Clean up the uploaded file if it exists
                if 'file_path' in locals() and os.path.exists(file_path):
                    os.remove(file_path)
                continue
        
        if uploaded_files:
            try:
                db.session.commit()
                return jsonify({
                    'success': True,
                    'message': f'Successfully uploaded {len(uploaded_files)} images',
                    'images': uploaded_files,
                    'errors': errors if errors else None
                })
            except Exception as db_error:
                db.session.rollback()
                current_app.logger.error(f"Database error in upload_instructor_images_api: {str(db_error)}", exc_info=True)
                # Clean up all uploaded files
                for file_info in uploaded_files:
                    # Extract the relative path from the URL path
                    static_path = file_info['path'].replace('/static/', '')
                    file_path = os.path.join(current_app.static_folder, static_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                return jsonify({'success': False, 'message': f'Database error: {str(db_error)}'}), 500
        else:
            return jsonify({
                'success': False,
                'message': 'No images were successfully uploaded',
                'errors': errors
            }), 400
    except Exception as e:
        current_app.logger.error(f"Unexpected error in upload_instructor_images_api: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}), 500

@api_bp.route('/test', methods=['GET'])
def test_api():
    """Test endpoint to verify API is working"""
    return jsonify({
        'status': 'success',
        'message': 'API is working',
        'routes': [str(rule) for rule in current_app.url_map.iter_rules()]
    })

@api_bp.route('/attendance/record', methods=['POST'])
def record_student_attendance():
    """Record student attendance from facial recognition system"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        # Extract required fields
        student_id = data.get('student_id')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        class_id = data.get('class_id')  # New: class_id for specific class validation
        confidence = data.get('confidence', 0.0)
        method = data.get('method', 'facial_recognition')
        status_str = data.get('status', 'late').lower()  # Default to late (changed from present)

        # Convert status string to enum
        try:
            if status_str == 'present':
                attendance_status = AttendanceStatus.PRESENT  # Keep for backward compatibility
            elif status_str == 'late':
                attendance_status = AttendanceStatus.LATE
            elif status_str == 'absent':
                attendance_status = AttendanceStatus.ABSENT
            else:
                attendance_status = AttendanceStatus.LATE  # Default fallback (changed from PRESENT)
        except:
            attendance_status = AttendanceStatus.LATE  # Default fallback (changed from PRESENT)

        if not all([student_id, first_name, last_name, class_id]):
            return jsonify({'success': False, 'message': 'Missing required fields: student_id, first_name, last_name, class_id'}), 400

        # Check if student exists
        student = Student.query.filter_by(id=student_id).first()
        if not student:
            return jsonify({'success': False, 'message': f'Student with ID {student_id} not found'}), 404

        # Check if student is enrolled in the specific class
        from models import Enrollment
        enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
        if not enrollment:
            return jsonify({
                'success': False,
                'message': f'Student {first_name} {last_name} (ID: {student_id}) is not enrolled in this class. Please enroll in this class first.',
                'error_type': 'not_enrolled_in_class'
            }), 403

        # Get class object to access schedule
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({'success': False, 'message': 'Class not found'}), 404
        
        # Find or create a class session for today
        from models import ClassSession
        today = date.today()
        class_session = ClassSession.query.filter_by(class_id=class_id, date=today).first()
        
        # If session exists but hasn't started, start it now
        if class_session and not class_session.start_time:
            class_session.start_time = pst_now_naive()
            db.session.commit()
            current_app.logger.info(f"Started class session {class_session.id} when first attendance was recorded")
        
        if not class_session:
            # Parse schedule to get scheduled start time (for reference only, not used for attendance calculations)
            now = pst_now_naive()
            scheduled_start_datetime = None
            scheduled_end_datetime = None
            
            try:
                schedule_str = class_obj.schedule.strip()
                time_str = None
                
                # Format 1: "MTW 6:58 PM-8:00 PM"
                if ' ' in schedule_str:
                    parts = schedule_str.split()
                    if len(parts) >= 2:
                        # Look for time pattern in the last parts
                        for i in range(len(parts)-1, -1, -1):
                            if ':' in parts[i] and any(period in parts[i].upper() for period in ['AM', 'PM']):
                                time_str = parts[i]
                                if i > 0 and parts[i-1].upper() in ['AM', 'PM']:
                                    time_str = parts[i-1] + ' ' + time_str
                                break
                
                # Format 2: "6:58 PM"
                if not time_str and ':' in schedule_str:
                    time_str = schedule_str
                
                if time_str:
                    # Clean up time string and parse
                    time_str = time_str.strip().upper()
                    if 'AM' not in time_str and 'PM' not in time_str:
                        time_str += ' AM'  # Default to AM if not specified
                    
                    scheduled_time = datetime.strptime(time_str, '%I:%M %p').time()
                    scheduled_start_datetime = datetime.combine(today, scheduled_time)
                    
                    # Also parse end time if available
                    if '-' in schedule_str:
                        end_time_str = schedule_str.split('-')[1].strip()
                        try:
                            end_time = datetime.strptime(end_time_str, '%I:%M %p').time()
                            scheduled_end_datetime = datetime.combine(today, end_time)
                        except ValueError:
                            scheduled_end_datetime = None
            except Exception as e:
                current_app.logger.error(f"Error parsing schedule '{class_obj.schedule}': {str(e)}")
                scheduled_start_datetime = None
                scheduled_end_datetime = None
            
            # Create a new class session for facial recognition attendance
            class_session = ClassSession(
                class_id=class_id,
                instructor_id=class_obj.instructor_id,
                date=today,
                start_time=now,  # Mark session as started
                scheduled_start_time=scheduled_start_datetime,
                scheduled_end_time=scheduled_end_datetime,
                is_attendance_processed=False,
                session_room_number=getattr(class_obj, 'room_number', None)
            )
            db.session.add(class_session)
            db.session.flush()  # Get the ID without committing

        # Determine attendance status based on actual class start time (when instructor clicked the class)
        # Logic: If scanned within 15min after actual start → PRESENT, If scanned more than 15min but less than 45min → LATE, If scanned 45min+ → ABSENT
        # Students who never check in are marked ABSENT at instructor checkout
        current_time = pst_now_naive()
        determined_status = AttendanceStatus.LATE  # Default to LATE
        
        if class_session.start_time:
            status_str = AttendanceTimeValidator.determine_attendance_status(
                class_session.start_time,
                current_time
            )
            # Convert string to enum
            determined_status = AttendanceStatus[status_str.upper()]
            time_diff = current_time - class_session.start_time
            current_app.logger.info(
                f"Student {student_id} marked as {status_str}. "
                f"Scan time: {current_time}, Actual start: {class_session.start_time}, "
                f"Difference: {time_diff}"
            )
        else:
            # If no actual start time (shouldn't happen if instructor checked in), use the status from the request
            determined_status = attendance_status
        
        # Check if student already has an attendance record for today in this class session
        existing_record = AttendanceRecord.query.filter_by(
            class_session_id=class_session.id,
            student_id=student_id
        ).first()

        if existing_record:
            # If status is already LATE, don't allow update (already checked in)
            if existing_record.status == AttendanceStatus.LATE:
                return jsonify({
                    'success': False,
                    'message': f'Attendance already recorded for {first_name} {last_name} today',
                    'existing_record': {
                        'id': existing_record.id,
                        'student_id': existing_record.student_id,
                        'time_in': existing_record.time_in.isoformat() if existing_record.time_in else None,
                        'date': existing_record.date.isoformat() if existing_record.date else None,
                        'status': existing_record.status.value if existing_record.status else 'Absent'
                    }
                }), 409
            # If status is ABSENT, update it to the new status
            elif existing_record.status == AttendanceStatus.ABSENT:
                existing_record.status = determined_status
                existing_record.time_in = current_time
                existing_record.marked_by = None
                existing_record.marked_at = current_time
                db.session.commit()
                logger.info(f"Updated attendance from ABSENT to {determined_status.value} for {first_name} {last_name} (ID: {student_id}) via {method}")
                return jsonify({
                    'success': True,
                    'message': f'Attendance updated for {first_name} {last_name}',
                    'record': {
                        'id': existing_record.id,
                        'student_id': existing_record.student_id,
                        'time_in': existing_record.time_in.isoformat() if existing_record.time_in else None,
                        'date': existing_record.date.isoformat() if existing_record.date else None,
                        'status': existing_record.status.value if existing_record.status else 'Absent'
                    }
                }), 200

        # Create new attendance record linked to the class session
        attendance_record = AttendanceRecord(
            student_id=student_id,
            class_session_id=class_session.id,
            time_in=current_time,
            date=current_time,
            status=determined_status,  # Use the determined status based on schedule
            marked_by=None,  # No user marked this, it was automatic
        )

        db.session.add(attendance_record)
        db.session.commit()

        logger.info(f"Attendance recorded for {first_name} {last_name} (ID: {student_id}) via {method}")

        return jsonify({
            'success': True,
            'message': f'Attendance recorded for {first_name} {last_name}',
            'record': {
                'id': attendance_record.id,
                'student_id': attendance_record.student_id,
                'time_in': attendance_record.time_in.isoformat() if attendance_record.time_in else None,
                'time_out': attendance_record.time_out.isoformat() if attendance_record.time_out else None,
                'date': attendance_record.date.isoformat() if attendance_record.date else None
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error recording attendance: {str(e)}")
        return jsonify({'success': False, 'message': f'Error recording attendance: {str(e)}'}), 500

@api_bp.route('/attendance/check', methods=['POST'])
def check_attendance_status():
    """Check if attendance is already marked for a student in a class session"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        student_id = data.get('student_id')
        class_session_id = data.get('class_session_id')
        
        if not all([student_id, class_session_id]):
            return jsonify({'success': False, 'message': 'Missing required fields: student_id, class_session_id'}), 400
            
        # Check if attendance record exists
        from models import AttendanceRecord
        existing_record = AttendanceRecord.query.filter_by(
            class_session_id=class_session_id,
            student_id=student_id
        ).first()
        
        if existing_record:
            return jsonify({
                'success': True,
                'has_attendance': True,
                'status': existing_record.status.value if existing_record.status else 'Unknown',
                'time_in': existing_record.time_in.isoformat() if existing_record.time_in else None,
                'record_id': existing_record.id
            }), 200
        else:
            return jsonify({
                'success': True,
                'has_attendance': False,
                'status': 'Not Marked'
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"Error checking attendance status: {str(e)}")
        return jsonify({'success': False, 'message': f'Error checking attendance status: {str(e)}'}), 500

@api_bp.route('/attendance/check/instructor', methods=['POST'])
def check_instructor_attendance_status():
    """Check if attendance is already marked for an instructor in a class session"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        instructor_id = data.get('instructor_id')
        class_session_id = data.get('class_session_id')
        
        if not all([instructor_id, class_session_id]):
            return jsonify({'success': False, 'message': 'Missing required fields: instructor_id, class_session_id'}), 400
            
        # Check if instructor attendance record exists
        from models import InstructorAttendance
        existing_record = InstructorAttendance.query.filter_by(
            class_session_id=class_session_id,
            instructor_id=instructor_id
        ).first()
        
        if existing_record:
            return jsonify({
                'success': True,
                'has_attendance': True,
                'status': existing_record.status.value if existing_record.status else 'Unknown',
                'time_in': existing_record.time_in.isoformat() if existing_record.time_in else None,
                'record_id': existing_record.id
            }), 200
        else:
            return jsonify({
                'success': True,
                'has_attendance': False,
                'status': 'Not Marked'
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"Error checking instructor attendance status: {str(e)}")
        return jsonify({'success': False, 'message': f'Error checking instructor attendance status: {str(e)}'}), 500 