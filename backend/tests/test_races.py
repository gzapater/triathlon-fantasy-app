import pytest
from backend.models import db, User, Role, Race, RaceFormat, Segment, RaceSegmentDetail
from datetime import datetime

# --- Model Tests ---

def test_create_race_format(db_session):
    fmt = RaceFormat(name="Ultra Marathon")
    db_session.add(fmt)
    db_session.commit()
    assert fmt.id is not None
    assert RaceFormat.query.filter_by(name="Ultra Marathon").first() is not None

def test_create_segment(db_session):
    seg = Segment(name="Trail Running")
    db_session.add(seg)
    db_session.commit()
    assert seg.id is not None
    assert Segment.query.filter_by(name="Trail Running").first() is not None

def test_create_race_and_segment_details(db_session, admin_user):
    # Get seeded formats and segments (assuming conftest seeded them)
    triathlon_format = RaceFormat.query.filter_by(name="Triatlón").first()
    natacion_segment = Segment.query.filter_by(name="Natación").first()
    ciclismo_segment = Segment.query.filter_by(name="Ciclismo").first()

    assert triathlon_format is not None, "Seeded 'Triatlón' RaceFormat not found"
    assert natacion_segment is not None, "Seeded 'Natación' Segment not found"
    assert ciclismo_segment is not None, "Seeded 'Ciclismo' Segment not found"

    race = Race(
        title="Test Race Event",
        description="A challenging race.",
        race_format_id=triathlon_format.id,
        event_date=datetime.strptime("2024-08-01", "%Y-%m-%d"),
        location="Test City",
        promo_image_url="http://example.com/image.png",
        category="Elite",
        gender_category="Ambos",
        user_id=admin_user.id
    )
    db_session.add(race)
    db_session.commit() # Commit to get race.id

    assert race.id is not None
    assert race.race_format == triathlon_format

    rsd1 = RaceSegmentDetail(race_id=race.id, segment_id=natacion_segment.id, distance_km=1.5)
    rsd2 = RaceSegmentDetail(race_id=race.id, segment_id=ciclismo_segment.id, distance_km=40)
    db_session.add_all([rsd1, rsd2])
    db_session.commit()

    assert len(race.segment_details) == 2
    assert rsd1 in race.segment_details
    assert rsd2 in race.segment_details
    assert rsd1.segment == natacion_segment
    assert rsd1.distance_km == 1.5

# --- API Endpoint Tests ---

# GET /api/race-formats
def test_get_race_formats(client, db_session): # db_session to ensure seeding
    response = client.get('/api/race-formats')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)

    # Check for seeded formats (names)
    expected_formats = ["Triatlón", "Duatlón", "Acuatlón"]
    response_format_names = [fmt['name'] for fmt in data]
    for fmt_name in expected_formats:
        assert fmt_name in response_format_names

    # Check structure of one item
    if data:
        assert 'id' in data[0]
        assert 'name' in data[0]

# POST /api/races tests will be added next
# For now, let's ensure this file is created and these initial tests can run.

# Placeholder for POST /api/races tests
def test_create_race_unauthenticated(client):
    race_data = {"title": "Insecure Race"} # Dummy data
    response = client.post('/api/races', json=race_data)
    # Flask-Login typically redirects to login page (302) or returns 401 if configured for APIs
    assert response.status_code in [401, 302]

