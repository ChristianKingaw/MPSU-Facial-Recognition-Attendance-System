from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from utils.timezone import get_pst_now, pst_now_naive
import calendar

from sqlalchemy.orm import joinedload
from extensions import db
from decorators import admin_required
from exceptions import AttendanceValidationError
import json
from models import User, Class, Student, Enrollment, AttendanceRecord, InstructorAttendance, AttendanceLog, FaceEncoding, InstructorFaceEncoding, VerificationCode, ClassSession, SystemSettings
from utils.system_settings_helper import (
    DEFAULT_ROOM_NUMBERS,
    load_room_numbers,
    normalize_room_numbers_payload,
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/instructors/attendance', methods=['GET'])
@login_required
def instructor_attendance():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Get current system settings for semester and school year
    from models import SystemSettings
    semester_setting = SystemSettings.query.filter_by(key='semester').first()
    school_year_setting = SystemSettings.query.filter_by(key='school_year').first()
    
    current_semester = semester_setting.value if semester_setting else '1st semester'
    current_school_year = school_year_setting.value if school_year_setting else '2025-2026'
    
    return render_template('admin/instructor_attendance.html', current_semester=current_semester, current_school_year=current_school_year)

@admin_bp.route('/api/instructors', methods=['GET'])
@login_required
def get_instructors():
    # Only allow admin to access
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Get all instructors sorted alphabetically by last name, then first name
    instructors = User.query.filter_by(role='instructor').order_by(User.last_name, User.first_name).all()
    
    instructor_list = []
    for instructor in instructors:
        # Count classes assigned to this instructor
        classes_count = Class.query.filter_by(instructor_id=instructor.id).count()
        
        # Calculate attendance rate for current month
        today = date.today()
        first_day = date(today.year, today.month, 1)
        _, last_day_num = calendar.monthrange(today.year, today.month)
        last_day = date(today.year, today.month, last_day_num)
        
        # Get attendance records for this month
        attendance_records = InstructorAttendance.query.filter(
            InstructorAttendance.instructor_id == instructor.id,
            InstructorAttendance.date >= first_day,
            InstructorAttendance.date <= last_day
        ).all()
        
        # Calculate attendance rate
        total_days = len(attendance_records)
        present_days = sum(1 for record in attendance_records if record.status == 'Present')
        attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
        
        instructor_list.append({
            'id': instructor.id,
            'name': f"{instructor.last_name}, {instructor.first_name}",
            'email': instructor.email,
            'classesCount': classes_count,
            'attendanceRate': round(attendance_rate, 1)
        })
    
    return jsonify(instructor_list)

@admin_bp.route('/api/instructors', methods=['POST'])
@login_required
@admin_required
def create_instructor_api():
    """API endpoint to create a new instructor (Admin only)."""
    data = request.get_json()

    # Basic validation
    required_fields = ['username', 'email', 'first_name', 'last_name', 'password']
    if not data:
        return jsonify({'success': False, 'message': 'No input data provided for instructor creation'}), 400
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'success': False, 'message': f'Missing or empty required field: {field}'}), 400

    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'message': 'Username already exists.'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'message': 'Email address already registered.'}), 400

    try:
        # Create new instructor
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            role='instructor',  # Force role to be instructor
            created_at=pst_now_naive()
        )
        user.set_password(data['password'])

        db.session.add(user)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Instructor created successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating instructor: {str(e)}'}), 500

@admin_bp.route('/api/instructors/<int:instructor_id>', methods=['GET'])
@login_required
@admin_required
def get_instructor_details(instructor_id):
    # Get instructor details
    instructor = User.query.get(instructor_id)
    if not instructor or instructor.role != 'instructor':
        return jsonify({'success': False, 'message': 'Instructor not found'}), 404
    
    # Get classes assigned to this instructor
    classes = Class.query.filter_by(instructor_id=instructor.id).all()
    class_list = [{
        'id': cls.id,
        'code': cls.class_code,
        'description': cls.description,
        'schedule': cls.schedule,
        'roomNumber': cls.room_number
    } for cls in classes]
    
    # Get current year's attendance data
    current_year = date.today().year
    attendance_data = {}
    
    for month in range(1, 13):
        first_day = date(current_year, month, 1)
        _, last_day_num = calendar.monthrange(current_year, month)
        last_day = date(current_year, month, last_day_num)
        
        # Get attendance records for this month
        records = InstructorAttendance.query.filter(
            InstructorAttendance.instructor_id == instructor_id,
            InstructorAttendance.date >= first_day,
            InstructorAttendance.date <= last_day
        ).all()
        
        # Calculate working days in the month (including scheduled weekend classes)
        working_days = 0
        current_day = first_day
        while current_day <= last_day:
            if current_day.weekday() < 5:  # Weekdays (0-4)
                working_days += 1
            else:  # Weekend (5-6)
                # Check if there are any classes scheduled for this weekend day
                day_abbr = 'S' if current_day.weekday() == 5 else 'U'
                has_weekend_classes = False
                
                # Check all classes assigned to this instructor
                for cls in classes:
                    schedule_parts = cls.schedule.split(',')
                    if any(day_abbr in slot.split()[0] for slot in schedule_parts):
                        has_weekend_classes = True
                        break
                
                if has_weekend_classes:
                    working_days += 1
            
            current_day += timedelta(days=1)
        
        # Only include months that have records or are in the past
        if records or (current_year < date.today().year or (current_year == date.today().year and month <= date.today().month)):
            # Count attendance by status
            status_counts = {
                'Present': 0,
                'Absent': 0,
                'Late': 0,
                'On Leave': 0
            }
            for record in records:
                status_counts[record.status] += 1
            
            # Calculate attendance rate based on working days
            total_records = sum(status_counts.values())
            if working_days > 0:
                attendance_rate = (status_counts['Present'] / working_days) * 100
            else:
                attendance_rate = 0
            
            attendance_data[calendar.month_name[month]] = {
                'counts': status_counts,
                'working_days': working_days,
                'attendance_rate': round(attendance_rate, 1)
            }
    
    return jsonify({
        'success': True,
        'name': f"{instructor.first_name} {instructor.last_name}",
        'email': instructor.email,
        'taught_classes': class_list,
        'attendance': attendance_data
    })

