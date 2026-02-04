from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app
from flask_login import login_required, current_user
import datetime
from datetime import date, timedelta
from utils.timezone import get_pst_now, pst_now_naive
import calendar

from extensions import db
from models import Class, Student, Enrollment, AttendanceRecord, FaceEncoding, ClassSession, AttendanceStatus, InstructorAttendance
from decorators import admin_required, instructor_required

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@attendance_bp.route('/api/classes', methods=['GET'])
@login_required
def get_classes_with_attendance():
    # If instructor, only show their classes
    if current_user.role == 'instructor':
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
    else:
        classes = Class.query.all()
        
    today = date.today()
    
    # Convert to dictionary
    class_list = []
    for cls in classes:
        # Count enrolled students
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        
        # Count students present today
        present_count = AttendanceRecord.query.filter_by(
            class_id=cls.id,
            date=today,
            status='Present'
        ).count()
        
        class_list.append({
            'id': cls.id,
            'classCode': cls.class_code,
            'description': cls.description,
            'schedule': cls.schedule,
            'roomNumber': cls.room_number,
            'instructorId': cls.instructor_id,
            'enrolledCount': enrolled_count,
            'presentCount': present_count,
            'date': today.strftime('%B %d %Y')
        })
    
    return jsonify(class_list)

@attendance_bp.route('/api/my-classes-today', methods=['GET'])
@login_required
def get_my_classes_today():
    """Get classes taught by the current instructor with attendance for today."""
    if current_user.role != 'instructor':
        return jsonify([])
        
    classes = Class.query.filter_by(instructor_id=current_user.id).all()
    today = date.today()
    
    class_list = []
    for cls in classes:
        # Count enrolled students
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        
        # Count students present today
        present_count = AttendanceRecord.query.filter_by(
            class_id=cls.id,
            date=today,
            status='Present'
        ).count()
        
        class_list.append({
            'id': cls.id,
            'classCode': cls.class_code,
            'description': cls.description,
            'schedule': cls.schedule,
            'roomNumber': cls.room_number,
            'enrolledCount': enrolled_count,
            'presentCount': present_count,
            'date': today.strftime('%B %d %Y')
        })
    
    return jsonify(class_list)

