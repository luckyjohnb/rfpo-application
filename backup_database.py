"""
Database Backup Script
Exports all data from Azure PostgreSQL to local backup files (JSON + SQL)
"""

import json
import os
import sys
from datetime import datetime, date
from decimal import Decimal

import sqlalchemy
from sqlalchemy import create_engine, inspect, text


def json_serializer(obj):
    """Handle non-serializable types."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    raise TypeError(f"Type {type(obj)} not serializable")


def backup_database(db_url, backup_dir):
    """Export all tables from the database to JSON and SQL files."""
    
    engine = create_engine(db_url)
    inspector = inspect(engine)
    
    table_names = inspector.get_table_names()
    print(f"Found {len(table_names)} tables: {', '.join(table_names)}")
    
    summary = {
        "backup_timestamp": datetime.now().isoformat(),
        "database_url": db_url.split("@")[1] if "@" in db_url else "local",  # Don't log credentials
        "tables": {}
    }
    
    # Create subdirectories
    json_dir = os.path.join(backup_dir, "json")
    sql_dir = os.path.join(backup_dir, "sql")
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(sql_dir, exist_ok=True)
    
    with engine.connect() as conn:
        # Export each table
        for table_name in sorted(table_names):
            try:
                # Get row count
                count_result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                row_count = count_result.scalar()
                
                # Get all data
                result = conn.execute(text(f'SELECT * FROM "{table_name}"'))
                columns = list(result.keys())
                rows = [dict(zip(columns, row)) for row in result.fetchall()]
                
                # Save as JSON
                json_path = os.path.join(json_dir, f"{table_name}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "table": table_name,
                        "columns": columns,
                        "row_count": row_count,
                        "data": rows
                    }, f, indent=2, default=json_serializer, ensure_ascii=False)
                
                # Generate SQL INSERT statements
                sql_path = os.path.join(sql_dir, f"{table_name}.sql")
                with open(sql_path, "w", encoding="utf-8") as f:
                    f.write(f"-- Backup of table: {table_name}\n")
                    f.write(f"-- Rows: {row_count}\n")
                    f.write(f"-- Date: {datetime.now().isoformat()}\n\n")
                    
                    for row in rows:
                        cols = ", ".join([f'"{c}"' for c in columns])
                        vals = []
                        for c in columns:
                            v = row[c]
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, (int, float, Decimal)):
                                vals.append(str(v))
                            elif isinstance(v, bool):
                                vals.append("TRUE" if v else "FALSE")
                            elif isinstance(v, (datetime, date)):
                                vals.append(f"'{v.isoformat()}'")
                            else:
                                escaped = str(v).replace("'", "''")
                                vals.append(f"'{escaped}'")
                        values_str = ", ".join(vals)
                        f.write(f'INSERT INTO "{table_name}" ({cols}) VALUES ({values_str});\n')
                
                summary["tables"][table_name] = {
                    "row_count": row_count,
                    "columns": columns
                }
                
                print(f"  {table_name}: {row_count} rows ({len(columns)} columns)")
                
            except Exception as e:
                print(f"  ERROR backing up {table_name}: {e}")
                summary["tables"][table_name] = {"error": str(e)}
    
    # Also export schema (CREATE TABLE statements)
    schema_path = os.path.join(backup_dir, "schema.sql")
    with engine.connect() as conn:
        with open(schema_path, "w", encoding="utf-8") as f:
            f.write(f"-- Database Schema Backup\n")
            f.write(f"-- Date: {datetime.now().isoformat()}\n\n")
            
            for table_name in sorted(table_names):
                try:
                    # Get column details
                    columns_info = inspector.get_columns(table_name)
                    pk = inspector.get_pk_constraint(table_name)
                    
                    f.write(f'\n-- Table: {table_name}\n')
                    f.write(f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n')
                    
                    col_defs = []
                    for col in columns_info:
                        nullable = "" if col.get("nullable", True) else " NOT NULL"
                        default = f" DEFAULT {col['default']}" if col.get("default") else ""
                        col_defs.append(f'  "{col["name"]}" {col["type"]}{nullable}{default}')
                    
                    if pk and pk.get("constrained_columns"):
                        pk_cols = ", ".join([f'"{c}"' for c in pk["constrained_columns"]])
                        col_defs.append(f"  PRIMARY KEY ({pk_cols})")
                    
                    f.write(",\n".join(col_defs))
                    f.write("\n);\n")
                    
                except Exception as e:
                    f.write(f"-- ERROR getting schema for {table_name}: {e}\n")
    
    # Save summary
    summary_path = os.path.join(backup_dir, "backup_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=json_serializer)
    
    # Print summary
    total_rows = sum(
        t.get("row_count", 0) for t in summary["tables"].values() if isinstance(t.get("row_count"), int)
    )
    print(f"\nBackup complete!")
    print(f"  Tables: {len(table_names)}")
    print(f"  Total rows: {total_rows}")
    print(f"  Output: {backup_dir}")
    
    return summary


if __name__ == "__main__":
    # Get database URL
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Try loading from .env
        try:
            from dotenv import load_dotenv
            load_dotenv()
            db_url = os.environ.get("DATABASE_URL")
        except ImportError:
            pass
    
    if not db_url:
        print("ERROR: DATABASE_URL not set. Pass it as environment variable.")
        sys.exit(1)
    
    # Create timestamped backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(__file__), "backups", timestamp)
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"Starting database backup to: {backup_dir}")
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print()
    
    backup_database(db_url, backup_dir)