def validate_attendance_data(instructor_id, date, status, class_id=None):
    """Centralized validation for attendance data"""
    # Validate instructor
    instructor = User.query.get(instructor_id)
    if not instructor or instructor.role != 'instructor':
        return False, "Invalid instructor ID"
    
    # Validate date
    try:
        attendance_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return False, "Invalid date format"
    
    if attendance_date > get_pst_now().date():
        return False, "Cannot mark attendance for future dates"
    
    if attendance_date < datetime(2020, 1, 1).date():
        return False, "Cannot mark attendance before 2020"
    
    # Validate status
    valid_statuses = {'Present', 'Absent', 'Late', 'On Leave'}
    if status not in valid_statuses:
        return False, "Invalid status"
    
    # Check for weekend classes if applicable
    if attendance_date.weekday() >= 5:  # Saturday or Sunday
        if class_id:
            class_obj = Class.query.get(class_id)
            if not class_obj:
                return False, "Invalid class ID"
            
            # Check if class is scheduled for this weekend day
            schedule = class_obj.schedule
            if not schedule:
                return False, "No schedule found for this class"
            
            # Parse schedule to check for weekend classes
            schedule_days = set(schedule.split(','))
            if attendance_date.weekday() == 5 and 'S' not in schedule_days:
                return False, "No classes scheduled for Saturday"
            if attendance_date.weekday() == 6 and 'U' not in schedule_days:
                return False, "No classes scheduled for Sunday"
        else:
            return False, "Class ID required for weekend attendance"
    
    return True, None

@admin_bp.route('/api/instructors/attendance', methods=['POST'])
@login_required
def mark_attendance():
    """Mark instructor attendance"""
    try:
        data = request.get_json()
        instructor_id = data.get('instructorId')
        class_id = data.get('classId')
        date = data.get('date')
        status = data.get('status')
        notes = data.get('notes', '')

        # Validate required fields
        if not all([instructor_id, date, status]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400

        # Check if instructor exists
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            return jsonify({
                'success': False,
                'message': 'Instructor not found'
            }), 404

        # Check if class exists if class_id is provided
        if class_id:
            class_record = Class.query.get(class_id)
            if not class_record:
                return jsonify({
                    'success': False,
                    'message': 'Class not found'
                }), 404

        # Check for existing attendance record
        # Use IS NOT DISTINCT FROM to handle NULL values correctly
        existing_attendance = db.session.query(InstructorAttendance).filter(
            InstructorAttendance.instructor_id == instructor_id,
            InstructorAttendance.date == date,
            InstructorAttendance.class_id.is_(None) if class_id is None else InstructorAttendance.class_id == class_id
        ).first()

        if existing_attendance:
            # Update existing record
            existing_attendance.status = status
            existing_attendance.notes = notes
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Attendance record updated successfully',
                'data': {
                    'id': existing_attendance.id,
                    'instructor_id': existing_attendance.instructor_id,
                    'class_id': existing_attendance.class_id,
                    'date': existing_attendance.date.isoformat(),
                    'status': existing_attendance.status,
                    'notes': existing_attendance.notes,
                    'created_at': existing_attendance.created_at.isoformat()
                }
            })
        else:
            # Create new attendance record
            attendance = InstructorAttendance(
                instructor_id=instructor_id,
                class_id=class_id,
                date=date,
                status=status,
                notes=notes
            )
            db.session.add(attendance)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Attendance marked successfully',
                'data': {
                    'id': attendance.id,
                    'instructor_id': attendance.instructor_id,
                    'class_id': attendance.class_id,
                    'date': attendance.date.isoformat(),
                    'status': attendance.status,
                    'notes': attendance.notes,
                    'created_at': attendance.created_at.isoformat()
                }
            })

    except Exception as e:
        db.session.rollback()
        print(f"Error marking attendance: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error marking attendance: {str(e)}'
        }), 500

@admin_bp.route('/api/instructors/<int:instructor_id>/attendance/report', methods=['GET'])
def get_attendance_report(instructor_id):
    try:
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
        
        report = AttendanceRecord.get_attendance_report(instructor_id, start_date, end_date)
        
        return jsonify({
            'success': True,
            'report': report
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': 'Invalid date format'
        }), 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error generating report'
        }), 500

@admin_bp.route('/api/instructors/<int:instructor_id>', methods=['PUT'])
@login_required
@admin_required
def update_instructor_api(instructor_id):
    """API endpoint to update an instructor (Admin only)."""
    instructor = User.query.get_or_404(instructor_id)

    data = request.get_json();

    # Basic validation - allow partial updates, but check types/formats if provided
    if not data:
        return jsonify({'success': False, 'message': 'No input data provided for instructor update'}), 400

    # Handle username update separately with unique check
    if 'username' in data:
        if not data['username']:
            return jsonify({'success': False, 'message': 'Username cannot be empty.'}), 400
        if data['username'] != instructor.username and User.query.filter_by(username=data['username']).first():
            return jsonify({'success': False, 'message': 'Username is already taken.'}), 400
        instructor.username = data['username']

    # Handle email update separately with unique check
    if 'email' in data:
        if not data['email']:
            return jsonify({'success': False, 'message': 'Email cannot be empty.'}), 400
        # Basic email format check (more robust validation is in forms, but good to have a basic check here)
        import re
        if not re.match(r'[^@]+@[^\.]+\..+', data['email']):
             return jsonify({'success': False, 'message': 'Invalid email format.'}), 400
        if data['email'] != instructor.email and User.query.filter_by(email=data['email']).first():
             return jsonify({'success': False, 'message': 'Email address already registered.'}), 400
        instructor.email = data['email']

    # Update other fields if provided and not empty
    if 'first_name' in data and data['first_name']: instructor.first_name = data['first_name']
    if 'last_name' in data and data['last_name']: instructor.last_name = data['last_name']

    # Update password if provided and not empty
    if 'password' in data and data['password']:
        instructor.set_password(data['password'])

    # Role cannot be changed via this endpoint for safety; requires separate admin logic if needed

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Instructor updated successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating instructor: {str(e)}'}), 500

