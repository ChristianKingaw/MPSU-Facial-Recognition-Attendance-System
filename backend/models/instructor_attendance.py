from extensions import db
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from datetime import datetime
from utils.timezone import pst_now_naive

class InstructorAttendance(db.Model):
    __tablename__ = 'instructor_attendance'
    
    id = Column(Integer, primary_key=True)
    instructor_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=True)
    date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)  # 'Present', 'Absent'
    notes = Column(String(500))
    time_in = Column(DateTime)
    time_out = Column(DateTime)
    created_at = Column(DateTime, default=pst_now_naive)
    updated_at = Column(DateTime, default=pst_now_naive, onupdate=pst_now_naive)
    
    # Relationships
    instructor = db.relationship('User', backref='instructor_attendance')
    class_ref = db.relationship('Class', backref='instructor_attendance')  




    # note not much time to meet deadline will rename after it will be defended