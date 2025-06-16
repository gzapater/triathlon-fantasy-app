import pytest
from backend.models import db, Race, FavoriteLink, User, Role, RaceFormat # Import necessary models
from datetime import datetime

# Helper function to create a race directly for testing setup
def create_race_for_test(db_session, user, title="API Test Race", is_general=False):
    race_format = RaceFormat.query.first() # Get any existing format
    if not race_format:
        race_format = RaceFormat(name="Default Format")
        db_session.add(race_format)
        db_session.commit()

    race = Race(
        title=title,
        user_id=user.id,
        race_format_id=race_format.id,
        event_date=datetime.utcnow(),
        gender_category="Mixed",
        is_general=is_general,
        category="Elite" # Add missing category field
    )
    db_session.add(race)
    db_session.commit()
    return race

# Helper function to create a favorite link
def create_favorite_link_for_test(db_session, race_id, title, url, order=0):
    link = FavoriteLink(race_id=race_id, title=title, url=url, order=order)
    db_session.add(link)
    db_session.commit()
    return link

# --- Tests for POST /api/races/<race_id>/favorite_links (Create) ---

def test_create_favorite_link_admin(authenticated_client, db_session, sample_race, admin_user):
    client, _ = authenticated_client("ADMIN")
    payload = {"title": "Admin Link", "url": "https://adminlink.com", "order": 1}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == payload["title"]
    assert FavoriteLink.query.filter_by(race_id=sample_race.id, title="Admin Link").first() is not None