@admin_bp.route('/api/instructors/<int:instructor_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_instructor_api(instructor_id):
    """API endpoint to delete an instructor (Admin only)."""
    instructor = User.query.get_or_404(instructor_id)

    # Don't allow deleting own account
    if instructor.id == current_user.id:
        return jsonify({'success': False, 'message': 'You cannot delete your own account.'}), 400

    # Check if instructor has classes
    if instructor.classes:
        return jsonify({'success': False, 'message': 'Cannot delete instructor with assigned classes.'}), 400

    # Block deletion if instructor has attendance records (to preserve audit trail)
    if InstructorAttendance.query.filter_by(instructor_id=instructor_id).first():
        return jsonify({'success': False, 'message': 'Cannot delete instructor with attendance records. Please delete attendance records first.'}), 400

    instructor_name = f"{instructor.first_name} {instructor.last_name}"

    try:
        # 1) Delete all associated instructor face encodings
        InstructorFaceEncoding.query.filter_by(instructor_id=instructor_id).delete(synchronize_session=False)

        # 2) Delete any verification codes tied to this user
        VerificationCode.query.filter_by(user_id=instructor_id).delete(synchronize_session=False)

        # 3) Null out any references in class sessions pointing to this instructor
        ClassSession.query.filter_by(instructor_id=instructor_id).update({ClassSession.instructor_id: None}, synchronize_session=False)

        # 4) Null out any attendance records "marked_by" this instructor
        AttendanceRecord.query.filter_by(marked_by=instructor_id).update({AttendanceRecord.marked_by: None}, synchronize_session=False)

        # 5) Finally, delete the instructor
        db.session.delete(instructor)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Instructor "{instructor_name}" deleted successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting instructor: {str(e)}'}), 500

@admin_bp.route('/api/instructors/attendance/export', methods=['GET'])
@login_required
@admin_required
def export_attendance():
    # Get date range from query parameters
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    
    if not date_from or not date_to:
        return jsonify({'success': False, 'message': 'Date range is required'}), 400
    
    try:
        # Parse dates
        from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        # Validate date range
        if from_date > to_date:
            return jsonify({'success': False, 'message': 'Invalid date range'}), 400
            
        if (to_date - from_date).days > 365:
            return jsonify({'success': False, 'message': 'Date range cannot exceed one year'}), 400
        
        # Get all attendance records for the date range
        records = InstructorAttendance.query.filter(
            InstructorAttendance.date >= from_date,
            InstructorAttendance.date <= to_date
        ).join(User, InstructorAttendance.instructor_id == User.id).all()
        
        # Format records for export
        export_data = []
        for record in records:
            instructor = User.query.get(record.instructor_id)
            class_name = record.class_ref.class_code if record.class_ref else 'General Attendance'
            
            export_data.append({
                'instructor_name': f"{instructor.first_name} {instructor.last_name}",
                'date': record.date.strftime('%Y-%m-%d'),
                'status': record.status,
                'class_name': class_name,
                'notes': record.notes or ''
            })
        
        return jsonify({'success': True, 'data': export_data})
        
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/api/instructors/<int:instructor_id>/attendance', methods=['GET'])
@login_required
@admin_required
def get_instructor_attendance_by_year(instructor_id):
    """Get attendance data for a specific instructor for a given year."""
    # Get instructor details
    instructor = User.query.get(instructor_id)
    if not instructor or instructor.role != 'instructor':
        return jsonify({'success': False, 'message': 'Instructor not found'}), 404
    
    # Get year from query parameters, default to current year
    try:
        year = int(request.args.get('year', date.today().year))
        if year < 1900 or year > 2100:
            return jsonify({'success': False, 'message': 'Invalid year'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid year format'}), 400
    
    # Get classes assigned to this instructor
    classes = Class.query.filter_by(instructor_id=instructor.id).all()
    class_list = [{
        'id': cls.id,
        'code': cls.class_code,
        'description': cls.description,
        'schedule': cls.schedule,
        'roomNumber': cls.room_number
    } for cls in classes]
    
    # Get attendance data for the year
    attendance_data = {}
    
    for month in range(1, 13):
        first_day = date(year, month, 1)
        _, last_day_num = calendar.monthrange(year, month)
        last_day = date(year, month, last_day_num)
        
        # Get attendance records for this month
        records = InstructorAttendance.query.filter(
            InstructorAttendance.instructor_id == instructor_id,
            InstructorAttendance.date >= first_day,
            InstructorAttendance.date <= last_day
        ).order_by(InstructorAttendance.date.asc()).all()
        
        # Calculate working days in the month (including scheduled weekend classes)
        working_days = 0
        current_day = first_day
        while current_day <= last_day:
            if current_day.weekday() < 5:  # Weekdays (0-4)
                working_days += 1
            else:  # Weekend (5-6)
                # Check if there are any classes scheduled for this weekend day
                day_abbr = 'S' if current_day.weekday() == 5 else 'U'
                has_weekend_classes = False
                
                # Check all classes assigned to this instructor
                for cls in classes:
                    schedule_parts = cls.schedule.split(',')
                    if any(day_abbr in slot.split()[0] for slot in schedule_parts):
                        has_weekend_classes = True
                        break
                
                if has_weekend_classes:
                    working_days += 1
            
            current_day += timedelta(days=1)
        
        # Only include months that have records or are in the past
        if records or (year < date.today().year or (year == date.today().year and month <= date.today().month)):
            # Count attendance by status
            status_counts = {
                'Present': 0,
                'Absent': 0,
                'Late': 0,
                'On Leave': 0
            }
            
            # Format records for the month
            month_records = []
            for record in records:
                status_counts[record.status] += 1
                if record.class_ref:
                    class_name = f"{record.class_ref.class_code} - {record.class_ref.description}"
                else:
                    class_name = 'General Attendance'
                month_records.append({
                    'id': record.id,
                    'date': record.date.strftime('%B %d %Y'),
                    'status': record.status,
                    'className': class_name,
                    'classId': record.class_id,
                    'notes': record.notes
                })
            
            # Calculate attendance rate based on working days
            total_records = sum(status_counts.values())
            if working_days > 0:
                attendance_rate = (status_counts['Present'] / working_days) * 100
            else:
                attendance_rate = 0
            
            attendance_data[calendar.month_name[month]] = {
                'counts': status_counts,
                'working_days': working_days,
                'attendance_rate': round(attendance_rate, 1),
                'records': month_records
            }
    
    return jsonify({
        'success': True,
        'instructor': {
            'id': instructor.id,
            'name': f"{instructor.first_name} {instructor.last_name}",
            'email': instructor.email
        },
        'taught_classes': class_list,
        'attendance': attendance_data
    })

@admin_bp.route('/api/instructors/attendance/<int:instructor_id>/<date>', methods=['PUT'])
@login_required
@admin_required
def update_attendance(instructor_id, date):
    print(f"Received PUT request for instructor {instructor_id} on date {date}")  # Debug log
    try:
        data = request.get_json()
        print("Received data:", data)  # Debug log
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
            
        status = data.get('status')
        notes = data.get('notes', '')
        class_id = data.get('classId')
        
        if not status:
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
            
        try:
            attendance_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        print(f"Looking for attendance record for instructor {instructor_id} on {attendance_date}")  # Debug log
        
        # Find any existing attendance record for this instructor and date
        existing_record = db.session.query(InstructorAttendance).filter(
            InstructorAttendance.instructor_id == instructor_id,
            InstructorAttendance.date == attendance_date
        ).first()
        
        if existing_record:
            print(f"Found existing record: {existing_record.id}")  # Debug log
            # Update the existing record
            existing_record.status = status
            existing_record.notes = notes
            existing_record.class_id = class_id
            record = existing_record
        else:
            print("No existing record, creating new one")  # Debug log
            # Create new record if none exist
            record = InstructorAttendance(
                instructor_id=instructor_id,
                date=attendance_date,
                status=status,
                notes=notes,
                class_id=class_id
            )
            db.session.add(record)
        
        # Save changes
        db.session.commit()
        print("Changes committed successfully")  # Debug log
        
        # Get class information for the response
        class_info = None
        if record.class_id:
            class_obj = Class.query.get(record.class_id)
            if class_obj:
                class_info = f"{class_obj.class_code} - {class_obj.description}"
        
        return jsonify({
            'success': True,
            'message': 'Attendance updated successfully',
            'record': {
                'id': record.id,
                'instructor_id': record.instructor_id,
                'class_id': record.class_id,
                'date': record.date.strftime('%Y-%m-%d'),
                'status': record.status,
                'notes': record.notes,
                'className': class_info if class_info else 'General Attendance',
                'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating attendance: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating attendance: {str(e)}'
        }), 500

@admin_bp.route('/api/instructors/attendance/<int:instructor_id>/<date>', methods=['DELETE'])
@login_required
def delete_attendance(instructor_id, date):
    """Delete an instructor attendance record"""
    try:
        # Parse the date
        try:
            attendance_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400

        # Find the attendance record
        record = InstructorAttendance.query.filter_by(
            instructor_id=instructor_id,
            date=attendance_date
        ).first()

        if not record:
            return jsonify({
                'success': False,
                'message': 'Attendance record not found'
            }), 404

        # Delete the record
        db.session.delete(record)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Attendance record deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting attendance: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error deleting attendance: {str(e)}'
        }), 500

@admin_bp.route('/api/instructors/<int:instructor_id>/attendance', methods=['DELETE'])
@login_required
@admin_required
def delete_all_instructor_attendance(instructor_id):
    """Delete all attendance records for a specific instructor"""
    try:
        instructor = User.query.get_or_404(instructor_id)
        # Delete all attendance records for this instructor
        deleted_count = 0
        records = InstructorAttendance.query.filter_by(instructor_id=instructor_id).all()
        for record in records:
            db.session.delete(record)
            deleted_count += 1
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} attendance record(s) for instructor {instructor.first_name} {instructor.last_name}.'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting attendance records: {str(e)}'}), 500

