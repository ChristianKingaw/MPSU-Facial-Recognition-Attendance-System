import datetime
from extensions import db
from utils.timezone import pst_now_naive

class VerificationCode(db.Model):
    """Stores verification codes for backup authentication and password reset"""
    __tablename__ = 'verification_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # changed from instructor_id
    code = db.Column(db.String(128), nullable=False)  # increased length for secure tokens
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=pst_now_naive)
    expires_at = db.Column(db.DateTime, nullable=False)
    purpose = db.Column(db.String(64), nullable=True)  # Added purpose field
    
    user = db.relationship('User', backref=db.backref('verification_codes', lazy=True))  # changed from instructor
    
    def __repr__(self):
        return f'<VerificationCode {self.code} for user {self.user_id}>'