#!/usr/bin/env python3
"""Test connection to Azure PostgreSQL database from local machine."""

import sys

import psycopg2


def test_azure_db_connection():
    """Test connection to Azure PostgreSQL database."""
    connection_string = "postgresql://rfpoadmin:RfpoSecure123!@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require"

    try:
        print("🔗 Attempting connection to Azure PostgreSQL...")
        conn = psycopg2.connect(connection_string)
        print("✅ Database connection successful!")

        cursor = conn.cursor()

        # Test basic query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"📊 PostgreSQL version: {version[0][:80]}...")

        # Count tables
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
        )
        table_count = cursor.fetchone()
        print(f"📋 Tables in database: {table_count[0]}")

        # List some tables
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name LIMIT 10;"
        )
        tables = cursor.fetchall()
        print("📂 Sample tables:")
        for table in tables:
            print(f"   - {table[0]}")

        conn.close()
        print("✅ Connection test completed successfully!")
        return True

    except psycopg2.Error as e:
        print(f"❌ PostgreSQL Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    success = test_azure_db_connection()
    sys.exit(0 if success else 1)