@admin_bp.route('/classes/<int:class_id>', methods=['GET'])
@login_required
@admin_required
def view_class(class_id):
    try:
        # Check if class exists
        cls = Class.query.get_or_404(class_id)
        
        # Get all students with their enrollment status
        all_students = Student.query.all()
        students_with_status = []
        for s in all_students:
            is_enrolled = Enrollment.query.filter_by(student_id=s.id, class_id=class_id).first() is not None
            students_with_status.append({
                'student': s,
                'is_enrolled': is_enrolled
            })
        
        students_count = len([s for s in students_with_status if not s['is_enrolled']])
        
        return render_template('admin/class_detail.html', **{'class': cls, 'students_with_status': students_with_status, 'students_count': students_count})
    except Exception as e:
        print(f"Error in view_class: {e}")
        return f"Error: {e}", 500

@admin_bp.route('/classes/<int:class_id>/enroll', methods=['POST'])
@login_required
@admin_required
def enroll_unenroll_students(class_id):
    try:
        # Check if class exists
        cls = Class.query.get_or_404(class_id)
        
        student_ids = request.form.getlist('student_ids')
        action = request.form.get('action')
        
        print(f"Action: {action}, Students: {student_ids}")
        
        if action == 'enroll':
            enrolled_count = 0
            for student_id in student_ids:
                # Check if already enrolled
                existing = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
                if not existing:
                    enrollment = Enrollment(student_id=student_id, class_id=class_id)
                    db.session.add(enrollment)
                    enrolled_count += 1
            db.session.commit()
            print(f"Committed {enrolled_count} enrollments")
            flash(f'Successfully enrolled {enrolled_count} student(s).', 'success')
        elif action == 'unenroll':
            unenrolled_count = 0
            for student_id in student_ids:
                enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
                if enrollment:
                    db.session.delete(enrollment)
                    unenrolled_count += 1
            db.session.commit()
            print(f"Committed {unenrolled_count} unenrollments")
            flash(f'Successfully unenrolled {unenrolled_count} student(s).', 'success')
        else:
            flash('Invalid action.', 'danger')
        
        return redirect(url_for('admin.view_class', class_id=class_id))
    except Exception as e:
        db.session.rollback()
        print(f"Error in enroll_unenroll_students: {e}")
        flash('An error occurred while processing the request.', 'danger')
        return redirect(url_for('admin.view_class', class_id=class_id))

