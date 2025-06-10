import os
from flask import Flask, jsonify, request, redirect, url_for, send_from_directory
# Updated model imports
from backend.models import db, User, Role, Race, RaceFormat, Segment, RaceSegmentDetail, QuestionType, Question, QuestionOption # Added Question, QuestionOption
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate # Import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix # <--- Añade esta importación
from flask import render_template
from datetime import datetime # For event_date processing

app = Flask(__name__)

# Añade esta línea DESPUÉS de app = Flask(__name__)
# Indica a Flask que confíe en los headers X-Forwarded-For, X-Forwarded-Host, X-Forwarded-Proto y X-Forwarded-Port del proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1) # <--- Añade esta línea

# Configuration
# ==============================================================================
# Lee la SECRET_KEY de una variable de entorno
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    raise ValueError("No FLASK_SECRET_KEY set for Flask application")
# Configuración de cookies mejorada para Cloudfront
app.config['SESSION_COOKIE_SECURE'] = True  # Para HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Seguridad adicional
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Cambiar de 'None' a 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutos

# Configuración CORS si es necesario
app.config['CORS_ORIGINS'] = '*'  # O especifica tu dominio de Cloudfront
app.config['CORS_SUPPORTS_CREDENTIALS'] = True
# Lee la URI de la base de datos de una variable de entorno
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
if not app.config['SQLALCHEMY_DATABASE_URI']:
    raise ValueError("No DATABASE_URL set for Flask application")
# ==============================================================================
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
migrate = Migrate(app, db) # Initialize Flask-Migrate

# Flask-Login Configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'serve_login_page' # Crucial for @login_required redirection
login_manager.session_protection = "strong"

app.config['LOGIN_DISABLED'] = False # Asegúrate de que no esté deshabilitado accidentalmente
app.config['DEBUG_LOGIN'] = True      # <--- AÑADE ESTA LÍNEA TEMPORALMENTE para depuración

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_initial_roles():
    #Checks for existing roles and creates them if not present, using code and description.
    # Definimos los roles con su código y descripción
    # El 'code' será el identificador interno (ej. ADMIN, LEAGUE_ADMIN, PLAYER)
    # La 'description' será lo que se muestre (ej. Administrador, Admin de liga, Jugador)
    roles_data = [
        {'code': 'ADMIN', 'description': 'Administrador'},
        {'code': 'LEAGUE_ADMIN', 'description': 'Admin de Liga'},
        {'code': 'PLAYER', 'description': 'Jugador'}
    ]

    for role_info in roles_data:
        # Buscamos el rol usando la nueva columna 'code'
        role = Role.query.filter_by(code=role_info['code']).first()
        
        if not role:
            # Si el rol no existe, lo creamos con 'code' y 'description'
            new_role = Role(code=role_info['code'], description=role_info['description'])
            db.session.add(new_role)
            print(f"Role '{role_info['description']}' with code '{role_info['code']}' created.")
        else:
            print(f"Role '{role_info['description']}' with code '{role_info['code']}' already exists.")

    db.session.commit()
    print("Initial roles check and creation complete.")
    # Commit after checking/adding all roles
    # Check if there were any roles added to avoid empty commit
    if db.session.new: # or check if any new_role was created
        db.session.commit()
    elif db.session.dirty: # For safety, if other changes were pending (should not be here ideally)
        db.session.commit()

def create_initial_race_data():
    #Seeds RaceFormat and Segment tables with initial data.
    race_formats_data = ["Triatlón", "Duatlón", "Acuatlón"]
    segments_data = ["Natación", "Ciclismo", "Carrera a pie", "Transición 1 (T1)", "Transición 2 (T2)"]

    for name in race_formats_data:
        if not RaceFormat.query.filter_by(name=name).first():
            db.session.add(RaceFormat(name=name))
            print(f"RaceFormat '{name}' created.")
        else:
            print(f"RaceFormat '{name}' already exists.")

    for name in segments_data:
        if not Segment.query.filter_by(name=name).first():
            db.session.add(Segment(name=name))
            print(f"Segment '{name}' created.")
        else:
            print(f"Segment '{name}' already exists.")

    # Check if any new data was added before committing
    if db.session.new:
        db.session.commit()
        print("Initial race data seeding complete.")
    else:
        print("Initial race data already exists. No new data seeded.")

def create_initial_question_types():
    #Seeds QuestionType table with initial data.
    question_type_names = ['FREE_TEXT', 'MULTIPLE_CHOICE', 'ORDERING']
    for name in question_type_names:
        if not QuestionType.query.filter_by(name=name).first():
            db.session.add(QuestionType(name=name))
            print(f"QuestionType '{name}' created.")
        else:
            print(f"QuestionType '{name}' already exists.")

    if db.session.new: # Check if any new data was added
        db.session.commit()
        print("Initial question types seeding complete.")
    else:
        print("Initial question types already exist. No new data seeded.")

with app.app_context():
    db.create_all() # Ensures all tables are created based on models - Handled by migrations
    create_initial_roles() # Comentado para permitir las migraciones
    create_initial_race_data() # Comentado para permitir las migraciones
    create_initial_question_types() # Comentado para permitir las migraciones
# --- API Routes ---

