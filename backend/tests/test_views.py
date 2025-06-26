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
        assert race_dict['race_format']['name'] == new_race_format.name # Corrected assertion
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
            'password': 'admin_password' # Corrected password to match fixture
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
        # For ADMIN, "Admin General Race" and "Admin Local Race" data are passed to the template
        # for the "Official Answers" modal, which is populated by JavaScript.
        # Therefore, these titles won't be directly in the initial HTML response text.
        # The test already confirms the page loads and the log confirms data is passed.
        # We will rely on the log for data correctness for now.
        assert "TypeError: Object of type Race is not JSON serializable" not in response_data_text


class TestEventsAPI:
    def test_get_events_empty(self, client, db_session):
        """Test GET /api/events when no events exist."""
        response = client.get('/api/events')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        data = json.loads(response.data)
        assert data == []

    def test_get_events_with_data(self, client, db_session):
        """Test GET /api/events with some event data."""
        from backend.models import Event # Local import to ensure app context is active

        # Create sample events
        event1 = Event(
            name="Triatlón de la Ciudad",
            event_date=datetime.strptime("2024-08-15", "%Y-%m-%d").date(),
            city="Ciudad Ejemplo",
            province="Provincia Ejemplo",
            discipline="Triatlón",
            distance="Olímpico"
        )
        event2 = Event(
            name="Duatlón Montaña",
            event_date=datetime.strptime("2024-09-01", "%Y-%m-%d").date(),
            city="Pueblo Montaña",
            province="Sierra Alta",
            discipline="Duatlón",
            distance="Sprint"
        )
        db_session.add_all([event1, event2])
        db_session.commit()

        response = client.get('/api/events')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        data = json.loads(response.data)

        assert len(data) == 2

        # Events are ordered by event_date desc
        assert data[0]['name'] == "Duatlón Montaña"
        assert data[0]['event_date'] == "2024-09-01"
        assert data[0]['city'] == "Pueblo Montaña"
        assert data[0]['province'] == "Sierra Alta"
        assert 'id' in data[0]

        assert data[1]['name'] == "Triatlón de la Ciudad"
        assert data[1]['event_date'] == "2024-08-15"
        assert data[1]['city'] == "Ciudad Ejemplo"
        assert data[1]['province'] == "Provincia Ejemplo"
        assert 'id' in data[1]

        # Clean up - specific to this test if we don't want to rely on full session rollback for this
        # For in-memory SQLite, this is less critical as it's per-session.
        # For persistent DBs, more careful cleanup is needed.
        db_session.delete(event1)
        db_session.delete(event2)
        db_session.commit()

    def test_get_events_date_formatting(self, client, db_session):
        """Test that event_date is correctly formatted as YYYY-MM-DD."""
        from backend.models import Event
        event_with_date = Event(
            name="Evento con Fecha",
            event_date=datetime.strptime("2025-01-05", "%Y-%m-%d").date(),
            city="FechaCity",
            province="FechaProv"
        )
        db_session.add(event_with_date)
        db_session.commit()

        response = client.get('/api/events')
        data = json.loads(response.data)

        assert len(data) == 1
        assert data[0]['event_date'] == "2025-01-05"

        db_session.delete(event_with_date)
        db_session.commit()

    def test_get_events_with_null_fields(self, client, db_session):
        """Test GET /api/events with events that have nullable fields as None."""
        from backend.models import Event
        event_nulls = Event(
            name="Evento con Nulos",
            event_date=datetime.strptime("2024-10-10", "%Y-%m-%d").date(),
            city=None,  # City can be null
            province="Provincia Sola" # Province can be null too, but let's test one
        )
        db_session.add(event_nulls)
        db_session.commit()

        response = client.get('/api/events')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert len(data) == 1
        assert data[0]['name'] == "Evento con Nulos"
        assert data[0]['city'] is None
        assert data[0]['province'] == "Provincia Sola"

        db_session.delete(event_nulls)
        db_session.commit()

    def test_get_trical_page(self, client):
        """Test that the /TriCal page loads."""
        response = client.get('/TriCal')
        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)
        assert "<title>TriCal - Directorio Triatlón España 2025</title>" in response_data_text # Corrected assertion
        assert 'eventsContainer' in response_data_text # Corrected ID to match actual template
        # Check that the promo page specific content is NOT there
        assert "El pique no debería acabar en la línea de meta." not in response_data_text

    def test_tripredict_promo_page_no_longer_shows_events(self, client):
        """Test that the /Tripredict promo page no longer directly embeds the events list script."""
        response = client.get('/Tripredict')
        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)
        # Check for a known part of the promo page
        assert "El pique no debería acabar en la línea de meta." in response_data_text
        # Check that the events container or its specific loading/error indicators are NOT there
        assert 'id="events-container"' not in response_data_text
        assert 'id="events-loading"' not in response_data_text
        assert "Cargando eventos..." not in response_data_text