def test_create_race_forbidden_for_player(authenticated_client):
    test_client, _ = authenticated_client("PLAYER") # Get client authenticated as PLAYER
    race_data = {
        "title": "Player's Race Attempt",
        "race_format_id": 1,
        "event_date": "2024-10-10",
        "gender_category": "Ambos",
        "segments": [{"segment_id": 1, "distance_km": 1}]
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 403
    data = response.get_json()
    assert "Forbidden" in data.get("message", "")

# More tests for POST /api/races will follow
# (successful creation, validation errors, etc.)

def test_create_race_success_league_admin(authenticated_client, db_session):
    test_client, league_admin = authenticated_client("LEAGUE_ADMIN")

    # Get IDs for seeded RaceFormat and Segments
    triatlon_format = RaceFormat.query.filter_by(name="Triatlón").first()
    natacion_segment = Segment.query.filter_by(name="Natación").first()
    ciclismo_segment = Segment.query.filter_by(name="Ciclismo").first()
    carrera_segment = Segment.query.filter_by(name="Carrera a pie").first()

    assert triatlon_format, "Triatlón format not found"
    assert natacion_segment, "Natación segment not found"
    assert ciclismo_segment, "Ciclismo segment not found"
    assert carrera_segment, "Carrera a pie segment not found"

    race_data = {
        "title": "Liga Admin's Grand Triathlon",
        "description": "A spectacular triathlon event organized by the league admin.",
        "race_format_id": triatlon_format.id,
        "event_date": "2025-01-15",
        "location": "Capital City",
        "promo_image_url": "http://example.com/tri_event.jpg",
        "gender_category": "Ambos",
        "segments": [
            {"segment_id": natacion_segment.id, "distance_km": 1.5},
            {"segment_id": ciclismo_segment.id, "distance_km": 40.0},
            {"segment_id": carrera_segment.id, "distance_km": 10.0}
        ]
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 201
    data = response.get_json()
    assert "race_id" in data

    # Verify in DB
    race_id = data['race_id']
    race_in_db = Race.query.get(race_id)
    assert race_in_db is not None
    assert race_in_db.title == race_data["title"]
    assert race_in_db.user_id == league_admin.id
    assert race_in_db.is_general is False # League Admin created races are always local
    assert race_in_db.category == "Elite" # Default
    assert len(race_in_db.segment_details) == 3

    # Check one segment detail
    detail_natacion = RaceSegmentDetail.query.filter_by(race_id=race_id, segment_id=natacion_segment.id).first()
    assert detail_natacion is not None
    assert detail_natacion.distance_km == 1.5


def test_create_race_success_admin(authenticated_client, db_session):
    test_client, admin = authenticated_client("ADMIN")

    duatlon_format = RaceFormat.query.filter_by(name="Duatlón").first()
    carrera_segment = Segment.query.filter_by(name="Carrera a pie").first()
    ciclismo_segment = Segment.query.filter_by(name="Ciclismo").first()

    assert duatlon_format, "Duatlón format not found"
    assert carrera_segment, "Carrera a pie segment not found"
    assert ciclismo_segment, "Ciclismo segment not found"

    race_data = {
        "title": "Admin's Duathlon Challenge",
        "race_format_id": duatlon_format.id,
        "event_date": "2025-02-20",
        "gender_category": "Masculino",
        "segments": [
            {"segment_id": carrera_segment.id, "distance_km": 5},
            {"segment_id": ciclismo_segment.id, "distance_km": 20},
            {"segment_id": carrera_segment.id, "distance_km": 2.5}
        ]
        # Optional fields omitted for this test
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 201
    data = response.get_json()
    assert "race_id" in data

    race_in_db = Race.query.get(data['race_id'])
    assert race_in_db is not None
    assert race_in_db.title == race_data["title"]
    assert race_in_db.user_id == admin.id
    assert race_in_db.is_general is False # Admin created races default to local if not specified
    assert len(race_in_db.segment_details) == 3

def test_create_race_admin_can_create_general_race(authenticated_client, db_session):
    test_client, admin = authenticated_client("ADMIN")

    triatlon_format = RaceFormat.query.filter_by(name="Triatlón").first()
    natacion_segment = Segment.query.filter_by(name="Natación").first()

    assert triatlon_format, "Triatlón format not found"
    assert natacion_segment, "Natación segment not found"

    race_data = {
        "title": "Admin's Public Grand Event",
        "description": "A major public event for all to see.",
        "race_format_id": triatlon_format.id,
        "event_date": "2025-03-20",
        "location": "Global City",
        "gender_category": "Ambos",
        "segments": [
            {"segment_id": natacion_segment.id, "distance_km": 3.8}
        ],
        "is_general": True # Explicitly set to True by Admin
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 201, f"Response data: {response.get_data(as_text=True)}"
    data = response.get_json()
    assert "race_id" in data

    race_in_db = Race.query.get(data['race_id'])
    assert race_in_db is not None
    assert race_in_db.title == race_data["title"]
    assert race_in_db.user_id == admin.id
    assert race_in_db.is_general is True # Key assertion for this test
    assert len(race_in_db.segment_details) == 1


# Validation Tests for POST /api/races
@pytest.mark.parametrize("missing_field", [
    "title", "race_format_id", "event_date", "gender_category", "segments"
])
def test_create_race_missing_required_fields(authenticated_client, missing_field):
    test_client, _ = authenticated_client("LEAGUE_ADMIN")
    triatlon_format = RaceFormat.query.filter_by(name="Triatlón").first()
    natacion_segment = Segment.query.filter_by(name="Natación").first()

    race_data = {
        "title": "Incomplete Race",
        "race_format_id": triatlon_format.id,
        "event_date": "2025-03-10",
        "gender_category": "Femenino",
        "segments": [{"segment_id": natacion_segment.id, "distance_km": 1.0}]
    }
    del race_data[missing_field] # Remove the field to be tested for missing

    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 400
    data = response.get_json()
    assert "Missing required fields" in data.get("message", "") or \
           f"Missing required fields: {missing_field}" in data.get("message", "")


def test_create_race_invalid_race_format_id(authenticated_client):
    test_client, _ = authenticated_client("LEAGUE_ADMIN")
    race_data = {
        "title": "Invalid Format Race",
        "race_format_id": 999, # Non-existent ID
        "event_date": "2025-04-01",
        "gender_category": "Ambos",
        "segments": [{"segment_id": 1, "distance_km": 1}]
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid race_format_id" in data.get("message", "")

def test_create_race_invalid_event_date_format(authenticated_client):
    test_client, _ = authenticated_client("LEAGUE_ADMIN")
    race_data = {
        "title": "Bad Date Race",
        "race_format_id": 1,
        "event_date": "01/05/2025", # Invalid format
        "gender_category": "Ambos",
        "segments": [{"segment_id": 1, "distance_km": 1}]
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid event_date format" in data.get("message", "")

def test_create_race_empty_segments_list(authenticated_client):
    test_client, _ = authenticated_client("LEAGUE_ADMIN")
    race_data = {
        "title": "No Segments Race",
        "race_format_id": 1,
        "event_date": "2025-06-01",
        "gender_category": "Ambos",
        "segments": [] # Empty list
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 400 # API expects non-empty list
    data = response.get_json()
    assert "Segments must be a non-empty list" in data.get("message", "")


def test_create_race_invalid_segment_id(authenticated_client):
    test_client, _ = authenticated_client("LEAGUE_ADMIN")
    race_data = {
        "title": "Invalid Segment ID Race",
        "race_format_id": 1,
        "event_date": "2025-07-01",
        "gender_category": "Ambos",
        "segments": [{"segment_id": 999, "distance_km": 10}] # Non-existent segment ID
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid segment_id" in data.get("message", "")

@pytest.mark.parametrize("invalid_distance", [-5, 0, "not_a_number"])
def test_create_race_invalid_segment_distance(authenticated_client, invalid_distance):
    test_client, _ = authenticated_client("LEAGUE_ADMIN")
    # Using a segment that is not a transition for the '0' distance test
    carrera_segment = Segment.query.filter_by(name="Carrera a pie").first()
    assert carrera_segment, "Carrera a pie segment not found for test"

    race_data = {
        "title": f"Invalid Distance Race (Dist: {invalid_distance})",
        "race_format_id": 1,
        "event_date": "2025-08-01",
        "gender_category": "Ambos",
        "segments": [{"segment_id": carrera_segment.id, "distance_km": invalid_distance}]
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 400
    data = response.get_json()
    if isinstance(invalid_distance, str):
        assert "Each segment's distance_km must be a non-negative number" in data.get("message", "") or \
               "distance_km for Carrera a pie must be a positive number" in data.get("message", "") # depending on how parsing fails
    elif invalid_distance <= 0 :
        assert "distance_km for Carrera a pie must be a positive number" in data.get("message", "")

def test_create_race_zero_distance_for_transition(authenticated_client, db_session):
    test_client, _ = authenticated_client("LEAGUE_ADMIN")
    triatlon_format = RaceFormat.query.filter_by(name="Triatlón").first()
    t1_segment = Segment.query.filter_by(name="Transición 1 (T1)").first()

    assert triatlon_format, "Triatlón format not found"
    assert t1_segment, "T1 segment not found"

    race_data = {
        "title": "Race with Zero Distance Transition",
        "race_format_id": triatlon_format.id,
        "event_date": "2025-08-15",
        "gender_category": "Ambos",
        "segments": [
            {"segment_id": t1_segment.id, "distance_km": 0} # Zero distance for transition
        ]
    }
    response = test_client.post('/api/races', json=race_data)
    assert response.status_code == 201 # Should be allowed
    data = response.get_json()
    assert "race_id" in data

    race_in_db = Race.query.get(data['race_id'])
    assert race_in_db is not None
    segment_detail = RaceSegmentDetail.query.filter_by(race_id=race_in_db.id, segment_id=t1_segment.id).first()
    assert segment_detail is not None
    assert segment_detail.distance_km == 0

# --- Tests for /Hello-world (index.html race display) ---

def test_hello_world_page_unauthenticated(client):
    response = client.get('/Hello-world')
    assert response.status_code == 302 # Should redirect to login

def test_hello_world_page_no_races(authenticated_client, db_session):
    test_client, _ = authenticated_client("PLAYER") # Any authenticated user

    # Ensure no races exist for this part of the test
    # This is tricky if other tests created races and db is not reset per test.
    # Assuming in-memory DB is clean per session, or specific cleanup for this test.
    # For now, we rely on the fact that no races are added by default for a fresh user.
    # A more robust way would be to explicitly delete all Race objects here.
    Race.query.delete() # Clear any existing races
    db_session.commit()

    response = test_client.get('/Hello-world')
    assert response.status_code == 200
    html_content = response.get_data(as_text=True)
    # The message for Admin dashboard (general races) is different from Player (general) or League Admin (local)
    # For a player with no general races:
    assert "No hay carreras públicas disponibles según los filtros aplicados." in html_content or \
           "No hay carreras destacadas por el momento." in html_content # Original message for player/index

    # Player shouldn't see "Crear Carrera" link
    assert "Crear Carrera" not in html_content

def test_dashboard_race_visibility(authenticated_client, db_session, new_user_factory):
    rf1 = RaceFormat.query.filter_by(name="Triatlón").first()
    if not rf1: # Ensure format exists
        rf1 = RaceFormat(name="Triatlón"); db_session.add(rf1); db_session.commit()

    admin_creator = new_user_factory("admin_creator", "admin_creator@test.com", "password", "ADMIN")
    la_creator1 = new_user_factory("la_creator1", "la_creator1@test.com", "password", "LEAGUE_ADMIN")
    la_creator2 = new_user_factory("la_creator2", "la_creator2@test.com", "password", "LEAGUE_ADMIN")

    # Create races
    general_race_by_admin = Race(title="General Race by Admin", race_format_id=rf1.id, event_date=datetime(2024, 7, 1),
                                 user_id=admin_creator.id, is_general=True, gender_category="Ambos", category="Elite")
    local_race_by_admin = Race(title="Local Race by Admin", race_format_id=rf1.id, event_date=datetime(2024, 7, 2),
                               user_id=admin_creator.id, is_general=False, gender_category="Ambos", category="Elite")
    local_race_by_la1 = Race(title="Local Race by LA1", race_format_id=rf1.id, event_date=datetime(2024, 7, 3),
                             user_id=la_creator1.id, is_general=False, gender_category="Ambos", category="Elite")
    local_race_by_la2 = Race(title="Local Race by LA2", race_format_id=rf1.id, event_date=datetime(2024, 7, 4),
                             user_id=la_creator2.id, is_general=False, gender_category="Ambos", category="Elite")

    db_session.add_all([general_race_by_admin, local_race_by_admin, local_race_by_la1, local_race_by_la2])
    db_session.commit()

    # Test as ADMIN user (using the one from authenticated_client, not necessarily admin_creator)
    admin_client, _ = authenticated_client("ADMIN")
    response_admin = admin_client.get('/Hello-world')
    assert response_admin.status_code == 200
    html_admin = response_admin.get_data(as_text=True)
    assert "General Race by Admin" in html_admin
    assert "Local Race by Admin" not in html_admin
    assert "Local Race by LA1" not in html_admin
    assert "Local Race by LA2" not in html_admin
    assert "Listado de Carreras Públicas" in html_admin # Title from admin_dashboard.html

    # Test as LEAGUE_ADMIN1 (la_creator1)
    # Need to log in as la_creator1 specifically
    la1_client, _ = authenticated_client(role_code=None) # Get client without auto-login
    login_resp_la1 = la1_client.post('/api/login', json={'username': 'la_creator1', 'password': 'password'})
    assert login_resp_la1.status_code == 200

    response_la1 = la1_client.get('/Hello-world')
    assert response_la1.status_code == 200
    html_la1 = response_la1.get_data(as_text=True)
    assert "Local Race by LA1" in html_la1
    assert "General Race by Admin" not in html_la1
    assert "Local Race by Admin" not in html_la1
    assert "Local Race by LA2" not in html_la1
    assert "Carreras Destacadas" in html_la1 # Title from index.html

    # Test as PLAYER user
    player_client, _ = authenticated_client("PLAYER")
    response_player = player_client.get('/Hello-world')
    assert response_player.status_code == 200
    html_player = response_player.get_data(as_text=True)
    assert "General Race by Admin" in html_player
    assert "Local Race by Admin" not in html_player
    assert "Local Race by LA1" not in html_player
    assert "Local Race by LA2" not in html_player
    # Player dashboard title might be different, e.g. "Próximas Carreras" or similar
    # For now, check "Crear Carrera" is not present
    assert "Crear Carrera" not in html_player


# --- Tests for conditional display of is_general checkbox ---

def test_admin_sees_is_general_checkbox_on_create_race_page(authenticated_client):
    admin_client, _ = authenticated_client("ADMIN")
    response = admin_client.get('/create-race')
    assert response.status_code == 200
    html_content = response.get_data(as_text=True)
    assert 'id="is_general"' in html_content
    assert "Marcar como Carrera General" in html_content

def test_league_admin_does_not_see_is_general_checkbox_on_create_race_page(authenticated_client):
    league_admin_client, _ = authenticated_client("LEAGUE_ADMIN")
    response = league_admin_client.get('/create-race')
    assert response.status_code == 200
    html_content = response.get_data(as_text=True)
    assert 'id="is_general"' not in html_content
    assert "Marcar como Carrera General" not in html_content


# --- Tests for PUT /api/races/<race_id>/details ---

def test_update_race_details_unauthenticated(client, sample_race):
    """Test updating race details by an unauthenticated user."""
    update_data = {"title": "Updated Title by Unauthenticated"}
    response = client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code in [401, 302] # Expect 401 for API, could be 302 if login_view redirects

def test_update_race_details_forbidden_player(authenticated_client, sample_race):
    """Test updating race details by a user with PLAYER role."""
    player_client, _ = authenticated_client("PLAYER")
    update_data = {"title": "Updated Title by Player"}
    response = player_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 403
    assert "Forbidden" in response.get_json().get("message", "")

def test_update_race_details_success_admin(authenticated_client, sample_race, db_session):
    """Test successful update of all editable race fields by an ADMIN."""
    admin_client, _ = authenticated_client("ADMIN")

    update_data = {
        "title": "Super Updated Race Title",
        "description": "This race has been thoroughly updated with new details.",
        "event_date": "2026-11-15T10:30", # YYYY-MM-DDTHH:MM format
        "location": "New Super Location",
        "promo_image_url": "https://example.com/new_super_promo.jpg",
        "gender_category": "FEMALE_ONLY"
    }
    response = admin_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 200

    json_response = response.get_json()
    assert json_response["message"] == "Race details updated successfully"
    updated_race_from_api = json_response["race"]

    # Verify response data
    assert updated_race_from_api["title"] == update_data["title"]
    assert updated_race_from_api["description"] == update_data["description"]
    assert updated_race_from_api["location"] == update_data["location"]
    assert updated_race_from_api["promo_image_url"] == update_data["promo_image_url"]
    assert updated_race_from_api["gender_category"] == update_data["gender_category"]
    # Compare event_date (ignoring seconds if not sent, or ensuring format matches)
    expected_event_date = datetime.strptime(update_data["event_date"], '%Y-%m-%dT%H:%M')
    api_event_date = datetime.strptime(updated_race_from_api["event_date"], '%Y-%m-%dT%H:%M:%S') # API returns with seconds
    assert api_event_date == expected_event_date

    # Verify database record
    db_session.refresh(sample_race) # Refresh object from session
    assert sample_race.title == update_data["title"]
    assert sample_race.description == update_data["description"]
    assert sample_race.event_date == expected_event_date
    assert sample_race.location == update_data["location"]
    assert sample_race.promo_image_url == update_data["promo_image_url"]
    assert sample_race.gender_category == update_data["gender_category"]

def test_update_race_details_success_league_admin(authenticated_client, sample_race, db_session):
    """Test successful update of some race fields by a LEAGUE_ADMIN."""
    league_admin_client, league_admin_user = authenticated_client("LEAGUE_ADMIN")

    # To make this test distinct, let's assume league_admin created this race
    # sample_race.user_id = league_admin_user.id
    # db_session.commit() # No, sample_race is created by admin_user from conftest fixture.
    # League admins should be able to edit any race as per current app logic.

    update_data = {
        "title": "League Admin Updated Title",
        "location": "League City Venue"
    }
    response = league_admin_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 200

    json_response = response.get_json()
    assert json_response["message"] == "Race details updated successfully"

    db_session.refresh(sample_race)
    assert sample_race.title == update_data["title"]
    assert sample_race.location == update_data["location"]
    # Ensure other fields remain unchanged from original sample_race
    assert sample_race.description is not None # or original value
    assert sample_race.gender_category is not None # or original value


def test_update_race_details_not_found(authenticated_client):
    """Test updating a non-existent race."""
    admin_client, _ = authenticated_client("ADMIN")
    non_existent_race_id = 99999
    update_data = {"title": "Title for Non-existent Race"}
    response = admin_client.put(f'/api/races/{non_existent_race_id}/details', json=update_data)
    assert response.status_code == 404
    assert "Race not found" in response.get_json().get("message", "")

# Validation error tests
def test_update_race_details_empty_title(authenticated_client, sample_race):
    admin_client, _ = authenticated_client("ADMIN")
    update_data = {"title": ""}
    response = admin_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 400
    assert "Title must be a non-empty string" in response.get_json().get("message", "")

def test_update_race_details_invalid_event_date_format(authenticated_client, sample_race):
    admin_client, _ = authenticated_client("ADMIN")
    update_data = {"event_date": "15/11/2026"} # Invalid format
    response = admin_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 400
    assert "Invalid event_date format" in response.get_json().get("message", "")

def test_update_race_details_invalid_gender_category(authenticated_client, sample_race):
    admin_client, _ = authenticated_client("ADMIN")
    update_data = {"gender_category": "INVALID_CATEGORY"}
    response = admin_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 400
    assert "Invalid gender_category" in response.get_json().get("message", "")

def test_update_race_details_invalid_promo_image_url(authenticated_client, sample_race):
    admin_client, _ = authenticated_client("ADMIN")
    update_data = {"promo_image_url": "not_a_valid_url"}
    response = admin_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 400
    assert "Invalid promo_image_url format" in response.get_json().get("message", "")

def test_update_race_details_clear_optional_fields(authenticated_client, sample_race, db_session):
    """Test clearing optional fields like description and promo_image_url."""
    admin_client, _ = authenticated_client("ADMIN")

    # Ensure fields have values first
    sample_race.description = "Initial Description"
    sample_race.promo_image_url = "http://example.com/initial.jpg"
    db_session.commit()

    update_data = {
        "description": "",
        "promo_image_url": ""
    }
    response = admin_client.put(f'/api/races/{sample_race.id}/details', json=update_data)
    assert response.status_code == 200

    json_response = response.get_json()
    assert json_response["race"]["description"] == ""
    assert json_response["race"]["promo_image_url"] == "" # Or None, depending on how backend handles empty string for URL

    db_session.refresh(sample_race)
    assert sample_race.description == ""
    assert sample_race.promo_image_url == "" # Or None


# --- Tests for Question Management ---

# --- Free Text Question Tests ---

@pytest.fixture
def sample_question_ft_data_payload():
    """Payload for creating a valid free text question."""
    return {
        "text": "What is your name?",
        "max_score_free_text": 10,
        "is_active": True
    }

# --- Authentication and Authorization Tests for Free Text Questions ---

def test_create_ft_question_unauthenticated(client, sample_race, sample_question_ft_data_payload):
    response = client.post(f'/api/races/{sample_race.id}/questions/free-text', json=sample_question_ft_data_payload)
    assert response.status_code in [401, 302]

def test_create_ft_question_forbidden_player(authenticated_client, sample_race, sample_question_ft_data_payload):
    player_client, _ = authenticated_client("PLAYER")
    response = player_client.post(f'/api/races/{sample_race.id}/questions/free-text', json=sample_question_ft_data_payload)
    assert response.status_code == 403

# Fixture for a created free text question to use in update/delete tests
@pytest.fixture
def created_ft_question(authenticated_client, sample_race, sample_question_ft_data_payload, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    response = admin_client.post(f'/api/races/{sample_race.id}/questions/free-text', json=sample_question_ft_data_payload)
    assert response.status_code == 201
    return response.get_json() # This is the serialized question from API

def test_update_ft_question_unauthenticated(client, created_ft_question):
    update_payload = {"text": "Updated FT question text"}
    response = client.put(f'/api/questions/free-text/{created_ft_question["id"]}', json=update_payload)
    assert response.status_code in [401, 302]

def test_update_ft_question_forbidden_player(authenticated_client, created_ft_question):
    player_client, _ = authenticated_client("PLAYER")
    update_payload = {"text": "Player trying to update FT question"}
    response = player_client.put(f'/api/questions/free-text/{created_ft_question["id"]}', json=update_payload)
    assert response.status_code == 403


# --- Create Free Text Question Tests ---

def test_create_free_text_question_success_admin(authenticated_client, sample_race, sample_question_ft_data_payload, db_session):
    admin_client, admin_user = authenticated_client("ADMIN")
    response = admin_client.post(f'/api/races/{sample_race.id}/questions/free-text', json=sample_question_ft_data_payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["text"] == sample_question_ft_data_payload["text"]
    assert data["max_score_free_text"] == sample_question_ft_data_payload["max_score_free_text"]
    assert data["is_active"] == sample_question_ft_data_payload["is_active"]
    assert data["question_type"] == "FREE_TEXT"
    assert data["race_id"] == sample_race.id

    # Verify in DB
    question_in_db = Question.query.get(data["id"])
    assert question_in_db is not None
    assert question_in_db.text == sample_question_ft_data_payload["text"]
    assert question_in_db.max_score_free_text == sample_question_ft_data_payload["max_score_free_text"]
    assert question_in_db.race_id == sample_race.id
    assert question_in_db.question_type.name == "FREE_TEXT"

def test_create_free_text_question_success_league_admin(authenticated_client, sample_race, sample_question_ft_data_payload, db_session):
    league_admin_client, _ = authenticated_client("LEAGUE_ADMIN")
    response = league_admin_client.post(f'/api/races/{sample_race.id}/questions/free-text', json=sample_question_ft_data_payload)
    assert response.status_code == 201
    # Further DB verification can be added if needed, similar to admin test


# Validation Error Tests for Create Free Text Question
@pytest.mark.parametrize("payload_modifier,expected_message_part", [
    ({"text": ""}, "Question text is required"),
    ({"pop": "text"}, "Question text is required"), # pop "text" field
    ({"max_score_free_text": 0}, "must be a positive integer"),
    ({"max_score_free_text": -5}, "must be a positive integer"),
    ({"max_score_free_text": "invalid"}, "must be a positive integer"), # Assuming type validation catches this
    ({"pop": "max_score_free_text"}, "is required and must be a positive integer"),
])
def test_create_free_text_question_validation_errors(authenticated_client, sample_race, sample_question_ft_data_payload, payload_modifier, expected_message_part):
    admin_client, _ = authenticated_client("ADMIN")
    payload = sample_question_ft_data_payload.copy()
    if "pop" in payload_modifier:
        payload.pop(payload_modifier["pop"], None)
    else:
        payload.update(payload_modifier)

    response = admin_client.post(f'/api/races/{sample_race.id}/questions/free-text', json=payload)
    assert response.status_code == 400
    assert expected_message_part in response.get_json().get("message", "")

def test_create_ft_question_for_non_existent_race(authenticated_client, sample_question_ft_data_payload):
    admin_client, _ = authenticated_client("ADMIN")
    non_existent_race_id = 9999
    response = admin_client.post(f'/api/races/{non_existent_race_id}/questions/free-text', json=sample_question_ft_data_payload)
    assert response.status_code == 404 # Race not found


# --- Update Free Text Question Tests ---
from backend.models import Question # Import Question model for direct DB checks

def test_update_free_text_question_success_admin(authenticated_client, created_ft_question, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    question_id = created_ft_question["id"]

    update_payload = {
        "text": "Updated What is your favorite color?",
        "max_score_free_text": 25,
        "is_active": False
    }
    response = admin_client.put(f'/api/questions/free-text/{question_id}', json=update_payload)
    assert response.status_code == 200
    data = response.get_json()

    assert data["text"] == update_payload["text"]
    assert data["max_score_free_text"] == update_payload["max_score_free_text"]
    assert data["is_active"] == update_payload["is_active"]

    # Verify in DB
    question_in_db = Question.query.get(question_id)
    assert question_in_db is not None
    assert question_in_db.text == update_payload["text"]
    assert question_in_db.max_score_free_text == update_payload["max_score_free_text"]
    assert question_in_db.is_active == update_payload["is_active"]

def test_update_ft_question_partial_update(authenticated_client, created_ft_question, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    question_id = created_ft_question["id"]
    original_max_score = created_ft_question["max_score_free_text"]

    update_payload = {"text": "Only text updated for FTQ"}
    response = admin_client.put(f'/api/questions/free-text/{question_id}', json=update_payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["text"] == update_payload["text"]
    assert data["max_score_free_text"] == original_max_score # Should remain unchanged

    question_in_db = Question.query.get(question_id)
    assert question_in_db.text == update_payload["text"]
    assert question_in_db.max_score_free_text == original_max_score

def test_update_ft_question_non_existent(authenticated_client):
    admin_client, _ = authenticated_client("ADMIN")
    response = admin_client.put('/api/questions/free-text/99999', json={"text": "Update non-existent"})
    assert response.status_code == 404

def test_update_ft_question_wrong_type_endpoint(authenticated_client, created_mc_question): # Assuming created_mc_question fixture exists or will be created
    """Try to update an MC question via FT endpoint."""
    admin_client, _ = authenticated_client("ADMIN")
    mc_question_id = created_mc_question["id"] # This fixture needs to be created for MC tests

    update_payload = {"text": "Trying to update MC via FT endpoint"}
    response = admin_client.put(f'/api/questions/free-text/{mc_question_id}', json=update_payload)
    assert response.status_code == 400 # Or specific error for wrong type
    assert "Cannot update non-FREE_TEXT question" in response.get_json().get("message", "")

# More specific validation for update (similar to create) can be added if necessary.
# For example, setting max_score_free_text to 0 or negative during update.
@pytest.mark.parametrize("invalid_score_payload,expected_message_part", [
    ({"max_score_free_text": 0}, "must be a positive integer"),
    ({"max_score_free_text": -10}, "must be a positive integer"),
])
def test_update_free_text_question_invalid_score(authenticated_client, created_ft_question, invalid_score_payload, expected_message_part):
    admin_client, _ = authenticated_client("ADMIN")
    question_id = created_ft_question["id"]

    response = admin_client.put(f'/api/questions/free-text/{question_id}', json=invalid_score_payload)
    assert response.status_code == 400
    assert expected_message_part in response.get_json().get("message", "")


# --- Multiple Choice Question Tests ---

@pytest.fixture
def sample_question_mc_data_payload_single_correct():
    """Payload for a single-correct MC question."""
    return {
        "text": "What is the capital of France?",
        "is_mc_multiple_correct": False,
        "total_score_mc_single": 10,
        "options": [
            {"option_text": "Berlin"}, # In a real scenario, one would be marked is_correct_mc_single=True by backend/frontend logic
            {"option_text": "Paris"},
            {"option_text": "London"},
            {"option_text": "Madrid"}
        ],
        "is_active": True
    }

@pytest.fixture
def sample_question_mc_data_payload_multiple_correct():
    """Payload for a multiple-correct MC question."""
    return {
        "text": "Which of these are primary colors?",
        "is_mc_multiple_correct": True,
        "points_per_correct_mc": 5,
        "points_per_incorrect_mc": -2,
        "options": [
            {"option_text": "Red"}, # Would be marked is_correct_mc_multiple=True
            {"option_text": "Green"}, # Would be marked is_correct_mc_multiple=True
            {"option_text": "Blue"},  # Would be marked is_correct_mc_multiple=True
            {"option_text": "Yellow"} # Actually, yellow is primary. Red, Yellow, Blue. Let's fix.
                                     # For testing structure, actual correctness isn't vital here, but good to be accurate.
                                     # Let's assume Red, Green, Blue for additive (light) primary colors often used in digital.
                                     # Or Red, Yellow, Blue for subtractive (pigment).
                                     # The key is the structure and that multiple can be marked.
        ],
        "is_active": True
    }


@pytest.fixture
def created_mc_question(authenticated_client, sample_race, sample_question_mc_data_payload_single_correct, db_session):
    """Creates a single-correct MC question and returns its API response data."""
    admin_client, _ = authenticated_client("ADMIN")
    # Modify payload to mark one option as correct for backend logic if necessary
    # Current backend create_multiple_choice_question doesn't require frontend to set is_correct flags in options.
    # It implies that the logic for setting correct options would be handled during an answer key setup phase.
    # For creation test, sending options without 'is_correct' flags is fine based on current backend.
    payload = sample_question_mc_data_payload_single_correct.copy()
    response = admin_client.post(f'/api/races/{sample_race.id}/questions/multiple-choice', json=payload)
    assert response.status_code == 201, f"Failed to create MC question: {response.get_data(as_text=True)}"
    return response.get_json()

# --- Auth tests for MC Questions ---
def test_create_mc_question_unauthenticated(client, sample_race, sample_question_mc_data_payload_single_correct):
    response = client.post(f'/api/races/{sample_race.id}/questions/multiple-choice', json=sample_question_mc_data_payload_single_correct)
    assert response.status_code in [401, 302]

def test_create_mc_question_forbidden_player(authenticated_client, sample_race, sample_question_mc_data_payload_single_correct):
    player_client, _ = authenticated_client("PLAYER")
    response = player_client.post(f'/api/races/{sample_race.id}/questions/multiple-choice', json=sample_question_mc_data_payload_single_correct)
    assert response.status_code == 403

def test_update_mc_question_unauthenticated(client, created_mc_question):
    update_payload = {"text": "Updated MC text"}
    response = client.put(f'/api/questions/multiple-choice/{created_mc_question["id"]}', json=update_payload)
    assert response.status_code in [401, 302]

def test_update_mc_question_forbidden_player(authenticated_client, created_mc_question):
    player_client, _ = authenticated_client("PLAYER")
    update_payload = {"text": "Player trying to update MC question"}
    response = player_client.put(f'/api/questions/multiple-choice/{created_mc_question["id"]}', json=update_payload)
    assert response.status_code == 403

# --- Create MC Question Tests ---
def test_create_mc_question_single_correct_success(authenticated_client, sample_race, sample_question_mc_data_payload_single_correct, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    payload = sample_question_mc_data_payload_single_correct
    response = admin_client.post(f'/api/races/{sample_race.id}/questions/multiple-choice', json=payload)
    assert response.status_code == 201
    data = response.get_json()

    assert data["text"] == payload["text"]
    assert data["is_mc_multiple_correct"] == False
    assert data["total_score_mc_single"] == payload["total_score_mc_single"]
    assert data["question_type"] == "MULTIPLE_CHOICE"
    assert data["race_id"] == sample_race.id
    assert len(data["options"]) == len(payload["options"])

    # Verify in DB
    question_in_db = Question.query.get(data["id"])
    assert question_in_db is not None
    assert question_in_db.text == payload["text"]
    assert question_in_db.is_mc_multiple_correct == False
    assert question_in_db.total_score_mc_single == payload["total_score_mc_single"]
    assert len(question_in_db.options.all()) == len(payload["options"])
    # Option text check (example for one option)
    assert question_in_db.options.filter(QuestionOption.option_text == payload["options"][0]["option_text"]).first() is not None

def test_create_mc_question_multiple_correct_success(authenticated_client, sample_race, sample_question_mc_data_payload_multiple_correct, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    payload = sample_question_mc_data_payload_multiple_correct

    # Adjust payload for realistic multiple correct scenario (Red, Yellow, Blue are subtractive primary)
    payload["options"] = [
        {"option_text": "Red"},
        {"option_text": "Yellow"},
        {"option_text": "Blue"},
        {"option_text": "Green"}
    ]

    response = admin_client.post(f'/api/races/{sample_race.id}/questions/multiple-choice', json=payload)
    assert response.status_code == 201
    data = response.get_json()

    assert data["text"] == payload["text"]
    assert data["is_mc_multiple_correct"] == True
    assert data["points_per_correct_mc"] == payload["points_per_correct_mc"]
    assert data["points_per_incorrect_mc"] == payload["points_per_incorrect_mc"]
    assert len(data["options"]) == len(payload["options"])

    question_in_db = Question.query.get(data["id"])
    assert question_in_db is not None
    assert question_in_db.is_mc_multiple_correct == True
    assert question_in_db.points_per_correct_mc == payload["points_per_correct_mc"]
    assert len(question_in_db.options.all()) == len(payload["options"])


# Validation Error Tests for Create Multiple Choice Question
@pytest.mark.parametrize("payload_modifier,expected_message_part", [
    ({"text": ""}, "Question text is required"),
    ({"pop": "text"}, "Question text is required"),
    ({"pop": "is_mc_multiple_correct"}, "is_mc_multiple_correct (boolean) is required"),
    ({"options": []}, "At least two options are required"),
    ({"options": [{"option_text": "Only one"}]}, "At least two options are required"),
    ({"options": [{"text_missing": "Option 1"}, {"option_text": "Option 2"}]}, "Each option must have 'option_text' (string)"), # Backend expects 'option_text'
    # Single-correct specific validation
    ({"is_mc_multiple_correct": False, "pop": "total_score_mc_single"}, "total_score_mc_single is required"),
    ({"is_mc_multiple_correct": False, "total_score_mc_single": 0}, "total_score_mc_single must be a positive integer"),
    ({"is_mc_multiple_correct": False, "total_score_mc_single": "invalid"}, "total_score_mc_single must be a positive integer"),
    # Multiple-correct specific validation
    ({"is_mc_multiple_correct": True, "pop": "points_per_correct_mc"}, "points_per_correct_mc is required"),
    ({"is_mc_multiple_correct": True, "points_per_correct_mc": "invalid"}, "points_per_correct_mc must be an integer"),
    ({"is_mc_multiple_correct": True, "points_per_incorrect_mc": "invalid"}, "points_per_incorrect_mc must be an integer"),
])
def test_create_mc_question_validation_errors(authenticated_client, sample_race, sample_question_mc_data_payload_single_correct, payload_modifier, expected_message_part):
    admin_client, _ = authenticated_client("ADMIN")
    # Base payload can be either single or multiple, adjust as needed or use a more generic one
    payload = sample_question_mc_data_payload_single_correct.copy()

    if "pop" in payload_modifier:
        # Handle popping nested keys like 'total_score_mc_single' when 'is_mc_multiple_correct' also changes
        if payload_modifier["pop"] == "total_score_mc_single" and "is_mc_multiple_correct" in payload_modifier and payload_modifier["is_mc_multiple_correct"] == True:
            # If we switch to multiple_correct, total_score_mc_single is not expected, so popping it is not a validation error for it.
            # Instead, points_per_correct_mc would be expected. This case should be handled by specific tests for switching types.
             pass # This specific pop case might not make sense if type is also changing.
        else:
            payload.pop(payload_modifier["pop"], None)

    # Apply other modifications
    for key, value in payload_modifier.items():
        if key != "pop":
            payload[key] = value

    # If testing for multiple correct, ensure the base payload has the right scoring keys initially
    if payload.get("is_mc_multiple_correct") == True:
        if "total_score_mc_single" in payload: del payload["total_score_mc_single"]
        payload.setdefault("points_per_correct_mc", 5) # Default if not being tested for missing
        payload.setdefault("points_per_incorrect_mc", 0)
    # If testing for single correct, ensure the base payload has the right scoring keys
    elif payload.get("is_mc_multiple_correct") == False:
        if "points_per_correct_mc" in payload: del payload["points_per_correct_mc"]
        if "points_per_incorrect_mc" in payload: del payload["points_per_incorrect_mc"]
        payload.setdefault("total_score_mc_single", 10) # Default if not being tested for missing


    response = admin_client.post(f'/api/races/{sample_race.id}/questions/multiple-choice', json=payload)
    assert response.status_code == 400, f"Request payload: {payload}"
    response_data = response.get_json()
    assert expected_message_part in response_data.get("message", ""), f"Unexpected error message: {response_data.get('message')}. Payload: {payload}"


def test_create_mc_question_for_non_existent_race(authenticated_client, sample_question_mc_data_payload_single_correct):
    admin_client, _ = authenticated_client("ADMIN")
    non_existent_race_id = 9999
    response = admin_client.post(f'/api/races/{non_existent_race_id}/questions/multiple-choice', json=sample_question_mc_data_payload_single_correct)
    assert response.status_code == 404 # Race not found
    assert "Race not found" in response.get_json().get("message", "")


# --- Update MC Question Tests ---

def test_update_mc_question_success_admin(authenticated_client, created_mc_question, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    question_id = created_mc_question["id"]

    # 1. Update basic text and is_active status
    update_payload_1 = {
        "text": "What is the updated capital of France?",
        "is_active": False
    }
    response1 = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json=update_payload_1)
    assert response1.status_code == 200
    data1 = response1.get_json()
    assert data1["text"] == update_payload_1["text"]
    assert data1["is_active"] == update_payload_1["is_active"]

    question_in_db = Question.query.get(question_id)
    assert question_in_db.text == update_payload_1["text"]
    assert question_in_db.is_active == update_payload_1["is_active"]

    # 2. Update scoring for the existing single-correct question
    update_payload_2 = {
        "total_score_mc_single": 15
    }
    response2 = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json=update_payload_2)
    assert response2.status_code == 200
    data2 = response2.get_json()
    assert data2["total_score_mc_single"] == update_payload_2["total_score_mc_single"]
    question_in_db.refresh() # SQLAlchemy term for reloading from DB if needed, or just query again
    assert Question.query.get(question_id).total_score_mc_single == update_payload_2["total_score_mc_single"]

    # 3. Change to multiple-correct
    update_payload_3 = {
        "is_mc_multiple_correct": True,
        "points_per_correct_mc": 7,
        "points_per_incorrect_mc": -3,
        "options": [ # Options can be updated too
            {"option_text": "Paris (France)"},
            {"option_text": "Lyon (France)"},
            {"option_text": "Marseille (France)"}
        ]
    }
    response3 = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json=update_payload_3)
    assert response3.status_code == 200
    data3 = response3.get_json()
    assert data3["is_mc_multiple_correct"] == True
    assert data3["points_per_correct_mc"] == update_payload_3["points_per_correct_mc"]
    assert data3["points_per_incorrect_mc"] == update_payload_3["points_per_incorrect_mc"]
    assert data3["total_score_mc_single"] is None # Should be nulled
    assert len(data3["options"]) == 3

    question_in_db = Question.query.get(question_id)
    assert question_in_db.is_mc_multiple_correct == True
    assert question_in_db.points_per_correct_mc == update_payload_3["points_per_correct_mc"]
    assert question_in_db.total_score_mc_single is None
    assert len(question_in_db.options.all()) == 3
    assert question_in_db.options.filter(QuestionOption.option_text == "Paris (France)").first() is not None

    # 4. Change back to single-correct
    update_payload_4 = {
        "is_mc_multiple_correct": False,
        "total_score_mc_single": 20,
        "options": [ # Options are typically updated if the type changes meaning
            {"option_text": "Paris"},
            {"option_text": "Berlin"}
        ]
    }
    response4 = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json=update_payload_4)
    assert response4.status_code == 200
    data4 = response4.get_json()
    assert data4["is_mc_multiple_correct"] == False
    assert data4["total_score_mc_single"] == update_payload_4["total_score_mc_single"]
    assert data4["points_per_correct_mc"] is None
    assert data4["points_per_incorrect_mc"] is None
    assert len(data4["options"]) == 2

    question_in_db = Question.query.get(question_id)
    assert question_in_db.is_mc_multiple_correct == False
    assert question_in_db.total_score_mc_single == update_payload_4["total_score_mc_single"]
    assert question_in_db.points_per_correct_mc is None
    assert len(question_in_db.options.all()) == 2
    assert question_in_db.options.filter(QuestionOption.option_text == "Berlin").first() is not None
    # Check that old options from payload_3 are gone
    assert question_in_db.options.filter(QuestionOption.option_text == "Paris (France)").first() is None


def test_update_mc_question_validation_errors(authenticated_client, created_mc_question):
    admin_client, _ = authenticated_client("ADMIN")
    question_id = created_mc_question["id"]

    # Invalid: empty text
    response = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json={"text": ""})
    assert response.status_code == 400
    assert "Question text must be a non-empty string" in response.get_json()["message"]

    # Invalid: options list too short
    response = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json={"options": [{"option_text": "TooFew"}]})
    assert response.status_code == 400
    assert "At least two options are required" in response.get_json()["message"]

    # Invalid: changing to single-correct but not providing total_score_mc_single
    # Current question (created_mc_question) is single-correct. Let's make it multi first.
    admin_client.put(f'/api/questions/multiple-choice/{question_id}', json={
        "is_mc_multiple_correct": True, "points_per_correct_mc": 5
    })
    # Now try to change back to single without total_score
    response = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json={"is_mc_multiple_correct": False})
    assert response.status_code == 400
    assert "total_score_mc_single is required for single-correct MCQs" in response.get_json()["message"]

    # Invalid: changing to multi-correct but not providing points_per_correct_mc
    # Make it single-correct first (it is by default from fixture)
    admin_client.put(f'/api/questions/multiple-choice/{question_id}', json={
        "is_mc_multiple_correct": False, "total_score_mc_single": 10
    })
    response = admin_client.put(f'/api/questions/multiple-choice/{question_id}', json={"is_mc_multiple_correct": True})
    assert response.status_code == 400
    assert "points_per_correct_mc is required for multiple-correct MCQs" in response.get_json()["message"]


def test_update_mc_question_not_found(authenticated_client):
    admin_client, _ = authenticated_client("ADMIN")
    response = admin_client.put('/api/questions/multiple-choice/99999', json={"text": "Update non-existent"})
    assert response.status_code == 404

def test_update_mc_question_wrong_type_endpoint(authenticated_client, created_ft_question):
    admin_client, _ = authenticated_client("ADMIN")
    ft_question_id = created_ft_question["id"]
    response = admin_client.put(f'/api/questions/multiple-choice/{ft_question_id}', json={"text": "Update FT via MC endpoint"})
    assert response.status_code == 400
    assert "Cannot update non-MULTIPLE_CHOICE question" in response.get_json()["message"]


# --- Ordering Question Tests ---

@pytest.fixture
def sample_question_ordering_data_payload():
    """Payload for a valid ordering question."""
    return {
        "text": "Rank these items from first to last.",
        "points_per_correct_order": 2,
        "bonus_for_full_order": 5,
        "options": [
            {"option_text": "Item A (should be 1st)"},
            {"option_text": "Item B (should be 2nd)"},
            {"option_text": "Item C (should be 3rd)"}
        ],
        "is_active": True
    }

@pytest.fixture
def created_ordering_question(authenticated_client, sample_race, sample_question_ordering_data_payload, db_session):
    """Creates an ordering question and returns its API response data."""
    admin_client, _ = authenticated_client("ADMIN")
    payload = sample_question_ordering_data_payload.copy()
    response = admin_client.post(f'/api/races/{sample_race.id}/questions/ordering', json=payload)
    assert response.status_code == 201, f"Failed to create Ordering question: {response.get_data(as_text=True)}"
    return response.get_json()

# --- Auth tests for Ordering Questions ---
def test_create_ordering_question_unauthenticated(client, sample_race, sample_question_ordering_data_payload):
    response = client.post(f'/api/races/{sample_race.id}/questions/ordering', json=sample_question_ordering_data_payload)
    assert response.status_code in [401, 302]

def test_create_ordering_question_forbidden_player(authenticated_client, sample_race, sample_question_ordering_data_payload):
    player_client, _ = authenticated_client("PLAYER")
    response = player_client.post(f'/api/races/{sample_race.id}/questions/ordering', json=sample_question_ordering_data_payload)
    assert response.status_code == 403

def test_update_ordering_question_unauthenticated(client, created_ordering_question):
    update_payload = {"text": "Updated Ordering text"}
    response = client.put(f'/api/questions/ordering/{created_ordering_question["id"]}', json=update_payload)
    assert response.status_code in [401, 302]

def test_update_ordering_question_forbidden_player(authenticated_client, created_ordering_question):
    player_client, _ = authenticated_client("PLAYER")
    update_payload = {"text": "Player trying to update Ordering question"}
    response = player_client.put(f'/api/questions/ordering/{created_ordering_question["id"]}', json=update_payload)
    assert response.status_code == 403


# --- Create Ordering Question Tests ---
def test_create_ordering_question_success_admin(authenticated_client, sample_race, sample_question_ordering_data_payload, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    payload = sample_question_ordering_data_payload
    response = admin_client.post(f'/api/races/{sample_race.id}/questions/ordering', json=payload)
    assert response.status_code == 201
    data = response.get_json()

    assert data["text"] == payload["text"]
    assert data["points_per_correct_order"] == payload["points_per_correct_order"]
    assert data["bonus_for_full_order"] == payload["bonus_for_full_order"]
    assert data["question_type"] == "ORDERING"
    assert data["race_id"] == sample_race.id
    assert len(data["options"]) == len(payload["options"])
    for i, option_data in enumerate(data["options"]):
        assert option_data["option_text"] == payload["options"][i]["option_text"]
        assert option_data["correct_order_index"] == i # Verify index assignment

    # Verify in DB
    question_in_db = Question.query.get(data["id"])
    assert question_in_db is not None
    assert question_in_db.points_per_correct_order == payload["points_per_correct_order"]
    assert question_in_db.bonus_for_full_order == payload["bonus_for_full_order"]
    db_options = sorted(question_in_db.options.all(), key=lambda opt: opt.correct_order_index)
    assert len(db_options) == len(payload["options"])
    for i, db_option in enumerate(db_options):
        assert db_option.option_text == payload["options"][i]["option_text"]
        assert db_option.correct_order_index == i


# Validation Error Tests for Create Ordering Question
@pytest.mark.parametrize("payload_modifier,expected_message_part", [
    ({"text": ""}, "Question text is required"),
    ({"pop": "text"}, "Question text is required"),
    ({"pop": "points_per_correct_order"}, "points_per_correct_order is required"),
    ({"points_per_correct_order": 0}, "points_per_correct_order must be a positive integer"),
    ({"points_per_correct_order": "invalid"}, "points_per_correct_order is required"), # type validation by model
    ({"bonus_for_full_order": -1}, "bonus_for_full_order must be a non-negative integer"),
    ({"bonus_for_full_order": "invalid"}, "bonus_for_full_order must be a non-negative integer"),
    ({"options": []}, "At least two options (items to order) are required"),
    ({"options": [{"option_text": "Only one item"}]}, "At least two options (items to order) are required"),
    ({"options": [{"text_missing": "Item 1"}, {"option_text": "Item 2"}]}, "Each option must have 'option_text' (string)"),
])
def test_create_ordering_question_validation_errors(authenticated_client, sample_race, sample_question_ordering_data_payload, payload_modifier, expected_message_part):
    admin_client, _ = authenticated_client("ADMIN")
    payload = sample_question_ordering_data_payload.copy()

    if "pop" in payload_modifier:
        payload.pop(payload_modifier["pop"], None)
    else:
        payload.update(payload_modifier)

    response = admin_client.post(f'/api/races/{sample_race.id}/questions/ordering', json=payload)
    assert response.status_code == 400
    response_data = response.get_json()
    assert expected_message_part in response_data.get("message", ""), f"Unexpected error: {response_data.get('message')}. Payload: {payload}"


def test_create_ordering_question_for_non_existent_race(authenticated_client, sample_question_ordering_data_payload):
    admin_client, _ = authenticated_client("ADMIN")
    non_existent_race_id = 9999
    response = admin_client.post(f'/api/races/{non_existent_race_id}/questions/ordering', json=sample_question_ordering_data_payload)
    assert response.status_code == 404
    assert "Race not found" in response.get_json().get("message", "")


# --- Update Ordering Question Tests ---
def test_update_ordering_question_success_admin(authenticated_client, created_ordering_question, db_session):
    admin_client, _ = authenticated_client("ADMIN")
    question_id = created_ordering_question["id"]

    # 1. Update text, scoring, and is_active
    update_payload_1 = {
        "text": "Rank these items from last to first.",
        "points_per_correct_order": 3,
        "bonus_for_full_order": 10,
        "is_active": False
    }
    response1 = admin_client.put(f'/api/questions/ordering/{question_id}', json=update_payload_1)
    assert response1.status_code == 200
    data1 = response1.get_json()
    assert data1["text"] == update_payload_1["text"]
    assert data1["points_per_correct_order"] == update_payload_1["points_per_correct_order"]
    assert data1["bonus_for_full_order"] == update_payload_1["bonus_for_full_order"]
    assert data1["is_active"] == update_payload_1["is_active"]

    question_in_db = Question.query.get(question_id)
    assert question_in_db.text == update_payload_1["text"]
    assert question_in_db.points_per_correct_order == update_payload_1["points_per_correct_order"]
    assert question_in_db.bonus_for_full_order == update_payload_1["bonus_for_full_order"]
    assert question_in_db.is_active == update_payload_1["is_active"]

    # 2. Update options (reorder and change text)
    update_payload_2 = {
        "options": [
            {"option_text": "New Item C (now 1st)"}, # Was Item C (should be 3rd)
            {"option_text": "New Item A (now 2nd)"}, # Was Item A (should be 1st)
            {"option_text": "New Item B (now 3rd)"}  # Was Item B (should be 2nd)
        ]
    }
    response2 = admin_client.put(f'/api/questions/ordering/{question_id}', json=update_payload_2)
    assert response2.status_code == 200
    data2 = response2.get_json()
    assert len(data2["options"]) == 3
    assert data2["options"][0]["option_text"] == "New Item C (now 1st)"
    assert data2["options"][0]["correct_order_index"] == 0
    assert data2["options"][1]["option_text"] == "New Item A (now 2nd)"
    assert data2["options"][1]["correct_order_index"] == 1
    assert data2["options"][2]["option_text"] == "New Item B (now 3rd)"
    assert data2["options"][2]["correct_order_index"] == 2

    question_in_db = Question.query.get(question_id)
    db_options = sorted(question_in_db.options.all(), key=lambda opt: opt.correct_order_index)
    assert len(db_options) == 3
    assert db_options[0].option_text == "New Item C (now 1st)"
    assert db_options[1].option_text == "New Item A (now 2nd)"
    assert db_options[2].option_text == "New Item B (now 3rd)"
    # Ensure old options are gone
    assert QuestionOption.query.filter_by(option_text="Item A (should be 1st)").first() is None


def test_update_ordering_question_validation_errors(authenticated_client, created_ordering_question):
    admin_client, _ = authenticated_client("ADMIN")
    question_id = created_ordering_question["id"]

    response = admin_client.put(f'/api/questions/ordering/{question_id}', json={"points_per_correct_order": 0})
    assert response.status_code == 400
    assert "must be a positive integer" in response.get_json()["message"]

    response = admin_client.put(f'/api/questions/ordering/{question_id}', json={"options": [{"option_text": "One item"}]})
    assert response.status_code == 400
    assert "At least two options are required" in response.get_json()["message"]

def test_update_ordering_question_not_found(authenticated_client):
    admin_client, _ = authenticated_client("ADMIN")
    response = admin_client.put('/api/questions/ordering/99999', json={"text": "Update non-existent"})
    assert response.status_code == 404

def test_update_ordering_question_wrong_type_endpoint(authenticated_client, created_ft_question):
    admin_client, _ = authenticated_client("ADMIN")
    ft_question_id = created_ft_question["id"]
    response = admin_client.put(f'/api/questions/ordering/{ft_question_id}', json={"text": "Update FT via Ordering endpoint"})
    assert response.status_code == 400
    assert "Cannot update non-ORDERING question" in response.get_json()["message"]


# --- Generic Question Deletion Tests ---

def test_delete_question_success_admin(authenticated_client, created_ft_question, created_mc_question, created_ordering_question, db_session):
    admin_client, _ = authenticated_client("ADMIN")

    question_ids_to_delete = [created_ft_question["id"], created_mc_question["id"], created_ordering_question["id"]]

    for q_id in question_ids_to_delete:
        # Verify options exist before deleting MC/Ordering questions
        question_before_delete = Question.query.get(q_id)
        if question_before_delete.question_type.name in ["MULTIPLE_CHOICE", "ORDERING"]:
            assert len(question_before_delete.options.all()) > 0, f"Question {q_id} should have options before delete."

        response = admin_client.delete(f'/api/questions/{q_id}')
        assert response.status_code == 200 # Assuming 200 for success with message
        assert "Question deleted successfully" in response.get_json()["message"]

        # Verify question is deleted from DB
        assert Question.query.get(q_id) is None
        # Verify associated options are also deleted
        assert QuestionOption.query.filter_by(question_id=q_id).count() == 0

def test_delete_question_success_league_admin(authenticated_client, created_ft_question, db_session): # Test with one type is enough for role check
    league_admin_client, _ = authenticated_client("LEAGUE_ADMIN")
    q_id = created_ft_question["id"] # Using FT question for simplicity

    response = league_admin_client.delete(f'/api/questions/{q_id}')
    assert response.status_code == 200
    assert Question.query.get(q_id) is None


def test_create_race_with_slider_question(authenticated_client, db_session):
    admin_client, admin_user = authenticated_client("ADMIN")
    triatlon_format = RaceFormat.query.filter_by(name="Triatlón").first()
    natacion_segment = Segment.query.filter_by(name="Natación").first()

    assert triatlon_format, "Triatlón format not found for slider test"
    assert natacion_segment, "Natación segment not found for slider test"

    slider_question_payload = {
        "text": "Rate your confidence (1-10)",
        "type": "SLIDER",
        "slider_unit": "points",
        "slider_min_value": 1.0,
        "slider_max_value": 10.0,
        "slider_step": 0.5,
        "slider_points_exact": 100,
        "slider_threshold_partial": 1.0,
        "slider_points_partial": 50,
        "is_active": True
        # No options for slider
    }

    race_data_with_slider = {
        "title": "Race with Slider Question",
        "description": "Testing slider question creation within a race.",
        "race_format_id": triatlon_format.id,
        "event_date": "2025-09-10",
        "location": "Slider Test City",
        "gender_category": "Ambos",
        "segments": [
            {"segment_id": natacion_segment.id, "distance_km": 0.5}
        ],
        "questions": [slider_question_payload],
        "is_general": True
    }

    response = admin_client.post('/api/races', json=race_data_with_slider)
    assert response.status_code == 201, f"Failed to create race with slider question: {response.get_data(as_text=True)}"

    data = response.get_json()
    assert "race_id" in data
    race_id = data['race_id']

    # Verify the question in the database
    question_in_db = Question.query.filter_by(race_id=race_id, text=slider_question_payload["text"]).first()
    assert question_in_db is not None
    assert question_in_db.question_type.name == "SLIDER"
    assert question_in_db.slider_unit == slider_question_payload["slider_unit"]
    assert question_in_db.slider_min_value == slider_question_payload["slider_min_value"]
    assert question_in_db.slider_max_value == slider_question_payload["slider_max_value"]
    assert question_in_db.slider_step == slider_question_payload["slider_step"]
    assert question_in_db.slider_points_exact == slider_question_payload["slider_points_exact"]
    assert question_in_db.slider_threshold_partial == slider_question_payload["slider_threshold_partial"]
    assert question_in_db.slider_points_partial == slider_question_payload["slider_points_partial"]
    assert question_in_db.is_active == slider_question_payload["is_active"]


def test_delete_question_unauthenticated(client, created_ft_question):
    q_id = created_ft_question["id"]
    response = client.delete(f'/api/questions/{q_id}')
    assert response.status_code in [401, 302]

def test_delete_question_forbidden_player(authenticated_client, created_ft_question):
    player_client, _ = authenticated_client("PLAYER")
    q_id = created_ft_question["id"]
    response = player_client.delete(f'/api/questions/{q_id}')
    assert response.status_code == 403
    assert "Forbidden" in response.get_json()["message"]

def test_delete_non_existent_question(authenticated_client):
    admin_client, _ = authenticated_client("ADMIN")
    non_existent_q_id = 99999
    response = admin_client.delete(f'/api/questions/{non_existent_q_id}')
    assert response.status_code == 404
    assert "Question not found" in response.get_json()["message"]
