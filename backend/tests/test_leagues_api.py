import pytest
from backend.models import db, User, Role, League, Race, LeagueInvitationCode, LeagueParticipant, UserRaceRegistration, RaceStatus
from datetime import datetime, timedelta

# Fixture para crear una liga de prueba
@pytest.fixture
def sample_league(db_session, league_admin_user):
    league = League(
        name="Test League for API",
        description="A league for testing API endpoints.",
        creator_id=league_admin_user.id,
        is_active=True,
        is_deleted=False
    )
    db_session.add(league)
    db_session.commit()
    return league

# Fixture para crear un código de invitación para una liga
@pytest.fixture
def sample_invitation_code(db_session, sample_league):
    inv_code = LeagueInvitationCode(
        league_id=sample_league.id,
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=7) # Código válido por 7 días
    )
    db_session.add(inv_code)
    db_session.commit()
    return inv_code

# Fixture para crear una carrera de prueba asociada a un usuario (league_admin_user por defecto)
@pytest.fixture
def sample_race_for_league(db_session, league_admin_user, new_race_format): # new_race_format de conftest
    race = Race(
        title="Test Race for League",
        race_format_id=new_race_format.id,
        event_date=datetime.utcnow() + timedelta(days=30),
        user_id=league_admin_user.id,
        status=RaceStatus.PLANNED, # Importante para la lógica de inscripción automática
        gender_category="Ambos",
        is_general=False
    )
    db_session.add(race)
    db_session.commit()
    return race

# Fixture para asociar una carrera a una liga
@pytest.fixture
def league_with_race(db_session, sample_league, sample_race_for_league):
    sample_league.races.append(sample_race_for_league)
    db_session.commit()
    return sample_league

# --- Tests para /api/leagues/join_by_code ---

def test_join_league_successfully(authenticated_client, league_with_race, sample_invitation_code, player_user):
    """Test joining a league successfully with a valid code."""
    client, _ = authenticated_client(role_code='PLAYER') # Autenticar como PLAYER

    # Asegurarse de que el player_user es el que está autenticado
    # Esto es un poco indirecto, el fixture authenticated_client crea un nuevo usuario para cada rol.
    # Necesitamos el ID del usuario que realmente se autenticó.
    # Una forma más directa sería tener un fixture que autentica un usuario específico.
    # Por ahora, asumimos que el player_user del fixture es diferente al creado por authenticated_client.
    # Para este test, el 'player_user' no es relevante, sino el usuario autenticado por 'client'.

    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': sample_invitation_code.code
    })

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['message'].startswith("¡Te has unido a la liga")
    assert json_data['league_id'] == league_with_race.id

    # Verificar que el usuario es ahora participante de la liga
    auth_user_id = User.query.filter_by(username='player_test_user').first().id # Asumiendo el nombre del usuario creado por authenticated_client
    participant_entry = LeagueParticipant.query.filter_by(user_id=auth_user_id, league_id=league_with_race.id).first()
    assert participant_entry is not None

    # Verificar que el usuario fue inscrito en la carrera de la liga
    race_in_league = league_with_race.races.first()
    assert race_in_league is not None
    race_registration = UserRaceRegistration.query.filter_by(user_id=auth_user_id, race_id=race_in_league.id).first()
    assert race_registration is not None

def test_join_league_invalid_code(authenticated_client, league_with_race):
    """Test joining a league with an invalid code."""
    client, _ = authenticated_client(role_code='PLAYER')

    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': 'INVALID-CODE-XYZ'
    })

    assert response.status_code == 404
    json_data = response.get_json()
    assert "Código de invitación no válido o ha expirado" in json_data['message']

def test_join_league_already_participant(authenticated_client, league_with_race, sample_invitation_code, player_user):
    """Test joining a league when the user is already a participant."""
    # El usuario autenticado por authenticated_client('PLAYER') es 'player_test_user'
    client, auth_player = authenticated_client(role_code='PLAYER')

    # Hacer que el usuario autenticado ya sea participante
    participant = LeagueParticipant(user_id=auth_player.id, league_id=league_with_race.id)
    db.session.add(participant)
    db.session.commit()

    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': sample_invitation_code.code
    })

    assert response.status_code == 200 # Debería ser 200 OK si ya es miembro
    json_data = response.get_json()
    assert "Ya eres participante de esta liga" in json_data['message']
    assert json_data['league_id'] == league_with_race.id

