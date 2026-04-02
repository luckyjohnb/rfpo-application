"""Add entra_oid column to users table for SSO support."""
import sqlalchemy
from dotenv import load_dotenv
import os

load_dotenv()
db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    print("ERROR: DATABASE_URL not set in .env")
    exit(1)

print(f"Connecting to: {db_url[:40]}...")
engine = sqlalchemy.create_engine(db_url)

with engine.connect() as conn:
    conn.execute(
        sqlalchemy.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS entra_oid VARCHAR(36) UNIQUE"
        )
    )
    conn.commit()
    print("entra_oid column added (or already exists)")

    result = conn.execute(
        sqlalchemy.text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='users' AND column_name='entra_oid'"
        )
    )
    for row in result:
        print(f"Verified: {row}")

print("Migration complete.")