@app.route('/api/race-formats', methods=['GET'])
def get_race_formats():
    try:
        formats = RaceFormat.query.all()
        return jsonify([{'id': fmt.id, 'name': fmt.name} for fmt in formats]), 200
    except Exception as e:
        print(f"Error fetching race formats: {e}")
        return jsonify(message="Error fetching race formats"), 500

@app.route('/api/races', methods=['POST'])
@login_required
def create_race():
    # Role check
    if current_user.role.code not in ['LEAGUE_ADMIN', 'ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to create races."), 403

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    # Required fields validation
    required_fields = ['title', 'race_format_id', 'event_date', 'gender_category', 'segments']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify(message=f"Missing required fields: {', '.join(missing_fields)}"), 400

    title = data.get('title')
    description = data.get('description')
    race_format_id = data.get('race_format_id')
    event_date_str = data.get('event_date')
    location = data.get('location')
    promo_image_url = data.get('promo_image_url')
    gender_category = data.get('gender_category')
    segments_data = data.get('segments')

    # Validate title
    if not isinstance(title, str) or not title.strip():
        return jsonify(message="Title must be a non-empty string."), 400

    # Validate race_format_id
    if not isinstance(race_format_id, int):
        return jsonify(message="race_format_id must be an integer."), 400
    race_format = RaceFormat.query.get(race_format_id)
    if not race_format:
        return jsonify(message=f"Invalid race_format_id: {race_format_id} does not exist."), 400

    # Validate event_date
    try:
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify(message="Invalid event_date format. Required format:YYYY-MM-DD."), 400

    # Validate gender_category
    if not isinstance(gender_category, str) or not gender_category.strip():
        return jsonify(message="gender_category must be a non-empty string."), 400

    # Validate segments
    if not isinstance(segments_data, list) or not segments_data:
        return jsonify(message="Segments must be a non-empty list."), 400

    race_segment_details_objects = []
    for seg_data in segments_data:
        segment_id = seg_data.get('segment_id')
        distance_km = seg_data.get('distance_km')

        if not isinstance(segment_id, int):
            return jsonify(message="Each segment's segment_id must be an integer."), 400
        segment = Segment.query.get(segment_id)
        if not segment:
            return jsonify(message=f"Invalid segment_id: {segment_id} does not exist."), 400

        if not (isinstance(distance_km, (float, int)) and distance_km > 0):
            # Allow distance_km = 0 for segments like transitions, if needed.
            # For now, strictly positive as per original prompt for "distance".
            # If 0 is allowed, change to: distance_km >= 0
            if not (isinstance(distance_km, (float, int)) and distance_km >= 0):
                   return jsonify(message="Each segment's distance_km must be a non-negative number."), 400
            # If distance is optional for some segments, this logic needs adjustment.
            # For now, assuming distance_km is required for all segments listed.
            if distance_km <=0 and segment.name not in ["Transición 1 (T1)", "Transición 2 (T2)"]:
                   return jsonify(message=f"distance_km for {segment.name} must be a positive number."), 400
            elif distance_km <0: # Negative distance is never allowed
                   return jsonify(message=f"distance_km for {segment.name} cannot be negative."), 400


        race_segment_details_objects.append(RaceSegmentDetail(
            segment_id=segment_id,
            distance_km=float(distance_km) # Ensure it's float
        ))

    # Create Race object
    new_race = Race(
        title=title,
        description=description,
        race_format_id=race_format_id,
        event_date=event_date,
        location=location,
        promo_image_url=promo_image_url,
        gender_category=gender_category,
        user_id=current_user.id,
        category="Elite" # Default as per requirement
    )

    try:
        db.session.add(new_race)
        # After adding new_race, it gets an ID (if auto-incrementing PK)
        # which is needed for race_segment_details_objects if they are not yet associated.
        # However, SQLAlchemy handles this association through backrefs or direct assignment.
        for rsd in race_segment_details_objects:
            rsd.race = new_race # Associate with the race
            db.session.add(rsd)

        db.session.commit()
        return jsonify(message="Race created successfully", race_id=new_race.id), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating race: {e}")
        return jsonify(message="Error creating race"), 500

@app.route('/api/races/<int:race_id>/details', methods=['PUT'])
@login_required
def update_race_details(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to update this race."), 403

    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    # Validate and update fields
    try:
        if 'title' in data:
            title = data.get('title')
            if not isinstance(title, str) or not title.strip():
                return jsonify(message="Title must be a non-empty string."), 400
            race.title = title

        if 'description' in data:
            race.description = data.get('description') # Allow empty description

        if 'event_date' in data:
            event_date_str = data.get('event_date')
            if event_date_str: # Check if not empty or None
                try:
                    # Accommodate datetime-local format from HTML form: %Y-%m-%dT%H:%M
                    race.event_date = datetime.strptime(event_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    try: # Fallback for just date if time is not included
                        race.event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
                    except ValueError:
                         return jsonify(message="Invalid event_date format. Use YYYY-MM-DDTHH:MM or YYYY-MM-DD."), 400
            else: # If event_date is explicitly set to null or empty string in JSON
                race.event_date = None


        if 'location' in data:
            race.location = data.get('location') # Allow empty location

        if 'promo_image_url' in data:
            promo_image_url = data.get('promo_image_url')
            # Basic URL validation (can be more sophisticated)
            if promo_image_url and not (promo_image_url.startswith('http://') or promo_image_url.startswith('https://')):
                # Allow empty string or None to clear the image URL
                if promo_image_url.strip() != "":
                    return jsonify(message="Invalid promo_image_url format. Must be a valid URL or empty."), 400
            race.promo_image_url = promo_image_url


        if 'gender_category' in data:
            gender_category = data.get('gender_category')
            # Assuming GenderCategory is an enum or has predefined valid values in your model/logic
            # For now, basic string validation. Add more specific checks if necessary.
            valid_gender_categories = ['MIXED', 'MALE_ONLY', 'FEMALE_ONLY', 'OTHER'] # Example
            if not isinstance(gender_category, str) or not gender_category.strip():
                 return jsonify(message="Gender category must be a non-empty string."), 400
            if gender_category not in valid_gender_categories: # Adapt this list as per your actual categories
                return jsonify(message=f"Invalid gender_category. Must be one of {valid_gender_categories}."), 400
            race.gender_category = gender_category

        if 'category' in data:
            # Assuming category can be any string, including empty.
            # If category needs specific validation (e.g., not empty, or from a predefined list), add it here.
            # For example, if it cannot be empty when provided:
            # if data['category'] is not None and not data['category'].strip():
            #     return jsonify(message="Category cannot be empty if provided."), 400
            race.category = data['category']

        db.session.commit()
        # Serialize the updated race object to return
        updated_race_data = {
            "id": race.id,
            "title": race.title,
            "description": race.description,
            "event_date": race.event_date.strftime('%Y-%m-%dT%H:%M:%S') if race.event_date else None,
            "location": race.location,
            "promo_image_url": race.promo_image_url,
            "gender_category": race.gender_category,
            "category": race.category, # Added category field
            "race_format_id": race.race_format_id,
            "user_id": race.user_id
            # Add other fields as necessary
        }
        return jsonify(message="Race details updated successfully", race=updated_race_data), 200
    except ValueError as ve: # Catch specific validation errors if any are raised manually
        db.session.rollback()
        return jsonify(message=str(ve)), 400
    except Exception as e:
        db.session.rollback()
        print(f"Error updating race details: {e}")
        return jsonify(message="Error updating race details"), 500


@app.route('/api/races/<int:race_id>', methods=['DELETE'])
@login_required
def delete_race(race_id):
    # 1. Check user role
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to delete this race."), 403

    # 2. Fetch the Race object
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    try:
        # 3. Explicitly delete associated RaceSegmentDetail objects
        #    SQLAlchemy ORM will handle this through cascades if configured,
        #    but explicit deletion is safer if cascades are not perfectly set for all related items.
        #    Given RaceSegmentDetail.race relationship has backref 'segment_details' with lazy=True (default),
        #    and no explicit cascade="all, delete-orphan" on that backref in Race model for segment_details.
        RaceSegmentDetail.query.filter_by(race_id=race.id).delete(synchronize_session='fetch')

        # 4. Explicitly delete associated Question objects
        #    Question.race relationship has backref 'questions' with lazy='dynamic'.
        #    QuestionOption.question relationship has cascade="all, delete-orphan".
        #    So deleting Questions should cascade to QuestionOptions.
        Question.query.filter_by(race_id=race.id).delete(synchronize_session='fetch')
        # Note: Using synchronize_session='fetch' or 'evaluate' can be important
        # if the session is to be used further before commit. 'fetch' is generally safer.

        # 5. Delete the Race object itself
        db.session.delete(race)

        # 6. Commit the database session
        db.session.commit()
        # HTTP 204 No Content is also appropriate for DELETE success if no message body is needed.
        # Returning 200 with a message is also common and acceptable.
        return jsonify(message="Race deleted successfully"), 200
    except Exception as e:
        # 7. Handle potential errors
        db.session.rollback()
        print(f"Error deleting race {race_id}: {e}") # Log the error
        return jsonify(message="Error deleting race"), 500


@app.route('/api/races/<int:race_id>/questions', methods=['GET'])
@login_required
def get_race_questions(race_id):
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    # Assuming race.questions is the backref from Question model
    # and it's set to lazy='dynamic' or similar to allow ordering.
    # If not dynamic, race.questions would be a list already.
    # For lazy='dynamic', it's a query object.
    # Let's order by question ID for consistent output.
    questions_query = race.questions.order_by(Question.id) # Use Question.id for ordering

    output = []
    for question in questions_query:
        question_data = {
            "id": question.id,
            "text": question.text,
            "question_type": question.question_type.name, # Accessing name from relationship
            "is_active": question.is_active
        }

        # Add type-specific scoring fields
        if question.question_type.name == 'FREE_TEXT':
            question_data["max_score_free_text"] = question.max_score_free_text
        elif question.question_type.name == 'MULTIPLE_CHOICE':
            question_data["is_mc_multiple_correct"] = question.is_mc_multiple_correct
            question_data["points_per_correct_mc"] = question.points_per_correct_mc
            question_data["points_per_incorrect_mc"] = question.points_per_incorrect_mc
            question_data["total_score_mc_single"] = question.total_score_mc_single
        elif question.question_type.name == 'ORDERING':
            question_data["points_per_correct_order"] = question.points_per_correct_order
            question_data["bonus_for_full_order"] = question.bonus_for_full_order

        options_output = []
        # Assuming question.options is the backref from QuestionOption model
        # and it's also lazy='dynamic' or similar.
        options_query = question.options.order_by(QuestionOption.id) # Order options by ID

        for opt in options_query:
            option_data = {
                "id": opt.id,
                "option_text": opt.option_text,
                "is_correct_mc_single": opt.is_correct_mc_single,
                "is_correct_mc_multiple": opt.is_correct_mc_multiple,
                "correct_order_index": opt.correct_order_index
            }
            options_output.append(option_data)

        question_data["options"] = options_output
        output.append(question_data)

    return jsonify(output), 200

# --- Helper function for question serialization ---
def _serialize_question(question):
    question_data = {
        "id": question.id,
        "text": question.text,
        "question_type": question.question_type.name,
        "is_active": question.is_active,
        "race_id": question.race_id
    }
    if question.question_type.name == 'FREE_TEXT':
        question_data["max_score_free_text"] = question.max_score_free_text
    elif question.question_type.name == 'MULTIPLE_CHOICE':
        question_data["is_mc_multiple_correct"] = question.is_mc_multiple_correct
        question_data["points_per_correct_mc"] = question.points_per_correct_mc
        question_data["points_per_incorrect_mc"] = question.points_per_incorrect_mc
        question_data["total_score_mc_single"] = question.total_score_mc_single
    elif question.question_type.name == 'ORDERING':
        question_data["points_per_correct_order"] = question.points_per_correct_order
        question_data["bonus_for_full_order"] = question.bonus_for_full_order

    options_output = []
    # Order options by ID for consistent output, could also be creation order or specific order field
    options_query = question.options.order_by(QuestionOption.id)
    for opt in options_query:
        option_data = {
            "id": opt.id,
            "option_text": opt.option_text,
            "is_correct_mc_single": opt.is_correct_mc_single,
            "is_correct_mc_multiple": opt.is_correct_mc_multiple,
            "correct_order_index": opt.correct_order_index
        }
        options_output.append(option_data)
    question_data["options"] = options_output
    return question_data

# --- CRUD for Free Text Questions ---
@app.route('/api/races/<int:race_id>/questions/free-text', methods=['POST'])
@login_required
def create_free_text_question(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    text = data.get('text')
    max_score_free_text = data.get('max_score_free_text')

    if not text or not isinstance(text, str) or not text.strip():
        return jsonify(message="Question text is required and must be a non-empty string"), 400
    if not isinstance(max_score_free_text, int) or max_score_free_text <= 0:
        return jsonify(message="max_score_free_text is required and must be a positive integer"), 400

    question_type_ft = QuestionType.query.filter_by(name='FREE_TEXT').first()
    if not question_type_ft:
        return jsonify(message="QuestionType 'FREE_TEXT' not found. Please seed database."), 500

    new_question = Question(
        race_id=race_id,
        question_type_id=question_type_ft.id,
        text=text,
        max_score_free_text=max_score_free_text,
        is_active=data.get('is_active', True) # Default to True if not provided
        # Other scoring fields will default to None as per model definition
    )
    try:
        db.session.add(new_question)
        db.session.commit()
        return jsonify(_serialize_question(new_question)), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating free text question: {e}")
        return jsonify(message="Error creating question"), 500

@app.route('/api/questions/free-text/<int:question_id>', methods=['PUT'])
@login_required
def update_free_text_question(question_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    question = Question.query.get(question_id)
    if not question:
        return jsonify(message="Question not found"), 404
    if question.question_type.name != 'FREE_TEXT':
        return jsonify(message="Cannot update non-FREE_TEXT question via this endpoint"), 400

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    if 'text' in data:
        text = data.get('text')
        if not isinstance(text, str) or not text.strip():
            return jsonify(message="Question text must be a non-empty string if provided"), 400
        question.text = text

    if 'max_score_free_text' in data:
        max_score = data.get('max_score_free_text')
        if not isinstance(max_score, int) or max_score <= 0:
            return jsonify(message="max_score_free_text must be a positive integer if provided"), 400
        question.max_score_free_text = max_score

    if 'is_active' in data:
        is_active = data.get('is_active')
        if not isinstance(is_active, bool):
            return jsonify(message="is_active must be a boolean if provided"), 400
        question.is_active = is_active

    try:
        db.session.commit()
        return jsonify(_serialize_question(question)), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error updating free text question: {e}")
        return jsonify(message="Error updating question"), 500

@app.route('/api/questions/<int:question_id>', methods=['DELETE'])
@login_required
def delete_question(question_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    question = Question.query.get(question_id)
    if not question:
        return jsonify(message="Question not found"), 404

    try:
        # Delete associated options first - important for all question types
        QuestionOption.query.filter_by(question_id=question_id).delete()
        # Then delete the question itself
        db.session.delete(question)
        db.session.commit()
        return jsonify(message="Question deleted successfully"), 200 # Or 204 No Content
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting question: {e}")
        return jsonify(message="Error deleting question"), 500

@app.route('/api/hello', methods=['GET'])
@login_required
def hello():
    return jsonify(message=f"Hello {current_user.username}, this is a protected message from Backend!")

@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data: return jsonify(message="Invalid input: No data provided"), 400
    name = data.get('name')
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role_code = data.get('role') # Get role from request

    # Aseguramos que role_code también venga en la solicitud
    if not all([name, username, email, password, role_code]):
        return jsonify(message="Missing required fields"), 400

    # Validar rol: Buscar el rol por su 'code'
    # La línea 'role_name = data.get('role', 'user')' era redundante y se ha eliminado.
    user_role_obj = Role.query.filter_by(code=role_code).first()

    # Este bloque 'if' ahora tiene la indentación correcta (4 espacios)
    if not user_role_obj:
        # Es crucial que create_initial_roles() haya corrido y poblado los roles con sus 'code's.
        # Los mensajes de error ahora deben reflejar los 'code's esperados.
        return jsonify(message=f"Invalid role code: '{role_code}' specified. Available role codes are typically 'PLAYER', 'LEAGUE_ADMIN', 'ADMIN'."), 400

    # Estas líneas también deben tener la misma indentación que el resto del bloque principal de la función
    if User.query.filter_by(username=username).first(): return jsonify(message="Username already exists"), 409
    if User.query.filter_by(email=email).first(): return jsonify(message="Email already exists"), 409

    new_user = User(name=name, username=username, email=email, role=user_role_obj)
    new_user.set_password(password)
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify(message="User registered successfully"), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error during registration: {e}")
        return jsonify(message="Registration failed due to a server error"), 500


@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.get_json()
    if not data: return jsonify(message="Invalid input: No data provided"), 400
    username = data.get('username')
    password = data.get('password')
    if not username or not password: return jsonify(message="Username and password are required"), 400
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password) and user.is_active:
        login_user(user)
        response = jsonify(message="Login successful", user_id=user.id, username=user.username)

        # Añadir headers CORS si es necesario
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))

        return response, 200
    elif user and not user.is_active:  
        return jsonify(message="Account disabled. Please contact support."), 403
    else:  
        return jsonify(message="Invalid username or password"), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout_api():
    logout_user()
    return jsonify(message="Logout successful"), 200

# --- CRUD for Multiple Choice Questions ---

@app.route('/api/races/<int:race_id>/questions/multiple-choice', methods=['POST'])
@login_required
def create_multiple_choice_question(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    # Validate required fields
    text = data.get('text')
    is_mc_multiple_correct = data.get('is_mc_multiple_correct') # Boolean: True for multi-select, False for single-select (radio)
    options_data = data.get('options')

    if not text or not isinstance(text, str) or not text.strip():
        return jsonify(message="Question text is required and must be a non-empty string"), 400
    if not isinstance(is_mc_multiple_correct, bool):
        return jsonify(message="is_mc_multiple_correct (boolean) is required"), 400
    if not options_data or not isinstance(options_data, list) or len(options_data) < 2:
        return jsonify(message="At least two options are required for a multiple choice question"), 400

    # Validate options structure and content
    # num_correct_options_for_single_choice = 0 # Removed
    for opt_data in options_data:
        if not isinstance(opt_data, dict) or \
           'option_text' not in opt_data or not isinstance(opt_data['option_text'], str) or not opt_data['option_text'].strip():
            # Removed checks for 'is_correct' field: 'is_correct' not in opt_data or not isinstance(opt_data['is_correct'], bool)
            return jsonify(message="Each option must have 'option_text' (string)"), 400
        # Removed logic for num_correct_options_for_single_choice
        # if not is_mc_multiple_correct and opt_data['is_correct']:
        #     num_correct_options_for_single_choice += 1

    # Removed validation based on num_correct_options_for_single_choice
    # if not is_mc_multiple_correct and num_correct_options_for_single_choice != 1:
    #     return jsonify(message="For single-correct multiple choice, exactly one option must be marked as correct"), 400

    # Validate scoring fields based on is_mc_multiple_correct
    points_per_correct_mc = None
    points_per_incorrect_mc = None
    total_score_mc_single = None

    if is_mc_multiple_correct:
        points_per_correct_mc = data.get('points_per_correct_mc')
        points_per_incorrect_mc = data.get('points_per_incorrect_mc', 0) # Default to 0 if not provided
        if not isinstance(points_per_correct_mc, int): # Assuming positive points for correct
            return jsonify(message="points_per_correct_mc is required and must be an integer for multiple-correct MCQs"), 400
        if not isinstance(points_per_incorrect_mc, int): # Can be negative or zero
            return jsonify(message="points_per_incorrect_mc must be an integer for multiple-correct MCQs"), 400
    else: # Single correct
        total_score_mc_single = data.get('total_score_mc_single')
        if not isinstance(total_score_mc_single, int) or total_score_mc_single <= 0:
            return jsonify(message="total_score_mc_single is required and must be a positive integer for single-correct MCQs"), 400

    question_type_mc = QuestionType.query.filter_by(name='MULTIPLE_CHOICE').first()
    if not question_type_mc:
        return jsonify(message="QuestionType 'MULTIPLE_CHOICE' not found. Please seed database."), 500

    new_question = Question(
        race_id=race_id,
        question_type_id=question_type_mc.id,
        text=text,
        is_active=data.get('is_active', True),
        is_mc_multiple_correct=is_mc_multiple_correct,
        points_per_correct_mc=points_per_correct_mc,
        points_per_incorrect_mc=points_per_incorrect_mc,
        total_score_mc_single=total_score_mc_single
    )
    db.session.add(new_question)
    # Need to commit here or flush to get new_question.id for options if not handled by backref immediately
    # However, if we add options to new_question.options, SQLAlchemy often handles it.
    # Let's try adding to session and then creating options.

    try:
        # Flush to get new_question.id if needed for options immediately,
        # or add options to new_question.options list and SQLAlchemy will handle it upon commit.
        # For clarity and explicit control, flushing can be an option:
        # db.session.flush() # if new_question.id is needed by QuestionOption constructor directly

        for opt_data in options_data:
            q_option = QuestionOption(
                question=new_question, # Associate with the question object
                option_text=opt_data['option_text']
                # is_correct_mc_multiple and is_correct_mc_single will use defaults or remain NULL
                # as per model, 'is_correct' from opt_data is no longer used here.
            )
            # Removed assignment from opt_data['is_correct']
            # if is_mc_multiple_correct:
            #     q_option.is_correct_mc_multiple = opt_data['is_correct']
            # else:
            #     q_option.is_correct_mc_single = opt_data['is_correct']
            db.session.add(q_option) # Add option to session

        db.session.commit()
        return jsonify(_serialize_question(new_question)), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating multiple choice question: {e}")
        return jsonify(message="Error creating question"), 500


@app.route('/api/questions/multiple-choice/<int:question_id>', methods=['PUT'])
@login_required
def update_multiple_choice_question(question_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    question = Question.query.get(question_id)
    if not question:
        return jsonify(message="Question not found"), 404
    if question.question_type.name != 'MULTIPLE_CHOICE':
        return jsonify(message="Cannot update non-MULTIPLE_CHOICE question via this endpoint"), 400

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    # Update common fields
    if 'text' in data:
        text = data.get('text')
        if not isinstance(text, str) or not text.strip():
            return jsonify(message="Question text must be a non-empty string if provided"), 400
        question.text = text
    if 'is_active' in data:
        is_active = data.get('is_active')
        if not isinstance(is_active, bool):
            return jsonify(message="is_active must be a boolean if provided"), 400
        question.is_active = is_active

    # Update type and scoring fields (can be complex if type itself changes, but here only MC fields)
    if 'is_mc_multiple_correct' in data:
        is_mc_multiple_correct = data.get('is_mc_multiple_correct')
        if not isinstance(is_mc_multiple_correct, bool):
             return jsonify(message="is_mc_multiple_correct (boolean) is required if provided"), 400
        question.is_mc_multiple_correct = is_mc_multiple_correct

        # Reset related scoring fields when type of MC (single/multi) changes
        question.points_per_correct_mc = None
        question.points_per_incorrect_mc = None
        question.total_score_mc_single = None

    # Apply new scoring fields based on the (potentially updated) is_mc_multiple_correct
    if question.is_mc_multiple_correct: # Handles both existing and newly set
        if 'points_per_correct_mc' in data:
            question.points_per_correct_mc = data.get('points_per_correct_mc')
            if not isinstance(question.points_per_correct_mc, int):
                return jsonify(message="points_per_correct_mc must be an integer for multiple-correct MCQs"), 400
        elif question.points_per_correct_mc is None: # If it became multi-select and this field is not provided
             return jsonify(message="points_per_correct_mc is required for multiple-correct MCQs"), 400


        if 'points_per_incorrect_mc' in data:
            question.points_per_incorrect_mc = data.get('points_per_incorrect_mc',0)
            if not isinstance(question.points_per_incorrect_mc, int):
                return jsonify(message="points_per_incorrect_mc must be an integer for multiple-correct MCQs"), 400
        elif question.points_per_incorrect_mc is None: # If it became multi-select and this field is not provided
             question.points_per_incorrect_mc = 0 # Default if not provided during update

    else: # Single correct
        if 'total_score_mc_single' in data:
            question.total_score_mc_single = data.get('total_score_mc_single')
            if not isinstance(question.total_score_mc_single, int) or question.total_score_mc_single <= 0:
                return jsonify(message="total_score_mc_single must be a positive integer for single-correct MCQs"), 400
        elif question.total_score_mc_single is None: # If it became single-select and this field is not provided
            return jsonify(message="total_score_mc_single is required for single-correct MCQs"), 400


    # Handle options: delete existing and recreate if 'options' is in payload
    if 'options' in data:
        options_data = data.get('options')
        if not isinstance(options_data, list) or len(options_data) < 2:
            return jsonify(message="At least two options are required if 'options' are provided for update"), 400

        # num_correct_options_for_single_choice = 0 # Removed
        for opt_data in options_data:
            if not isinstance(opt_data, dict) or \
               'option_text' not in opt_data or not isinstance(opt_data['option_text'], str) or not opt_data['option_text'].strip():
                # Removed checks for 'is_correct' field
                return jsonify(message="Each option must have 'option_text' (string)"), 400
            # Removed logic for num_correct_options_for_single_choice
            # if not question.is_mc_multiple_correct and opt_data['is_correct']:
            #     num_correct_options_for_single_choice += 1

        # Removed validation based on num_correct_options_for_single_choice
        # if not question.is_mc_multiple_correct and num_correct_options_for_single_choice != 1:
        #     return jsonify(message="For single-correct multiple choice, exactly one new option must be marked as correct"), 400

        # Delete old options
        QuestionOption.query.filter_by(question_id=question_id).delete()

        # Add new options
        for opt_data in options_data:
            q_option = QuestionOption(
                question_id=question_id,
                option_text=opt_data['option_text']
                # is_correct_mc_multiple and is_correct_mc_single will use defaults or remain NULL
            )
            # Removed assignment from opt_data['is_correct']
            # if question.is_mc_multiple_correct:
            #     q_option.is_correct_mc_multiple = opt_data['is_correct']
            # else:
            #     q_option.is_correct_mc_single = opt_data['is_correct']
            db.session.add(q_option)

    try:
        db.session.commit()
        return jsonify(_serialize_question(question)), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error updating multiple choice question: {e}")
        return jsonify(message="Error updating question"), 500

# --- CRUD for Ordering Questions ---

@app.route('/api/races/<int:race_id>/questions/ordering', methods=['POST'])
@login_required
def create_ordering_question(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    text = data.get('text')
    points_per_correct_order = data.get('points_per_correct_order')
    bonus_for_full_order = data.get('bonus_for_full_order', 0) # Default to 0
    options_data = data.get('options')

    if not text or not isinstance(text, str) or not text.strip():
        return jsonify(message="Question text is required and must be a non-empty string"), 400
    if not isinstance(points_per_correct_order, int) or points_per_correct_order <= 0:
        return jsonify(message="points_per_correct_order is required and must be a positive integer"), 400
    if not isinstance(bonus_for_full_order, int) or bonus_for_full_order < 0:
        return jsonify(message="bonus_for_full_order must be a non-negative integer"), 400
    if not options_data or not isinstance(options_data, list) or len(options_data) < 2:
        return jsonify(message="At least two options (items to order) are required"), 400

    for opt_data in options_data:
        if not isinstance(opt_data, dict) or \
           'option_text' not in opt_data or not isinstance(opt_data['option_text'], str) or not opt_data['option_text'].strip():
            return jsonify(message="Each option must have 'option_text' (string)"), 400

    question_type_ordering = QuestionType.query.filter_by(name='ORDERING').first()
    if not question_type_ordering:
        return jsonify(message="QuestionType 'ORDERING' not found. Please seed database."), 500

    new_question = Question(
        race_id=race_id,
        question_type_id=question_type_ordering.id,
        text=text,
        is_active=data.get('is_active', True),
        points_per_correct_order=points_per_correct_order,
        bonus_for_full_order=bonus_for_full_order
    )

    try:
        db.session.add(new_question)
        # db.session.flush() # To get new_question.id if needed for options immediately

        for index, opt_data in enumerate(options_data):
            q_option = QuestionOption(
                question=new_question, # Associate with the question object
                option_text=opt_data['option_text'],
                correct_order_index=index
            )
            db.session.add(q_option)

        db.session.commit()
        return jsonify(_serialize_question(new_question)), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating ordering question: {e}")
        return jsonify(message="Error creating ordering question"), 500

@app.route('/api/questions/ordering/<int:question_id>', methods=['PUT'])
@login_required
def update_ordering_question(question_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    question = Question.query.get(question_id)
    if not question:
        return jsonify(message="Question not found"), 404
    if question.question_type.name != 'ORDERING':
        return jsonify(message="Cannot update non-ORDERING question via this endpoint"), 400

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    if 'text' in data:
        text = data.get('text')
        if not isinstance(text, str) or not text.strip():
            return jsonify(message="Question text must be a non-empty string if provided"), 400
        question.text = text

    if 'points_per_correct_order' in data:
        points = data.get('points_per_correct_order')
        if not isinstance(points, int) or points <= 0:
            return jsonify(message="points_per_correct_order must be a positive integer if provided"), 400
        question.points_per_correct_order = points

    if 'bonus_for_full_order' in data:
        bonus = data.get('bonus_for_full_order')
        if not isinstance(bonus, int) or bonus < 0:
            return jsonify(message="bonus_for_full_order must be a non-negative integer if provided"), 400
        question.bonus_for_full_order = bonus

    if 'is_active' in data:
        is_active = data.get('is_active')
        if not isinstance(is_active, bool):
            return jsonify(message="is_active must be a boolean if provided"), 400
        question.is_active = is_active

    if 'options' in data:
        options_data = data.get('options')
        if not isinstance(options_data, list) or len(options_data) < 2:
            return jsonify(message="At least two options are required if 'options' are provided for update"), 400

        for opt_data in options_data:
            if not isinstance(opt_data, dict) or \
               'option_text' not in opt_data or not isinstance(opt_data['option_text'], str) or not opt_data['option_text'].strip():
                return jsonify(message="Each new option must have 'option_text' (string)"), 400

        # Delete old options
        QuestionOption.query.filter_by(question_id=question_id).delete()

        # Add new options
        for index, opt_data in enumerate(options_data):
            q_option = QuestionOption(
                question_id=question_id,
                option_text=opt_data['option_text'],
                correct_order_index=index
            )
            db.session.add(q_option)

    try:
        db.session.commit()
        return jsonify(_serialize_question(question)), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error updating ordering question: {e}")
        return jsonify(message="Error updating ordering question"), 500

@app.route('/api/user/me', methods=['GET'])
@login_required
def current_user_details():
    # @login_required should ensure current_user is authenticated
    # Acceder a la descripción del rol para mostrarla en el frontend
    return jsonify(
        username=current_user.username,
        role=current_user.role.description # CAMBIO AQUÍ: Usar .description para visualización
    ), 200

@app.route('/api/admin/general_data', methods=['GET'])
@login_required
def general_admin_data():
    # Comprobación de permisos: Usar .code para la lógica de autorización
    if current_user.role.code == 'ADMIN': # CAMBIO AQUÍ: 'admin' a 'ADMIN' (el código)
        return jsonify(message="Data for General Admin"), 200
    else:
        return jsonify(message="Forbidden: You do not have the required permissions."), 403

@app.route('/api/admin/league_data', methods=['GET'])
@login_required
def league_admin_data():
    # Comprobación de permisos: Usar .code para la lógica de autorización
    if current_user.role.code == 'LEAGUE_ADMIN' or \
       current_user.role.code == 'ADMIN': # CAMBIO AQUÍ: 'admin de liga' a 'LEAGUE_ADMIN', 'admin' a 'ADMIN'
        return jsonify(message="Data for League Admin (accessible by League and General Admins)"), 200
    else:
        return jsonify(message="Forbidden: You do not have the required permissions."), 403
        
@app.route('/api/user/personal_data', methods=['GET'])
@login_required
def user_personal_data():
    # Comprobación de permisos: Usar .code para la lógica de autorización
    if current_user.role.code == 'PLAYER': # CAMBIO AQUÍ: 'jugador' a 'PLAYER'
        return jsonify(message="Data for User role"), 200
    else:
        return jsonify(message="Forbidden: You do not have the required permissions for this data."), 403
# --- HTML Serving Routes ---
@app.route('/')
def root():
    return redirect(url_for('serve_login_page'))

@app.route('/login')
def serve_login_page():
    # Assuming frontend folder is one level up from where app.py is (backend/app.py -> frontend/)
    return render_template('login.html')

@app.route('/register')
def register_page():
    all_roles = Role.query.all()
    return render_template('register.html', roles=all_roles)


@app.route('/Hello-world')
@login_required
def serve_hello_world_page():
    filter_date_from_str = request.args.get('filter_date_from')
    filter_date_to_str = request.args.get('filter_date_to')
    filter_race_format_id_str = request.args.get('filter_race_format_id')

    all_race_formats = RaceFormat.query.order_by(RaceFormat.name).all() # Fetch all formats

    date_from_obj = None
    date_to_obj = None
    race_format_id_int = None

    if filter_date_from_str:
        try:
            date_from_obj = datetime.strptime(filter_date_from_str, '%Y-%m-%d')
        except ValueError:
            print(f"Invalid 'from' date format received: {filter_date_from_str}")
            pass

    if filter_date_to_str:
        try:
            parsed_date_to = datetime.strptime(filter_date_to_str, '%Y-%m-%d')
            date_to_obj = datetime.combine(parsed_date_to.date(), datetime.max.time())
        except ValueError:
            print(f"Invalid 'to' date format received: {filter_date_to_str}")
            pass

    if filter_race_format_id_str and filter_race_format_id_str.strip():
        try:
            race_format_id_int = int(filter_race_format_id_str)
        except ValueError:
            print(f"Invalid 'race_format_id' format received: {filter_race_format_id_str}")
            pass # Ignore if not a valid integer

    query = Race.query

    if date_from_obj:
        query = query.filter(Race.event_date >= date_from_obj)

    if date_to_obj:
        query = query.filter(Race.event_date <= date_to_obj)

    if race_format_id_int is not None:
        query = query.filter(Race.race_format_id == race_format_id_int)

    try:
        all_races = query.order_by(Race.event_date.desc()).all()
    except Exception as e:
        print(f"Error fetching races for index page: {e}")
        all_races = []
        pass

    return render_template('index.html',
                           races=all_races,
                           all_race_formats=all_race_formats, # Pass formats to template
                           filter_date_from_str=filter_date_from_str,
                           filter_date_to_str=filter_date_to_str,
                           filter_race_format_id_str=filter_race_format_id_str) # Pass format ID for repopulation

@app.route('/create-race')
@login_required
def serve_create_race_page():
    if current_user.role.code not in ['LEAGUE_ADMIN', 'ADMIN']:
        # For a page serving route, redirecting to an error page or flashing a message might be better
        # For now, returning JSON as per existing possible pattern, but could be improved for UX.
        return jsonify(message="Forbidden: You do not have permission to access this page."), 403

    race_formats = RaceFormat.query.all()
    all_segments = Segment.query.all()

    # Prepare data for JavaScript
    # This will be converted to JSON array of objects by |tojson filter in template
    race_formats_data = [{'id': rf.id, 'name': rf.name} for rf in race_formats]
    all_segments_data = [{'id': s.id, 'name': s.name} for s in all_segments]

    return render_template('create_race.html',
                           all_race_formats_data=race_formats_data,
                           all_segments_data=all_segments_data)

@app.route('/race/<int:race_id>')
@login_required
def serve_race_detail_page(race_id):
    race = Race.query.get_or_404(race_id)
    current_year = datetime.utcnow().year

    user_role_code = 'GUEST' # Default role if not authenticated or no role
    if current_user and current_user.is_authenticated and hasattr(current_user, 'role') and current_user.role:
        user_role_code = current_user.role.code

    return render_template('race_detail.html',
                           race=race,
                           current_year=current_year,
                           currentUserRole=user_role_code)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
