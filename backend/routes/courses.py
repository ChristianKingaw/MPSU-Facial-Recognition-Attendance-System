from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import calendar

from extensions import db
from models import User, Class, Student, Enrollment, AttendanceRecord, InstructorAttendance, AttendanceLog, FaceEncoding, Course
from decorators import admin_required
from exceptions import AttendanceValidationError
import json
from forms import ClassForm

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')

@courses_bp.route('/api/list', methods=['GET'])
@login_required
def get_courses():
    """API endpoint to get all courses"""
    courses = Course.query.order_by(Course.code).all()
    course_list = [{'id': course.id, 'code': course.code, 'description': course.description} for course in courses]
    return jsonify(course_list)

@courses_bp.route('/manage', methods=['GET'])
@login_required
def manage():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('students.enroll'))
    
    # Get all courses from database
    courses = Course.query.order_by(Course.code).all()
    
    # Convert to list of tuples for template
    courses_for_template = [(course.code, course.description) for course in courses]
    
    return render_template('admin/courses.html', courses=courses_for_template)

@courses_bp.route('/add', methods=['POST'])
@login_required
def add():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
    
    course_code = request.form.get('courseCode')
    description = request.form.get('description')
    
    # Enhanced validation
    if not course_code or not description:
        flash('Course code and description are required.', 'danger')
        return redirect(url_for('courses.manage'))

    # Validate course code format
    if not course_code.isalnum():
        flash('Course code should only contain letters and numbers.', 'danger')
        return redirect(url_for('courses.manage'))

    if len(course_code) < 3 or len(course_code) > 10:
        flash('Course code should be between 3 and 10 characters.', 'danger')
        return redirect(url_for('courses.manage'))

    # Validate description length
    if len(description) < 5 or len(description) > 255:
        flash('Description should be between 5 and 255 characters.', 'danger')
        return redirect(url_for('courses.manage'))
        
    # Check if course already exists (case-insensitive)
    existing_course = Course.query.filter(Course.code.ilike(course_code)).first()
    if existing_course:
        flash(f'A course with code "{course_code}" already exists.', 'danger')
        return redirect(url_for('courses.manage'))

    try:
        # Create new course
        new_course = Course(
            code=course_code.upper(),  # Store in uppercase
            description=description
        )
        
        db.session.add(new_course)
        db.session.commit()
        
        flash(f'Course "{course_code}: {description}" has been added.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding course: {str(e)}', 'danger')
    
    return redirect(url_for('courses.manage'))

@courses_bp.route('/update', methods=['POST'])
@login_required
def update():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
    
    old_code = request.form.get('old_class_code')
    new_code = request.form.get('class_code')
    new_description = request.form.get('description')
    
    # Enhanced validation
    if not old_code or not new_code or not new_description:
        flash('All fields are required.', 'danger')
        return redirect(url_for('courses.manage'))

    # Validate new course code format
    if not new_code.isalnum():
        flash('Course code should only contain letters and numbers.', 'danger')
        return redirect(url_for('courses.manage'))

    if len(new_code) < 3 or len(new_code) > 10:
        flash('Course code should be between 3 and 10 characters.', 'danger')
        return redirect(url_for('courses.manage'))

    # Validate description length
    if len(new_description) < 5 or len(new_description) > 255:
        flash('Description should be between 5 and 255 characters.', 'danger')
        return redirect(url_for('courses.manage'))

    try:
        # Get the course to update
        course = Course.query.filter_by(code=old_code).first()
        if not course:
            flash(f'Course "{old_code}" not found.', 'warning')
            return redirect(url_for('courses.manage'))
            
        # Check if new code already exists (case-insensitive)
        if new_code.upper() != old_code.upper():
            existing_course = Course.query.filter(Course.code.ilike(new_code)).first()
            if existing_course:
                flash(f'A course with code "{new_code}" already exists.', 'danger')
                return redirect(url_for('courses.manage'))
            
            # Update the code
            course.code = new_code.upper()  # Store in uppercase
            
        # Update the description
        course.description = new_description
        
        db.session.commit()
        flash(f'Course "{old_code}" updated to "{new_code}" successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating course: {str(e)}', 'danger')

    return redirect(url_for('courses.manage'))

@courses_bp.route('/delete/<string:course_code>', methods=['POST'])
@login_required
def delete(course_code):
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
    
    try:
        # Get the course to delete
        course = Course.query.filter_by(code=course_code).first()
        if not course:
            flash(f'Course "{course_code}" not found.', 'warning')
            return redirect(url_for('courses.manage'))
            
        # Check if any classes are linked to this course
        linked_classes = Class.query.filter_by(course_id=course.id).first()
        if linked_classes:
            flash(f'Cannot delete course "{course_code}" because existing classes are linked to it. Delete linked classes first.', 'danger')
            return redirect(url_for('courses.manage'))
            
        # Delete the course
        db.session.delete(course)
        db.session.commit()
        
        flash(f'Course "{course_code}" removed successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting course: {str(e)}', 'danger')
    
    return redirect(url_for('courses.manage'))

@courses_bp.route('/api/import-courses', methods=['POST'])
@login_required
def import_courses():
    """API endpoint to import courses from CSV data"""
    # Only allow admin to access
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'You do not have permission to perform this action.'}), 403
    
    try:
        data = request.get_json()
        if not data or 'courses' not in data:
            return jsonify({'success': False, 'message': 'No courses data provided'}), 400
        
        courses_data = data['courses']
        if not courses_data:
            return jsonify({'success': False, 'message': 'No courses data provided'}), 400
        
        imported_count = 0
        updated_count = 0
        errors = []
        
        for course_data in courses_data:
            try:
                # Get course code and description
                course_code = course_data.get('course_code', '').strip()
                description = course_data.get('description', '').strip()
                
                if not course_code or not description:
                    errors.append(f'Missing course code or description for row')
                    continue
                
                # Check if course already exists
                existing_course = Course.query.filter_by(code=course_code).first()
                
                if existing_course:
                    # Update existing course
                    existing_course.description = description
                    updated_count += 1
                else:
                    # Create new course
                    new_course = Course(
                        code=course_code,
                        description=description
                    )
                    db.session.add(new_course)
                    imported_count += 1
                    
            except Exception as e:
                errors.append(f'Error processing course {course_code}: {str(e)}')
                continue
        
        # Commit all changes
        if imported_count > 0 or updated_count > 0:
            db.session.commit()
        
        message = f'Import completed: {imported_count} new courses added, {updated_count} courses updated'
        if errors:
            message += f'. {len(errors)} errors occurred.'
        
        return jsonify({
            'success': True,
            'message': message,
            'imported': imported_count,
            'updated': updated_count,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Import failed: {str(e)}'}), 500