@attendance_bp.route('/api/class/<int:class_id>/attendance', methods=['GET'])
@login_required
def get_class_attendance(class_id):
    try:
        # Check if class exists and belongs to the instructor (or if user is admin)
        if current_user.role == 'instructor':
            class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
            if not class_obj:
                return jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403
        elif current_user.role != 'admin':
             return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        # Get date from request query parameters
        date_str = request.args.get('date')
        
        if date_str:
            # Return attendance for specific date
            try:
                attendance_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                attendance_date = date.today()
            
            # Get all students enrolled in this class
            enrollments = Enrollment.query.filter_by(class_id=class_id).all()
            
            attendance_list = []
            for enrollment in enrollments:
                student = Student.query.get(enrollment.student_id)
                
                if not student:
                    continue
                
                # Get the class session for this date
                class_session = ClassSession.query.filter_by(class_id=class_id, date=attendance_date).first()
                
                if class_session:
                    # Check if attendance record exists for this session
                    attendance = AttendanceRecord.query.filter_by(
                        class_session_id=class_session.id,
                        student_id=student.id
                    ).first()
                else:
                    attendance = None
                
                if attendance:
                    status = attendance.status.value if attendance.status else 'Absent'  # Get the string value of the enum
                    time_in = attendance.time_in.strftime('%H:%M') if attendance.time_in else None
                    time_out = attendance.time_out.strftime('%H:%M') if attendance.time_out else None
                else:
                    status = 'Absent'  # Default to Absent if no record
                    time_in = None
                    time_out = None
                
                attendance_list.append({
                    'studentId': student.id,
                    'studentName': f"{student.first_name} {student.last_name}",
                    'status': status,
                    'time_in': time_in,
                    'time_out': time_out
                })
            
            return jsonify({
                'date': attendance_date.strftime('%Y-%m-%d'),
                'attendance': attendance_list
            })
        else:
            # Return all attendance data for the class
            print(f"DEBUG: Getting all attendance for class {class_id}")
            
            # Get all class sessions for this class
            class_sessions = ClassSession.query.filter_by(class_id=class_id).order_by(ClassSession.date).all()
            print(f"DEBUG: Found {len(class_sessions)} class sessions")
            
            # Get all students enrolled
            enrollments = Enrollment.query.filter_by(class_id=class_id).all()
            students = [Student.query.get(e.student_id) for e in enrollments if Student.query.get(e.student_id)]
            print(f"DEBUG: Found {len(students)} students")
            
            # Get all attendance records for these sessions
            session_ids = [cs.id for cs in class_sessions]
            print(f"DEBUG: Session IDs: {session_ids}")
            attendance_records = AttendanceRecord.query.filter(AttendanceRecord.class_session_id.in_(session_ids)).all()
            print(f"DEBUG: Found {len(attendance_records)} attendance records")
            
            # Group by date
            attendance_by_date = {}
            dates = set()
            for cs in class_sessions:
                date_str = cs.date.strftime('%Y-%m-%d')
                dates.add(date_str)
                attendance_by_date[date_str] = {}
                for student in students:
                    attendance_by_date[date_str][student.id] = 'A'  # Default Absent
            
            for record in attendance_records:
                session = next((cs for cs in class_sessions if cs.id == record.class_session_id), None)
                if session:
                    date_str = session.date.strftime('%Y-%m-%d')
                    status = record.status.value if record.status else 'Absent'
                    print(f"DEBUG: Record for student {record.student_id} on {date_str}: {status}")
                    attendance_by_date[date_str][record.student_id] = status[0]  # P, L, A
            
            dates = sorted(list(dates))
            print(f"DEBUG: Dates: {dates}")
            
            # Prepare response
            student_attendance = []
            for student in students:
                student_data = {
                    'studentId': student.id,
                    'studentName': f"{student.first_name} {student.last_name}",
                    'attendance': {}
                }
                for date_str in dates:
                    student_data['attendance'][date_str] = attendance_by_date[date_str].get(student.id, 'A')
                student_attendance.append(student_data)
            
            print(f"DEBUG: Returning {len(student_attendance)} students with attendance")
            return jsonify({
                'dates': dates,
                'students': student_attendance
            })
    except Exception as e:
        print(f"ERROR in get_class_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/api/student/<string:student_id>/attendance', methods=['GET'])
@login_required
@instructor_required
def get_student_attendance(student_id):
    print(f"[BACKEND LOG] get_student_attendance called for student {student_id}")

    # Get class ID from request
    class_id = request.args.get('class_id')
    if not class_id:
        print("[BACKEND LOG] get_student_attendance: Class ID is required")
        return jsonify({'success': False, 'message': 'Class ID is required'}), 400
    
    # Get month from request, default to current month
    month_str = request.args.get('month')
    
    if month_str:
        try:
            month_date = datetime.datetime.strptime(month_str, '%Y-%m')
            year = month_date.year
            month = month_date.month
            print(f"[BACKEND LOG] get_student_attendance: Using month from request: {year}-{month}")
        except ValueError:
            today = date.today()
            year = today.year
            month = today.month
            print(f"[BACKEND LOG] get_student_attendance: Invalid month format ({month_str}), defaulting to current month: {year}-{month}")
    else:
        today = date.today()
        year = today.year
        month = today.month
        print(f"[BACKEND LOG] get_student_attendance: No month provided, defaulting to current month: {year}-{month}")
    
    # Get all attendance records for this student in this class for the given month
    first_day = date(year, month, 1)
    _, last_day_num = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_num)
    
    print(f"[BACKEND LOG] get_student_attendance: Fetching records for student {student_id}, class {class_id} between {first_day} and {last_day}")

    # We need to filter by class_session_id dates within the range for this class
    # First, find the class sessions within the date range for this class
    class_sessions_in_month = ClassSession.query.filter(
        ClassSession.class_id == class_id,
        ClassSession.date >= first_day,
        ClassSession.date <= last_day
    ).all()
    
    session_ids_in_month = [session.id for session in class_sessions_in_month]
    print(f"[BACKEND LOG] get_student_attendance: Found {len(session_ids_in_month)} class sessions in month with IDs: {session_ids_in_month}")

    # Then, filter attendance records by these session IDs and the student ID
    attendance_records = AttendanceRecord.query.filter(
        AttendanceRecord.class_session_id.in_(session_ids_in_month),
        AttendanceRecord.student_id == student_id
    ).order_by(AttendanceRecord.date.asc()).all()
    
    print(f"[BACKEND LOG] get_student_attendance: Found {len(attendance_records)} attendance records for student {student_id} in sessions.")

    # Get the class and student information
    cls = Class.query.get(class_id)
    student = Student.query.get(student_id)
    
    if not cls or not student:
        print(f"[BACKEND LOG] get_student_attendance: Class ({class_id}) or student ({student_id}) not found")
        return jsonify({'success': False, 'message': 'Class or student not found'}), 404
    
    # Check if the class belongs to the instructor (or if user is admin)
    if current_user.role == 'instructor':
        if cls.instructor_id != current_user.id:
             print(f"[BACKEND LOG] get_student_attendance: Instructor {current_user.id} not authorized for class {class_id}")
             return jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403
    elif current_user.role != 'admin':
         print(f"[BACKEND LOG] get_student_attendance: User {current_user.id} is not admin or authorized instructor")
         return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    # Check if student is enrolled in this class (optional but good practice)
    enrollment = Enrollment.query.filter_by(class_id=class_id, student_id=student_id).first()
    if not enrollment:
        print(f"[BACKEND LOG] get_student_attendance: Student {student_id} not enrolled in class {class_id}")
        return jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 404 # Using 404 as student not found in class
    
    # Generate all dates in the month based on class schedule and available class sessions
    # This should now iterate through the actual class sessions found
    class_dates_in_month = sorted([session.date for session in class_sessions_in_month])
    print(f"[BACKEND LOG] get_student_attendance: Scheduled class dates in month: {class_dates_in_month}")

    # Format attendance records for easy lookup by date
    attendance_lookup = {}
    for record in attendance_records:
        # Find the corresponding class session to get the date
        session = next((s for s in class_sessions_in_month if s.id == record.class_session_id), None)
        if session:
            formatted_date = session.date.strftime('%B %d %Y') # Match frontend format
            attendance_lookup[formatted_date] = {
                'status': record.status,
                'attendance_id': record.id # Include attendance ID
            }
            print(f"[BACKEND LOG] get_student_attendance: Added record to lookup: {formatted_date}: {attendance_lookup[formatted_date]}")

    # Create attendance list for all *scheduled* class dates in the month
    # Include attendance status, defaulting to 'Absent' if no record exists for that date
    attendance_list = []
    present_count = 0
    absent_count = 0
    late_count = 0
    
    for class_date in class_dates_in_month:
        formatted_date = class_date.strftime('%B %d %Y') # Match frontend format
        record_data = attendance_lookup.get(formatted_date);
        
        if record_data:
            status = record_data['status']
            attendance_id = record_data['attendance_id']
            print(f"[BACKEND LOG] get_student_attendance: Found attendance for {formatted_date}: {status}")
        else:
            # If no record exists for a scheduled class date, consider the student Absent by default
            status = 'Absent'
            attendance_id = None # No attendance ID as no record exists
            print(f"[BACKEND LOG] get_student_attendance: No attendance found for {formatted_date}, defaulting to Absent")
            
        attendance_list.append({
            'date': formatted_date,
            'status': status,
            'attendance_id': attendance_id
        })
        
        # Increment counters based on the determined status for this date
        print(f"[BACKEND LOG] get_student_attendance: Status for {formatted_date} before counter increment: {status}") # Added logging
        if status == 'Present':
            present_count += 1
        elif status == 'Absent':
            absent_count += 1
        elif status == 'Late':
            late_count += 1

    print(f"[BACKEND LOG] get_student_attendance: Final counts - Present: {present_count}, Absent: {absent_count}, Late: {late_count}")
    print(f"[BACKEND LOG] get_student_attendance: Returning attendance list with {len(attendance_list)} entries.")

    return jsonify({
        'success': True,
        'studentName': f"{student.first_name} {student.last_name}",
        'className': cls.description,
        'classCode': cls.class_code,
        'month': calendar.month_name[month],
        'year': year,
        'presentCount': present_count, # Ensure these are included and correctly calculated
        'absentCount': absent_count,   # Ensure these are included and correctly calculated
        'lateCount': late_count,       # Ensure these are included and correctly calculated
        'attendance': attendance_list # This is the list of daily attendance records
    })

