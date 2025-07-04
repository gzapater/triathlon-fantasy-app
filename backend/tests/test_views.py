import json
from datetime import datetime
from backend.models import User, Race, RaceFormat, Role, db, UserRaceRegistration # Adjusted import path, Added UserRaceRegistration

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
        assert "Directorio de Triatlón y Duatlón en España" in response_data_text # Check for H1 content
        assert 'eventsContainer' in response_data_text # Check for the div where events would be loaded
        # Check that the promo page specific content is NOT there
        assert "El pique no debería acabar en la línea de meta." not in response_data_text

class TestLeagueDetailView:
    def test_league_detail_no_participants(self, client, new_league_admin_user, new_league):
        """Test league detail page when league has no participants."""
        db.session.add(new_league_admin_user)
        new_league.creator_id = new_league_admin_user.id
        db.session.add(new_league)
        db.session.commit()

        client.post('/api/login', json={'username': new_league_admin_user.username, 'password': 'testpassword'})

        response = client.get(f'/league/{new_league.id}/view')
        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)
        assert "Clasificación de la Liga" in response_data_text
        assert "Aún no hay participantes en esta liga o no se han calculado puntuaciones." in response_data_text
        assert f"Participantes (0)" in response_data_text


    def test_league_detail_with_participants_no_scores(self, client, new_league_admin_user, new_player_user, new_league, sample_race):
        """Test league detail page with participants but no scores."""
        from backend.models import LeagueParticipant, league_races_table, UserScore

        # Setup league, admin, player
        db.session.add(new_league_admin_user)
        new_league.creator_id = new_league_admin_user.id
        db.session.add(new_league)
        db.session.add(new_player_user)
        db.session.commit()

        # Add race to league
        sample_race.user_id = new_league_admin_user.id # Race created by league admin
        db.session.add(sample_race)
        db.session.commit()
        insert_league_race = league_races_table.insert().values(league_id=new_league.id, race_id=sample_race.id)
        db.session.execute(insert_league_race)

        # Add player as participant to league
        lp = LeagueParticipant(user_id=new_player_user.id, league_id=new_league.id)
        db.session.add(lp)
        db.session.commit()

        client.post('/api/login', json={'username': new_league_admin_user.username, 'password': 'testpassword'})
        response = client.get(f'/league/{new_league.id}/view')

        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)

        assert "Clasificación de la Liga" in response_data_text
        assert f'<td class="px-6 py-4 whitespace-nowrap text-center">\n                                        <div class="text-sm font-medium text-gray-900">1</div>\n                                    </td>' in response_data_text
        assert f'<div class="text-sm text-gray-700">{new_player_user.username}</div>' in response_data_text
        assert f'<div class="text-sm font-bold text-gray-900">0</div>' in response_data_text # Expect 0 points
        assert f"Participantes (1)" in response_data_text
        # Check that "Generar Nuevo Código" button is NOT present
        assert "Generar Nuevo Código" not in response_data_text
        # If an admin is viewing and a code exists, the "Ver Código de Invitación" button should be there.
        # For this test, no code was explicitly created and associated, so the button might not be there.
        # We can add a sub-test for when a code exists.

    def test_league_detail_shows_view_code_button_for_admin_if_code_exists(self, client, new_league_admin_user, new_league):
        from backend.models import LeagueInvitationCode
        db.session.add(new_league_admin_user)
        new_league.creator_id = new_league_admin_user.id
        db.session.add(new_league)
        db.session.commit() # Commit league to get its ID

        # Create an active invitation code for the league
        inv_code = LeagueInvitationCode(league_id=new_league.id, code="TESTCODE123", is_active=True)
        db.session.add(inv_code)
        db.session.commit()

        client.post('/api/login', json={'username': new_league_admin_user.username, 'password': 'testpassword'})
        response = client.get(f'/league/{new_league.id}/view')
        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)

        assert "Ver Código de Invitación" in response_data_text
        assert "TESTCODE123" in response_data_text # Code should be in the modal structure (hidden initially)
        assert "Generar Nuevo Código" not in response_data_text # Button to generate should be gone

    def test_league_detail_with_participants_and_scores(self, client, new_league_admin_user, new_player_user, another_player_user, new_league, sample_race, another_race):
        """Test league detail page with participants and scores in multiple races."""
        from backend.models import LeagueParticipant, league_races_table, UserScore

        # Setup users and league
        db.session.add_all([new_league_admin_user, new_player_user, another_player_user])
        new_league.creator_id = new_league_admin_user.id
        db.session.add(new_league)
        db.session.commit()

        # Setup races (created by league admin)
        sample_race.user_id = new_league_admin_user.id
        another_race.user_id = new_league_admin_user.id
        db.session.add_all([sample_race, another_race])
        db.session.commit()

        # Add races to league
        db.session.execute(league_races_table.insert().values(league_id=new_league.id, race_id=sample_race.id))
        db.session.execute(league_races_table.insert().values(league_id=new_league.id, race_id=another_race.id))

        # Add participants to league
        lp1 = LeagueParticipant(user_id=new_player_user.id, league_id=new_league.id)
        lp2 = LeagueParticipant(user_id=another_player_user.id, league_id=new_league.id)
        db.session.add_all([lp1, lp2])

        # Add scores for participants in races
        # Player 1: Race 1 = 100 pts, Race 2 = 50 pts. Total = 150
        score1_race1 = UserScore(user_id=new_player_user.id, race_id=sample_race.id, score=100)
        score1_race2 = UserScore(user_id=new_player_user.id, race_id=another_race.id, score=50)
        # Player 2: Race 1 = 70 pts, Race 2 = 120 pts. Total = 190
        score2_race1 = UserScore(user_id=another_player_user.id, race_id=sample_race.id, score=70)
        score2_race2 = UserScore(user_id=another_player_user.id, race_id=another_race.id, score=120)
        db.session.add_all([score1_race1, score1_race2, score2_race1, score2_race2])
        db.session.commit()

        client.post('/api/login', json={'username': new_league_admin_user.username, 'password': 'testpassword'})
        response = client.get(f'/league/{new_league.id}/view')
        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)

        assert "Clasificación de la Liga" in response_data_text
        # Player 2 should be first (190 points)
        assert f'<div class="text-sm text-gray-700">{another_player_user.username}</div>' in response_data_text
        assert f'<div class="text-sm font-bold text-gray-900">190</div>' in response_data_text
        # Player 1 should be second (150 points)
        assert f'<div class="text-sm text-gray-700">{new_player_user.username}</div>' in response_data_text
        assert f'<div class="text-sm font-bold text-gray-900">150</div>' in response_data_text

        # Check order (Player 2 then Player 1)
        # This is a bit fragile, depends on exact HTML structure. A more robust way would be to parse HTML.
        pos_player2 = response_data_text.find(f'<div class="text-sm text-gray-700">{another_player_user.username}</div>')
        pos_player1 = response_data_text.find(f'<div class="text-sm text-gray-700">{new_player_user.username}</div>')
        assert pos_player2 != -1 and pos_player1 != -1
        assert pos_player2 < pos_player1 # Player 2 appears before Player 1 in the standings

        assert f"Participantes (2)" in response_data_text


    def test_league_detail_participant_with_no_scores_in_league_races(self, client, new_league_admin_user, new_player_user, new_league, sample_race):
        """Test a participant in the league has scores for other races, but not for this league's races."""
        from backend.models import LeagueParticipant, league_races_table, UserScore, Race as RaceModel

        # Setup users and league
        db.session.add_all([new_league_admin_user, new_player_user])
        new_league.creator_id = new_league_admin_user.id
        db.session.add(new_league)

        # League's race
        sample_race.user_id = new_league_admin_user.id
        sample_race.title = "League Race With No Scores For Player"
        db.session.add(sample_race)
        db.session.commit()
        db.session.execute(league_races_table.insert().values(league_id=new_league.id, race_id=sample_race.id))

        # Another race, NOT in the league, where the player has a score
        non_league_race = RaceModel(title="Non-League Race", race_format_id=sample_race.race_format_id, event_date=datetime.utcnow(), gender_category="MIXED", user_id=new_league_admin_user.id)
        db.session.add(non_league_race)
        db.session.commit()

        # Player is participant in the league
        lp = LeagueParticipant(user_id=new_player_user.id, league_id=new_league.id)
        db.session.add(lp)

        # Player has score in non-league race
        score_in_other_race = UserScore(user_id=new_player_user.id, race_id=non_league_race.id, score=500)
        db.session.add(score_in_other_race)
        db.session.commit()

        client.post('/api/login', json={'username': new_league_admin_user.username, 'password': 'testpassword'})
        response = client.get(f'/league/{new_league.id}/view')
        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)

        assert "Clasificación de la Liga" in response_data_text
        assert f'<div class="text-sm text-gray-700">{new_player_user.username}</div>' in response_data_text
        # Expect 0 points for this league, despite having scores elsewhere
        assert f'<div class="text-sm font-bold text-gray-900">0</div>' in response_data_text
        assert f"Participantes (1)" in response_data_text

    def test_tripredict_promo_page_no_longer_shows_events(self, client):
        """Test that the / promo page no longer directly embeds the events list script."""
        response = client.get('/')
        assert response.status_code == 200
        response_data_text = response.get_data(as_text=True)
        # Check for a known part of the promo page
        assert "El pique no debería acabar en la línea de meta." in response_data_text
        # Check that the events container or its specific loading/error indicators are NOT there
        assert 'id="events-container"' not in response_data_text
        assert 'id="events-loading"' not in response_data_text
        assert "Cargando eventos..." not in response_data_text


