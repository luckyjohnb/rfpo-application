"""Seed the Global Approval Workflow with Financial, USCAR Internal, and PO Release stages.

From the approval matrix:
  - Finance Approval:
      1. Diana Zielonka (diana.zielonka@stellantis.com) — backup: David Pollock
      2. Gabriela Grajales (ggrajale@ford.com) — backup: Cynthia Flanigan
      3. George Faux (aina.faux@gm.com) — backup: Paul Krajewski
  - USCAR Internal Approval:
      1. Chuck Gough (cgough@uscar.org) — backup: Steve Przesmitzki
  - PO Release Approval:
      1. Karin Darovitz (kdarovitz@doeren.com) — backup: Nadette Bullington
"""
import os
import sys

os.environ.setdefault("FLASK_ENV", "production")

from sqlalchemy import create_engine, text

if "--azure" in sys.argv:
    # Use Azure PostgreSQL directly
    AZURE_DB_URL = os.environ.get("AZURE_DATABASE_URL", "")
    if not AZURE_DB_URL:
        # Fetch from container app env
        import subprocess
        result = subprocess.run(
            ["az", "containerapp", "show", "-n", "rfpo-api", "-g", "rg-rfpo-e108977f",
             "--query", "properties.template.containers[0].env[?name=='DATABASE_URL'].value",
             "-o", "tsv"],
            capture_output=True, text=True
        )
        AZURE_DB_URL = result.stdout.strip()
        if not AZURE_DB_URL:
            print("ERROR: Could not fetch Azure DATABASE_URL")
            sys.exit(1)
    print(f"Using Azure DB: {AZURE_DB_URL[:30]}...")
    db_url = AZURE_DB_URL
else:
    from env_config import get_database_url
    db_url = get_database_url()

engine = create_engine(db_url)

# --- Approver definitions (email -> role) ---
# Primary approvers with their backup approvers
STAGES = [
    {
        "section_type": "financial",
        "bracket_key": "GLOBAL_FINANCIAL",
        "stage_name": "Financial Approvers",
        "stage_order": 1,
        "steps": [
            {
                "name": "Diana Zielonka",
                "email": "diana.zielonka@stellantis.com",
                "backup_email": None,  # Will search by name
                "backup_name": "David Pollock",
                "step_order": 1,
            },
            {
                "name": "Gabriela Grajales",
                "email": "ggrajale@ford.com",
                "backup_email": None,
                "backup_name": "Cynthia Flanigan",
                "step_order": 2,
            },
            {
                "name": "George Faux",
                "email": "aina.faux@gm.com",
                "backup_email": None,
                "backup_name": "Paul Krajewski",
                "step_order": 3,
            },
        ],
    },
    {
        "section_type": "uscar_internal",
        "bracket_key": "GLOBAL_USCAR_INTERNAL",
        "stage_name": "US Car Internals",
        "stage_order": 2,
        "steps": [
            {
                "name": "Chuck Gough",
                "email": "cgough@uscar.org",
                "backup_email": None,
                "backup_name": "Steve Przesmitzki",
                "step_order": 1,
            },
        ],
    },
    {
        "section_type": "po_release",
        "bracket_key": "GLOBAL_PO_RELEASE",
        "stage_name": "P.O. Release Approvers",
        "stage_order": 3,
        "steps": [
            {
                "name": "Karin Darovitz",
                "email": "kdarovitz@doeren.com",
                "backup_email": None,
                "backup_name": "Nadette Bullington",
                "step_order": 1,
            },
        ],
    },
]


