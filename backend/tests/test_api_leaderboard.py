import pytest
from backend.models import db, User, Race, UserScore
from datetime import datetime, timedelta

# Helper function to create a race
def create_race_for_leaderboard(db_session, admin_user, title="Leaderboard Test Race", days_from_now=0):
    race = Race(
        title=title,
        race_format_id=1, # Assuming RaceFormat with ID 1 exists from conftest
        event_date=datetime.utcnow() + timedelta(days=days_from_now),
        quiniela_close_date=datetime.utcnow() + timedelta(days=days_from_now -1), # Closed yesterday if days_from_now=0
        user_id=admin_user.id,
        gender_category="MIXED",
        category="Elite"
    )
    db_session.add(race)
    db_session.commit()
    return race

# Helper function to create user scores
def create_user_score(db_session, user, race, score):
    user_score = UserScore(user_id=user.id, race_id=race.id, score=score)
    db_session.add(user_score)
    db_session.commit()
    return user_score

def test_get_quiniela_leaderboard_unauthenticated(client, sample_race):
    """Test that an unauthenticated user gets a 401 (or redirect to login)."""
    response = client.get(f"/api/races/{sample_race.id}/quiniela_leaderboard")
    # Flask-Login usually redirects to login_view if login_required fails
    # For API, it might be 401 if configured, or redirect.
    # Given current setup, it's likely a redirect to login which might result in HTML response.
    # For pure API, 401 is more standard. Let's check for non-200.
    assert response.status_code != 200
    # Depending on Flask-Login config, could be 302 (redirect) or 401
    # If login_manager.unauthorized() returns a response with 401, this will be 401.
    # If it redirects, it will be 302. For now, checking it's not 200 is a basic guard.
    # A more specific check would be `assert response.status_code == 401` if API is JSON-based for auth errors.


def test_get_quiniela_leaderboard_authenticated(authenticated_client, db_session, admin_user, new_user_factory):
    """Test that an authenticated user can access the endpoint and data is correct."""
    client, player1 = authenticated_client("PLAYER") # player1 is the logged-in user

    race = create_race_for_leaderboard(db_session, admin_user, title="Leaderboard Race 1")

    # Create other users for scoring
    player2 = new_user_factory("leaderboard_p2", "p2@test.com", "pwpw", "PLAYER")
    player3 = new_user_factory("leaderboard_p3", "p3@test.com", "pwpw", "PLAYER")

    create_user_score(db_session, player1, race, 100)
    create_user_score(db_session, player2, race, 150)
    create_user_score(db_session, player3, race, 50)

    response = client.get(f"/api/races/{race.id}/quiniela_leaderboard")
    assert response.status_code == 200
    data = response.json

    assert isinstance(data, list)
    assert len(data) == 3

    # Check sorting (descending by score)
    assert data[0]["username"] == player2.username
    assert data[0]["score"] == 150
    assert data[1]["username"] == player1.username
    assert data[1]["score"] == 100
    assert data[2]["username"] == player3.username
    assert data[2]["score"] == 50

    # Check structure of each item
    for item in data:
        assert "user_id" in item
        assert "username" in item
        assert "score" in item
        assert isinstance(item["user_id"], int)
        assert isinstance(item["username"], str)
        assert isinstance(item["score"], int)

def test_get_quiniela_leaderboard_race_not_exist(authenticated_client):
    """Test that a 404 is returned if the race does not exist."""
    client, _ = authenticated_client("PLAYER")
    response = client.get("/api/races/99999/quiniela_leaderboard") # Non-existent race ID
    assert response.status_code == 404
    data = response.json
    assert data["message"] == "Race not found"

def test_get_quiniela_leaderboard_no_scores(authenticated_client, db_session, admin_user):
    """Test with a race that has no scores, expecting an empty list."""
    client, _ = authenticated_client("PLAYER")
    race_no_scores = create_race_for_leaderboard(db_session, admin_user, title="Race No Scores")

    response = client.get(f"/api/races/{race_no_scores.id}/quiniela_leaderboard")
    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) == 0

def test_get_quiniela_leaderboard_multiple_users_same_score(authenticated_client, db_session, admin_user, new_user_factory):
    """Test leaderboard when multiple users have the same score (secondary sort by user_id or username is not specified, but order should be consistent)."""
    client, player1 = authenticated_client("PLAYER")

    race = create_race_for_leaderboard(db_session, admin_user, title="Leaderboard Race Same Score")

    player2 = new_user_factory("leaderboard_s_p2", "s_p2@test.com", "pwpw", "PLAYER")
    player3 = new_user_factory("leaderboard_s_p3", "s_p3@test.com", "pwpw", "PLAYER")

    create_user_score(db_session, player1, race, 100) # Logged in user
    create_user_score(db_session, player2, race, 150)
    create_user_score(db_session, player3, race, 150) # Same score as player2

    response = client.get(f"/api/races/{race.id}/quiniela_leaderboard")
    assert response.status_code == 200
    data = response.json

    assert len(data) == 3
    assert data[0]["score"] == 150
    assert data[1]["score"] == 150
    assert data[2]["score"] == 100

    # Check that the two users with 150 are present
    usernames_with_150 = {item["username"] for item in data if item["score"] == 150}
    assert player2.username in usernames_with_150
    assert player3.username in usernames_with_150

    # Ensure the lowest score is last
    assert data[2]["username"] == player1.username

# More tests could be added:
# - Pagination (if implemented on the endpoint)
# - Performance with many scores (though typically out of scope for unit/integration tests like these)

# Note on unauthenticated test:
# The behavior of @login_required (from Flask-Login) when an unauthenticated user
# tries to access a protected endpoint can vary.
# - If it's a regular web route, it usually redirects to the login page (status 302).
# - For an API, it's common to configure it to return a 401 Unauthorized JSON response.
# The `authenticated_client` fixture logs in a user. For unauthenticated, just use `client`.
# The `conftest.py` has `LOGIN_DISABLED = False`.
# If the default Flask-Login behavior for `login_manager.unauthorized()` is active
# and not customized for APIs (e.g., to return JSON 401), it might return HTML for redirect.
# The current assertion `assert response.status_code != 200` is a general check.
# To make it more specific for an API, you might expect 401.
# If using `flask_login.login_required` with default settings and the request is AJAX/XHR,
# it might return 401. If it's a direct browser-like GET, it might redirect. Test client acts more like direct.
# To ensure 401 for APIs, often a custom handler for `login_manager.unauthorized` is set up.
# For now, the test assumes that a non-200 status indicates access denial.
