import pytest
from backend.models import db, User, Role, Race, League, RaceStatus, RaceFormat
from flask_login import login_user, logout_user
from datetime import datetime, timedelta

# Helper to create roles if they don't exist
def get_or_create_role(role_code, description="Test Role"):
    role = Role.query.filter_by(code=role_code).first()
    if not role:
        role = Role(code=role_code, description=description)
        db.session.add(role)
        db.session.commit()
    return role

# Helper to create a user with a specific role
def create_user_with_role(username, email, password, role_code):
    role = get_or_create_role(role_code)
    user = User(username=username, email=email, role_id=role.id, name=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user

# Helper to create a race format
def get_or_create_race_format(name="Triathlon"):
    race_format = RaceFormat.query.filter_by(name=name).first()
    if not race_format:
        race_format = RaceFormat(name=name)
        db.session.add(race_format)
        db.session.commit()
    return race_format

# Helper to create a race
def create_race_test_helper(client_app, user, title="Test Race", status=RaceStatus.PLANNED, days_from_now=7):
    race_format = get_or_create_race_format()
    race = Race(
        title=title,
        race_format_id=race_format.id,
        event_date=datetime.utcnow() + timedelta(days=days_from_now),
        gender_category="MIXED",
        user_id=user.id,
        status=status
    )
    db.session.add(race)
    db.session.commit()
    return race

@pytest.fixture(scope='module')
def app_for_leagues(app_context): # Using app_context from conftest.py
    # Ensure roles and a race format exist for tests
    with app_context.app_context():
        get_or_create_role('ADMIN', 'Administrator')
        get_or_create_role('LEAGUE_ADMIN', 'League Administrator')
        get_or_create_role('PLAYER', 'Player')
        get_or_create_race_format()
    return app_context

@pytest.fixture
def admin_user(app_for_leagues):
    with app_for_leagues.app_context():
        return create_user_with_role("adminleague", "adminleague@test.com", "password", "ADMIN")

@pytest.fixture
def league_admin_user(app_for_leagues):
    with app_for_leagues.app_context():
        return create_user_with_role("leagueadmin", "leagueadmin@test.com", "password", "LEAGUE_ADMIN")

@pytest.fixture
def player_user(app_for_leagues):
    with app_for_leagues.app_context():
        return create_user_with_role("playerleague", "playerleague@test.com", "password", "PLAYER")

@pytest.fixture
def planned_race_by_league_admin(app_for_leagues, league_admin_user):
    with app_for_leagues.app_context():
        return create_race_test_helper(app_for_leagues, league_admin_user, title="LA Planned Race 1", status=RaceStatus.PLANNED)

@pytest.fixture
def planned_race_by_admin(app_for_leagues, admin_user):
     with app_for_leagues.app_context():
        return create_race_test_helper(app_for_leagues, admin_user, title="Admin Planned Race 1", status=RaceStatus.PLANNED)

@pytest.fixture
def active_race_by_league_admin(app_for_leagues, league_admin_user):
    with app_for_leagues.app_context():
        return create_race_test_helper(app_for_leagues, league_admin_user, title="LA Active Race", status=RaceStatus.ACTIVE)


def test_create_league_as_admin(client, admin_user, planned_race_by_admin):
    login_user(admin_user)
    response = client.post('/api/leagues', json={
        "name": "Admin Super League",
        "description": "League created by Admin",
        "race_ids": [planned_race_by_admin.id]
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['message'] == "League created successfully"
    assert data['league']['name'] == "Admin Super League"
    assert planned_race_by_admin.id in data['league']['race_ids']

    league = League.query.get(data['league']['id'])
    assert league is not None
    assert league.admin_id == admin_user.id
    logout_user()

def test_create_league_as_league_admin_own_races(client, league_admin_user, planned_race_by_league_admin):
    login_user(league_admin_user)
    response = client.post('/api/leagues', json={
        "name": "League Admin's Own League",
        "description": "League with own races",
        "race_ids": [planned_race_by_league_admin.id]
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['league']['name'] == "League Admin's Own League"
    assert planned_race_by_league_admin.id in data['league']['race_ids']

    league = League.query.get(data['league']['id'])
    assert league is not None
    assert league.admin_id == league_admin_user.id
    logout_user()

def test_create_league_as_league_admin_other_race_forbidden(client, league_admin_user, planned_race_by_admin):
    login_user(league_admin_user)
    response = client.post('/api/leagues', json={
        "name": "League Admin Tries Other Race",
        "race_ids": [planned_race_by_admin.id] # Race created by admin_user
    })
    assert response.status_code == 403
    data = response.get_json()
    assert "you can only add races you created" in data['message'].lower()
    logout_user()

def test_create_league_as_player_forbidden(client, player_user, planned_race_by_admin):
    login_user(player_user)
    response = client.post('/api/leagues', json={
        "name": "Player League Attempt",
        "race_ids": [planned_race_by_admin.id]
    })
    assert response.status_code == 403
    logout_user()

def test_create_league_with_non_planned_race_forbidden(client, admin_user, active_race_by_league_admin):
    login_user(admin_user) # Admin can create leagues
    response = client.post('/api/leagues', json={
        "name": "League With Active Race",
        "race_ids": [active_race_by_league_admin.id] # This race is ACTIVE
    })
    assert response.status_code == 400
    data = response.get_json()
    assert "not in PLANNED status" in data['message']
    logout_user()

def test_create_league_duplicate_name(client, admin_user, planned_race_by_admin):
    login_user(admin_user)
    client.post('/api/leagues', json={"name": "Duplicate Name League", "race_ids": [planned_race_by_admin.id]}) # First creation
    response = client.post('/api/leagues', json={"name": "Duplicate Name League", "race_ids": []}) # Second attempt
    assert response.status_code == 409
    data = response.get_json()
    assert "already exists" in data['message']
    logout_user()

def test_get_leagues(client, admin_user, league_admin_user, planned_race_by_admin, planned_race_by_league_admin):
    # Create some leagues
    login_user(admin_user)
    client.post('/api/leagues', json={"name": "League Alpha", "race_ids": [planned_race_by_admin.id]})
    logout_user()
    login_user(league_admin_user)
    client.post('/api/leagues', json={"name": "League Beta", "race_ids": [planned_race_by_league_admin.id]})

    # Player should be able to list leagues (assuming public listing for now)
    response = client.get('/api/leagues')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    # Check if our created leagues are in the list (names might vary due to test order)
    league_names = [l['name'] for l in data]
    assert "League Alpha" in league_names
    assert "League Beta" in league_names
    logout_user()

def test_get_league_details(client, admin_user, planned_race_by_admin):
    login_user(admin_user)
    create_response = client.post('/api/leagues', json={
        "name": "Detailed League",
        "description": "A league for detail testing",
        "race_ids": [planned_race_by_admin.id]
    })
    league_id = create_response.get_json()['league']['id']

    response = client.get(f'/api/leagues/{league_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == league_id
    assert data['name'] == "Detailed League"
    assert data['description'] == "A league for detail testing"
    assert len(data['races']) == 1
    assert data['races'][0]['id'] == planned_race_by_admin.id
    assert data['races'][0]['title'] == planned_race_by_admin.title
    logout_user()

def test_update_league_as_owner(client, league_admin_user, planned_race_by_league_admin, planned_race_by_admin):
    login_user(league_admin_user)
    create_response = client.post('/api/leagues', json={
        "name": "League To Update",
        "race_ids": [planned_race_by_league_admin.id]
    })
    league_id = create_response.get_json()['league']['id']

    # Admin creates another planned race, league admin should not be able to add it unless admin edits
    # For this test, league admin is updating their own league. They can only add their own races.

    # Create another race by the league_admin to add
    another_la_race = create_race_test_helper(client.application, league_admin_user, "LA Second Planned Race")

    update_payload = {
        "name": "Updated League Name",
        "description": "Updated Description",
        "race_ids": [planned_race_by_league_admin.id, another_la_race.id]
    }
    response = client.put(f'/api/leagues/{league_id}', json=update_payload)
    assert response.status_code == 200
    data = response.get_json()['league']
    assert data['name'] == "Updated League Name"
    assert data['description'] == "Updated Description"
    assert len(data['race_ids']) == 2
    assert planned_race_by_league_admin.id in data['race_ids']
    assert another_la_race.id in data['race_ids']
    logout_user()

def test_update_league_as_admin_can_add_any_planned_race(client, admin_user, league_admin_user, planned_race_by_league_admin, planned_race_by_admin):
    # League admin creates a league
    login_user(league_admin_user)
    create_response = client.post('/api/leagues', json={
        "name": "League For Admin Update",
        "race_ids": [planned_race_by_league_admin.id]
    })
    league_id = create_response.get_json()['league']['id']
    logout_user()

    # Admin logs in and updates the league, adding their own race
    login_user(admin_user)
    update_payload = {
        "name": "Admin Updated This League",
        "race_ids": [planned_race_by_league_admin.id, planned_race_by_admin.id]
    }
    response = client.put(f'/api/leagues/{league_id}', json=update_payload)
    assert response.status_code == 200
    data = response.get_json()['league']
    assert data['name'] == "Admin Updated This League"
    assert len(data['race_ids']) == 2
    assert planned_race_by_admin.id in data['race_ids'] # Admin's race added
    logout_user()


def test_update_league_by_non_owner_league_admin_forbidden(client, admin_user, league_admin_user, player_user, planned_race_by_admin):
    # Admin creates a league
    login_user(admin_user)
    create_resp = client.post('/api/leagues', json={"name": "Admin's League To Protect", "race_ids": [planned_race_by_admin.id]})
    league_id = create_resp.get_json()['league']['id']
    logout_user()

    # Another league admin tries to update it - should be forbidden
    login_user(league_admin_user) # This is a different league admin
    response = client.put(f'/api/leagues/{league_id}', json={"name": "Attempted Takeover"})
    assert response.status_code == 403
    logout_user()

    # Player tries to update it - should be forbidden
    login_user(player_user)
    response = client.put(f'/api/leagues/{league_id}', json={"name": "Player Takeover Attempt"})
    assert response.status_code == 403
    logout_user()


def test_delete_league_as_owner(client, league_admin_user, planned_race_by_league_admin):
    login_user(league_admin_user)
    create_response = client.post('/api/leagues', json={
        "name": "League To Delete",
        "race_ids": [planned_race_by_league_admin.id]
    })
    league_id = create_response.get_json()['league']['id']

    response = client.delete(f'/api/leagues/{league_id}')
    assert response.status_code == 200
    assert response.get_json()['message'] == "League deleted successfully"

    # Verify it's marked as deleted (or actually gone if not soft delete)
    league = League.query.get(league_id)
    assert league.is_deleted is True
    logout_user()

def test_delete_league_as_admin(client, admin_user, league_admin_user, planned_race_by_league_admin):
    # League admin creates a league
    login_user(league_admin_user)
    create_response = client.post('/api/leagues', json={"name": "LA League for Admin Delete", "race_ids": [planned_race_by_league_admin.id]})
    league_id = create_response.get_json()['league']['id']
    logout_user()

    # Admin deletes it
    login_user(admin_user)
    response = client.delete(f'/api/leagues/{league_id}')
    assert response.status_code == 200

    league = League.query.get(league_id)
    assert league.is_deleted is True
    logout_user()

def test_delete_league_by_non_owner_league_admin_forbidden(client, admin_user, league_admin_user, player_user, planned_race_by_admin):
    login_user(admin_user)
    create_resp = client.post('/api/leagues', json={"name": "Admin's League To Protect Deletion", "race_ids": [planned_race_by_admin.id]})
    league_id = create_resp.get_json()['league']['id']
    logout_user()

    # Another league admin tries to delete it
    login_user(league_admin_user)
    response = client.delete(f'/api/leagues/{league_id}')
    assert response.status_code == 403
    logout_user()

    # Player tries to delete it
    login_user(player_user)
    response = client.delete(f'/api/leagues/{league_id}')
    assert response.status_code == 403
    logout_user()

def test_get_planned_races_for_league_creation_as_admin(client, admin_user, planned_race_by_admin, planned_race_by_league_admin, active_race_by_league_admin):
    login_user(admin_user)
    response = client.get('/api/races/planned_for_league_creation')
    assert response.status_code == 200
    data = response.get_json()

    race_ids_in_response = [r['id'] for r in data]
    assert planned_race_by_admin.id in race_ids_in_response
    assert planned_race_by_league_admin.id in race_ids_in_response # Admin sees all planned
    assert active_race_by_league_admin.id not in race_ids_in_response # Active race should not be listed
    logout_user()

def test_get_planned_races_for_league_creation_as_league_admin(client, league_admin_user, planned_race_by_admin, planned_race_by_league_admin, active_race_by_league_admin):
    login_user(league_admin_user)
    response = client.get('/api/races/planned_for_league_creation')
    assert response.status_code == 200
    data = response.get_json()

    race_ids_in_response = [r['id'] for r in data]
    assert planned_race_by_league_admin.id in race_ids_in_response # LA sees their own planned race
    assert planned_race_by_admin.id not in race_ids_in_response # LA does not see admin's race
    assert active_race_by_league_admin.id not in race_ids_in_response # Active race should not be listed
    logout_user()

def test_get_planned_races_for_league_creation_as_player_forbidden(client, player_user):
    login_user(player_user)
    response = client.get('/api/races/planned_for_league_creation')
    assert response.status_code == 403
    logout_user()

# Clean up leagues after tests (optional, but good practice if not using in-memory DB that resets)
@pytest.fixture(scope="session", autouse=True)
def cleanup_leagues(app_context):
    yield # let tests run
    with app_context.app_context():
        # Using a more direct way to delete if cascade isn't set up on association for soft deletes
        # For hard delete:
        # db.session.execute(sa.text("DELETE FROM league_races;"))
        # League.query.delete()
        # For soft delete, mark them as deleted:
        leagues_to_cleanup = League.query.all()
        for league in leagues_to_cleanup:
            league.is_deleted = True # Or actual deletion if preferred
            # If you want to clear associations for soft delete and they aren't cascaded:
            # league.races = []
        db.session.commit()

        # Also clean up test users and races if they persist and might interfere
        # For simplicity here, focusing on leagues. A full teardown would be more extensive.
        # User.query.filter(User.username.like('%league%')).delete()
        # Race.query.filter(Race.title.like('%League Test%')).delete()
        # db.session.commit()
        pass
