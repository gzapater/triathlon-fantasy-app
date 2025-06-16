import pytest
from backend.models import db, Race, FavoriteLink, User # Assuming User model is needed for race creation context
from datetime import datetime

def test_favorite_link_creation(db_session, sample_race):
    """Test creating a FavoriteLink with valid data and association to a race."""
    link_title = "Official Event Page"
    link_url = "https://example.com/race-details"
    link_order = 1

    fav_link = FavoriteLink(
        title=link_title,
        url=link_url,
        order=link_order,
        race_id=sample_race.id
    )
    db_session.add(fav_link)
    db_session.commit()

    assert fav_link.id is not None
    assert fav_link.title == link_title
    assert fav_link.url == link_url
    assert fav_link.order == link_order
    assert fav_link.race_id == sample_race.id
    assert fav_link.created_at is not None
    assert fav_link.updated_at is not None
    assert fav_link.race == sample_race

def test_favorite_link_default_order(db_session, sample_race):
    """Test that the default order for a FavoriteLink is 0."""
    fav_link = FavoriteLink(
        title="Sponsor Site",
        url="https://sponsor.example.com",
        race_id=sample_race.id
        # order is not specified
    )
    db_session.add(fav_link)
    db_session.commit()

    assert fav_link.order == 0

def test_favorite_link_repr(db_session, sample_race):
    """Test the __repr__ method of FavoriteLink."""
    fav_link = FavoriteLink(
        title="Results Page",
        url="https://results.example.com",
        race_id=sample_race.id
    )
    db_session.add(fav_link)
    db_session.commit()

    assert repr(fav_link) == f"<FavoriteLink {fav_link.title}>"

def test_favorite_link_to_dict(db_session, sample_race):
    """Test the to_dict() method for correct serialization."""
    fav_link = FavoriteLink(
        title="Photos",
        url="https://photos.example.com",
        order=2,
        race_id=sample_race.id,
        created_at=datetime(2023, 1, 1, 10, 0, 0), # Fixed datetime for predictable isoformat
        updated_at=datetime(2023, 1, 1, 11, 0, 0)  # Fixed datetime
    )
    db_session.add(fav_link)
    db_session.commit()

    # Fetch from DB to ensure created_at/updated_at are handled as they would be in app
    retrieved_link = FavoriteLink.query.get(fav_link.id)

    expected_dict = {
        'id': retrieved_link.id,
        'title': "Photos",
        'url': "https://photos.example.com",
        'order': 2,
        'race_id': sample_race.id,
        'created_at': retrieved_link.created_at.isoformat(),
        'updated_at': retrieved_link.updated_at.isoformat()
    }
    assert retrieved_link.to_dict() == expected_dict

def test_race_favorite_links_relationship(db_session, sample_race):
    """Test the relationship from Race to FavoriteLink."""
    link1 = FavoriteLink(title="Link 1", url="https://link1.com", race_id=sample_race.id, order=1)
    link2 = FavoriteLink(title="Link 2", url="https://link2.com", race_id=sample_race.id, order=0)
    db_session.add_all([link1, link2])
    db_session.commit()

    # Refresh sample_race to ensure relationships are loaded
    db_session.refresh(sample_race)

    assert len(sample_race.favorite_links) == 2
    # SQLAlchemy default order for relationships is not guaranteed unless specified in relationship
    # For testing, we can sort them
    sorted_links = sorted(sample_race.favorite_links, key=lambda x: x.order)
    assert sorted_links[0].title == "Link 2"
    assert sorted_links[1].title == "Link 1"
    assert link2 in sample_race.favorite_links
    assert link1 in sample_race.favorite_links

def test_favorite_link_cascade_delete_on_race_delete(db_session, admin_user):
    """Test that FavoriteLinks are deleted when their parent Race is deleted."""
    # Create a new race for this test to avoid affecting sample_race if it's used elsewhere
    race_format = db.session.query(RaceFormat).first()
    if not race_format:
        race_format = RaceFormat(name="Test Format for Cascade")
        db_session.add(race_format)
        db_session.commit()

    test_race = Race(
        title="Race for Cascade Delete Test",
        race_format_id=race_format.id,
        event_date=datetime.utcnow(),
        user_id=admin_user.id, # Assuming admin_user fixture is available and provides a User object
        gender_category="Mixed",
        category="All"
    )
    db_session.add(test_race)
    db_session.commit()

    link1 = FavoriteLink(title="Cascade Link 1", url="https://cascade1.com", race_id=test_race.id)
    link2 = FavoriteLink(title="Cascade Link 2", url="https://cascade2.com", race_id=test_race.id)
    db_session.add_all([link1, link2])
    db_session.commit()

    assert FavoriteLink.query.count() == 2 # Before deleting race

    race_id_to_delete = test_race.id
    db_session.delete(test_race)
    db_session.commit()

    assert Race.query.get(race_id_to_delete) is None
    # Check if links associated with the deleted race are also gone
    # This relies on the cascade="all, delete-orphan" in Race.favorite_links relationship
    assert FavoriteLink.query.filter_by(race_id=race_id_to_delete).count() == 0
    # If other races/links exist, this check should be specific to the links of the deleted race
    # For this test, we assume these are the only links. If not, adjust count or filter more specifically.
    # A better check if other links might exist:
    # assert FavoriteLink.query.get(link1.id) is None
    # assert FavoriteLink.query.get(link2.id) is None
    # For this setup, the count check is fine.
    # Re-querying:
    links_after_delete = FavoriteLink.query.filter(FavoriteLink.race_id == race_id_to_delete).all()
    assert len(links_after_delete) == 0

# Fixture for RaceFormat if not already broadly available or to ensure it exists for tests
@pytest.fixture(scope="function") # or module if shared
def ensure_race_format(db_session):
    race_format = db_session.query(RaceFormat).filter_by(name="Triatlón Test Model").first()
    if not race_format:
        race_format = RaceFormat(name="Triatlón Test Model")
        db_session.add(race_format)
        db_session.commit()
    return race_format

# Fixture for a race, specifically for model tests if `sample_race` has broader scope issues
@pytest.fixture
def test_race_model(db_session, admin_user, ensure_race_format):
    race = Race(
        title="Model Test Race",
        description="A race for model testing.",
        race_format_id=ensure_race_format.id,
        event_date=datetime.strptime("2025-01-01", "%Y-%m-%d"),
        location="Model Test Location",
        user_id=admin_user.id,
        is_general=False,
        gender_category="Mixed",
        category="Elite"
    )
    db_session.add(race)
    db_session.commit()
    return race

# Example of using the specific test_race_model fixture
def test_favorite_link_with_specific_race(db_session, test_race_model):
    link = FavoriteLink(title="Link A", url="https://linka.com", race_id=test_race_model.id)
    db_session.add(link)
    db_session.commit()
    assert link.race == test_race_model
    assert len(test_race_model.favorite_links) == 1
    assert test_race_model.favorite_links[0].title == "Link A"
