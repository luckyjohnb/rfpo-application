#!/usr/bin/env python3
"""
Simple team management verification test
"""
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from models import db, Team
        from app import app
        print("✅ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_database_creation():
    """Test database table creation"""
    try:
        from models import db, Team
        from app import app

        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")

            # Test that we can query the teams table
            teams_count = Team.query.count()
            print(f"✅ Teams table operational. Current teams: {teams_count}")

            return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_team_model():
    """Test the Team model functionality"""
    try:
        from models import db, Team
        from app import app

        with app.app_context():
            # Create a test team
            test_team = Team(
                name="Test Team",
                abbrev="TT",
                consortium_id=1,
                description="A test team for verification",
                viewer_user_ids="user1,user2",
                limited_admin_user_ids="admin1",
                active=True
            )

            # Add to database
            db.session.add(test_team)
            db.session.commit()

            print("✅ Test team created successfully")

            # Test the to_dict method
            team_dict = test_team.to_dict()
            expected_keys = ['id', 'name', 'abbrev', 'consortium_id', 'viewer_user_ids', 'limited_admin_user_ids', 'active']
            if all(key in team_dict for key in expected_keys):
                print("✅ Team to_dict() method working correctly")
            else:
                print("❌ Team to_dict() method missing keys")
                return False

            # Verify the team can be retrieved
            retrieved_team = Team.query.filter_by(name="Test Team").first()
            if retrieved_team and retrieved_team.abbrev == "TT":
                print("✅ Team retrieval working correctly")
            else:
                print("❌ Team retrieval failed")
                return False

            # Clean up - delete the test team
            db.session.delete(test_team)
            db.session.commit()
            print("✅ Test cleanup completed")

            return True
    except Exception as e:
        print(f"❌ Team model test error: {e}")
        return False

def test_api_routes():
    """Test that API routes are properly registered"""
    try:
        from app import app

        # Get all registered routes
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(rule.rule)

        # Check for team API routes
        expected_routes = [
            '/api/teams',
            '/api/teams/<int:team_id>',
            '/api/teams/<int:team_id>/activate',
            '/api/teams/<int:team_id>/deactivate'
        ]

        missing_routes = []
        for route in expected_routes:
            if route not in routes:
                missing_routes.append(route)

        if not missing_routes:
            print("✅ All team API routes registered correctly")
            return True
        else:
            print(f"❌ Missing routes: {missing_routes}")
            return False

    except Exception as e:
        print(f"❌ Route test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Team Management Verification Tests")
    print("=" * 50)

    tests = [
        ("Import Test", test_imports),
        ("Database Creation Test", test_database_creation),
        ("Team Model Test", test_team_model),
        ("API Routes Test", test_api_routes)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")

    print("\n" + "=" * 50)
    print(f"🏁 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Team management functionality is ready!")
        return True
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