# System Settings Routes
@admin_bp.route('/api/system-settings', methods=['GET'])
@login_required
def get_system_settings():
    if current_user.role not in ['admin', 'instructor']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    from models import SystemSettings
    settings = SystemSettings.query.all()
    settings_dict = {s.key: s.value for s in settings}
    raw_rooms = settings_dict.get('room_numbers') or settings_dict.get('room_number')
    room_list = load_room_numbers(
        raw_rooms,
        fallback=DEFAULT_ROOM_NUMBERS,
    )
    settings_dict['room_numbers_list'] = room_list
    if not settings_dict.get('room_numbers'):
        settings_dict['room_numbers'] = ','.join(room_list)
    return jsonify(settings_dict)

@admin_bp.route('/api/system-settings', methods=['POST'])
@login_required
def update_system_settings():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    from models import SystemSettings, Class
    import datetime
    
    try:
        # Check if changing semester or school_year and classes exist with current settings
        if 'semester' in data or 'school_year' in data:
            current_semester_setting = SystemSettings.query.filter_by(key='semester').first()
            current_school_year_setting = SystemSettings.query.filter_by(key='school_year').first()
            
            current_semester = current_semester_setting.value if current_semester_setting else None
            current_school_year = current_school_year_setting.value if current_school_year_setting else None
            
            # Check if there are classes with current semester and school_year
            if current_semester and current_school_year:
                classes_exist = Class.query.filter(
                    Class.term == current_semester.lower(),
                    Class.school_year == current_school_year
                ).first()
                if classes_exist:
                    return jsonify({'success': False, 'message': 'Cannot change semester or school year while classes exist for the current period. Please reset attendance and classes first.'}), 400
        
        for key, value in data.items():
            if key == 'semester':
                value = value.lower()
            elif key == 'room_numbers':
                try:
                    _, value = normalize_room_numbers_payload(value)
                except ValueError as exc:
                    return jsonify({'success': False, 'message': str(exc)}), 400
            elif key == 'room_number':
                try:
                    _, value = normalize_room_numbers_payload([value])
                except ValueError as exc:
                    return jsonify({'success': False, 'message': str(exc)}), 400
                key = 'room_numbers'

            if key == 'room_numbers' and not value:
                continue

            setting = SystemSettings.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = SystemSettings(key=key, value=value)
                db.session.add(setting)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating system settings: {e}")
        return jsonify({'success': False, 'message': 'Failed to update settings'}), 500

