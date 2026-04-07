"""One-time script to update John Bouchard to RFPO_ADMIN."""
import json
import os
from sqlalchemy import create_engine, text

db_url = os.environ.get("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT id, fullname, email, permissions FROM users WHERE fullname ILIKE :name"),
        {"name": "%bouchard%"},
    )
    rows = result.fetchall()
    for row in rows:
        print(f"ID={row[0]} Name={row[1]} Email={row[2]} Perms={row[3]}")

    if rows:
        user = rows[0]
        current_perms = json.loads(user[3]) if user[3] else []
        print(f"\nCurrent permissions: {current_perms}")

        if "RFPO_ADMIN" not in current_perms:
            current_perms.append("RFPO_ADMIN")
        if "RFPO_USER" not in current_perms:
            current_perms.append("RFPO_USER")

        new_perms = json.dumps(current_perms)
        print(f"New permissions: {new_perms}")

        conn.execute(
            text("UPDATE users SET permissions = :perms WHERE id = :id"),
            {"perms": new_perms, "id": user[0]},
        )
        conn.commit()
        print("Updated successfully!")
    else:
        print("User not found!")
