#!/usr/bin/env python3
"""
SQLAlchemy Database Initializer for Azure PostgreSQL
This script uses SQLAlchemy models to create tables properly
"""

import os
import sys
import bcrypt
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from env_config import get_database_url

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load DATABASE_URL from environment variables
os.environ["DATABASE_URL"] = get_database_url()

# Import Flask and SQLAlchemy models
from flask import Flask
from models import db, User, Team, Consortium, Project, Vendor


def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    return app


def create_admin_user(app):
    """Create the admin user with proper SQLAlchemy model"""
    with app.app_context():
        # Check if admin user already exists
        existing_admin = User.query.filter_by(email="admin@rfpo.com").first()
        if existing_admin:
            print("👤 Admin user already exists")
            return existing_admin

        # Hash the password
        password = "admin123"
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # Create admin user
        admin_user = User(
            record_id="ADM00000001",
            fullname="System Administrator",
            email="admin@rfpo.com",
            password_hash=password_hash,
            permissions='["GOD"]',
            global_admin=True,
            active=True,
            use_rfpo=True,
            agreed_to_terms=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(admin_user)
        db.session.commit()

        print("✅ Admin user created successfully")
        return admin_user


def initialize_database():
    """Initialize the PostgreSQL database"""
    try:
        database_url = get_database_url()
        logger.info(f"Connecting to database...")

        # Create engine
        engine = create_engine(database_url)

        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")

        # Import models to ensure tables are created
        logger.info("Importing models...")
        sys.path.append("/app")

        try:
            from models import db, User, Team, RFPORequest, UploadedFile
            from flask import Flask
            from config import Config

            # Create Flask app for database context
            app = Flask(__name__)
            app.config.from_object(Config)
            app.config["SQLALCHEMY_DATABASE_URI"] = database_url

            # Initialize database with app
            db.init_app(app)

            with app.app_context():
                logger.info("Creating database tables...")
                db.create_all()
                logger.info("Database tables created successfully")

                # Create admin user
                create_admin_user(engine)

        except ImportError as e:
            logger.error(f"Failed to import models: {e}")
            # Fallback: Create tables using raw SQL
            logger.info("Creating tables using raw SQL...")
            create_tables_sql(engine)
            create_admin_user(engine)

        logger.info("Database initialization completed successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def create_tables_sql(engine):
    """Create tables using raw SQL as fallback"""
    logger.info("Creating tables with raw SQL...")

    sql_commands = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            first_name VARCHAR(80) NOT NULL,
            last_name VARCHAR(80) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rfpo_requests (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'draft',
            created_by INTEGER REFERENCES users(id),
            assigned_team INTEGER REFERENCES teams(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            due_date TIMESTAMP,
            priority VARCHAR(20) DEFAULT 'medium'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size INTEGER,
            mime_type VARCHAR(100),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by INTEGER REFERENCES users(id),
            rfpo_request_id INTEGER REFERENCES rfpo_requests(id)
        )
        """,
    ]

    with engine.connect() as conn:
        for sql in sql_commands:
            try:
                conn.execute(text(sql))
                conn.commit()
            except SQLAlchemyError as e:
                logger.warning(f"SQL command failed (may be expected): {e}")

    logger.info("Tables created successfully")


if __name__ == "__main__":
    success = initialize_database()
    sys.exit(0 if success else 1)