def generate_student_attendance_pdf(classes, enrollments, attendance_records, attendance_logs, class_sessions):
    """Generate PDF for student attendance data"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from io import BytesIO
    import datetime
    from models import Class, Enrollment
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
    )
    story.append(Paragraph("Student Attendance Archive", title_style))
    timestamp = get_pst_now().strftime('%Y-%m-%d %H:%M:%S')
    story.append(Paragraph(f"Generated on: {timestamp}", styles['Normal']))
    story.append(Paragraph("Note: This archive contains all attendance records.", styles['Italic']))
    story.append(Spacer(1, 20))
    
    # Fetch enrollment data from database
    enrollments_data = Enrollment.query.all()
    
    # Get unique class IDs from enrollments to find classes that have enrollments
    enrolled_class_ids = set()
    for enrollment in enrollments_data:
        enrolled_class_ids.add(enrollment.class_id)
    
    # Students Enrolled section - show enrollment details grouped by class
    enrollments_data = Enrollment.query.all()
    if enrollments_data:
        try:
            # Summary section
            total_students = len(set(e.student_id for e in enrollments_data))
            total_classes = len(set(e.class_id for e in enrollments_data))
            story.append(Paragraph("Enrollment Summary", styles['Heading2']))
            story.append(Spacer(1, 5))
            story.append(Paragraph(f"Total Students Enrolled: {total_students}", styles['Normal']))
            story.append(Paragraph(f"Total Classes with Enrollments: {total_classes}", styles['Normal']))
            story.append(Spacer(1, 10))

            # Complete list of all enrolled students
            story.append(Paragraph("Complete Student Enrollment List", styles['Heading3']))
            story.append(Spacer(1, 5))
            
            all_students_data = [['Student ID', 'Student Name', 'Year Level', 'Enrolled Classes']]
            student_class_map = {}
            
            # Build student to classes mapping
            for enrollment in enrollments_data:
                student_id = enrollment.student_id
                if student_id not in student_class_map:
                    student_class_map[student_id] = {
                        'name': 'N/A',
                        'year_level': 'N/A', 
                        'classes': []
                    }
                
                # Get student info
                try:
                    if enrollment.student:
                        student_class_map[student_id]['name'] = f"{enrollment.student.first_name} {enrollment.student.last_name}"
                        student_class_map[student_id]['year_level'] = enrollment.student.year_level or 'N/A'
                except:
                    pass
                
                # Add class info
                class_name = "N/A"
                try:
                    if enrollment.class_record:
                        class_name = enrollment.class_record.class_code
                except:
                    class_name = f"Class ID: {enrollment.class_id}"
                
                student_class_map[student_id]['classes'].append(class_name)
            
            # Create table rows
            for student_id, info in student_class_map.items():
                all_students_data.append([
                    str(student_id),
                    info['name'],
                    info['year_level'],
                    ', '.join(sorted(info['classes']))
                ])
            
            all_students_table = Table(all_students_data)
            all_students_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(all_students_table)
            story.append(Spacer(1, 15))

            story.append(Paragraph("Detailed Enrollment by Class", styles['Heading2']))
            story.append(Spacer(1, 10))

            story.append(Paragraph("Detailed Enrollment by Class", styles['Heading2']))
            story.append(Spacer(1, 10))

            # Group enrollments by class code
            enrollments_by_class = {}
            for enrollment in enrollments_data:
                class_code = "N/A"
                try:
                    if enrollment.class_record:
                        class_code = enrollment.class_record.class_code
                except:
                    class_code = f"Class ID: {enrollment.class_id}"

                if class_code not in enrollments_by_class:
                    enrollments_by_class[class_code] = []
                enrollments_by_class[class_code].append(enrollment)

            # Create separate table for each class
            for class_code, class_enrollments in enrollments_by_class.items():
                # Class header
                story.append(Paragraph(f"Class: {class_code}", styles['Heading3']))
                story.append(Spacer(1, 5))

                # Table data for this class
                enrollment_data = [['Student ID', 'Student Name', 'Enrollment Date']]
                for enrollment in class_enrollments:
                    student_name = "N/A"
                    try:
                        if enrollment.student:
                            student_name = f"{enrollment.student.first_name} {enrollment.student.last_name}"
                    except:
                        student_name = f"Student ID: {enrollment.student_id}"

                    enrollment_data.append([
                        str(enrollment.student_id),
                        student_name,
                        enrollment.created_at.strftime('%Y-%m-%d') if enrollment.created_at else 'N/A'
                    ])

                enrollment_table = Table(enrollment_data)
                enrollment_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(enrollment_table)
                story.append(Spacer(1, 15))
        except Exception as e:
            pass
    
    # Student Attendance Records section - grouped by class
    if attendance_records:
        try:
            story.append(Paragraph("Attendance Records", styles['Heading2']))
            story.append(Spacer(1, 10))

            # Group attendance records by class code
            attendance_by_class = {}
            for record in attendance_records:
                class_code = "N/A"
                try:
                    if record.class_session:
                        # Query the Class model using class_session.class_id
                        from models import Class
                        class_obj = Class.query.get(record.class_session.class_id)
                        if class_obj:
                            class_code = class_obj.class_code
                    else:
                        class_code = f"Session ID: {record.class_session_id}"
                except:
                    class_code = f"Session ID: {record.class_session_id}"

                if class_code not in attendance_by_class:
                    attendance_by_class[class_code] = []
                attendance_by_class[class_code].append(record)

            # Create separate table for each class
            for class_code, class_records in attendance_by_class.items():
                # Class header
                story.append(Paragraph(f"Class: {class_code}", styles['Heading3']))
                story.append(Spacer(1, 5))

                # Table data for this class
                attendance_data = [['Student ID', 'Student Name', 'Session Date', 'Status', 'Time In', 'Room']]
                for record in class_records:
                    student_name = "N/A"
                    try:
                        if record.student:
                            student_name = f"{record.student.first_name} {record.student.last_name}"
                    except:
                        student_name = f"Student ID: {record.student_id}"

                    # Determine room for this record (session-specific if available, otherwise class room)
                    room_value = 'N/A'
                    try:
                        if record.class_session and record.class_session.session_room_number:
                            room_value = record.class_session.session_room_number
                        elif record.class_session:
                            # Fallback: query Class from class_session
                            from models import Class as ClassModel
                            session_class = ClassModel.query.get(record.class_session.class_id)
                            if session_class and getattr(session_class, 'room_number', None):
                                room_value = session_class.room_number
                    except Exception:
                        pass

                    attendance_data.append([
                        str(record.student_id),
                        student_name,
                        record.date.strftime('%Y-%m-%d') if record.date else 'N/A',
                        record.status.value.title() if record.status and hasattr(record.status, 'value') else 'Absent',
                        record.time_in.strftime('%H:%M') if record.time_in else 'N/A',
                        room_value
                    ])
                    print(f"Student {record.student_id}: time_in={record.time_in}, time_out={record.time_out}")  # Debug

                attendance_table = Table(attendance_data)
                attendance_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(attendance_table)
                story.append(Spacer(1, 15))
        except Exception as e:
            pass
    
    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

def generate_instructor_attendance_pdf(instructor_attendance):
    """Generate PDF for instructor attendance data"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from io import BytesIO
    import datetime
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
    )
    story.append(Paragraph("Instructor Attendance Archive", title_style))
    timestamp = get_pst_now().strftime('%Y-%m-%d %H:%M:%S')
    story.append(Paragraph(f"Generated on: {timestamp}", styles['Normal']))
    story.append(Paragraph("Note: This archive contains all attendance records.", styles['Italic']))
    story.append(Spacer(1, 20))
    
    # Classes Assigned section - show all classes assigned to instructors
    classes_assigned = Class.query.filter(Class.instructor_id.isnot(None)).all()
    print(f"Found {len(classes_assigned)} classes assigned to instructors")  # Debug
    if classes_assigned:
        try:
            # Summary section
            total_classes = len(classes_assigned)
            unique_instructors = len(set(cls.instructor_id for cls in classes_assigned))
            story.append(Paragraph("Instructor Assignment Summary", styles['Heading2']))
            story.append(Spacer(1, 5))
            story.append(Paragraph(f"Total Classes Assigned: {total_classes}", styles['Normal']))
            story.append(Paragraph(f"Total Instructors with Classes: {unique_instructors}", styles['Normal']))
            story.append(Spacer(1, 10))

            # Complete list of instructors and their classes
            story.append(Paragraph("Complete Instructor-Class Assignments", styles['Heading3']))
            story.append(Spacer(1, 5))
            
            instructor_class_data = [['Instructor ID', 'Instructor Name', 'Assigned Classes']]
            instructor_assignments = {}
            
            # Build instructor to classes mapping
            for cls in classes_assigned:
                instructor_id = cls.instructor_id
                if instructor_id not in instructor_assignments:
                    instructor_assignments[instructor_id] = {
                        'name': 'N/A',
                        'classes': []
                    }
                
                # Get instructor info
                try:
                    if cls.instructor:
                        instructor_assignments[instructor_id]['name'] = f"{cls.instructor.first_name} {cls.instructor.last_name}"
                except:
                    pass
                
                # Add class info
                class_info = cls.class_code or f"Class ID: {cls.id}"
                instructor_assignments[instructor_id]['classes'].append(class_info)
            
            # Create table rows
            for instructor_id, info in instructor_assignments.items():
                instructor_class_data.append([
                    str(instructor_id),
                    info['name'],
                    ', '.join(sorted(info['classes']))
                ])
            
            instructor_class_table = Table(instructor_class_data)
            instructor_class_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(instructor_class_table)
            story.append(Spacer(1, 15))

            story.append(Paragraph("Detailed Class Assignments", styles['Heading2']))
            story.append(Spacer(1, 10))
            class_data = [['Class Code', 'Course Description', 'Instructor', 'Term', 'School Year', 'Room Number']]
            for cls in classes_assigned:
                course_desc = "N/A"
                try:
                    if cls.course:
                        course_desc = cls.course.description
                except:
                    course_desc = f"Course ID: {cls.course_id}"
                
                instructor_name = "N/A"
                try:
                    if cls.instructor:
                        instructor_name = f"{cls.instructor.first_name} {cls.instructor.last_name}"
                except:
                    instructor_name = f"Instructor ID: {cls.instructor_id}"
                
                term_value = "N/A"
                try:
                    if cls.term:
                        term_value = str(cls.term.value)
                    else:
                        term_value = "N/A"
                except:
                    term_value = str(cls.term) if cls.term else "N/A"
                    
                class_data.append([
                    str(cls.class_code or 'N/A'),
                    str(course_desc),
                    instructor_name,
                    term_value,
                    str(cls.school_year or 'N/A'),
                    str(cls.room_number or 'N/A')
                ])
            
            class_table = Table(class_data)
            class_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(class_table)
            story.append(Spacer(1, 20))
        except Exception as e:
            print(f"Error in Classes Assigned section: {e}")  # Debug
            pass
    
    # Instructor Attendance Records section - grouped by class
    if instructor_attendance:
        try:
            story.append(Paragraph("Attendance Records", styles['Heading2']))
            story.append(Spacer(1, 10))

            # Group instructor attendance records by class
            attendance_by_class = {}
            for record in instructor_attendance:
                class_code = "N/A"
                try:
                    if record.class_ref:
                        class_code = record.class_ref.class_code
                    else:
                        class_code = f"Class ID: {record.class_id}"
                except:
                    class_code = f"Class ID: {record.class_id}"

                if class_code not in attendance_by_class:
                    attendance_by_class[class_code] = []
                attendance_by_class[class_code].append(record)

            # Create separate table for each class
            for class_code, class_records in attendance_by_class.items():
                # Class header
                story.append(Paragraph(f"Class: {class_code}", styles['Heading3']))
                story.append(Spacer(1, 5))

                # Table data for this class
                instructor_data = [['Instructor ID', 'Instructor Name', 'Status', 'Date', 'Time In']]
                for record in class_records:
                    instructor_name = "N/A"
                    try:
                        if record.instructor:
                            instructor_name = f"{record.instructor.first_name} {record.instructor.last_name}"
                    except:
                        instructor_name = f"Instructor ID: {record.instructor_id}"
                        
                    instructor_data.append([
                        str(record.instructor_id),
                        instructor_name,
                        str(record.status),
                        record.date.strftime('%Y-%m-%d') if record.date else 'N/A',
                        record.time_in.strftime('%H:%M') if record.time_in else 'N/A'
                    ])

                instructor_table = Table(instructor_data)
                instructor_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(instructor_table)
                story.append(Spacer(1, 15))
        except Exception as e:
            pass
    
    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

