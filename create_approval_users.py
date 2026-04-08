"""
Create user accounts for RFPO approval workflow members.
Uncertain/guessed emails are prefixed with '#'.
"""
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash

# Bootstrap Flask app context
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from env_config import get_database_url, get_secret_key
from models import db, User
from flask import Flask


AZURE_DB_URL = (
    "postgresql://rfpoadmin:RfpoSecure123!"
    "@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require"
)


def create_app(use_azure=False):
    app = Flask(__name__)
    if use_azure:
        db_url = AZURE_DB_URL
        print(f"Connecting to AZURE PostgreSQL...")
    else:
        db_url = get_database_url()
        # Convert relative SQLite path to absolute
        if db_url.startswith('sqlite:///') and not db_url.startswith('sqlite:////'):
            rel_path = db_url.replace('sqlite:///', '')
            abs_path = os.path.join(os.path.dirname(__file__), rel_path)
            db_url = f'sqlite:///{abs_path}'
        print(f"Connecting to local database...")
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = get_secret_key('FLASK_SECRET_KEY')
    db.init_app(app)
    return app


# Default password for new accounts - users should change on first login
DEFAULT_PASSWORD = "ChangeMeNow2026!"

USERS = [
    # Technical Approval
    {"fullname": "Hong Jiang", "email": "hjiang@ford.com", "company": "Ford", "company_code": "FRD"},
    {"fullname": "Azadeh Narimissa", "email": "azadeh.narimissa@gm.com", "company": "General Motors", "company_code": "GM"},
    {"fullname": "Mark Levine", "email": "mark.levine@stellantis.com", "company": "FCA US LLC", "company_code": "FCA"},

    # Technical Leadership Council
    {"fullname": "Halim Santoso", "email": "halim.santoso@stellantis.com", "company": "FCA US LLC", "company_code": "FCA"},
    {"fullname": "Sanjeev M Naik", "email": "sanjeev.m.naik@gm.com", "company": "General Motors", "company_code": "GM"},
    {"fullname": "Tom McCarthy", "email": "tmccart3@ford.com", "company": "Ford", "company_code": "FRD"},

    # Finance Approval - primaries
    {"fullname": "Diana Zielonka", "email": "diana.zielonka@stellantis.com", "company": "FCA US LLC", "company_code": "FCA"},
    {"fullname": "Gabriela Grajales", "email": "ggrajale@ford.com", "company": "Ford", "company_code": "FRD"},
    {"fullname": "George Faux", "email": "aina.faux@gm.com", "company": "General Motors", "company_code": "GM"},

    # Finance Approval - backups (emails uncertain, prefixed with #)
    {"fullname": "David Pollock", "email": "#david.pollock@stellantis.com", "company": "FCA US LLC", "company_code": "FCA"},
    {"fullname": "Cynthia Flanigan", "email": "#cynthia.flanigan@ford.com", "company": "Ford", "company_code": "FRD"},
    {"fullname": "Paul Krajewski", "email": "#paul.krajewski@gm.com", "company": "General Motors", "company_code": "GM"},

    # USCAR Internal Approval
    {"fullname": "Chuck Gough", "email": "cgough@uscar.org", "company": "USCAR", "company_code": "USC"},
    {"fullname": "Steve Przesmitzki", "email": "#sprzesmitzki@uscar.org", "company": "USCAR", "company_code": "USC"},

    # PO Release Approval
    {"fullname": "Karin Darovitz", "email": "kdarovitz@doeren.com", "company": "Doeren Mayhew", "company_code": "DOE"},
    {"fullname": "Nadette Bullington", "email": "#nbullington@doeren.com", "company": "Doeren Mayhew", "company_code": "DOE"},
]


def main(use_azure=False):
    app = create_app(use_azure=use_azure)
    with app.app_context():
        created = []
        skipped = []

        for u in USERS:
            existing = User.query.filter_by(email=u["email"]).first()
            if existing:
                skipped.append(f"  SKIP: {u['fullname']} ({u['email']}) - already exists (id={existing.id})")
                continue

            user = User(
                record_id=str(uuid.uuid4())[:8].upper(),
                fullname=u["fullname"],
                email=u["email"],
                password_hash=generate_password_hash(DEFAULT_PASSWORD),
                company=u["company"],
                company_code=u["company_code"],
                active=True,
                is_approver=True,
                created_at=datetime.utcnow(),
                created_by="admin@rfpo.com",
            )
            user.set_permissions(["RFPO_USER"])

            db.session.add(user)
            created.append(f"  ADD:  {u['fullname']} ({u['email']}) - {u['company']}")

        if created:
            db.session.commit()

        print(f"\n=== User Creation Results ===")
        print(f"Created: {len(created)}")
        for c in created:
            print(c)
        if skipped:
            print(f"\nSkipped: {len(skipped)}")
            for s in skipped:
                print(s)
        print(f"\nDefault password: {DEFAULT_PASSWORD}")
        print("NOTE: Emails starting with '#' are unverified guesses - update before use.\n")


if __name__ == "__main__":
    use_azure = "--azure" in sys.argv
    main(use_azure=use_azure)
