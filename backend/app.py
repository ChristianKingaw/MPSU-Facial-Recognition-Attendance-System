import os
import sys
import logging

# Suppress TensorFlow and h5py warnings BEFORE any imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Suppress debug loggers
for logger_name in ['tensorflow', 'h5py', 'h5py._conv', 'absl']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)
    logging.getLogger(logger_name).propagate = False

from flask import Flask, redirect, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
# Ensure the backend directory is on sys.path for intra-package imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from extensions import db
from flask_migrate import Migrate
from flask_session import Session
from flask_login import LoginManager
from routes.admin import admin_bp
from models import User, Student, Class, Enrollment, AttendanceRecord, FaceEncoding

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create the global login_manager instance
login_manager = LoginManager()

def create_app():
    # Create the Flask app and point to frontend assets
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(base_dir, '..', 'frontend'))
    app = Flask(
        __name__,
        static_folder=os.path.join(frontend_dir, 'static'),
        template_folder=os.path.join(frontend_dir, 'templates')
    )
    app.config.from_object(Config)
    app.secret_key = app.config["SECRET_KEY"]
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Add CORS headers
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    Session(app)  # Initialize Flask-Session
    
    # Initialize rate limiter with app context
    from routes.api import limiter
    limiter.init_app(app)
    limiter.default_limits = [app.config['API_RATE_LIMIT']]

    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Import and register blueprints
    from routes.auth import auth_bp
    from routes.instructors import instructors_bp
    from routes.students import students_bp
    from routes.classes import classes_bp
    from routes.attendance import attendance_bp
    from routes.admin import admin_bp
    from routes.courses import courses_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(instructors_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(api_bp)


   

    # Root route to redirect to login page
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # Configure session
    @app.before_request
    def before_request():
        session.permanent = True

    return app

# Load the user from the database when needed
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)