@admin_bp.route('/api/reset-attendance-classes', methods=['POST'])
@login_required
@admin_required
def reset_attendance_and_classes():
    """Reset all attendance data and class enrollments, generating PDFs as archive"""
    try:
        # Fetch records for PDF generation
        classes = Class.query.all()
        enrollments = Enrollment.query.all()
        attendance_records = AttendanceRecord.query.all()
        attendance_logs = AttendanceLog.query.all()
        class_sessions = ClassSession.query.all()
        instructor_attendance = InstructorAttendance.query.all()
        
        # Generate PDFs with error handling
        try:
            student_pdf_data = generate_student_attendance_pdf(classes, enrollments, attendance_records, attendance_logs, class_sessions)
        except Exception as e:
            print(f"Error generating student PDF: {e}")
            student_pdf_data = b"Error generating student attendance PDF"
            
        try:
            instructor_pdf_data = generate_instructor_attendance_pdf(instructor_attendance)
        except Exception as e:
            print(f"Error generating instructor PDF: {e}")
            instructor_pdf_data = b"Error generating instructor attendance PDF"
        
        # Create ZIP file
        from io import BytesIO
        import zipfile
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('student_attendance_archive.pdf', student_pdf_data)
            zip_file.writestr('instructor_attendance_archive.pdf', instructor_pdf_data)
        
        zip_data = zip_buffer.getvalue()
        zip_buffer.close()
        
        # Delete all attendance-related data
        try:
            # Delete in order of dependencies (children first)
            AttendanceLog.query.delete()
            AttendanceRecord.query.delete()
            InstructorAttendance.query.delete()
            Enrollment.query.delete()
            ClassSession.query.delete()
            Class.query.delete()
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Failed to delete data: {str(e)}'}), 500
        
        # Set the reset timestamp
        import datetime
        reset_timestamp = SystemSettings.query.filter_by(key='last_reset_timestamp').first()
        if reset_timestamp:
            reset_timestamp.value = str(get_pst_now().timestamp())
        else:
            reset_timestamp = SystemSettings(key='last_reset_timestamp', value=str(get_pst_now().timestamp()))
            db.session.add(reset_timestamp)
        db.session.commit()
        
        # Return ZIP file
        from flask import send_file
        zip_buffer = BytesIO(zip_data)
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='attendance_archive.zip'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to reset data: {str(e)}'}), 500