def test_create_favorite_link_league_admin_own_race(authenticated_client, db_session, league_admin_user):
    client, user = authenticated_client("LEAGUE_ADMIN")
    own_race = create_race_for_test(db_session, user, title="League Admin Own Race")
    payload = {"title": "League Link", "url": "https://leaguelink.com"}
    response = client.post(f"/api/races/{own_race.id}/favorite_links", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == payload["title"]
    assert FavoriteLink.query.filter_by(race_id=own_race.id, title="League Link").first() is not None

def test_create_favorite_link_league_admin_other_race(authenticated_client, db_session, sample_race, league_admin_user):
    # sample_race is owned by admin_user by default
    client, _ = authenticated_client("LEAGUE_ADMIN")
    payload = {"title": "League Link Other Race", "url": "https://leaguelinkother.com"}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links", json=payload)
    assert response.status_code == 403 # Forbidden

def test_create_favorite_link_player(authenticated_client, sample_race, player_user):
    client, _ = authenticated_client("PLAYER")
    payload = {"title": "Player Link", "url": "https://playerlink.com"}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links", json=payload)
    assert response.status_code == 403

def test_create_favorite_link_unauthenticated(client, sample_race):
    payload = {"title": "Unauth Link", "url": "https://unauthlink.com"}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links", json=payload)
    assert response.status_code == 401 # Unauthorized

def test_create_favorite_link_validation(authenticated_client, sample_race, admin_user):
    client, _ = authenticated_client("ADMIN")
    # Missing title
    response = client.post(f"/api/races/{sample_race.id}/favorite_links", json={"url": "https://validurl.com"})
    assert response.status_code == 400
    # Missing URL
    response = client.post(f"/api/races/{sample_race.id}/favorite_links", json={"title": "Valid Title"})
    assert response.status_code == 400
    # Invalid URL format
    response = client.post(f"/api/races/{sample_race.id}/favorite_links", json={"title": "Valid Title", "url": "invalidurl"})
    assert response.status_code == 400
    # Invalid race_id
    response = client.post("/api/races/9999/favorite_links", json={"title": "Valid Title", "url": "https://validurl.com"})
    assert response.status_code == 404


# --- Tests for GET /api/races/<race_id>/favorite_links (Read) ---

def test_get_favorite_links(client, db_session, sample_race):
    link1 = create_favorite_link_for_test(db_session, sample_race.id, "Link Alpha", "https://alpha.com", order=1)
    link2 = create_favorite_link_for_test(db_session, sample_race.id, "Link Beta", "https://beta.com", order=0)

    response = client.get(f"/api/races/{sample_race.id}/favorite_links")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "Link Beta" # Ordered by 'order', then 'id' (if order is same)
    assert data[1]["title"] == "Link Alpha"

def test_get_favorite_links_no_links(client, sample_race):
    response = client.get(f"/api/races/{sample_race.id}/favorite_links")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 0

def test_get_favorite_links_invalid_race_id(client):
    response = client.get("/api/races/9999/favorite_links")
    assert response.status_code == 404


# --- Tests for PUT /api/favorite_links/<link_id> (Update) ---

def test_update_favorite_link_admin(authenticated_client, db_session, sample_race, admin_user):
    client, _ = authenticated_client("ADMIN")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Old Title", "https://oldurl.com")
    payload = {"title": "New Title Admin", "url": "https://newurladmin.com", "order": 5}
    response = client.put(f"/api/favorite_links/{link.id}", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "New Title Admin"
    assert data["order"] == 5
    updated_link = FavoriteLink.query.get(link.id)
    assert updated_link.title == "New Title Admin"

def test_update_favorite_link_league_admin_own_race(authenticated_client, db_session, league_admin_user):
    client, user = authenticated_client("LEAGUE_ADMIN")
    own_race = create_race_for_test(db_session, user, title="League Admin Race for Update")
    link = create_favorite_link_for_test(db_session, own_race.id, "League Old", "https://leagueold.com")
    payload = {"title": "League New"}
    response = client.put(f"/api/favorite_links/{link.id}", json=payload)
    assert response.status_code == 200
    updated_link = FavoriteLink.query.get(link.id)
    assert updated_link.title == "League New"

def test_update_favorite_link_league_admin_other_race(authenticated_client, db_session, sample_race, league_admin_user, admin_user):
    # sample_race owned by admin_user
    client, _ = authenticated_client("LEAGUE_ADMIN")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Other's Link", "https://other.com")
    payload = {"title": "Attempt Update"}
    response = client.put(f"/api/favorite_links/{link.id}", json=payload)
    assert response.status_code == 403

def test_update_favorite_link_player(authenticated_client, db_session, sample_race, player_user):
    client, _ = authenticated_client("PLAYER")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Player Cannot Update", "https://playercant.com")
    payload = {"title": "Player Update Attempt"}
    response = client.put(f"/api/favorite_links/{link.id}", json=payload)
    assert response.status_code == 403

def test_update_favorite_link_unauthenticated(client, db_session, sample_race):
    link = create_favorite_link_for_test(db_session, sample_race.id, "Unauth Update Test", "https://unauthupdate.com")
    payload = {"title": "Unauth Update Attempt"}
    response = client.put(f"/api/favorite_links/{link.id}", json=payload)
    assert response.status_code == 401

def test_update_favorite_link_not_found(authenticated_client, admin_user):
    client, _ = authenticated_client("ADMIN")
    response = client.put("/api/favorite_links/9999", json={"title": "Not Found"})
    assert response.status_code == 404

def test_update_favorite_link_validation(authenticated_client, db_session, sample_race, admin_user):
    client, _ = authenticated_client("ADMIN")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Valid Update", "https://validupdate.com")
    response = client.put(f"/api/favorite_links/{link.id}", json={"url": "invalidurl"})
    assert response.status_code == 400


# --- Tests for DELETE /api/favorite_links/<link_id> (Delete) ---

def test_delete_favorite_link_admin(authenticated_client, db_session, sample_race, admin_user):
    client, _ = authenticated_client("ADMIN")
    link = create_favorite_link_for_test(db_session, sample_race.id, "To Delete Admin", "https://deleteadmin.com")
    link_id = link.id
    response = client.delete(f"/api/favorite_links/{link_id}")
    assert response.status_code == 200
    assert FavoriteLink.query.get(link_id) is None

def test_delete_favorite_link_league_admin_own_race(authenticated_client, db_session, league_admin_user):
    client, user = authenticated_client("LEAGUE_ADMIN")
    own_race = create_race_for_test(db_session, user, title="League Admin Race for Delete")
    link = create_favorite_link_for_test(db_session, own_race.id, "To Delete League", "https://deleteleague.com")
    link_id = link.id
    response = client.delete(f"/api/favorite_links/{link_id}")
    assert response.status_code == 200
    assert FavoriteLink.query.get(link_id) is None

def test_delete_favorite_link_league_admin_other_race(authenticated_client, db_session, sample_race, league_admin_user):
    client, _ = authenticated_client("LEAGUE_ADMIN")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Other's Link To Delete", "https://otherdelete.com")
    response = client.delete(f"/api/favorite_links/{link.id}")
    assert response.status_code == 403

def test_delete_favorite_link_player(authenticated_client, db_session, sample_race, player_user):
    client, _ = authenticated_client("PLAYER")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Player Cannot Delete", "https://playerdelete.com")
    response = client.delete(f"/api/favorite_links/{link.id}")
    assert response.status_code == 403

def test_delete_favorite_link_unauthenticated(client, db_session, sample_race):
    link = create_favorite_link_for_test(db_session, sample_race.id, "Unauth Delete Test", "https://unauthdelete.com")
    response = client.delete(f"/api/favorite_links/{link.id}")
    assert response.status_code == 401

def test_delete_favorite_link_not_found(authenticated_client, admin_user):
    client, _ = authenticated_client("ADMIN")
    response = client.delete("/api/favorite_links/9999")
    assert response.status_code == 404

# --- Tests for POST /api/races/<race_id>/favorite_links/reorder (Reorder) ---

def test_reorder_favorite_links_admin(authenticated_client, db_session, sample_race, admin_user):
    client, _ = authenticated_client("ADMIN")
    link1 = create_favorite_link_for_test(db_session, sample_race.id, "Link R1", "https://r1.com", order=0)
    link2 = create_favorite_link_for_test(db_session, sample_race.id, "Link R2", "https://r2.com", order=1)
    link3 = create_favorite_link_for_test(db_session, sample_race.id, "Link R3", "https://r3.com", order=2)

    payload = {"link_ids": [link3.id, link1.id, link2.id]}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links/reorder", json=payload)
    assert response.status_code == 200

    db_session.refresh(link1)
    db_session.refresh(link2)
    db_session.refresh(link3)

    assert link3.order == 0
    assert link1.order == 1
    assert link2.order == 2

def test_reorder_favorite_links_league_admin_own_race(authenticated_client, db_session, league_admin_user):
    client, user = authenticated_client("LEAGUE_ADMIN")
    own_race = create_race_for_test(db_session, user, title="League Admin Race for Reorder")
    linkA = create_favorite_link_for_test(db_session, own_race.id, "Link RA", "https://ra.com", order=0)
    linkB = create_favorite_link_for_test(db_session, own_race.id, "Link RB", "https://rb.com", order=1)

    payload = {"link_ids": [linkB.id, linkA.id]}
    response = client.post(f"/api/races/{own_race.id}/favorite_links/reorder", json=payload)
    assert response.status_code == 200
    db_session.refresh(linkA)
    db_session.refresh(linkB)
    assert linkB.order == 0
    assert linkA.order == 1

def test_reorder_favorite_links_league_admin_other_race(authenticated_client, db_session, sample_race, league_admin_user):
    client, _ = authenticated_client("LEAGUE_ADMIN")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Other Link Reorder", "https://otherreorder.com")
    payload = {"link_ids": [link.id]}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links/reorder", json=payload)
    assert response.status_code == 403

def test_reorder_favorite_links_player(authenticated_client, db_session, sample_race, player_user):
    client, _ = authenticated_client("PLAYER")
    link = create_favorite_link_for_test(db_session, sample_race.id, "Player Reorder", "https://playerreorder.com")
    payload = {"link_ids": [link.id]}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links/reorder", json=payload)
    assert response.status_code == 403

def test_reorder_favorite_links_unauthenticated(client, db_session, sample_race):
    link = create_favorite_link_for_test(db_session, sample_race.id, "Unauth Reorder", "https://unauthreorder.com")
    payload = {"link_ids": [link.id]}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links/reorder", json=payload)
    assert response.status_code == 401

def test_reorder_favorite_links_invalid_race_id(authenticated_client, admin_user):
    client, _ = authenticated_client("ADMIN")
    response = client.post("/api/races/9999/favorite_links/reorder", json={"link_ids": [1, 2]})
    assert response.status_code == 404

def test_reorder_favorite_links_empty_list(authenticated_client, sample_race, admin_user):
    client, _ = authenticated_client("ADMIN")
    create_favorite_link_for_test(db_session, sample_race.id, "Link E1", "https://e1.com", order=0)
    payload = {"link_ids": []}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links/reorder", json=payload)
    assert response.status_code == 200 # API should handle this gracefully, perhaps no change or success
    # Verify no change or specific behavior if needed, e.g. all links still exist with original order
    link_e1 = FavoriteLink.query.filter_by(title="Link E1").first()
    assert link_e1.order == 0 # Assuming it doesn't get re-ordered to 0 if it's the only one and list is empty

def test_reorder_favorite_links_ids_not_belonging_to_race(authenticated_client, db_session, sample_race, admin_user):
    client, user = authenticated_client("ADMIN")
    other_race = create_race_for_test(db_session, user, title="Another Race for Reorder Test")
    link_in_sample_race = create_favorite_link_for_test(db_session, sample_race.id, "Link S", "https://s.com")
    link_in_other_race = create_favorite_link_for_test(db_session, other_race.id, "Link O", "https://o.com")

    # Try to reorder links for sample_race, but include a link from other_race
    payload = {"link_ids": [link_in_sample_race.id, link_in_other_race.id]}
    response = client.post(f"/api/races/{sample_race.id}/favorite_links/reorder", json=payload)
    # The API should either ignore the foreign link_id or return an error.
    # Current implementation of reorder in app.py filters by race_id, so foreign link is ignored.
    # If it ignores, the response might be 200 but only link_in_sample_race is affected.
    assert response.status_code == 400 # Expecting bad request as some IDs don't belong
    # Or if API is lenient and reorders only valid ones:
    # assert response.status_code == 200
    # db_session.refresh(link_in_sample_race)
    # assert link_in_sample_race.order == 0 # Would be the only valid link in the list
    # db_session.refresh(link_in_other_race)
    # assert link_in_other_race.order == 0 # Unchanged from its creation

    # Test with only a link not belonging to the race
    payload_only_other = {"link_ids": [link_in_other_race.id]}
    response_only_other = client.post(f"/api/races/{sample_race.id}/favorite_links/reorder", json=payload_only_other)
    assert response_only_other.status_code == 400 # Expecting bad request
    # Or if API is lenient:
    # assert response_only_other.status_code == 200
    # db_session.refresh(link_in_other_race)
    # assert link_in_other_race.order == 0 # Unchanged

# Note: The `sample_race` fixture is owned by `admin_user`.
# `league_admin_user` and `player_user` are separate.
# Helper functions might be needed for more complex scenarios like creating races owned by league_admin_user.
# The `create_race_for_test` helper above is a good start.

# Ensure all tests clean up: pytest-flask with SQLAlchemy usually handles session rollback for in-memory DBs.
# If using persistent DBs for testing, more explicit cleanup might be needed.
# For these tests, the in-memory SQLite DB is reset for each test session due to `app` fixture scope.
# Individual test functions get a clean `db_session` but data from previous tests in the same session might persist
# if not properly isolated or if commits are made directly without rollback.
# `db_session.commit()` is used in helpers, so data persists for the duration of a test.
# For full isolation, each test should ideally run in a transaction that's rolled back.
# However, for simplicity and common patterns, this setup is often used.
# The current `conftest.py` structure seems to create tables once per session.
# Granular cleanup per test might be needed if tests interfere.
# For `sqlite:///:memory:`, the database is per-session.
# The `db_session` fixture in `conftest.py` does `_db.session.remove()` and `_db.drop_all()` at the end of the app context (session scope).
# So individual tests should be relatively isolated in terms of DB state if they create their own specific data.
# Data created by fixtures like `sample_race` will persist across tests using it within the same session.
# This is generally fine if tests only read or add non-conflicting data.
# For tests that modify or delete shared fixture data, care must be taken.
# For example, if a test deletes `sample_race`, other tests using it will fail.
# The `sample_race` fixture is function-scoped (re-created for each test function that uses it) if `db_session` is function-scoped.
# In current `conftest.py`, `db_session` is function-scoped, so `sample_race` should also be.
# Let's confirm `sample_race` scope. It uses `db_session` (function) and `admin_user` (function). So `sample_race` is function-scoped. Good.

# Add a missing import from conftest
@pytest.fixture
def race_format(db_session):
    rf = RaceFormat.query.filter_by(name="Triatlón").first()
    if not rf:
        rf = RaceFormat(name="Triatlón")
        db_session.add(rf)
        db_session.commit()
    return rf

# A fixture for a race owned by league_admin_user
@pytest.fixture
def league_admin_owned_race(db_session, league_admin_user, race_format):
    race = Race(
        title="League Admin's Test Race",
        user_id=league_admin_user.id,
        race_format_id=race_format.id,
        event_date=datetime.utcnow(),
        gender_category="Female",
        is_general=False, # Local race
        category="Masters"
    )
    db_session.add(race)
    db_session.commit()
    return race

# Re-check test: test_create_favorite_link_league_admin_own_race
# It creates its own race, which is fine.
# Re-check test: test_update_favorite_link_league_admin_own_race
# It also creates its own race.

# Re-check test: test_reorder_favorite_links_ids_not_belonging_to_race
# The current API implementation for reorder filters links by race_id first.
# If any of the provided link_ids do not belong to that race_id after filtering,
# it means the client sent invalid data. The API should return 400 in this case.
# The test logic seems to anticipate this.
# The `FavoriteLink.query.filter(FavoriteLink.id.in_(link_ids), FavoriteLink.race_id == race_id).all()`
# in the app code handles this correctly. If `len(links_to_reorder)` is not equal to `len(link_ids)`,
# it means some IDs were filtered out, implying they didn't belong to `race_id`.
# The app code returns 400 in that case with a message. This is correct.

# The test `test_reorder_favorite_links_ids_not_belonging_to_race` already checks for 400.
# The commented out section was for an alternative lenient API behavior.
# The current strict behavior (400 if any link ID doesn't match) is good.

# A small addition to `create_race_for_test` if `category` is mandatory.
# In `models.py`, `Race.category` has `default="Elite", nullable=False`. So it's handled.
# This is fine.
