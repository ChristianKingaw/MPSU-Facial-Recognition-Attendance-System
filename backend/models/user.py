from extensions import db
from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from utils.timezone import pst_now_naive

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True) #must be unique numeric
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=True)
    password_hash = Column(String(256))
    first_name = Column(String(50))
    middle_name = Column(String(50), nullable=True)
    last_name = Column(String(50))
    role = Column(String(20), nullable=False)  # 'admin', 'instructor', 'student'
    department = Column(String(50), nullable=True)  # Department for instructors (IT, CRIM, etc.)
    profile_picture = Column(String(255), nullable=True)  # Path to profile picture
    created_at = Column(DateTime, default=pst_now_naive)
    
    def set_password(self, password):
        self.password_hash = password  # Store plaintext password
        
    def check_password(self, password):
        return self.password_hash == password  # Direct comparison for plaintext