@admin_bp.route('/api/attendance/instructor/get', methods=['GET'])
@login_required
def get_instructor_attendance_for_class():
    """Get instructor attendance for a specific class (Admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    class_id = request.args.get('classId')
    if not class_id:
        return jsonify([]), 200
    
    # Get the class and its instructor
    class_obj = Class.query.get(class_id)
    if not class_obj or not class_obj.instructor_id:
        return jsonify([]), 200
    
    # Get attendance records strictly for this class to avoid mixing other instructor classes
    attendance_records = InstructorAttendance.query.filter_by(
        class_id=class_obj.id
    ).order_by(InstructorAttendance.date.desc()).all()
    
    attendance_data = []
    for attendance in attendance_records:
        # Determine display value for time_out: show formatted time, or 'No Log' if session was processed without an OUT
        if attendance.time_out:
            time_out_display = attendance.time_out.strftime('%I:%M %p')
        else:
            # Check if a session exists for this class/date and has been processed (i.e., ended automatically)
            session = ClassSession.query.filter_by(class_id=class_obj.id, date=attendance.date).first()
            if session and session.is_attendance_processed:
                time_out_display = 'Not Logged Out'
            else:
                time_out_display = None

        attendance_data.append({
            'date': attendance.date.strftime('%B %d %Y'),
            'status': attendance.status,
            'time_in': attendance.time_in.strftime('%I:%M %p') if attendance.time_in else None,
            'time_out': time_out_display
        })
    
    return jsonify(attendance_data)

@admin_bp.route('/api/clear-test-attendance', methods=['POST'])
def clear_test_attendance():
    """Clear test attendance records for specified students (API endpoint for testing)"""
    # Check API key for this admin endpoint
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != current_app.config['API_KEY']:
        return jsonify({'error': 'Unauthorized: Missing or invalid API Key'}), 401
    
    try:
        data = request.get_json()
        if not data or 'student_ids' not in data:
            return jsonify({'success': False, 'message': 'Missing student_ids parameter'}), 400

        student_ids = data['student_ids']
        today = date.today()

        # Delete attendance records for the specified students from today onwards
        deleted_count = AttendanceRecord.query.filter(
            AttendanceRecord.student_id.in_(student_ids),
            AttendanceRecord.date >= today
        ).delete()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} test attendance records',
            'cleared_count': deleted_count
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error clearing test attendance: {str(e)}")
        return jsonify({'success': False, 'message': f'Error clearing test attendance: {str(e)}'}), 500

@admin_bp.route('/api/extract-embeddings', methods=['POST'])
@login_required
@admin_required
def extract_embeddings():
    """Run the extract_embeddings.py script to regenerate face embeddings"""
    try:
        payload = request.get_json(silent=True) or {}
        mode = (payload.get('mode') or 'all').lower()
        if mode not in {'all', 'new'}:
            mode = 'all'

        # Import the extract_embeddings module
        import sys
        from pathlib import Path
        
        # Add backend directory to path if not already there
        backend_dir = Path(__file__).parent.parent
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        
        # Import and run the main function
        from extract_embeddings import main
        
        # Run the extraction process
        success = main(mode=mode)
        mode_label = 'new faces' if mode == 'new' else 'all faces'
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Face embeddings extracted successfully ({mode_label})!'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to extract embeddings. Check server logs for details.'
            }), 500
            
    except ImportError as e:
        current_app.logger.error(f"Error importing extract_embeddings: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error importing extract_embeddings module: {str(e)}'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Error extracting embeddings: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error extracting embeddings: {str(e)}'
        }), 500
