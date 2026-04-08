"""Check global workflow configuration in the database."""
import os
os.environ.setdefault('FLASK_ENV', 'production')
from env_config import get_database_url
from sqlalchemy import create_engine, text

engine = create_engine(get_database_url())
with engine.connect() as conn:
    # Check global workflows
    rows = conn.execute(text("""
        SELECT w.id, w.name, w.workflow_type, w.is_active, w.is_template,
               COUNT(s.id) as stage_count
        FROM rfpo_approval_workflows w
        LEFT JOIN rfpo_approval_stages s ON s.workflow_id = w.id
        WHERE w.workflow_type = 'global'
        GROUP BY w.id, w.name, w.workflow_type, w.is_active, w.is_template
    """)).fetchall()
    print("=== GLOBAL WORKFLOWS ===")
    if not rows:
        print("  ** NO GLOBAL WORKFLOWS FOUND **")
    for r in rows:
        print(f"  ID={r[0]} name={r[1]} type={r[2]} active={r[3]} template={r[4]} stages={r[5]}")

    # Check stages in global workflows
    rows2 = conn.execute(text("""
        SELECT s.id, s.stage_name, s.stage_order, s.budget_bracket_key, s.budget_bracket_amount,
               s.workflow_id, COUNT(st.id) as step_count
        FROM rfpo_approval_stages s
        JOIN rfpo_approval_workflows w ON w.id = s.workflow_id AND w.workflow_type = 'global'
        LEFT JOIN rfpo_approval_steps st ON st.stage_id = s.id
        GROUP BY s.id, s.stage_name, s.stage_order, s.budget_bracket_key, s.budget_bracket_amount, s.workflow_id
        ORDER BY s.workflow_id, s.stage_order
    """)).fetchall()
    print()
    print("=== GLOBAL WORKFLOW STAGES ===")
    if not rows2:
        print("  ** NO STAGES FOUND IN GLOBAL WORKFLOWS **")
    for r in rows2:
        print(f"  Stage ID={r[0]} name={r[1]} order={r[2]} bracket_key={r[3]} amount={r[4]} workflow={r[5]} steps={r[6]}")

    # Check steps in global stages
    rows3 = conn.execute(text("""
        SELECT st.id, st.step_name, st.step_order, st.primary_approver_id,
               s.stage_name, s.budget_bracket_key
        FROM rfpo_approval_steps st
        JOIN rfpo_approval_stages s ON s.id = st.stage_id
        JOIN rfpo_approval_workflows w ON w.id = s.workflow_id AND w.workflow_type = 'global'
        ORDER BY s.stage_order, st.step_order
    """)).fetchall()
    print()
    print("=== STEPS IN GLOBAL STAGES ===")
    if not rows3:
        print("  ** NO STEPS FOUND IN GLOBAL STAGES **")
    for r in rows3:
        print(f"  Step ID={r[0]} name={r[1]} order={r[2]} approver={r[3]} stage={r[4]} bracket={r[5]}")