def find_user(conn, email=None, name=None):
    """Find a user by email (case-insensitive) or by fullname search."""
    if email:
        row = conn.execute(
            text("SELECT record_id, email, fullname FROM users WHERE LOWER(email) = LOWER(:email) AND active = true"),
            {"email": email},
        ).fetchone()
        if row:
            return {"record_id": row[0], "email": row[1], "name": row[2]}

    if name:
        # Try exact fullname match
        row = conn.execute(
            text("SELECT record_id, email, fullname FROM users WHERE LOWER(fullname) = LOWER(:name) AND active = true"),
            {"name": name},
        ).fetchone()
        if row:
            return {"record_id": row[0], "email": row[1], "name": row[2]}

        # Try LIKE match on fullname
        row = conn.execute(
            text("SELECT record_id, email, fullname FROM users WHERE LOWER(fullname) LIKE LOWER(:pattern) AND active = true"),
            {"pattern": f"%{name}%"},
        ).fetchone()
        if row:
            return {"record_id": row[0], "email": row[1], "name": row[2]}

    return None


def get_next_id(conn, table, id_field, prefix):
    """Get next auto-increment ID for a table."""
    row = conn.execute(
        text(f"SELECT {id_field} FROM {table} ORDER BY {id_field} DESC LIMIT 1")
    ).fetchone()
    if row and row[0]:
        try:
            num = int(row[0].replace(prefix, "").lstrip("0") or "0") + 1
        except ValueError:
            num = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0] + 1
    else:
        num = 1
    return f"{prefix}{num:08d}"


