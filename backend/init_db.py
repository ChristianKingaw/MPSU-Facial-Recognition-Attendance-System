import os
import logging
from flask import Flask
from flask_migrate import Migrate, upgrade
from models import db, User
from config import Config
from extensions import db as extensions_db

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def init_app():
    """Initialize Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    extensions_db.init_app(app)
    
    return app

def init_database():
    """Initialize database and run migrations."""
    logger = setup_logging()
    app = init_app()
    
    with app.app_context():
        try:
            # Initialize migrations
            migrate = Migrate(app, extensions_db)
            
            # Run migrations
            logger.info("Running database migrations...")
            upgrade()
            logger.info("Migrations completed successfully")
            
            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            return False

def main():
    """Main function to initialize the database."""
    logger = setup_logging()
    logger.info("Starting database initialization...")
    
    if init_database():
        logger.info("Database initialization completed successfully!")
    else:
        logger.error("Database initialization failed!")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main()) 