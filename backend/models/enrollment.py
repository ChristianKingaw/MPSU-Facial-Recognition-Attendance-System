from extensions import db
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from datetime import datetime
from utils.timezone import pst_now_naive

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(db.String(20), ForeignKey('students.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    created_at = Column(DateTime, default=pst_now_naive)
    
    # Relationships
    student = db.relationship('Student', back_populates='enrollments')
    class_record = db.relationship('Class', backref='enrollments')

    @property
    def enrolled_date(self):
        """Backward-compatible alias used throughout the codebase."""
        return self.created_at

    @enrolled_date.setter
    def enrolled_date(self, value):
        self.created_at = value