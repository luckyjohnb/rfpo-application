"""Add pdf_snapshot_path column to rfpos table."""
import psycopg2
import os

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://rfpoadmin:RfpoSecure123!@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require",
)

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='rfpos' AND column_name='pdf_snapshot_path'"
)
if cur.fetchone():
    print("Column pdf_snapshot_path already exists")
else:
    cur.execute("ALTER TABLE rfpos ADD COLUMN pdf_snapshot_path VARCHAR(512)")
    conn.commit()
    print("Column pdf_snapshot_path added successfully")

cur.close()
conn.close()
