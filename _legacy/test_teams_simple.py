#!/usr/bin/env python3
"""
Simple test app for team functionality
"""
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_teams.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    abbrev = db.Column(db.String(32), nullable=False)
    consortium_id = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'abbrev': self.abbrev,
            'consortium_id': self.consortium_id,
            'active': self.active,
            'viewer_user_ids': [],
            'limited_admin_user_ids': []
        }

@app.route('/api/teams', methods=['GET'])
def test_teams():
    """Simple teams endpoint for testing"""
    try:
        teams = Team.query.all()
        return jsonify([team.to_dict() for team in teams])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teams', methods=['POST'])
def create_test_team():
    """Create a test team"""
    try:
        data = request.get_json()
        team = Team(
            name=data['name'],
            abbrev=data['abbrev'],
            consortium_id=data.get('consortium_id', 1),
            active=data.get('active', True)
        )
        db.session.add(team)
        db.session.commit()
        return jsonify(team.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created")

        # Create a test team if none exist
        if Team.query.count() == 0:
            test_team = Team(
                name='Test Team',
                abbrev='TT',
                consortium_id=1,
                active=True
            )
            db.session.add(test_team)
            db.session.commit()
            print("Test team created")

    print("Starting test Flask app on port 5001...")
    app.run(debug=True, port=5001)