def test_join_league_inactive_league(authenticated_client, sample_league, sample_invitation_code):
    """Test joining a league that is inactive."""
    client, _ = authenticated_client(role_code='PLAYER')

    sample_league.is_active = False
    db.session.commit()

    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': sample_invitation_code.code
    })

    assert response.status_code == 404 # La liga no se considera "disponible"
    json_data = response.get_json()
    assert "La liga asociada a este código no está disponible o no está activa" in json_data['message']

    sample_league.is_active = True # Reset para otros tests
    db.session.commit()


def test_join_league_inactive_invitation_code(authenticated_client, sample_league, sample_invitation_code):
    """Test joining a league with an inactive invitation code."""
    client, _ = authenticated_client(role_code='PLAYER')

    sample_invitation_code.is_active = False
    db.session.commit()

    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': sample_invitation_code.code
    })

    assert response.status_code == 404
    json_data = response.get_json()
    assert "Código de invitación no válido o ha expirado" in json_data['message']

    sample_invitation_code.is_active = True # Reset para otros tests
    db.session.commit()


def test_join_league_no_code_provided(authenticated_client):
    """Test joining a league without providing an access code."""
    client, _ = authenticated_client(role_code='PLAYER')

    response = client.post('/api/leagues/join_by_code', json={}) # Payload vacío
    assert response.status_code == 400
    json_data = response.get_json()
    assert "El código de acceso de la liga es requerido" in json_data['message']

    response_empty_code = client.post('/api/leagues/join_by_code', json={'league_access_code': '   '}) # Código vacío
    assert response_empty_code.status_code == 400
    json_data_empty = response_empty_code.get_json()
    assert "El código de acceso de la liga no puede estar vacío" in json_data_empty['message']


def test_join_league_unauthenticated(client, sample_invitation_code): # client normal, no autenticado
    """Test joining a league when unauthenticated."""
    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': sample_invitation_code.code
    })
    # Flask-Login debería redirigir a la página de login o devolver 401 si es una API
    assert response.status_code == 401 # Esperamos 401 Unauthorized para API
    json_data = response.get_json()
    assert "Authentication required" in json_data['message']

def test_join_league_registers_for_multiple_races(authenticated_client, sample_league, sample_invitation_code, db_session, league_admin_user, new_race_format):
    """Test that joining a league registers the user for all PLANNED/ACTIVE races in that league."""
    client, auth_player = authenticated_client(role_code='PLAYER')

    # Crear dos carreras para la liga
    race1 = Race(title="League Race 1", race_format_id=new_race_format.id, event_date=datetime.utcnow() + timedelta(days=10), user_id=league_admin_user.id, status=RaceStatus.PLANNED, gender_category="Ambos")
    race2 = Race(title="League Race 2", race_format_id=new_race_format.id, event_date=datetime.utcnow() + timedelta(days=20), user_id=league_admin_user.id, status=RaceStatus.ACTIVE, gender_category="Ambos")
    race3_archived = Race(title="League Race Archived", race_format_id=new_race_format.id, event_date=datetime.utcnow() - timedelta(days=5), user_id=league_admin_user.id, status=RaceStatus.ARCHIVED, gender_category="Ambos")

    db_session.add_all([race1, race2, race3_archived])
    db_session.commit()

    sample_league.races.append(race1)
    sample_league.races.append(race2)
    sample_league.races.append(race3_archived)
    db_session.commit()

    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': sample_invitation_code.code
    })

    assert response.status_code == 201
    # auth_user_id = auth_player.id # Usar el ID del usuario autenticado devuelto por el fixture

    # Verificar inscripción en la liga
    assert LeagueParticipant.query.filter_by(user_id=auth_player.id, league_id=sample_league.id).first() is not None

    # Verificar inscripción en las carreras PLANNED y ACTIVE
    assert UserRaceRegistration.query.filter_by(user_id=auth_player.id, race_id=race1.id).first() is not None
    assert UserRaceRegistration.query.filter_by(user_id=auth_player.id, race_id=race2.id).first() is not None

    # Verificar que NO se inscribió en la carrera ARCHIVED
    assert UserRaceRegistration.query.filter_by(user_id=auth_player.id, race_id=race3_archived.id).first() is None

    json_data = response.get_json()
    assert f"inscrito en 2 carrera(s) de la liga" in json_data['message']