@attendance_bp.route('/api/attendance/<class_id>/<student_id>/<date>', methods=['PUT'])
@login_required
def update_attendance(class_id, student_id, date):
    data = request.get_json()

    if not data or 'status' not in data:
        return jsonify({'success': False, 'message': 'Missing status field'}), 400

    # Parse the date string from URL
    try:
        attendance_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400
    
    # Find existing attendance record
    attendance = AttendanceRecord.query.filter_by(
        class_id=class_id,
        student_id=student_id,
        date=attendance_date
    ).first()

    if attendance:
        # Update existing record
        attendance.status = data['status']
        attendance.marked_by = current_user.id
        attendance.marked_at = pst_now_naive()
    else:
        # Create new record
        attendance = AttendanceRecord(
            class_id=class_id,
            student_id=student_id,
            date=attendance_date,
            status=data['status'],
            marked_by=current_user.id,
            marked_at=pst_now_naive()
        )
        db.session.add(attendance)
    
    try:
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Attendance updated successfully',
            'attendance': {
                'id': attendance.id,
                'classId': attendance.class_id,
                'studentId': attendance.student_id,
                'date': attendance_date.strftime('%B %d %Y'),
                'status': attendance.status
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@attendance_bp.route('/api/bulk-update', methods=['POST'])
@login_required
def bulk_update_attendance():
    data = request.get_json()
    
    if not data or 'records' not in data:
        return jsonify({'success': False, 'message': 'Missing attendance records'}), 400
    
    try:
        for record in data['records']:
            # Validate required fields for each record
            required_fields_record = ['classId', 'studentId', 'date', 'status']
            if not all(key in record and record[key] for key in required_fields_record):
                 # Skip this record or return an error? Returning an error is safer.
                 return jsonify({'success': False, 'message': 'Missing or empty required field in one or more attendance records.'}), 400

            # Check if the class belongs to the instructor (or if user is admin)
            if current_user.role == 'instructor':
                class_obj = Class.query.filter_by(id=record['classId'], instructor_id=current_user.id).first()
                if not class_obj:
                     return jsonify({'success': False, 'message': f'Class ID {record["classId"]} not found or not authorized for one or more records.'}), 403
            elif current_user.role != 'admin':
                 return jsonify({'success': False, 'message': 'Unauthorized to perform bulk attendance update.'}), 403

            # Check if student is enrolled in the class
            enrollment = Enrollment.query.filter_by(student_id=record['studentId'], class_id=record['classId']).first()
            if not enrollment:
                 return jsonify({'success': False, 'message': f'Student ID {record["studentId"]} not enrolled in Class ID {record["classId"]} for one or more records.'}), 400

            # Parse the date
            try:
                attendance_date = datetime.datetime.strptime(record['date'], '%Y-%m-%d').date()
            except ValueError:
                try:
                    attendance_date = datetime.datetime.strptime(record['date'], '%B %d %Y').date()
                except ValueError:
                    continue
            
            # Find existing record
            attendance = AttendanceRecord.query.filter_by(
                class_id=record['classId'],
                student_id=record['studentId'],
                date=attendance_date
            ).first()
            
            if attendance:
                # Update existing record
                attendance.status = record['status']
                attendance.marked_by = current_user.id
                attendance.marked_at = pst_now_naive()
            else:
                # Create new record
                attendance = AttendanceRecord(
                    class_id=record['classId'],
                    student_id=record['studentId'],
                    date=attendance_date,
                    status=record['status'],
                    marked_by=current_user.id,
                    marked_at=pst_now_naive()
                )
                db.session.add(attendance)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attendance records updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@attendance_bp.route('/manual', methods=['POST'])
@login_required
@instructor_required
def add_manual_attendance():
    try:
        data = request.get_json();
        print(f"[BACKEND LOG] add_manual_attendance received data: {data}") # Added logging

        if not data:
            print("[BACKEND LOG] add_manual_attendance: No data provided") # Added logging
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['student_id', 'class_id', 'date', 'status']
        if not all(field in data for field in required_fields):
            print(f"[BACKEND LOG] add_manual_attendance: Missing required fields in data: {data}") # Added logging
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate date is not in the future
        try:
            attendance_date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
            if attendance_date > get_pst_now().date():
                print(f"[BACKEND LOG] add_manual_attendance: Future date provided: {data['date']}") # Added logging
                return jsonify({'error': 'Cannot add attendance for future dates'}), 400
        except ValueError:
            print(f"[BACKEND LOG] add_manual_attendance: Invalid date format: {data['date']}") # Added logging
            return jsonify({'error': 'Invalid date format'}), 400
        
        # Check if class belongs to the instructor
        class_obj = Class.query.filter_by(id=data['class_id'], instructor_id=current_user.id).first()
        if not class_obj:
            print(f"[BACKEND LOG] add_manual_attendance: Class not found or not authorized. Class ID: {data.get('class_id')}, Instructor ID: {current_user.id}") # Added logging
            return jsonify({'error': 'Class not found or not authorized'}), 403
        
        # Check if student is enrolled in the class
        enrollment = Enrollment.query.filter_by(student_id=data['student_id'], class_id=data['class_id']).first()
        if not enrollment:
            print(f"[BACKEND LOG] add_manual_attendance: Student not enrolled in class. Student ID: {data.get('student_id')}, Class ID: {data.get('class_id')}") # Added logging
            return jsonify({'error': 'Student not enrolled in this class'}), 400
        
        # Get or create class session for this date
        class_session = ClassSession.query.filter_by(
            class_id=data['class_id'],
            date=attendance_date
        ).first()
        
        if not class_session:
            print(f"[BACKEND LOG] add_manual_attendance: No class session found for {data['date']}, creating one.") # Added logging
            # Create new class session
            now = pst_now_naive()
            # Assuming a default time if not provided. Adjust as needed.
            scheduled_start_time = datetime.time(hour=9, minute=0)
            try:
                 # Attempt to parse time from class schedule if available
                 # This is a basic attempt, might need more sophisticated parsing
                 schedule_parts = class_obj.schedule.split()
                 if len(schedule_parts) > 1:
                      time_str = schedule_parts[-1] # Assuming time is the last part
                      # Basic regex to find HH:MM format, handles AM/PM if present
                      import re
                      time_match = re.search(r'\d{1,2}:\d{2}(?:[ ]?(?:AM|PM))?', class_obj.schedule, re.IGNORECASE)
                      if time_match:
                           time_obj = datetime.datetime.strptime(time_match.group(0), '%I:%M %p').time() if 'AM' in time_match.group(0).upper() or 'PM' in time_match.group(0).upper() else datetime.datetime.strptime(time_match.group(0), '%H:%M').time()
                           scheduled_start_time = time_obj
                           print(f"[BACKEND LOG] add_manual_attendance: Parsed scheduled time {scheduled_start_time} from schedule {class_obj.schedule}") # Added logging
                      else:
                           print(f"[BACKEND LOG] add_manual_attendance: Could not parse time from schedule {class_obj.schedule}, using default") # Added logging

            except Exception as e:
                 print(f"[BACKEND LOG] add_manual_attendance: Error parsing schedule time: {e}, using default.") # Added logging
                 pass # Use default time if parsing fails

            class_session = ClassSession(
                class_id=data['class_id'],
                instructor_id=current_user.id,
                date=attendance_date,
                # Use current time for actual start time if manual, or scheduled
                start_time=datetime.datetime.combine(attendance_date, get_pst_now().time()),  # Use current time or scheduled?
                scheduled_start_time=datetime.datetime.combine(attendance_date, scheduled_start_time),  # Store as datetime
                is_attendance_processed=False,
                # Manual attendance: default to the class room number if available
                session_room_number=getattr(class_obj, 'room_number', None)
            )
            db.session.add(class_session)
            db.session.flush()  # Get the ID of the new session
            print(f"[BACKEND LOG] add_manual_attendance: Created new class session with ID {class_session.id}") # Added logging
            
            # Don't automatically create ABSENT records - let manual marking create them as needed
            # This prevents students from being marked absent before they have a chance to check in
        else:
            print(f"[BACKEND LOG] add_manual_attendance: Found existing class session with ID {class_session.id} for {data['date']}") # Added logging
        
        # Check for existing attendance record using class_session_id and student_id
        existing_attendance = AttendanceRecord.query.filter_by(
            class_session_id=class_session.id,
            student_id=data['student_id']
        ).first()
        
        if existing_attendance:
            # Update existing record instead of creating duplicate
            existing_attendance.status = AttendanceStatus[data['status'].upper()]
            existing_attendance.time_in = pst_now_naive() if data['status'].upper() == 'PRESENT' else existing_attendance.time_in
            # Removed time_out update - time_out functionality removed
            db.session.commit()
            print(f"[BACKEND LOG] add_manual_attendance: Updated existing attendance record for student {data['student_id']} in session {class_session.id}") # Added logging
            return jsonify({
                'success': True,
                'message': 'Attendance record updated successfully',
                'attendance': {
                    'id': existing_attendance.id,
                    'student_id': existing_attendance.student_id,
                    'class_session_id': existing_attendance.class_session_id,
                    'date': attendance_date.strftime('%Y-%m-%d'),
                    'status': existing_attendance.status.value if existing_attendance.status else 'Absent'
                }
            }), 200
        
        # Create new attendance record (fallback, though we create defaults now)
        new_attendance = AttendanceRecord(
            class_session_id=class_session.id,
            student_id=data['student_id'],
            status=AttendanceStatus[data['status'].upper()],
            date=pst_now_naive()
        )
        db.session.add(new_attendance)
        db.session.commit()
        print(f"[BACKEND LOG] add_manual_attendance: Successfully added new attendance record with ID {new_attendance.id}") # Added logging
        return jsonify({
            'success': True,
            'message': 'Attendance record added successfully',
            'attendance': {
                'id': new_attendance.id,
                'student_id': new_attendance.student_id,
                'class_session_id': new_attendance.class_session_id,
                'date': attendance_date.strftime('%Y-%m-%d'),
                'status': new_attendance.status.value if new_attendance.status else 'Absent'  # Convert enum to string value
            }
        }), 201
            
    except Exception as e:
        print(f"[BACKEND LOG] add_manual_attendance: Unexpected error: {e}", exc_info=True) # Added logging
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/update', methods=['PUT'])
@login_required
def update_manual_attendance():
    try:
        data = request.get_json()
        print(f"[BACKEND LOG] update_manual_attendance received data: {data}")  # Added logging
        
        # Validate required fields
        required_fields = ['student_id', 'class_id', 'date', 'status']
        for field in required_fields:
            if field not in data or not data[field]:
                print(f"[BACKEND LOG] update_manual_attendance: Missing required field: {field}")  # Added logging
                return jsonify({'success': False, 'message': f'Missing or empty required field: {field}'}), 400

        student_id = data['student_id']
        class_id = data['class_id']
        date_str = data['date']
        status_str = data['status']

        # Convert date string to date object
        try:
            attendance_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError as e:
            print(f"[BACKEND LOG] update_manual_attendance: Invalid date format: {date_str}")  # Added logging
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400

        # Check if class belongs to the instructor (or if user is admin)
        if current_user.role == 'instructor':
            class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
            if not class_obj:
                print(f"[BACKEND LOG] update_manual_attendance: Class {class_id} not found or not authorized for instructor {current_user.id}")  # Added logging
                return jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403
        elif current_user.role != 'admin':
            print(f"[BACKEND LOG] update_manual_attendance: Unauthorized access attempt by user {current_user.id} with role {current_user.role}")  # Added logging
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        # Check if student is enrolled in the class
        enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
        if not enrollment:
            print(f"[BACKEND LOG] update_manual_attendance: Student {student_id} not enrolled in class {class_id}")  # Added logging
            return jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 400

        # Find the class session for this date
        class_session = ClassSession.query.filter_by(
            class_id=class_id,
            date=attendance_date
        ).first()

        print(f"[BACKEND LOG] update_manual_attendance: Looking for class session: class_id={class_id}, date={attendance_date}")  # Added logging
        
        if not class_session:
            print(f"[BACKEND LOG] update_manual_attendance: No class session found for class {class_id} on {attendance_date}")  # Added logging
            return jsonify({'success': False, 'message': 'No class session found for this date'}), 404

        # Find the attendance record
        attendance_record = AttendanceRecord.query.filter_by(
            class_session_id=class_session.id,
            student_id=student_id
        ).first()

        print(f"[BACKEND LOG] update_manual_attendance: Looking for attendance record: session_id={class_session.id}, student_id={student_id}")  # Added logging
        
        if not attendance_record:
            print(f"[BACKEND LOG] update_manual_attendance: No attendance record found for student {student_id} in class {class_id} on {attendance_date}")  # Added logging
            return jsonify({'success': False, 'message': 'No attendance record found'}), 404

        try:
            # Convert status string to enum value
            status_enum = AttendanceStatus[status_str.upper()]
            attendance_record.status = status_enum
            attendance_record.updated_at = pst_now_naive()
            
            db.session.commit()
            print(f"[BACKEND LOG] update_manual_attendance: Successfully updated attendance record for student {student_id} in class {class_id}")  # Added logging
            return jsonify({'success': True, 'message': 'Attendance record updated successfully'})
        except Exception as e:
            db.session.rollback()
            print(f"[BACKEND LOG] update_manual_attendance: Database error: {str(e)}")  # Added logging
            return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500

    except Exception as e:
        db.session.rollback()
        print(f"[BACKEND LOG] update_manual_attendance: Unexpected error: {str(e)}")  # Added logging
        return jsonify({'success': False, 'message': str(e)}), 500

@attendance_bp.route('/api/instructor/update', methods=['POST'])
@login_required
@admin_required
def update_instructor_attendance():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    class_id = data.get('classId')
    instructor_name = data.get('instructorName')
    date_str = data.get('date')
    status = data.get('status')
    time_in = data.get('timeIn')
    # Removed time_out parsing - time_out functionality removed
    
    if not all([class_id, instructor_name, date_str]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    try:
        attendance_date = datetime.datetime.strptime(date_str, '%B %d, %Y').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400
    
    # Find the instructor by name
    name_parts = instructor_name.split(' ', 1)
    if len(name_parts) != 2:
        return jsonify({'success': False, 'message': 'Invalid instructor name format'}), 400
    
    first_name, last_name = name_parts
    instructor = User.query.filter_by(first_name=first_name, last_name=last_name, role='instructor').first()
    if not instructor:
        return jsonify({'success': False, 'message': 'Instructor not found'}), 404
    
    # Check if class exists
    class_obj = Class.query.get(class_id)
    if not class_obj:
        return jsonify({'success': False, 'message': 'Class not found'}), 404
    
    # Find or create attendance record
    attendance = InstructorAttendance.query.filter_by(
        instructor_id=instructor.id,
        class_id=class_id,
        date=attendance_date
    ).first()
    
    if attendance:
        if status:
            attendance.status = status
        if time_in:
            attendance.time_in = datetime.datetime.combine(attendance_date, datetime.datetime.strptime(time_in, '%H:%M').time())
        # Removed time_out update - time_out functionality removed
    else:
        time_in_dt = None
        # Removed time_out_dt - time_out functionality removed
        if time_in:
            time_in_dt = datetime.datetime.combine(attendance_date, datetime.datetime.strptime(time_in, '%H:%M').time())
        # Removed time_out_dt assignment - time_out functionality removed
        
        attendance = InstructorAttendance(
            instructor_id=instructor.id,
            class_id=class_id,
            date=attendance_date,
            status=status or 'Present',
            time_in=time_in_dt
            # Removed time_out - time_out functionality removed
        )
        db.session.add(attendance)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attendance updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@attendance_bp.route('/api/instructor/get', methods=['GET'])
@login_required
@admin_required
def get_instructor_attendance():
    class_id = request.args.get('classId')
    
    if not class_id:
        return jsonify({'success': False, 'message': 'Missing classId'}), 400
    
    # Get the instructor for the class
    class_obj = Class.query.get(class_id)
    if not class_obj or not class_obj.instructor_id:
        return jsonify([]), 200
    
    instructor_id = class_obj.instructor_id
    
    # Get all attendance records for this instructor and class
    attendance_records = InstructorAttendance.query.filter_by(
        instructor_id=instructor_id,
        class_id=class_id
    ).order_by(InstructorAttendance.date.desc()).all()
    
    attendance_data = []
    for attendance in attendance_records:
        attendance_data.append({
            'date': attendance.date.strftime('%B %d, %Y'),
            'status': attendance.status,
            'time_in': attendance.time_in.strftime('%I:%M %p') if attendance.time_in else None,
            'time_out': attendance.time_out.strftime('%I:%M %p') if attendance.time_out else None
        })
    
    return jsonify(attendance_data)
