"""
Approval Reminder & Escalation Service

Standalone script that queries overdue pending approval actions, sends
reminder emails (up to MAX_REMINDERS), then auto-escalates to the backup
approver. Designed to run as a scheduled Container Apps Job (daily 8 AM ET).

Usage:
    python reminder_service.py          # run reminders + escalations
    docker-compose run --rm rfpo-reminder  # local dev
    az containerapp job start -n rfpo-reminder-job -g rg-rfpo-e108977f  # Azure
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from env_config import get_database_url
from models import (
    db,
    User,
    RFPO,
    RFPOApprovalAction,
    RFPOApprovalInstance,
    Notification,
)
from email_service import send_approval_reminder, send_escalation_notification

logger = logging.getLogger("reminder_service")

# Configurable via environment variables
REMINDER_REPEAT_DAYS = int(os.environ.get("REMINDER_REPEAT_DAYS", "2"))
MAX_REMINDERS_BEFORE_ESCALATION = int(
    os.environ.get("MAX_REMINDERS_BEFORE_ESCALATION", "3")
)


def _create_flask_app() -> Flask:
    """Create a minimal Flask app with DB access for the reminder service."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def _get_backup_approver_info(instance, action):
    """Look up the backup approver from the instance_data snapshot.

    Returns (backup_record_id, backup_user) or (None, None).
    """
    try:
        data = instance.get_instance_data()
        for stage in data.get("stages", []):
            if stage.get("stage_order") == action.stage_order:
                for step in stage.get("steps", []):
                    if step.get("step_order") == action.step_order:
                        backup_id = step.get("backup_approver_id")
                        if backup_id:
                            backup_user = User.query.filter_by(
                                record_id=backup_id, active=True
                            ).first()
                            return backup_id, backup_user
                        return None, None
                break
    except Exception:
        pass
    return None, None


def _create_notification(user_id, notif_type, title, message, link=None,
                         entity_type=None, entity_id=None):
    """Insert an in-app notification."""
    notif = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        link=link,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.session.add(notif)


def run_reminders(app: Flask) -> dict:
    """Send reminders for overdue pending actions.

    Returns a summary dict with counts of reminders sent and skipped.
    """
    now = datetime.utcnow()
    repeat_threshold = now - timedelta(days=REMINDER_REPEAT_DAYS)
    sent = 0
    skipped = 0

    with app.app_context():
        # Query overdue pending actions eligible for a reminder
        overdue_actions = (
            db.session.query(RFPOApprovalAction)
            .join(RFPOApprovalInstance)
            .filter(
                RFPOApprovalAction.status == "pending",
                RFPOApprovalAction.due_date < now,
                RFPOApprovalAction.reminder_count < MAX_REMINDERS_BEFORE_ESCALATION,
                RFPOApprovalInstance.overall_status == "waiting",
            )
            .filter(
                db.or_(
                    RFPOApprovalAction.last_reminder_sent_utc.is_(None),
                    RFPOApprovalAction.last_reminder_sent_utc < repeat_threshold,
                )
            )
            .all()
        )

        action_ids = [a.id for a in overdue_actions]
        logger.info("Found %d overdue actions eligible for reminders", len(action_ids))

        for action_id in action_ids:
            # Re-fetch to guard against race conditions
            action = db.session.get(RFPOApprovalAction, action_id)
            if not action or action.status != "pending":
                skipped += 1
                continue

            instance = action.instance
            rfpo = instance.rfpo if instance else None
            approver = action.get_approver()

            if not approver or not approver.email:
                logger.warning(
                    "Action %s: approver %s has no email, skipping",
                    action.action_id, action.approver_id,
                )
                skipped += 1
                continue

            days_overdue = (now - action.due_date).days if action.due_date else 0
            new_reminder_count = (action.reminder_count or 0) + 1
            rfpo_id_str = rfpo.rfpo_id if rfpo else "Unknown"
            rfpo_db_id = rfpo.id if rfpo else None

            try:
                send_approval_reminder(
                    user_email=approver.email,
                    user_name=approver.get_display_name(),
                    rfpo_id=rfpo_id_str,
                    step_name=action.step_name,
                    due_date=action.due_date.strftime("%Y-%m-%d") if action.due_date else "N/A",
                    days_overdue=days_overdue,
                    reminder_number=new_reminder_count,
                    max_reminders=MAX_REMINDERS_BEFORE_ESCALATION,
                    rfpo_db_id=rfpo_db_id,
                )

                _create_notification(
                    user_id=approver.id,
                    notif_type="overdue",
                    title=f"Overdue Approval Reminder ({new_reminder_count}/{MAX_REMINDERS_BEFORE_ESCALATION})",
                    message=f"RFPO {rfpo_id_str} approval is {days_overdue} days overdue.",
                    link=f"/rfpos/{rfpo_db_id}" if rfpo_db_id else None,
                    entity_type="approval_action",
                    entity_id=str(action.id),
                )

                action.reminder_count = new_reminder_count
                action.last_reminder_sent_utc = now
                db.session.commit()
                sent += 1
                logger.info(
                    "Reminder %d/%d sent for action %s (RFPO %s) to %s",
                    new_reminder_count, MAX_REMINDERS_BEFORE_ESCALATION,
                    action.action_id, rfpo_id_str, approver.email,
                )
            except Exception as e:
                db.session.rollback()
                logger.error("Failed to send reminder for action %s: %s", action.action_id, e)
                skipped += 1

    summary = {"reminders_sent": sent, "reminders_skipped": skipped}
    logger.info("Reminders complete: %s", summary)
    return summary