def test_join_league_user_already_registered_for_some_races(authenticated_client, sample_league, sample_invitation_code, db_session, league_admin_user, new_race_format):
    """Test joining a league when user is already registered for some races in it."""
    client, auth_player = authenticated_client(role_code='PLAYER')

    race1 = Race(title="League Race Alpha", race_format_id=new_race_format.id, event_date=datetime.utcnow() + timedelta(days=15), user_id=league_admin_user.id, status=RaceStatus.PLANNED, gender_category="Ambos")
    race2 = Race(title="League Race Beta", race_format_id=new_race_format.id, event_date=datetime.utcnow() + timedelta(days=25), user_id=league_admin_user.id, status=RaceStatus.ACTIVE, gender_category="Ambos")
    db_session.add_all([race1, race2])
    db_session.commit()

    sample_league.races.append(race1)
    sample_league.races.append(race2)
    db_session.commit()

    # Pre-registrar al usuario en race1
    pre_registration = UserRaceRegistration(user_id=auth_player.id, race_id=race1.id)
    db_session.add(pre_registration)
    db_session.commit()

    response = client.post('/api/leagues/join_by_code', json={
        'league_access_code': sample_invitation_code.code
    })
    assert response.status_code == 201

    # Verificar inscripción en la liga
    assert LeagueParticipant.query.filter_by(user_id=auth_player.id, league_id=sample_league.id).first() is not None
    # Verificar que sigue inscrito en race1 (o que no se intentó duplicar)
    assert UserRaceRegistration.query.filter_by(user_id=auth_player.id, race_id=race1.id).count() == 1
    # Verificar que se inscribió en race2
    assert UserRaceRegistration.query.filter_by(user_id=auth_player.id, race_id=race2.id).first() is not None

    json_data = response.get_json()
    # Solo se habrá unido a 1 nueva carrera
    assert f"inscrito en 1 carrera(s) de la liga" in json_data['message']

# Más tests podrían incluir:
# - Código de invitación expirado (si se implementa la lógica de expires_at en la ruta)
# - Liga sin carreras (debería unirse a 0 carreras)
# - Concurrencia (más complejo, podría requerir tests de carga/estrés)
# - Lógica de roles: ¿Puede un ADMIN unirse a una liga como participante usando un código? (Actualmente sí, como cualquier usuario)
# - Códigos de un solo uso (si se implementa esa característica)
# - Diferentes estados de carreras (ej. si una carrera pasa de PLANNED a ACTIVE mientras el código está activo)
# - Limpieza de fixtures (ej. eliminar carreras/ligas creadas para no afectar otros tests si la BD es persistente entre tests)
#   (conftest usa :memory: SQLite, por lo que la BD es fresca para cada sesión de test_app)
# - Asegurar que el `authenticated_client` usa el `player_user` explícitamente si es necesario.
#   El fixture actual crea un `player_test_user`. Si se necesita el `player_user` de `conftest`
#   para un test específico, se tendría que loguear ese usuario explícitamente.
#   Para los tests actuales, `player_test_user` funciona bien.

# Ejemplo de cómo loguear un usuario específico si fuera necesario:
# def login(client, username, password):
#     return client.post('/api/login', json={'username': username, 'password': password}, follow_redirects=True)

# def test_something_with_specific_player(client, player_user, sample_invitation_code):
#     login_res = login(client, player_user.username, "player_password") # Usar la contraseña real
#     assert login_res.status_code == 200
#     # ... el resto del test ...

# Sin embargo, `authenticated_client` es más conveniente para la mayoría de los casos.
# La clave es obtener el `user.id` del usuario que `authenticated_client` realmente logueó.
# El fixture `authenticated_client` ya devuelve el objeto `user` logueado.
# Se puede modificar así: `client, logged_in_user = authenticated_client(role_code='PLAYER')`
# y luego usar `logged_in_user.id`. Los tests han sido actualizados para reflejar esto.
