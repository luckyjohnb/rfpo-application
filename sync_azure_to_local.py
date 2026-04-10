#!/usr/bin/env python3
"""
Sync Azure PostgreSQL schema + data → local SQLite.
Azure is authoritative: local tables are dropped and recreated.
Uses models.py for schema (cross-DB compatible), Azure for data.
Read-only on Azure — only writes to local ./instance/rfpo_admin.db
"""

import os
import sys
import shutil
from datetime import datetime
from flask import Flask
from sqlalchemy import create_engine, MetaData, text, inspect
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__) or ".")

from models import db  # noqa: E402 — imports all models via relationships

# Azure source (read-only)
AZURE_URL = os.environ.get(
    "AZURE_DATABASE_URL",
    "postgresql://rfpoadmin:RfpoSecure123!@"
    "rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require",
)

# Local target
LOCAL_DB = os.path.join(os.path.dirname(__file__) or ".", "instance", "rfpo_admin.db")
LOCAL_URL = f"sqlite:///{LOCAL_DB}"
BACKUP_DB = LOCAL_DB.replace(".db", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")


def sync():
    # --- Connect to Azure and reflect tables ---
    print("Connecting to Azure PostgreSQL...")
    azure_engine = create_engine(AZURE_URL, echo=False)
    azure_meta = MetaData()
    azure_meta.reflect(bind=azure_engine)
    azure_tables = sorted(azure_meta.tables.keys())
    print(f"Found {len(azure_tables)} tables in Azure: {', '.join(azure_tables)}")

    azure_session = sessionmaker(bind=azure_engine)()

    # --- Backup local DB ---
    os.makedirs("instance", exist_ok=True)
    if os.path.exists(LOCAL_DB):
        print(f"Backing up local DB to {BACKUP_DB}")
        shutil.copy2(LOCAL_DB, BACKUP_DB)
        os.remove(LOCAL_DB)

    # --- Create local schema from models.py (cross-DB compatible) ---
    print(f"Creating local SQLite from models.py: {LOCAL_DB}")
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = LOCAL_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

        # Verify what was created
        local_inspector = inspect(db.engine)
        local_tables = sorted(local_inspector.get_table_names())
        print(f"Created {len(local_tables)} tables in local SQLite")

        # Check for Azure tables not in models.py
        missing_in_models = set(azure_tables) - set(local_tables)
        if missing_in_models:
            print(f"  NOTE: Azure-only tables (not in models.py): {missing_in_models}")
            # Create these tables by reflecting and adapting
            for tname in missing_in_models:
                azure_table = azure_meta.tables[tname]
                # Strip server defaults that are PG-specific
                for col in azure_table.columns:
                    col.server_default = None
                try:
                    azure_table.create(bind=db.engine)
                    local_tables.append(tname)
                    print(f"  Created extra table: {tname}")
                except Exception as e:
                    print(f"  WARNING: Could not create {tname}: {e}")

        # --- Copy data ---
        print("\nCopying data from Azure to local...")
        total_rows = 0

        # Reflect local schema fully for insert operations
        local_meta = MetaData()
        local_meta.reflect(bind=db.engine)

        with db.engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))

            for table_name in azure_tables:
                azure_table = azure_meta.tables[table_name]
                local_table = local_meta.tables.get(table_name)
                if local_table is None:
                    print(f"  {table_name}: SKIPPED (not in local)")
                    continue

                # Read all rows from Azure
                rows = azure_session.execute(azure_table.select()).fetchall()
                if not rows:
                    print(f"  {table_name}: 0 rows")
                    continue

                # Only use columns that exist in both
                azure_cols = {c.name for c in azure_table.columns}
                local_cols = {c.name for c in local_table.columns}
                common_cols = sorted(azure_cols & local_cols)
                skipped_cols = azure_cols - local_cols
                if skipped_cols:
                    print(f"  {table_name}: Azure-only cols (skipped): {skipped_cols}")

                # Build insert batch
                batch = []
                for row in rows:
                    row_dict = {}
                    for col in common_cols:
                        val = getattr(row, col, None)
                        if isinstance(val, bool):
                            val = 1 if val else 0
                        row_dict[col] = val
                    batch.append(row_dict)

                try:
                    conn.execute(local_table.insert(), batch)
                    print(f"  {table_name}: {len(rows)} rows")
                    total_rows += len(rows)
                except Exception as e:
                    print(f"  {table_name}: ERROR - {e}")

            conn.execute(text("PRAGMA foreign_keys=ON"))

    azure_session.close()
    print(f"\nSync complete: {len(local_tables)} tables, {total_rows} total rows")
    print(f"   Local DB: {LOCAL_DB}")
    print(f"   Backup:   {BACKUP_DB}")
    print(f"\nRestart containers: docker-compose restart rfpo-api rfpo-user-app rfpo-admin")


if __name__ == "__main__":
    sync()



if __name__ == "__main__":
    sync()
