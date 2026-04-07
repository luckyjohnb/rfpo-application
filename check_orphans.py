"""Check for orphaned records across all FK relationships."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Allow overriding DB URL via CLI arg
if len(sys.argv) > 1 and sys.argv[1] == '--azure':
    # Fetch from Azure container env
    import subprocess
    result = subprocess.run(
        'az containerapp show -n rfpo-api -g rg-rfpo-e108977f --query "properties.template.containers[0].env[?name==\'DATABASE_URL\'].value" -o tsv',
        capture_output=True, text=True, shell=True
    )
    db_url = result.stdout.strip()
    if not db_url or not db_url.startswith('postgresql'):
        print("ERROR: Could not retrieve Azure DATABASE_URL")
        sys.exit(1)
    print(f"=== AZURE DATABASE (PostgreSQL) ===\n")
elif len(sys.argv) > 1:
    db_url = sys.argv[1]
    print(f"=== DATABASE ({db_url[:40]}...) ===\n")
else:
    db_url = 'sqlite:///instance/rfpo_admin.db'
    print(f"=== LOCAL DATABASE ({db_url}) ===\n")

from flask import Flask
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

orphan_count = 0

def check(label, sql):
    global orphan_count
    with db.engine.connect() as conn:
        rows = conn.execute(db.text(sql)).fetchall()
    if rows:
        orphan_count += len(rows)
        print(f"  ORPHANS FOUND: {label} — {len(rows)} record(s)")
        for r in rows[:10]:
            print(f"    {dict(r._mapping)}")
        if len(rows) > 10:
            print(f"    ... and {len(rows)-10} more")
    else:
        print(f"  OK: {label}")

with app.app_context():
    # First, show table counts
    print("--- Table Counts ---")
    tables = [
        'users', 'consortiums', 'teams', 'projects', 'vendors', 'vendor_sites',
        'rfpos', 'rfpo_line_items', 'uploaded_files', 'user_teams', 'lists',
        'pdf_positioning', 'rfpo_approval_workflows', 'rfpo_approval_stages',
        'rfpo_approval_steps', 'rfpo_approval_instances', 'rfpo_approval_actions',
        'audit_logs', 'notifications', 'email_logs'
    ]
    for t in tables:
        try:
            with db.engine.connect() as conn:
                cnt = conn.execute(db.text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t}: {cnt}")
        except Exception as e:
            print(f"  {t}: TABLE MISSING ({e})")

    print("\n--- Orphan Checks ---")

    # 1. Line items pointing to non-existent RFPOs
    check("rfpo_line_items → rfpos",
          "SELECT li.id, li.rfpo_id, li.description FROM rfpo_line_items li "
          "LEFT JOIN rfpos r ON li.rfpo_id = r.id WHERE r.id IS NULL")

    # 2. Uploaded files pointing to non-existent RFPOs
    check("uploaded_files → rfpos",
          "SELECT uf.id, uf.rfpo_id, uf.original_filename FROM uploaded_files uf "
          "LEFT JOIN rfpos r ON uf.rfpo_id = r.id WHERE r.id IS NULL")

    # 3. RFPOs pointing to non-existent teams
    check("rfpos.team_id → teams",
          "SELECT r.id, r.rfpo_id, r.team_id FROM rfpos r "
          "LEFT JOIN teams t ON r.team_id = t.id "
          "WHERE r.team_id IS NOT NULL AND t.id IS NULL")

    # 4. RFPOs pointing to non-existent vendors
    check("rfpos.vendor_id → vendors",
          "SELECT r.id, r.rfpo_id, r.vendor_id FROM rfpos r "
          "LEFT JOIN vendors v ON r.vendor_id = v.id "
          "WHERE r.vendor_id IS NOT NULL AND v.id IS NULL")

    # 5. RFPOs pointing to non-existent vendor sites
    check("rfpos.vendor_site_id → vendor_sites",
          "SELECT r.id, r.rfpo_id, r.vendor_site_id FROM rfpos r "
          "LEFT JOIN vendor_sites vs ON r.vendor_site_id = vs.id "
          "WHERE r.vendor_site_id IS NOT NULL AND vs.id IS NULL")

    # 6. Vendor sites pointing to non-existent vendors
    check("vendor_sites → vendors",
          "SELECT vs.id, vs.vendor_site_id, vs.vendor_id FROM vendor_sites vs "
          "LEFT JOIN vendors v ON vs.vendor_id = v.id WHERE v.id IS NULL")

    # 7. User-team links pointing to non-existent users
    check("user_teams.user_id → users",
          "SELECT ut.id, ut.user_id, ut.team_id FROM user_teams ut "
          "LEFT JOIN users u ON ut.user_id = u.id WHERE u.id IS NULL")

    # 8. User-team links pointing to non-existent teams
    check("user_teams.team_id → teams",
          "SELECT ut.id, ut.user_id, ut.team_id FROM user_teams ut "
          "LEFT JOIN teams t ON ut.team_id = t.id WHERE t.id IS NULL")

    # 9. Approval stages pointing to non-existent workflows
    check("rfpo_approval_stages → workflows",
          "SELECT s.id, s.stage_id, s.workflow_id FROM rfpo_approval_stages s "
          "LEFT JOIN rfpo_approval_workflows w ON s.workflow_id = w.id WHERE w.id IS NULL")

    # 10. Approval steps pointing to non-existent stages
    check("rfpo_approval_steps → stages",
          "SELECT st.id, st.step_id, st.stage_id FROM rfpo_approval_steps st "
          "LEFT JOIN rfpo_approval_stages s ON st.stage_id = s.id WHERE s.id IS NULL")

    # 11. Approval instances pointing to non-existent RFPOs
    check("rfpo_approval_instances.rfpo_id → rfpos",
          "SELECT ai.id, ai.instance_id, ai.rfpo_id, ai.overall_status FROM rfpo_approval_instances ai "
          "LEFT JOIN rfpos r ON ai.rfpo_id = r.id WHERE r.id IS NULL")

    # 12. Approval instances pointing to non-existent workflows
    check("rfpo_approval_instances.template_workflow_id → workflows",
          "SELECT ai.id, ai.instance_id, ai.template_workflow_id FROM rfpo_approval_instances ai "
          "LEFT JOIN rfpo_approval_workflows w ON ai.template_workflow_id = w.id WHERE w.id IS NULL")

    # 13. Approval actions pointing to non-existent instances
    check("rfpo_approval_actions → instances",
          "SELECT aa.id, aa.action_id, aa.instance_id FROM rfpo_approval_actions aa "
          "LEFT JOIN rfpo_approval_instances ai ON aa.instance_id = ai.id WHERE ai.id IS NULL")

    # 14. Approval workflows pointing to non-existent teams
    check("rfpo_approval_workflows.team_id → teams",
          "SELECT w.id, w.workflow_id, w.team_id FROM rfpo_approval_workflows w "
          "LEFT JOIN teams t ON w.team_id = t.id "
          "WHERE w.team_id IS NOT NULL AND t.id IS NULL")

    # --- Soft-delete related checks ---
    print("\n--- Soft-Deleted RFPO Checks ---")

    # 15. Soft-deleted RFPOs
    check("Soft-deleted RFPOs (deleted_at IS NOT NULL)",
          "SELECT r.id, r.rfpo_id, r.title, r.status, r.deleted_at FROM rfpos r "
          "WHERE r.deleted_at IS NOT NULL")

    # 16. Line items on soft-deleted RFPOs
    check("Line items on soft-deleted RFPOs",
          "SELECT li.id, li.rfpo_id, r.rfpo_id as rfpo_name, r.deleted_at "
          "FROM rfpo_line_items li "
          "JOIN rfpos r ON li.rfpo_id = r.id WHERE r.deleted_at IS NOT NULL")

    # 17. Files on soft-deleted RFPOs
    check("Files on soft-deleted RFPOs",
          "SELECT uf.id, uf.rfpo_id, uf.original_filename, r.deleted_at "
          "FROM uploaded_files uf "
          "JOIN rfpos r ON uf.rfpo_id = r.id WHERE r.deleted_at IS NOT NULL")

    # 18. Approval instances on soft-deleted RFPOs
    check("Approval instances on soft-deleted RFPOs",
          "SELECT ai.id, ai.instance_id, ai.rfpo_id, ai.overall_status, r.deleted_at "
          "FROM rfpo_approval_instances ai "
          "JOIN rfpos r ON ai.rfpo_id = r.id WHERE r.deleted_at IS NOT NULL")

    # 19. Actions on soft-deleted RFPOs (through instance)
    check("Actions on soft-deleted RFPOs",
          "SELECT aa.id, aa.action_id, ai.rfpo_id, r.deleted_at "
          "FROM rfpo_approval_actions aa "
          "JOIN rfpo_approval_instances ai ON aa.instance_id = ai.id "
          "JOIN rfpos r ON ai.rfpo_id = r.id WHERE r.deleted_at IS NOT NULL")

    print(f"\n=== TOTAL ORPHANED/STALE RECORDS: {orphan_count} ===")
