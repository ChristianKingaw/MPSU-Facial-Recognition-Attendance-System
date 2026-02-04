import datetime
from extensions import db
from utils.timezone import pst_now_naive

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.String(20), primary_key=True)  # Format YY-XXXXX must be unique and must numeric
    first_name = db.Column(db.String(64), nullable=False, index=True)
    middle_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=False, index=True)
    year_level = db.Column(db.String(20), nullable=False, index=True)
    department = db.Column(db.String(32), nullable=False, default='BSIT')
    created_at = db.Column(db.DateTime, default=pst_now_naive)
    
    # Relationships with eager loading by default
    enrollments = db.relationship('Enrollment', back_populates='student', lazy='joined', cascade="all, delete-orphan")
    face_encodings = db.relationship('FaceEncoding', backref='student', lazy='joined', cascade="all, delete-orphan")
    attendance_records = db.relationship('AttendanceRecord', back_populates='student', lazy='joined', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Student {self.id}: {self.first_name} {self.last_name}>' 