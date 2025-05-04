from app import app, db
from models import User
import datetime
from werkzeug.security import generate_password_hash

def create_admin_user():
    """Create an admin user if no users exist."""
    with app.app_context():
        if User.query.count() == 0:
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                first_name="System",
                last_name="Administrator",
                role="admin",
                password_hash=generate_password_hash("admin1234"),
                created_at=datetime.datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
            print("Username: admin")
            print("Password: admin1234")
        else:
            print("Users already exist in database. No action taken.")

if __name__ == "__main__":
    create_admin_user()