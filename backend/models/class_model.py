from extensions import db
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from datetime import datetime
from utils.timezone import pst_now_naive

class Class(db.Model):
    __tablename__ = 'classes'

    id = Column(Integer, primary_key=True)
    class_code = Column(String(20), unique=True, nullable=False)
    description = Column(String(200))
    instructor_id = Column(Integer, ForeignKey('users.id'))
    substitute_instructor_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    schedule = Column(String(100))  # Format: "M 9:00-10:30,T 13:00-14:30"
    room_number = Column(String(20))
    created_at = Column(DateTime, default=pst_now_naive)
    term = Column(Enum('1st semester', '2nd semester', 'summer', name='term_enum'), nullable=True)
    school_year = Column(String(9), nullable=True)  # Example: '2025-2026'

    # Relationships
    instructor = db.relationship('User', foreign_keys=[instructor_id], backref='classes')
    substitute_instructor = db.relationship('User', foreign_keys=[substitute_instructor_id], backref='substitute_classes')
    course = db.relationship('Course', backref='classes')

    def get_schedule(self, date):
        """Get schedule for a specific date"""
        # TODO: Implement schedule parsing and matching
        return None 