def main():
    dry_run = "--dry-run" in sys.argv

    with engine.connect() as conn:
        # Check if global workflow already exists
        existing = conn.execute(
            text("SELECT id, name FROM rfpo_approval_workflows WHERE workflow_type = 'global' AND is_template = true")
        ).fetchone()
        if existing:
            # Check if it has stages already
            stage_count = conn.execute(
                text("SELECT COUNT(*) FROM rfpo_approval_stages WHERE workflow_id = :wf_pk"),
                {"wf_pk": existing[0]},
            ).fetchone()[0]
            if stage_count > 0:
                print(f"ERROR: Global workflow already exists (ID={existing[0]}, name='{existing[1]}') with {stage_count} stages.")
                print("Delete it first or edit it in the admin UI.")
                sys.exit(1)
            else:
                print(f"Found existing empty global workflow (ID={existing[0]}, name='{existing[1]}') — will add stages to it.")
                wf_pk = existing[0]
                wf_id = None  # Skip creating workflow

        # Look up all users first
        print("=== Looking up users ===")
        missing_users = []
        for stage_def in STAGES:
            for step_def in stage_def["steps"]:
                user = find_user(conn, email=step_def["email"])
                if user:
                    step_def["_user"] = user
                    print(f"  OK: {step_def['name']} -> {user['record_id']} ({user['email']})")
                else:
                    step_def["_user"] = None
                    missing_users.append(f"{step_def['name']} ({step_def['email']})")
                    print(f"  MISSING: {step_def['name']} ({step_def['email']})")

                # Look up backup
                if step_def.get("backup_name"):
                    backup = find_user(conn, email=step_def.get("backup_email"), name=step_def["backup_name"])
                    if backup:
                        step_def["_backup"] = backup
                        print(f"    Backup OK: {step_def['backup_name']} -> {backup['record_id']} ({backup['email']})")
                    else:
                        step_def["_backup"] = None
                        print(f"    Backup MISSING: {step_def['backup_name']}")

        if missing_users:
            print(f"\nWARNING: {len(missing_users)} primary approver(s) not found in users table:")
            for m in missing_users:
                print(f"  - {m}")
            resp = input("Continue anyway? Steps with missing users will be SKIPPED. (y/n): ")
            if resp.lower() != "y":
                print("Aborted.")
                sys.exit(1)

        if dry_run:
            print("\n=== DRY RUN — no changes made ===")
            sys.exit(0)

        # Create the global workflow
        wf_id = get_next_id(conn, "rfpo_approval_workflows", "workflow_id", "WF-")
        print(f"\n=== Creating global workflow (workflow_id={wf_id}) ===")
        conn.execute(
            text("""
                INSERT INTO rfpo_approval_workflows
                    (workflow_id, name, description, version, workflow_type,
                     is_active, is_template, created_by)
                VALUES
                    (:wf_id, :name, :desc, '1.0', 'global',
                     true, true, 'system-seed')
            """),
            {
                "wf_id": wf_id,
                "name": "Global Approval Workflow",
                "desc": "Global approval stages: Financial, USCAR Internal, PO Release",
            },
        )

        # Get the auto-generated workflow PK
        wf_row = conn.execute(
            text("SELECT id FROM rfpo_approval_workflows WHERE workflow_id = :wf_id"),
            {"wf_id": wf_id},
        ).fetchone()
        wf_pk = wf_row[0]
        print(f"  Workflow PK: {wf_pk}")

        # Create stages and steps
        total_steps = 0
        for stage_def in STAGES:
            stg_id = get_next_id(conn, "rfpo_approval_stages", "stage_id", "STG-")
            print(f"\n  Creating stage: {stage_def['stage_name']} (stage_id={stg_id}, bracket_key={stage_def['bracket_key']})")
            conn.execute(
                text("""
                    INSERT INTO rfpo_approval_stages
                        (stage_id, stage_name, stage_order, description,
                         budget_bracket_key, budget_bracket_amount,
                         workflow_id, requires_all_steps, is_parallel)
                    VALUES
                        (:stg_id, :name, :order, :desc,
                         :bracket_key, 0.00,
                         :wf_pk, true, false)
                """),
                {
                    "stg_id": stg_id,
                    "name": stage_def["stage_name"],
                    "order": stage_def["stage_order"],
                    "desc": f"Global {stage_def['stage_name']} stage",
                    "bracket_key": stage_def["bracket_key"],
                    "wf_pk": wf_pk,
                },
            )

            # Get stage PK
            stg_row = conn.execute(
                text("SELECT id FROM rfpo_approval_stages WHERE stage_id = :stg_id"),
                {"stg_id": stg_id},
            ).fetchone()
            stg_pk = stg_row[0]

            # Create steps
            for step_def in stage_def["steps"]:
                user = step_def.get("_user")
                if not user:
                    print(f"    SKIPPING step {step_def['name']} — user not found")
                    continue

                backup = step_def.get("_backup")
                stp_id = get_next_id(conn, "rfpo_approval_steps", "step_id", "STP-")

                print(f"    Step {step_def['step_order']}: {step_def['name']} ({user['record_id']})"
                      + (f" backup={backup['name']} ({backup['record_id']})" if backup else ""))

                conn.execute(
                    text("""
                        INSERT INTO rfpo_approval_steps
                            (step_id, step_name, step_order, description,
                             approval_type_key, approval_type_name,
                             stage_id, primary_approver_id, backup_approver_id,
                             is_required, timeout_days, auto_escalate)
                        VALUES
                            (:stp_id, :name, :order, :desc,
                             :type_key, :type_name,
                             :stg_pk, :primary_id, :backup_id,
                             true, 5, false)
                    """),
                    {
                        "stp_id": stp_id,
                        "name": step_def["name"],
                        "order": step_def["step_order"],
                        "desc": f"{stage_def['stage_name']} - {step_def['name']}",
                        "type_key": stage_def["bracket_key"],
                        "type_name": stage_def["stage_name"],
                        "stg_pk": stg_pk,
                        "primary_id": user["record_id"],
                        "backup_id": backup["record_id"] if backup else None,
                    },
                )
                total_steps += 1

        conn.commit()
        print(f"\n=== DONE ===")
        print(f"  Global Workflow: {wf_id} (PK={wf_pk})")
        print(f"  Stages: {len(STAGES)}")
        print(f"  Steps: {total_steps}")
        print(f"\nValidate in Admin UI: https://rfpo-admin.uscar.org/approval-workflow/{wf_pk}")


if __name__ == "__main__":
    main()
