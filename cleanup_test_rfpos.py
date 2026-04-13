"""
Cleanup script — Deletes test RFPOs tied to the Splendor Analytics vendor
and all related records, including Azure Blob Storage objects.

Usage:
    python cleanup_test_rfpos.py                  # Dry run (default)
    python cleanup_test_rfpos.py --execute        # Delete with confirmation prompt
    python cleanup_test_rfpos.py --execute --yes  # Delete without confirmation

Requires AZURE_DATABASE_URL in .env (PostgreSQL) or DATABASE_URL override.
Azure blob cleanup requires AZURE_STORAGE_ACCOUNT_URL and AZURE_CONTAINER_NAME
(or AZURE_STORAGE_ACCOUNT_KEY) in .env.
"""

import os
import sys

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import text

load_dotenv()

# ── Azure Blob Storage ──────────────────────────────────────────────────────
AZURE_STORAGE_ACCOUNT_URL = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
AZURE_STORAGE_ACCOUNT_KEY = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
AZURE_CONTAINER_NAME = os.environ.get("AZURE_CONTAINER_NAME", "usabc-uploads-stage")

# ── Configuration ────────────────────────────────────────────────────────────
VENDOR_NAME = "Splendor"  # Will match via ILIKE '%Splendor%'
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Prefer AZURE_DATABASE_URL, then DATABASE_URL
db_url = os.environ.get("AZURE_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not db_url or "postgresql" not in db_url:
    print("ERROR: No PostgreSQL connection string found.")
    print("       Set AZURE_DATABASE_URL or DATABASE_URL in .env or environment.")
    sys.exit(1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from models import (
    RFPO, Vendor, RFPOLineItem, UploadedFile,
    RFPOApprovalInstance, RFPOApprovalAction,
    AuditLog, Notification, EmailLog, AIUsageLog, db,
)

db.init_app(app)

DRY_RUN = "--execute" not in sys.argv
SKIP_CONFIRM = "--yes" in sys.argv


def get_blob_container_client():
    """Create Azure Blob container client if credentials are available."""
    if not AZURE_STORAGE_ACCOUNT_URL:
        return None
    try:
        from azure.storage.blob import BlobServiceClient
        if AZURE_STORAGE_ACCOUNT_KEY:
            blob_service = BlobServiceClient(
                account_url=AZURE_STORAGE_ACCOUNT_URL,
                credential=AZURE_STORAGE_ACCOUNT_KEY,
            )
        else:
            from azure.identity import DefaultAzureCredential
            blob_service = BlobServiceClient(
                account_url=AZURE_STORAGE_ACCOUNT_URL,
                credential=DefaultAzureCredential(),
            )
        return blob_service.get_container_client(AZURE_CONTAINER_NAME)
    except Exception as e:
        print(f"WARNING: Could not connect to Azure Blob Storage: {e}")
        return None


def list_blobs_for_rfpos(container_client, rfpo_id_strings):
    """List all blobs under rfpo/{rfpo_id}/ for each target RFPO."""
    blobs = []
    for rfpo_id_str in rfpo_id_strings:
        prefix = f"rfpo/{rfpo_id_str}/"
        try:
            for blob in container_client.list_blobs(name_starts_with=prefix):
                blobs.append(blob.name)
        except Exception as e:
            print(f"  WARNING: Error listing blobs for prefix '{prefix}': {e}")
    return blobs


def delete_blobs(container_client, blob_names):
    """Delete blobs from Azure storage. Returns count of successfully deleted."""
    deleted = 0
    for name in blob_names:
        try:
            container_client.delete_blob(name)
            deleted += 1
        except Exception as e:
            print(f"  WARNING: Failed to delete blob '{name}': {e}")
    return deleted


def run_cleanup():
    with app.app_context():
        # ── Step 1: Find vendor ──────────────────────────────────────────
        vendors = Vendor.query.filter(
            Vendor.company_name.ilike(f"%{VENDOR_NAME}%")
        ).all()
        if not vendors:
            print(f"No vendor matching '{VENDOR_NAME}' found. Nothing to do.")
            return

        vendor_ids = [v.id for v in vendors]
        print(f"Matched vendor(s): {', '.join(v.company_name for v in vendors)}")

        # ── Step 2: Find target RFPOs ────────────────────────────────────
        rfpos = RFPO.query.filter(RFPO.vendor_id.in_(vendor_ids)).all()
        if not rfpos:
            print("No RFPOs found for this vendor. Nothing to do.")
            return

        rfpo_ids = [r.id for r in rfpos]
        rfpo_id_strs = [str(r.id) for r in rfpos]
        rfpo_display_ids = [r.rfpo_id for r in rfpos]

        print(f"\n{'DRY RUN — no changes will be made' if DRY_RUN else 'EXECUTING CLEANUP'}")
        print(f"{'=' * 60}")
        print(f"RFPOs to delete: {len(rfpos)}")
        for r in rfpos:
            print(f"  [{r.id:>3}] {r.rfpo_id} — {r.title} ({r.status})")

        # ── Step 3: Count affected records ───────────────────────────────
        line_items_count = RFPOLineItem.query.filter(
            RFPOLineItem.rfpo_id.in_(rfpo_ids)
        ).count()

        files_count = UploadedFile.query.filter(
            UploadedFile.rfpo_id.in_(rfpo_ids)
        ).count()

        instances = RFPOApprovalInstance.query.filter(
            RFPOApprovalInstance.rfpo_id.in_(rfpo_ids)
        ).all()
        instance_ids = [i.id for i in instances]

        actions_count = (
            RFPOApprovalAction.query.filter(
                RFPOApprovalAction.instance_id.in_(instance_ids)
            ).count()
            if instance_ids
            else 0
        )

        audit_count = AuditLog.query.filter(
            AuditLog.entity_type == "rfpo",
            AuditLog.entity_id.in_(rfpo_id_strs),
        ).count()

        notif_count = Notification.query.filter(
            Notification.entity_type == "rfpo",
            Notification.entity_id.in_(rfpo_id_strs),
        ).count()

        email_count = EmailLog.query.filter(
            EmailLog.rfpo_id.in_(rfpo_ids)
        ).count()

        ai_count = AIUsageLog.query.filter(
            AIUsageLog.rfpo_id.in_(rfpo_ids)
        ).count()

        # ── Azure Blob Storage scan ──────────────────────────────────────
        container_client = get_blob_container_client()
        blob_names = []
        if container_client:
            print("\nScanning Azure Blob Storage...")
            blob_names = list_blobs_for_rfpos(container_client, rfpo_display_ids)
            print(f"  Found {len(blob_names)} blob(s) across {len(rfpo_display_ids)} RFPO prefixes")
        else:
            print("\nAzure Blob Storage not configured — skipping blob cleanup")

        print(f"\n{'WOULD DELETE' if DRY_RUN else 'DELETING'}:")
        print(f"  Azure Blobs:         {len(blob_names)}")
        print(f"  Approval Actions:    {actions_count}")
        print(f"  Approval Instances:  {len(instances)}")
        print(f"  Line Items:          {line_items_count}")
        print(f"  Uploaded Files:      {files_count}")
        print(f"  Audit Logs:          {audit_count}")
        print(f"  Notifications:       {notif_count}")
        print(f"  Email Logs:          {email_count} (SET rfpo_id = NULL)")
        print(f"  AI Usage Logs:       {ai_count} (SET rfpo_id = NULL)")
        print(f"  RFPOs:               {len(rfpos)}")

        if DRY_RUN:
            if blob_names:
                print(f"\n  Sample blobs (first 10):")
                for b in blob_names[:10]:
                    print(f"    {b}")
                if len(blob_names) > 10:
                    print(f"    ... and {len(blob_names) - 10} more")
            print(f"\n{'=' * 60}")
            print("DRY RUN complete. No records were modified.")
            print("Run with --execute to perform the cleanup.")
            return

        # ── Confirmation prompt ──────────────────────────────────────────
        if not SKIP_CONFIRM:
            total = len(rfpos) + actions_count + len(instances) + line_items_count + files_count + audit_count + notif_count + len(blob_names)
            answer = input(f"\nAbout to delete {total} records + unlink {email_count + ai_count} logs. Continue? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted.")
                return

        # ── Step 4: Execute cleanup ──────────────────────────────────────
        # Delete blobs FIRST (before DB records are gone)
        if blob_names and container_client:
            print("\nDeleting Azure blobs...")
            deleted_blobs = delete_blobs(container_client, blob_names)
            print(f"  ✓ Deleted {deleted_blobs}/{len(blob_names)} blobs from Azure Storage")

        try:
            # Deepest children first
            if instance_ids:
                RFPOApprovalAction.query.filter(
                    RFPOApprovalAction.instance_id.in_(instance_ids)
                ).delete(synchronize_session=False)
                print(f"  ✓ Deleted {actions_count} approval actions")

            RFPOApprovalInstance.query.filter(
                RFPOApprovalInstance.rfpo_id.in_(rfpo_ids)
            ).delete(synchronize_session=False)
            print(f"  ✓ Deleted {len(instances)} approval instances")

            RFPOLineItem.query.filter(
                RFPOLineItem.rfpo_id.in_(rfpo_ids)
            ).delete(synchronize_session=False)
            print(f"  ✓ Deleted {line_items_count} line items")

            UploadedFile.query.filter(
                UploadedFile.rfpo_id.in_(rfpo_ids)
            ).delete(synchronize_session=False)
            print(f"  ✓ Deleted {files_count} uploaded file records")

            # Soft-reference tables: delete audit logs and notifications
            AuditLog.query.filter(
                AuditLog.entity_type == "rfpo",
                AuditLog.entity_id.in_(rfpo_id_strs),
            ).delete(synchronize_session=False)
            print(f"  ✓ Deleted {audit_count} audit logs")

            Notification.query.filter(
                Notification.entity_type == "rfpo",
                Notification.entity_id.in_(rfpo_id_strs),
            ).delete(synchronize_session=False)
            print(f"  ✓ Deleted {notif_count} notifications")

            # SET NULL on logs (preserve email/AI log history, just unlink)
            EmailLog.query.filter(
                EmailLog.rfpo_id.in_(rfpo_ids)
            ).update({EmailLog.rfpo_id: None}, synchronize_session=False)
            print(f"  ✓ Unlinked {email_count} email logs")

            AIUsageLog.query.filter(
                AIUsageLog.rfpo_id.in_(rfpo_ids)
            ).update({AIUsageLog.rfpo_id: None}, synchronize_session=False)
            print(f"  ✓ Unlinked {ai_count} AI usage logs")

            # Finally, delete the RFPOs themselves
            RFPO.query.filter(
                RFPO.id.in_(rfpo_ids)
            ).delete(synchronize_session=False)
            print(f"  ✓ Deleted {len(rfpos)} RFPOs")

            db.session.commit()
            print(f"\n{'=' * 60}")
            print(f"CLEANUP COMPLETE — {len(rfpos)} test RFPOs and all related records removed.")

        except Exception as e:
            db.session.rollback()
            print(f"\nERROR — Transaction rolled back. No data was changed.")
            print(f"  {e}")
            sys.exit(1)


if __name__ == "__main__":
    run_cleanup()
