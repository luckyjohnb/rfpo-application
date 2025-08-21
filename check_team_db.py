#!/usr/bin/env python3
"""
Quick database verification without external dependencies
"""
import sqlite3
import os

def check_database():
    """Check if the database exists and has the team table"""
    db_path = os.path.join('instance', 'app.db')

    if not os.path.exists(db_path):
        print(f"❌ Database file not found at {db_path}")
        return False

    print(f"✅ Database file found at {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if teams table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams';")
        result = cursor.fetchone()

        if result:
            print("✅ Teams table exists in database")

            # Check team table structure
            cursor.execute("PRAGMA table_info(teams)")
            columns = cursor.fetchall()
            print(f"✅ Teams table has {len(columns)} columns")

            # List column names
            column_names = [col[1] for col in columns]
            print(f"   Columns: {', '.join(column_names)}")

            # Check current team count
            cursor.execute("SELECT COUNT(*) FROM teams")
            count = cursor.fetchone()[0]
            print(f"✅ Current teams in database: {count}")

            # If there are teams, show them
            if count > 0:
                cursor.execute("SELECT id, name, abbrev, consortium_id, active FROM teams")
                teams = cursor.fetchall()
                print("   Teams:")
                for team in teams:
                    status = "Active" if team[4] else "Inactive"
                    print(f"     - ID: {team[0]}, Name: {team[1]}, Abbrev: {team[2]}, Consortium: {team[3]}, Status: {status}")

        else:
            print("❌ Teams table not found in database")

            # Show what tables do exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            if tables:
                table_names = [table[0] for table in tables]
                print(f"   Existing tables: {', '.join(table_names)}")
            else:
                print("   No tables found in database")

            return False

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Checking Team Management Database...")
    print("=" * 50)

    if check_database():
        print("\n🎉 Database verification completed successfully!")
    else:
        print("\n⚠️ Database verification failed. Tables may need to be created.")
        print("   Try running: python init_db.py")
