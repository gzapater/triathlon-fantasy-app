import json
from datetime import datetime
from backend.models import User, Race, RaceFormat, Role, db # Adjusted import path

class TestDashboardView:

    def test_race_object_serialization(self, client, new_user, new_race_format):
        """
        Tests the to_dict() method of the Race model and its JSON serializability.
        """
        # Ensure new_user and new_race_format are committed and have IDs
        db.session.add(new_user)
        db.session.add(new_race_format)
        db.session.commit()

        race = Race(
            title="Test Race Serialization",
            description="Testing to_dict.",
            race_format_id=new_race_format.id,
            event_date=datetime(2024, 8, 15, 10, 0, 0),
            location="Test Location",
            promo_image_url="http://example.com/image.png",
            category="Elite",
            gender_category="MIXED",
            user_id=new_user.id,
            is_general=True,
            created_at=datetime(2024, 7, 1, 12, 0, 0),
            updated_at=datetime(2024, 7, 2, 12, 0, 0)
        )
        db.session.add(race)
        db.session.commit()

        race_dict = race.to_dict()

        assert race_dict['id'] == race.id
        assert race_dict['title'] == "Test Race Serialization"
        assert race_dict['description'] == "Testing to_dict."
        assert race_dict['race_format_name'] == new_race_format.name
        assert race_dict['event_date'] == "2024-08-15T10:00:00"
        assert race_dict['location'] == "Test Location"
        assert race_dict['promo_image_url'] == "http://example.com/image.png"
        assert race_dict['category'] == "Elite"
        assert race_dict['gender_category'] == "MIXED"
        assert race_dict['user_username'] == new_user.username
        assert race_dict['is_general'] is True
        assert race_dict['created_at'] == "2024-07-01T12:00:00"
        assert race_dict['updated_at'] == "2024-07-02T12:00:00"

        # Test conditional fields for None (if related objects don't exist)
        race_no_relations = Race(
            title="Test Race No Relations",
            event_date=datetime(2025, 1, 1),
            gender_category="FEMALE_ONLY",
            # No race_format_id, no user_id purposefully
        )
        # Temporarily remove user and race_format for this specific test case if they were auto-assigned
        # Or create a new race instance that truly has no relations.
        # For this example, assuming direct instantiation without auto-relations from fixtures for these fields.
        # If user_id and race_format_id are nullable and not set, they should be None.
        # However, current Race model has user_id and race_format_id as nullable=False.
        # So, we'll test with existing relations for now, as per current model constraints.
        # A more robust test would involve a race where race.user or race.race_format is None,
        # if the model allowed it. Given the constraints, these will always be present.

        # Test JSON serialization
        try:
            json_output = json.dumps(race_dict)
            assert isinstance(json_output, str)
        except TypeError:
            pytest.fail("Race.to_dict() output is not JSON serializable")


    def test_admin_dashboard_with_races(self, client, new_admin_user, new_race_format):
        """
        Tests that the admin dashboard loads correctly and race objects are serialized
        without causing a TypeError.
        """
        # Ensure admin user and race format are committed
        db.session.add(new_admin_user)
        db.session.add(new_race_format)
        db.session.commit()

        # Create a couple of races
        race1 = Race(
            title="Admin General Race",
            race_format_id=new_race_format.id,
            event_date=datetime(2024, 9, 1),
            gender_category="MIXED",
            user_id=new_admin_user.id,
            is_general=True
        )
        race2 = Race(
            title="Admin Local Race",
            race_format_id=new_race_format.id,
            event_date=datetime(2024, 9, 15),
            gender_category="MALE_ONLY",
            user_id=new_admin_user.id,
            is_general=False # This one is not general
        )
        db.session.add_all([race1, race2])
        db.session.commit()

        # Log in the admin user
        login_resp = client.post('/api/login', json={
            'username': new_admin_user.username,
            'password': 'adminpassword' # Assuming 'adminpassword' from fixture example
        })
        assert login_resp.status_code == 200

        # Make a GET request to the dashboard
        dashboard_resp = client.get('/Hello-world')
        assert dashboard_resp.status_code == 200

        response_data_text = dashboard_resp.get_data(as_text=True)

        # Check for a string that indicates successful rendering of the page
        # (e.g., something from the template that appears after race lists)
        assert "</footer>" in response_data_text, "The page did not render completely, possibly due to a serialization error before this point."

        # More specific check: ensure our race titles appear (if they are supposed to be on the admin dashboard)
        # Admin dashboard shows general races in the main list.
        assert "Admin General Race" in response_data_text
        # Admin dashboard also has a dropdown for "Official Answers" which should list ALL races.
        # So, "Admin Local Race" should appear there.
        # A more robust check would parse the HTML, but string checking is a good first step.
        # For now, the absence of "TypeError: Object of type Race is not JSON serializable" is implicitly tested
        # by the page rendering successfully up to "</footer>".
        # If that error occurred, Flask would likely return a 500 error or a different page.
        assert "TypeError: Object of type Race is not JSON serializable" not in response_data_text

        # Check if the non-general race title is present (likely in the official answers dropdown)
        assert "Admin Local Race" in response_data_text
```
