from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    abbrev = db.Column(db.String(32), nullable=False, unique=True)
    consortium_id = db.Column(db.Integer, nullable=False)
    viewer_user_ids = db.Column(db.Text)  # Comma-separated user IDs
    limited_admin_user_ids = db.Column(db.Text)  # Comma-separated user IDs
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))

    __table_args__ = (
        db.UniqueConstraint('name', 'consortium_id', name='uq_team_name_consortium'),
        db.UniqueConstraint('abbrev', 'consortium_id', name='uq_team_abbrev_consortium'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'abbrev': self.abbrev,
            'consortium_id': self.consortium_id,
            'viewer_user_ids': self.viewer_user_ids.split(',') if self.viewer_user_ids else [],
            'limited_admin_user_ids': self.limited_admin_user_ids.split(',') if self.limited_admin_user_ids else [],
            'active': self.active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
        }