class TestRaceParticipationWizardAPI:
    def test_wizard_start_unauthenticated(self, client, sample_race):
        db.session.add(sample_race)
        db.session.commit()
        response = client.get(f'/api/race/{sample_race.id}/wizard/start')
        assert response.status_code == 401 # Expect unauthorized

    def test_wizard_start_race_not_found(self, client, new_player_user):
        db.session.add(new_player_user)
        db.session.commit()
        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        response = client.get('/api/race/9999/wizard/start') # Non-existent race
        assert response.status_code == 404
        assert "Race not found" in response.get_json()['message']

    def test_wizard_start_user_not_registered(self, client, new_player_user, sample_race):
        db.session.add_all([new_player_user, sample_race])
        db.session.commit()
        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        response = client.get(f'/api/race/{sample_race.id}/wizard/start')
        assert response.status_code == 403
        assert "not registered for this race" in response.get_json()['message']

    def test_wizard_start_quiniela_closed(self, client, new_player_user, sample_race_with_registration):
        # sample_race_with_registration already has user registered
        race = sample_race_with_registration.race
        race.quiniela_close_date = datetime.utcnow() - timedelta(hours=1) # Quiniela closed
        db.session.add(race)
        db.session.commit()

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        response = client.get(f'/api/race/{race.id}/wizard/start')
        assert response.status_code == 403
        assert "quiniela for this race is closed" in response.get_json()['message']

        # Reset quiniela_close_date for other tests if race object is reused
        race.quiniela_close_date = datetime.utcnow() + timedelta(days=1)
        db.session.commit()


    def test_wizard_start_no_questions(self, client, new_player_user, sample_race_with_registration):
        race = sample_race_with_registration.race
        # Ensure no questions for this race
        Question.query.filter_by(race_id=race.id).delete()
        db.session.commit()

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        response = client.get(f'/api/race/{race.id}/wizard/start')
        assert response.status_code == 404
        assert "No questions found" in response.get_json()['message']

    def test_wizard_start_success_one_question(self, client, new_player_user, sample_race_with_registration_and_question):
        race = sample_race_with_registration_and_question.race
        question = sample_race_with_registration_and_question.question # The single question

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        response = client.get(f'/api/race/{race.id}/wizard/start')
        assert response.status_code == 200
        data = response.get_json()
        assert data['question']['id'] == question.id
        assert data['question']['text'] == question.text
        assert data['is_final_step'] is True # Only one question

    def test_wizard_start_success_multiple_questions(self, client, new_player_user, sample_race_with_registration_and_questions):
        race = sample_race_with_registration_and_questions.race
        first_question = sample_race_with_registration_and_questions.questions[0]

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        response = client.get(f'/api/race/{race.id}/wizard/start')
        assert response.status_code == 200
        data = response.get_json()
        assert data['question']['id'] == first_question.id
        assert data['is_final_step'] is False # Multiple questions

    def test_wizard_next_save_answer_and_get_next_q(self, client, new_player_user, sample_race_with_registration_and_questions):
        race = sample_race_with_registration_and_questions.race
        questions = sample_race_with_registration_and_questions.questions # List of 2 questions
        q1 = questions[0]
        q2 = questions[1]

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})

        # Answer Q1
        payload_q1 = {
            "current_question_id": q1.id,
            "answer": {"answer_text": "Answer for Q1"} # Assuming Q1 is FREE_TEXT
        }
        response_q1_submit = client.post(f'/api/race/{race.id}/wizard/next', json=payload_q1)
        assert response_q1_submit.status_code == 200
        data_q1_submit = response_q1_submit.get_json()

        assert data_q1_submit['is_final_step'] is True # Because q2 will be the last one presented
        assert data_q1_submit['next_question']['id'] == q2.id

        # Verify Q1 answer was saved
        ua_q1 = UserAnswer.query.filter_by(user_id=new_player_user.id, question_id=q1.id).first()
        assert ua_q1 is not None
        assert ua_q1.answer_text == "Answer for Q1"

        # Answer Q2 (the last one)
        payload_q2 = {
            "current_question_id": q2.id,
            "answer": {"answer_text": "Final Answer for Q2"} # Assuming Q2 is FREE_TEXT
        }
        response_q2_submit = client.post(f'/api/race/{race.id}/wizard/next', json=payload_q2)
        assert response_q2_submit.status_code == 200
        data_q2_submit = response_q2_submit.get_json()

        assert data_q2_submit['is_final_step'] is True
        assert "answered all questions" in data_q2_submit['completion_message']
        assert 'next_question' not in data_q2_submit # No next question

        # Verify Q2 answer was saved
        ua_q2 = UserAnswer.query.filter_by(user_id=new_player_user.id, question_id=q2.id).first()
        assert ua_q2 is not None
        assert ua_q2.answer_text == "Final Answer for Q2"

    def test_wizard_next_quiniela_closed(self, client, new_player_user, sample_race_with_registration_and_question):
        race = sample_race_with_registration_and_question.race
        question = sample_race_with_registration_and_question.question
        race.quiniela_close_date = datetime.utcnow() - timedelta(hours=1) # Quiniela closed
        db.session.add(race)
        db.session.commit()

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        payload = {"current_question_id": question.id, "answer": {"answer_text": "Too late"}}
        response = client.post(f'/api/race/{race.id}/wizard/next', json=payload)
        assert response.status_code == 403
        assert "quiniela for this race is closed" in response.get_json()['message']

        # Reset quiniela_close_date
        race.quiniela_close_date = datetime.utcnow() + timedelta(days=1)
        db.session.commit()


    def test_wizard_finish_success(self, client, new_player_user, sample_race_with_registration):
        race = sample_race_with_registration.race
        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})
        response = client.post(f'/api/race/{race.id}/wizard/finish')
        assert response.status_code == 200
        assert "Participation successfully recorded" in response.get_json()['message']

    def test_wizard_next_save_mc_single_answer(self, client, new_player_user, sample_race_with_registration_and_mc_question):
        race = sample_race_with_registration_and_mc_question.race
        question = sample_race_with_registration_and_mc_question.question # MC Single
        option_to_select = question.options.first() # Select the first option

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})

        payload = {
            "current_question_id": question.id,
            "answer": {"selected_option_id": option_to_select.id}
        }
        response = client.post(f'/api/race/{race.id}/wizard/next', json=payload)
        assert response.status_code == 200 # Assuming this is the last/only question

        ua = UserAnswer.query.filter_by(user_id=new_player_user.id, question_id=question.id).first()
        assert ua is not None
        assert ua.selected_option_id == option_to_select.id

    def test_wizard_next_save_mc_multiple_answer(self, client, new_player_user, sample_race_with_registration_and_mc_multi_question):
        race = sample_race_with_registration_and_mc_multi_question.race
        question = sample_race_with_registration_and_mc_multi_question.question # MC Multi
        options_to_select = [opt.id for opt in question.options.limit(2).all()] # Select first two options

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})

        payload = {
            "current_question_id": question.id,
            "answer": {"selected_option_ids": options_to_select}
        }
        response = client.post(f'/api/race/{race.id}/wizard/next', json=payload)
        assert response.status_code == 200

        ua = UserAnswer.query.filter_by(user_id=new_player_user.id, question_id=question.id).first()
        assert ua is not None
        assert len(ua.selected_mc_options) == len(options_to_select)
        selected_ids_in_db = {mc_opt.question_option_id for mc_opt in ua.selected_mc_options}
        assert selected_ids_in_db == set(options_to_select)

    def test_wizard_next_save_slider_answer(self, client, new_player_user, sample_race_with_registration_and_slider_question):
        race = sample_race_with_registration_and_slider_question.race
        question = sample_race_with_registration_and_slider_question.question # Slider

        client.post('/api/login', json={'username': new_player_user.username, 'password': 'testpassword'})

        slider_value_to_save = (question.slider_min_value + question.slider_max_value) / 2
        payload = {
            "current_question_id": question.id,
            "answer": {"slider_answer_value": slider_value_to_save}
        }
        response = client.post(f'/api/race/{race.id}/wizard/next', json=payload)
        assert response.status_code == 200

        ua = UserAnswer.query.filter_by(user_id=new_player_user.id, question_id=question.id).first()
        assert ua is not None
        assert ua.slider_answer_value == slider_value_to_save

# Make sure to import timedelta and Question, UserAnswer if not already imported at the top
from datetime import timedelta
from backend.models import Question, UserAnswer
