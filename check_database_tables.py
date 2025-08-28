#!/usr/bin/env python3
"""
CHECK DATABASE TABLES
See what tables exist in the database
"""
import sqlite3

def check_database_tables():
    print("🔍 CHECK DATABASE TABLES")
    print("="*50)
    
    try:
        # Connect to database
        conn = sqlite3.connect('instance/rfpo.db')
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📋 Found {len(tables)} tables:")
        for table in tables:
            table_name = table[0]
            print(f"   • {table_name}")
            
            # Get row count for each table
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"     Rows: {count}")
                
                # Show sample data for small tables
                if count <= 5 and count > 0:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                    rows = cursor.fetchall()
                    # Get column names
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [col[1] for col in cursor.fetchall()]
                    print(f"     Columns: {', '.join(columns)}")
                    for i, row in enumerate(rows):
                        print(f"     Row {i+1}: {row}")
            except Exception as e:
                print(f"     Error querying {table_name}: {e}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    check_database_tables()
