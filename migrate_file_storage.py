"""
Migrate file storage from old flat structure to RFPO-number-based folder structure.

OLD structure:
  uploads/rfpo_files/rfpo_{db_id}/{uuid}_{filename}
  uploads/snapshots/{uuid12}_{rfpo_id}.pdf

NEW structure:
  uploads/rfpos/{rfpo_id}/documents/{uuid}_{filename}
  uploads/rfpos/{rfpo_id}/snapshots/{timestamp}_snapshot.pdf

This script:
1. Moves uploaded files from rfpo_files/rfpo_{id}/ to rfpos/{rfpo_id}/documents/
2. Moves snapshots from snapshots/ to rfpos/{rfpo_id}/snapshots/
3. Updates UploadedFile.file_path and RFPO.pdf_snapshot_path in the database
4. Preserves old directories until manual cleanup

Usage:
  python migrate_file_storage.py              # Dry run (default)
  python migrate_file_storage.py --execute    # Actually move files and update DB
"""

import os
import sys
import shutil
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Bootstrap Flask app for DB access ────────────────────────────────────

sys.path.insert(0, os.path.dirname(__file__))
from env_config import get_database_url

from flask import Flask

app = Flask(__name__)
db_url = get_database_url()
# Fix relative SQLite paths to be absolute (relative to this script's directory)
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
    rel_path = db_url[len("sqlite:///"):]
    abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    db_url = f"sqlite:///{abs_path}"
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from models import (
    db, RFPO, UploadedFile, User, Consortium, Team, UserTeam, Project,
    Vendor, VendorSite, PDFPositioning, List, RFPOLineItem,
    RFPOApprovalWorkflow, RFPOApprovalStage, RFPOApprovalStep,
    RFPOApprovalInstance, RFPOApprovalAction, AuditLog,
)

db.init_app(app)


def migrate(dry_run=True):
    """Migrate files and DB paths from old to new structure."""
    prefix = "[DRY RUN] " if dry_run else ""
    moved_files = 0
    moved_snapshots = 0
    errors = 0

    with app.app_context():
        # ── 1. Migrate uploaded documents ────────────────────────────
        uploaded_files = UploadedFile.query.all()
        logger.info("Found %d UploadedFile records to check", len(uploaded_files))

        for uf in uploaded_files:
            old_path = uf.file_path  # e.g. uploads/rfpo_files/rfpo_3/uuid_file.pdf

            # Skip if already migrated (check both slash styles)
            normalized = old_path.replace("\\", "/") if old_path else ""
            if normalized.startswith("uploads/rfpos/"):
                continue

            # Look up the RFPO business ID
            rfpo = RFPO.query.get(uf.rfpo_id)
            if not rfpo:
                logger.warning("UploadedFile %s references missing RFPO id=%s, skipping", uf.file_id, uf.rfpo_id)
                errors += 1
                continue

            # Build new path (always use forward slashes for cross-platform consistency)
            new_dir = os.path.join("uploads", "rfpos", rfpo.rfpo_id, "documents")
            new_path = os.path.join(new_dir, uf.stored_filename)
            # Normalize to forward slashes (Linux containers)
            new_dir = new_dir.replace("\\", "/")
            new_path = new_path.replace("\\", "/")

            logger.info("%sMove: %s → %s", prefix, old_path, new_path)

            if not dry_run:
                try:
                    os.makedirs(new_dir, exist_ok=True)
                    if os.path.exists(old_path):
                        shutil.move(old_path, new_path)
                    elif os.path.exists(os.path.join(app.root_path, old_path)):
                        shutil.move(os.path.join(app.root_path, old_path), new_path)
                    else:
                        logger.warning("  Source file not found on disk: %s (updating DB path anyway)", old_path)

                    uf.file_path = new_path
                    moved_files += 1
                except Exception as e:
                    logger.error("  Failed to move %s: %s", old_path, e)
                    errors += 1
            else:
                moved_files += 1

        # ── 2. Migrate PDF snapshots ─────────────────────────────────
        rfpos_with_snapshots = RFPO.query.filter(RFPO.pdf_snapshot_path.isnot(None)).all()
        logger.info("Found %d RFPOs with PDF snapshots to check", len(rfpos_with_snapshots))

        for rfpo in rfpos_with_snapshots:
            old_snap = rfpo.pdf_snapshot_path  # e.g. uploads/snapshots/uuid12_RFPO-XXX.pdf

            # Skip if already migrated
            if old_snap and "rfpos/" in old_snap and "/snapshots/" in old_snap:
                continue

            old_filename = os.path.basename(old_snap)
            new_dir = os.path.join("uploads", "rfpos", rfpo.rfpo_id, "snapshots")
            # Normalize to forward slashes
            new_dir = new_dir.replace("\\", "/")
            # Keep original filename to avoid breaking anything
            new_snap_path = f"{new_dir}/{old_filename}"
            new_relative = f"uploads/rfpos/{rfpo.rfpo_id}/snapshots/{old_filename}"

            logger.info("%sSnapshot: %s → %s", prefix, old_snap, new_relative)

            if not dry_run:
                try:
                    os.makedirs(new_dir, exist_ok=True)

                    # Try relative and absolute paths
                    abs_old = old_snap
                    if not os.path.isabs(old_snap):
                        abs_old = os.path.join(app.root_path, old_snap)

                    if os.path.exists(abs_old):
                        shutil.move(abs_old, new_snap_path)
                    elif os.path.exists(old_snap):
                        shutil.move(old_snap, new_snap_path)
                    else:
                        logger.warning("  Snapshot file not found on disk: %s (updating DB path anyway)", old_snap)

                    rfpo.pdf_snapshot_path = new_relative
                    moved_snapshots += 1
                except Exception as e:
                    logger.error("  Failed to move snapshot %s: %s", old_snap, e)
                    errors += 1
            else:
                moved_snapshots += 1

        # ── 3. Commit DB changes ─────────────────────────────────────
        if not dry_run:
            db.session.commit()
            logger.info("Database paths updated and committed.")

    # ── Summary ──────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("%sMigration summary:", prefix)
    logger.info("  Documents to move: %d", moved_files)
    logger.info("  Snapshots to move: %d", moved_snapshots)
    logger.info("  Errors: %d", errors)
    if dry_run:
        logger.info("Run with --execute to apply changes.")
    else:
        logger.info("Migration complete. Old directories can be cleaned up manually.")
        logger.info("  rm -rf uploads/rfpo_files/")
        logger.info("  rm -rf uploads/snapshots/")


if __name__ == "__main__":
    execute = "--execute" in sys.argv
    if execute:
        logger.info("Running migration in EXECUTE mode — files will be moved and DB updated.")
    else:
        logger.info("Running migration in DRY RUN mode — no changes will be made.")
    migrate(dry_run=not execute)
