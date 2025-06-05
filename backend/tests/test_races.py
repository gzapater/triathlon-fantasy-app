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
    assert len(race_in_db.segment_details) == 3


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
