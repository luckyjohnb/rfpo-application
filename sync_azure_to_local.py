#!/usr/bin/env python3
"""
Sync Azure PostgreSQL production data to local SQLite database.
Safe read-only operation on Azure — only writes to local ./instance/rfpo_admin.db
"""

import os
import sys
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.orm import sessionmaker

# Azure source (read-only)
AZURE_URL = (
    "postgresql://rfpoadmin:RfpoSecure123!@"
    "rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require"
)

# Local target
LOCAL_DB = os.path.join(os.path.dirname(__file__), "instance", "rfpo_admin.db")
LOCAL_URL = f"sqlite:///{LOCAL_DB}"

# Tables in dependency order (parents before children)
TABLE_ORDER = [
    "consortiums",
    "projects",
    "teams",
    "users",
    "user_teams",
    "vendors",
    "vendor_sites",
    "lists",
    "rfpos",
    "rfpo_line_items",
    "uploaded_files",
    "document_chunks",
    "pdf_positioning",
    "rfpo_approval_workflows",
    "rfpo_approval_stages",
    "rfpo_approval_steps",
    "rfpo_approval_instances",
    "rfpo_approval_actions",
]


def sync():
    print(f"📡 Connecting to Azure PostgreSQL...")
    azure_engine = create_engine(AZURE_URL, echo=False)

    print(f"💾 Connecting to local SQLite: {LOCAL_DB}")
    local_engine = create_engine(LOCAL_URL, echo=False)

    # Reflect Azure schema
    azure_meta = MetaData()
    azure_meta.reflect(bind=azure_engine)

    azure_session = sessionmaker(bind=azure_engine)()
    local_session = sessionmaker(bind=local_engine)()

    # Reflect local schema
    local_meta = MetaData()
    local_meta.reflect(bind=local_engine)

    total_rows = 0

    for table_name in TABLE_ORDER:
        if table_name not in azure_meta.tables:
            print(f"  ⚠️  {table_name}: not found in Azure, skipping")
            continue
        if table_name not in local_meta.tables:
            print(f"  ⚠️  {table_name}: not found in local DB, skipping")
            continue

        azure_table = azure_meta.tables[table_name]
        local_table = local_meta.tables[table_name]

        # Read all rows from Azure
        rows = azure_session.execute(azure_table.select()).fetchall()
        count = len(rows)

        if count == 0:
            print(f"  ⏭️  {table_name}: empty, skipping")
            continue

        # Get column names that exist in both source and target
        azure_cols = {c.name for c in azure_table.columns}
        local_cols = {c.name for c in local_table.columns}
        common_cols = azure_cols & local_cols

        # Clear local table
        local_session.execute(local_table.delete())

        # Insert rows
        for row in rows:
            row_dict = {col: getattr(row, col) for col in common_cols if hasattr(row, col)}
            local_session.execute(local_table.insert().values(**row_dict))

        local_session.commit()
        total_rows += count
        print(f"  ✅ {table_name}: {count} rows synced")

    azure_session.close()
    local_session.close()

    print(f"\n🎉 Sync complete! {total_rows} total rows copied to local SQLite.")
    print(f"   Restart containers: docker-compose down; docker-compose up -d")


if __name__ == "__main__":
    sync()
