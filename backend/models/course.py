from extensions import db
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from utils.timezone import pst_now_naive

class Course(db.Model):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    # name = Column(String(100), nullable=False) # Commented out conflicting 'name' column
    description = Column(String(500), nullable=False, default='No description')
    created_at = Column(DateTime, default=pst_now_naive) 