def run_escalations(app: Flask) -> dict:
    """Escalate actions that have exhausted all reminders.

    Returns a summary dict with counts of escalations triggered and skipped.
    """
    now = datetime.utcnow()
    escalated = 0
    skipped = 0

    with app.app_context():
        # Query pending actions that have maxed out reminders and aren't yet escalated
        actions_to_escalate = (
            db.session.query(RFPOApprovalAction)
            .join(RFPOApprovalInstance)
            .filter(
                RFPOApprovalAction.status == "pending",
                RFPOApprovalAction.reminder_count >= MAX_REMINDERS_BEFORE_ESCALATION,
                RFPOApprovalAction.is_escalated.is_(False),
                RFPOApprovalInstance.overall_status == "waiting",
            )
            .all()
        )

        action_ids = [a.id for a in actions_to_escalate]
        logger.info("Found %d actions eligible for escalation", len(action_ids))

        for action_id in action_ids:
            # Re-fetch to guard against race conditions
            action = db.session.get(RFPOApprovalAction, action_id)
            if not action or action.status != "pending" or action.is_escalated:
                skipped += 1
                continue

            instance = action.instance
            rfpo = instance.rfpo if instance else None
            primary_approver = action.get_approver()
            rfpo_id_str = rfpo.rfpo_id if rfpo else "Unknown"
            rfpo_db_id = rfpo.id if rfpo else None
            days_overdue = (now - action.due_date).days if action.due_date else 0

            # Look up backup approver
            backup_id, backup_user = _get_backup_approver_info(instance, action)

            try:
                # Mark as escalated
                action.is_escalated = True
                action.escalated_at = now
                action.escalation_reason = (
                    f"Auto-escalation: {MAX_REMINDERS_BEFORE_ESCALATION} reminders unanswered"
                )

                due_date_str = action.due_date.strftime("%Y-%m-%d") if action.due_date else "N/A"
                primary_name = primary_approver.get_display_name() if primary_approver else "Unknown"
                backup_name = backup_user.get_display_name() if backup_user else "N/A"

                # Send escalation email to backup approver
                if backup_user and backup_user.email:
                    send_escalation_notification(
                        user_email=backup_user.email,
                        user_name=backup_user.get_display_name(),
                        rfpo_id=rfpo_id_str,
                        step_name=action.step_name,
                        due_date=due_date_str,
                        days_overdue=days_overdue,
                        reminders_sent=action.reminder_count or 0,
                        is_backup=True,
                        primary_approver_name=primary_name,
                        rfpo_db_id=rfpo_db_id,
                    )
                    _create_notification(
                        user_id=backup_user.id,
                        notif_type="escalation",
                        title=f"Escalated: RFPO {rfpo_id_str} Approval",
                        message=f"You are the backup approver. Primary approver ({primary_name}) has not responded after {action.reminder_count} reminders.",
                        link=f"/rfpos/{rfpo_db_id}" if rfpo_db_id else None,
                        entity_type="approval_action",
                        entity_id=str(action.id),
                    )

                # Send escalation notice to primary approver
                if primary_approver and primary_approver.email:
                    send_escalation_notification(
                        user_email=primary_approver.email,
                        user_name=primary_approver.get_display_name(),
                        rfpo_id=rfpo_id_str,
                        step_name=action.step_name,
                        due_date=due_date_str,
                        days_overdue=days_overdue,
                        reminders_sent=action.reminder_count or 0,
                        is_backup=False,
                        backup_approver_name=backup_name,
                        rfpo_db_id=rfpo_db_id,
                    )
                    _create_notification(
                        user_id=primary_approver.id,
                        notif_type="escalation",
                        title=f"Escalated: RFPO {rfpo_id_str} Approval",
                        message=f"This approval has been escalated to backup approver ({backup_name}) due to no response.",
                        link=f"/rfpos/{rfpo_db_id}" if rfpo_db_id else None,
                        entity_type="approval_action",
                        entity_id=str(action.id),
                    )

                db.session.commit()
                escalated += 1
                logger.info(
                    "Escalated action %s (RFPO %s): primary=%s, backup=%s",
                    action.action_id, rfpo_id_str,
                    primary_approver.email if primary_approver else "N/A",
                    backup_user.email if backup_user else "N/A",
                )
            except Exception as e:
                db.session.rollback()
                logger.error("Failed to escalate action %s: %s", action.action_id, e)
                skipped += 1

    summary = {"escalations_triggered": escalated, "escalations_skipped": skipped}
    logger.info("Escalations complete: %s", summary)
    return summary


def main() -> int:
    """Entry point for the reminder service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Approval Reminder & Escalation Service")
    logger.info(
        "Config: REMINDER_REPEAT_DAYS=%d, MAX_REMINDERS=%d",
        REMINDER_REPEAT_DAYS, MAX_REMINDERS_BEFORE_ESCALATION,
    )

    app = _create_flask_app()

    reminder_summary = run_reminders(app)
    escalation_summary = run_escalations(app)

    total_sent = reminder_summary["reminders_sent"] + escalation_summary["escalations_triggered"]
    logger.info(
        "Service complete. Reminders sent: %d, Escalations: %d",
        reminder_summary["reminders_sent"],
        escalation_summary["escalations_triggered"],
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
