#!/usr/bin/env python3
"""
Direct PostgreSQL Database Initializer for Azure
This script connects directly to Azure PostgreSQL and initializes the database
"""

import psycopg2
import psycopg2.extras
import bcrypt
import os
import sys
from env_config import get_database_url

# Load DATABASE_URL from environment variables
DATABASE_URL = get_database_url()


def create_admin_user():
    """Create the admin user with hashed password"""
    email = "admin@rfpo.com"
    password = "admin123"
    fullname = "System Administrator"

    # Hash the password
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    return {
        "email": email,
        "fullname": fullname,
        "password_hash": password_hash,
        "permissions": '["GOD"]',
        "global_admin": True,
        "active": True,
        "use_rfpo": True,
        "agreed_to_terms": True,
    }


def initialize_database():
    """Initialize PostgreSQL database with tables and admin user"""
    try:
        print("🔌 Connecting to PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        print("✅ Connected to PostgreSQL database")

        # Create users table (simplified version)
        print("🔧 Creating users table...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                record_id VARCHAR(32) UNIQUE,
                fullname VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                sex VARCHAR(10),
                company_code VARCHAR(50),
                company VARCHAR(255),
                position VARCHAR(255),
                department VARCHAR(255),
                building_address TEXT,
                address1 VARCHAR(255),
                address2 VARCHAR(255),
                city VARCHAR(100),
                state VARCHAR(100),
                zip_code VARCHAR(20),
                country VARCHAR(100),
                phone VARCHAR(50),
                phone_ext VARCHAR(20),
                mobile VARCHAR(50),
                fax VARCHAR(50),
                permissions TEXT,
                global_admin BOOLEAN DEFAULT FALSE,
                use_rfpo BOOLEAN DEFAULT TRUE,
                agreed_to_terms BOOLEAN DEFAULT FALSE,
                max_upload_size INTEGER DEFAULT 16777216,
                last_visit TIMESTAMP,
                last_ip VARCHAR(45),
                last_browser TEXT,
                is_approver BOOLEAN DEFAULT FALSE,
                approver_updated_at TIMESTAMP,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                updated_by INTEGER
            )
        """
        )

        # Check if admin user exists
        cursor.execute("SELECT id FROM users WHERE email = %s", ("admin@rfpo.com",))
        admin_exists = cursor.fetchone()

        if not admin_exists:
            print("👤 Creating admin user...")
            admin_data = create_admin_user()

            cursor.execute(
                """
                INSERT INTO users (
                    record_id, fullname, email, password_hash, permissions,
                    global_admin, active, use_rfpo, agreed_to_terms
                ) VALUES (
                    'ADM00000001', %s, %s, %s, %s, %s, %s, %s, %s
                )
            """,
                (
                    admin_data["fullname"],
                    admin_data["email"],
                    admin_data["password_hash"],
                    admin_data["permissions"],
                    admin_data["global_admin"],
                    admin_data["active"],
                    admin_data["use_rfpo"],
                    admin_data["agreed_to_terms"],
                ),
            )

            print("✅ Admin user created successfully")
        else:
            print("👤 Admin user already exists")

        # Create other essential tables
        print("🔧 Creating other essential tables...")

        # Teams table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id SERIAL PRIMARY KEY,
                team_id VARCHAR(32) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Consortiums table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS consortiums (
                id SERIAL PRIMARY KEY,
                consort_id VARCHAR(32) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL UNIQUE,
                abbrev VARCHAR(20) NOT NULL UNIQUE,
                logo VARCHAR(255),
                terms_pdf VARCHAR(255),
                require_approved_vendors BOOLEAN DEFAULT TRUE,
                non_government_project_id VARCHAR(32),
                rfpo_viewer_user_ids TEXT,
                rfpo_admin_user_ids TEXT,
                invoicing_address TEXT,
                doc_fax_name VARCHAR(255),
                doc_fax_number VARCHAR(255),
                doc_email_name VARCHAR(255),
                doc_email_address VARCHAR(255),
                doc_post_name VARCHAR(255),
                doc_post_address TEXT,
                po_email VARCHAR(255),
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Projects table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                project_id VARCHAR(32) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        print("✅ Database initialization completed successfully!")
        print("\n🎉 RFPO Database Ready!")
        print("📧 Admin Login: admin@rfpo.com")
        print("🔐 Admin Password: admin123")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Starting PostgreSQL Database Initialization")
    print("=" * 50)

    success = initialize_database()

    if success:
        print("\n✅ Database initialization completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)
