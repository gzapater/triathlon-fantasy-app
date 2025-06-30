import os
import boto3
from flask import Flask, jsonify, request, redirect, url_for, send_from_directory, flash, session
import logging # Importación añadida
# Updated model imports
from backend.models import db, User, Role, Race, RaceFormat, Segment, RaceSegmentDetail, QuestionType, Question, QuestionOption, UserRaceRegistration, UserAnswer, UserAnswerMultipleChoiceOption, OfficialAnswer, OfficialAnswerMultipleChoiceOption, UserFavoriteRace, FavoriteLink, UserScore, RaceStatus, Event # Added UserScore and RaceStatus, AND Event
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError # Import for handling unique constraint violations
from sqlalchemy import func # Add this import at the top of app.py if not present
from flask_migrate import Migrate # Import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix # <--- Añade esta importación
from flask import render_template
from datetime import datetime # For event_date processing

app = Flask(__name__)

# Configuración de logging para que funcione bien con Gunicorn
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.setLevel(gunicorn_logger.level if gunicorn_logger.level != 0 else logging.INFO) # Usar INFO si el nivel de gunicorn es 0 (NOTSET)
else:
    # Configuración para desarrollo local (ej. python app.py)
    app.logger.setLevel(logging.DEBUG)

# Filtro Jinja2 para formatear fechas
def format_date_filter(value, format='%d %b %Y'):
    """Formatea un objeto de fecha o una cadena de fecha."""
    if value is None:
        return "Fecha no disponible"
    if isinstance(value, str):
        try:
            # Intenta parsear si es una cadena (ej. 'YYYY-MM-DD')
            dt_obj = datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            try:
                # Intenta parsear si es una cadena con hora (ej. 'YYYY-MM-DDTHH:MM:SS')
                dt_obj = datetime.fromisoformat(value)
            except ValueError:
                return value # Devuelve el valor original si no se puede parsear
    elif isinstance(value, datetime):
        dt_obj = value
    else:
        return value # Devuelve el valor original si no es ni cadena ni datetime

    # Formatear con mes en español y capitalizado
    # Nota: esto depende de la configuración regional del servidor.
    # Para asegurar español, se podría usar Babel u otra librería, o un mapeo manual.
    # Por simplicidad, usamos strftime y luego ajustamos el mes si es necesario.
    # Esta es una aproximación simple y podría no ser perfecta para todos los locales.
    formatted_date = dt_obj.strftime(format) # ej. "01 Jan 2025" # pragma: no cover
    # Reemplazo simple de meses en inglés a español (abreviado)
    month_map = {
        'Jan': 'Ene', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Abr', # pragma: no cover
        'May': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
        'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dic'
    }
    for en, es in month_map.items():
        if en in formatted_date:
            formatted_date = formatted_date.replace(en, es)
            break
    return formatted_date

app.jinja_env.filters['format_date_filter'] = format_date_filter

# Slugify filter for Jinja2
import re
import unicodedata

def slugify(value, separator='-'):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    if value is None:
        return ""
    # Normalize and handle unicode characters
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode('ascii')
    # Remove characters that are not alphanumeric, underscores, or hyphens
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    # Replace whitespace and repeated hyphens with a single separator
    value = re.sub(r'[-\s]+', separator, value)
    return value

app.jinja_env.filters['slugify'] = slugify

def get_ssm_parameter(name, default=None):
    """Función para obtener un parámetro de AWS SSM Parameter Store."""
    try:
        # La región se debe ajustar si es diferente.
        ssm_client = boto3.client('ssm', region_name='eu-north-1')
        response = ssm_client.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        # Si falla (ej. en local, sin credenciales), usa un valor por defecto.
        print(f"No se pudo obtener el parámetro '{name}' de SSM. Error: {e}")
        return default
# Añade esta línea DESPUÉS de app = Flask(__name__)
# Indica a Flask que confíe en los headers X-Forwarded-For, X-Forwarded-Host, X-Forwarded-Proto y X-Forwarded-Port del proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1) # <--- Añade esta línea

# Configuration
# ==============================================================================
# Lee los secretos desde las variables de entorno o, en su defecto, desde AWS Parameter Store
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or get_ssm_parameter('/tripredict/prod/FLASK_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or get_ssm_parameter('/tripredict/prod/DATABASE_URL')

# Comprobación de que las variables se han cargado correctamente
if not app.secret_key:
    raise ValueError("FLASK_SECRET_KEY is not set in environment or SSM Parameter Store.")
if not app.config['SQLALCHEMY_DATABASE_URI']:
    raise ValueError("DATABASE_URL is not set in environment or SSM Parameter Store.")

# Configuración de cookies mejorada para Cloudfront
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutos

# Configuración CORS si es necesario
app.config['CORS_ORIGINS'] = '*'  # O especifica tu dominio de Cloudfront
app.config['CORS_SUPPORTS_CREDENTIALS'] = True
# ==============================================================================
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
migrate = Migrate(app, db, directory='migrations') # Initialize Flask-Migrate

# Flask-Login Configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'serve_login_page' # Crucial for @login_required redirection
login_manager.session_protection = "strong"

@login_manager.unauthorized_handler
def unauthorized():
    original_url = request.url

    # Construir next_url a partir de path y query_string para evitar '?' innecesarios
    next_url = request.path
    if request.query_string:
        # request.query_string es bytes, necesita ser decodificado
        next_url += '?' + request.query_string.decode('utf-8')

    app.logger.info(f"[Flask-Login Unauthorized] Acceso no autorizado a: {original_url}")
    app.logger.info(f"[Flask-Login Unauthorized] 'next' URL para login será: {next_url}")

    if login_manager.login_message:
        # Usar el mensaje y categoría configurados en LoginManager, o los predeterminados.
        flash(login_manager.login_message or "Please log in to access this page.",
              category=login_manager.login_message_category or "message")

    # Construir la URL de login con el 'next' correcto
    # login_manager.login_view es el nombre del endpoint, ej 'serve_login_page'
    login_url_redirect = url_for(login_manager.login_view, next=next_url)
    app.logger.info(f"[Flask-Login Unauthorized] Redirigiendo a: {login_url_redirect}")
    # If the request is an API request, return JSON instead of redirecting
    # Check if request.blueprint is 'api' or path starts with /api/
    # Using request.path.startswith('/api/') for simplicity as blueprint might not be set for all API routes
    if request.path.startswith('/api/'):
        app.logger.info("[Flask-Login Unauthorized] API request detected. Returning JSON 401.")
        return jsonify(message="Authentication required. Please log in."), 401
    else:
        return redirect(login_url_redirect)


app.config['LOGIN_DISABLED'] = False # Asegúrate de que no esté deshabilitado accidentalmente
app.config['DEBUG_LOGIN'] = True      # <--- AÑADE ESTA LÍNEA TEMPORALMENTE para depuración

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Seeding functions (create_initial_roles, create_initial_race_data, create_initial_question_types)
# have been moved to backend/seed.py and will be run via CLI.

# The with app.app_context() block that called these functions is also removed
# as it's no longer needed here for initial data seeding.
# If it was used for other purposes like db.create_all(), ensure those are handled
# appropriately (e.g., by Flask-Migrate).

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

    is_general_from_form = data.get('is_general', False) # Get value, default to False if not present

    if current_user.role.code == 'ADMIN':
        is_general = bool(is_general_from_form) # Convert to boolean, respect admin's choice
    elif current_user.role.code == 'LEAGUE_ADMIN':
        is_general = False # League admins always create local races
    else:
        # This case should ideally not happen if only ADMIN and LEAGUE_ADMIN can access this route
        is_general = False

    questions_data = data.get('questions', []) # Extract questions data
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
    quiniela_close_date_str = data.get('quiniela_close_date')

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
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d') # Assuming event_date is just date for now
    except ValueError:
        return jsonify(message="Invalid event_date format. Required format: YYYY-MM-DD."), 400

    quiniela_close_date_obj = None
    if quiniela_close_date_str:
        try:
            quiniela_close_date_obj = datetime.strptime(quiniela_close_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            return jsonify(message="Invalid quiniela_close_date format. Required format: YYYY-MM-DDTHH:MM"), 400

    # Validate gender_category
    if not isinstance(gender_category, str) or not gender_category.strip():
        return jsonify(message="gender_category must be a non-empty string."), 400

    # Validate segments
    if not isinstance(segments_data, list) or not segments_data:
        return jsonify(message="Segments must be a non-empty list."), 400

    race_segment_details_objects = []
    for seg_data in segments_data:
        segment_id = seg_data.get('segment_id')
        distance_km = seg_data.get('distance_km') # This is before float conversion

        app.logger.info(f"Processing segment for RaceSegmentDetail: segment_id='{segment_id}', raw distance_km='{distance_km}'")

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

    if not current_user or not current_user.is_authenticated or current_user.id is None:
        app.logger.error(f"Race creation attempt by unauthenticated or invalid user. current_user: {current_user}, is_authenticated: {current_user.is_authenticated if current_user else 'N/A'}, user_id: {current_user.id if current_user else 'N/A'}")
        return jsonify(message="Forbidden: User authentication issue. Cannot create race."), 403

    # Create Race object
    app.logger.info(f"Attempting to create Race with parameters: title='{title}', description='{description}', race_format_id={race_format_id}, event_date='{event_date}', location='{location}', promo_image_url='{promo_image_url}', gender_category='{gender_category}', is_general={is_general}, user_id={current_user.id}, category='Elite'")
    new_race = Race(
        title=title,
        description=description,
        race_format_id=race_format_id,
        event_date=event_date,
        location=location,
        promo_image_url=promo_image_url,
        gender_category=gender_category,
        is_general=is_general,
        quiniela_close_date=quiniela_close_date_obj, # Add new field here
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

        if questions_data:  # Check if there are any questions to process
            for question_payload in questions_data:
                question_type_name = question_payload.get('type')
                if not question_type_name:
                    # Consider how to handle this error; maybe return a 400 or log
                    app.logger.warning(f"Skipping question due to missing type: {question_payload.get('text')}")
                    continue

                question_type_obj = QuestionType.query.filter_by(name=question_type_name).first()
                if not question_type_obj:
                    # Consider how to handle this error
                    app.logger.warning(f"Skipping question due to invalid type '{question_type_name}': {question_payload.get('text')}")
                    continue

                new_question = Question(
                    race_id=new_race.id, # new_race is defined earlier in the function
                    question_type_id=question_type_obj.id,
                    text=question_payload.get('text'),
                    is_active=question_payload.get('is_active', True)
                )

                # Populate scoring fields based on type
                if question_type_name == 'FREE_TEXT':
                    new_question.max_score_free_text = question_payload.get('max_score_free_text')
                elif question_type_name == 'MULTIPLE_CHOICE':
                    new_question.is_mc_multiple_correct = question_payload.get('is_mc_multiple_correct')
                    if new_question.is_mc_multiple_correct:
                        new_question.points_per_correct_mc = question_payload.get('points_per_correct_mc')
                        new_question.points_per_incorrect_mc = question_payload.get('points_per_incorrect_mc', 0)
                    else:
                        new_question.total_score_mc_single = question_payload.get('total_score_mc_single')
                elif question_type_name == 'ORDERING':
                    new_question.points_per_correct_order = question_payload.get('points_per_correct_order')
                    new_question.bonus_for_full_order = question_payload.get('bonus_for_full_order', 0)
                elif question_type_name == 'SLIDER':
                    # Retrieve and process slider-specific fields
                    slider_unit_raw = question_payload.get('slider_unit')
                    new_question.slider_unit = slider_unit_raw if slider_unit_raw and slider_unit_raw.strip() else None


                    slider_min_val_payload = question_payload.get('slider_min_value')
                    slider_max_val_payload = question_payload.get('slider_max_value')

                    if slider_min_val_payload is None or slider_max_val_payload is None:
                        # Consider rolling back if parts of the race are already added to db.session,
                        # but create_race commits at the end, so returning early is okay.
                        return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_min_value and slider_max_value are required."), 400

                    try:
                        slider_min_val = float(slider_min_val_payload)
                        slider_max_val = float(slider_max_val_payload)
                    except (ValueError, TypeError):
                        return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_min_value and slider_max_value must be valid numbers."), 400

                    if slider_min_val >= slider_max_val:
                        return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_min_value must be less than slider_max_value."), 400

                    new_question.slider_min_value = slider_min_val
                    new_question.slider_max_value = slider_max_val

                    # Process other slider fields (step, points_exact are also critical)
                    slider_step_payload = question_payload.get('slider_step')
                    slider_points_exact_payload = question_payload.get('slider_points_exact')

                    if slider_step_payload is None or slider_points_exact_payload is None:
                        return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_step and slider_points_exact are required."), 400

                    try:
                        new_question.slider_step = float(slider_step_payload)
                        new_question.slider_points_exact = int(slider_points_exact_payload)
                    except (ValueError, TypeError):
                         return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_step must be a number and slider_points_exact must be an integer."), 400

                    if new_question.slider_step <= 0:
                        return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_step must be positive."), 400
                    if new_question.slider_points_exact < 0:
                         return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_points_exact must be non-negative."), 400

                    # Optional fields: threshold_partial, points_partial
                    slider_threshold_partial_raw = question_payload.get('slider_threshold_partial')
                    if slider_threshold_partial_raw is not None:
                        try:
                            new_question.slider_threshold_partial = float(slider_threshold_partial_raw)
                        except (ValueError, TypeError):
                            app.logger.error(f"Error converting slider_threshold_partial for question '{question_payload.get('text')}'")
                            new_question.slider_threshold_partial = None # Or handle error
                    else:
                        new_question.slider_threshold_partial = None

                    slider_points_partial_raw = question_payload.get('slider_points_partial')

                    # Validate partial scoring fields if either is present
                    if slider_threshold_partial_raw is not None or slider_points_partial_raw is not None:
                        if slider_threshold_partial_raw is None or slider_points_partial_raw is None:
                            return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', if providing partial scoring, both slider_threshold_partial and slider_points_partial must be present."), 400
                        try:
                            new_question.slider_threshold_partial = float(slider_threshold_partial_raw)
                            new_question.slider_points_partial = int(slider_points_partial_raw)
                        except (ValueError, TypeError):
                            return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_threshold_partial must be a number and slider_points_partial must be an integer."), 400
                        if new_question.slider_threshold_partial < 0:
                             return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_threshold_partial must be non-negative."), 400
                        if new_question.slider_points_partial < 0:
                             return jsonify(message=f"For slider question '{question_payload.get('text', 'N/A')}', slider_points_partial must be non-negative."), 400
                    else:
                        new_question.slider_threshold_partial = None
                        new_question.slider_points_partial = None

                db.session.add(new_question)
                # Flushing here can be useful if new_question.id is needed immediately by options
                # that are not being associated via backref.
                # db.session.flush()

                options_payload = question_payload.get('options', [])
                if options_payload:
                    for index, option_data in enumerate(options_payload):
                        option_text_value = option_data.get('option_text')
                        if not option_text_value:
                            app.logger.warning(f"Skipping option for question '{new_question.text}' due to missing option_text.")
                            continue

                        new_option = QuestionOption(
                            question=new_question,
                            option_text=option_text_value
                        )
                        if question_type_name == 'ORDERING':
                            new_option.correct_order_index = index

                        # As noted before, client-side JS for create_race wizard doesn't currently send
                        # correctness data for MC options during initial race creation.
                        # If it did, you would set new_option.is_correct_mc_single or
                        # new_option.is_correct_mc_multiple here based on payload.

                        db.session.add(new_option)

        db.session.commit()
        return jsonify(message="Race created successfully", race_id=new_race.id), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating race: {e}", exc_info=True)
        return jsonify(message="Error creating race"), 500

@app.route('/api/races/<int:race_id>/details', methods=['PUT'])
@login_required
def update_race_details(race_id):
    app.logger.info(f"update_race_details called for race_id: {race_id}")
    data = request.get_json()
    app.logger.info(f"Received JSON data: {data}")

    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.username} forbidden to update race {race_id}")
        return jsonify(message="Forbidden: You do not have permission to update this race."), 403

    race = Race.query.get(race_id)
    if not race:
        app.logger.warning(f"Race with id {race_id} not found.")
        return jsonify(message="Race not found"), 404

    app.logger.info(f"Race object before modifications: {race.to_dict() if hasattr(race, 'to_dict') else race}")

    if not data:
        app.logger.warning("Invalid input: No data provided")
        return jsonify(message="Invalid input: No data provided"), 400

    # Validate and update fields
    try:
        if 'title' in data:
            title = data.get('title')
            if not isinstance(title, str) or not title.strip():
                return jsonify(message="Title must be a non-empty string."), 400
            race.title = title

        if 'description' in data:
            race.description = data.get('description')

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
                    app.logger.warning(f"Invalid promo_image_url format: {promo_image_url}")
                    return jsonify(message="Invalid promo_image_url format. Must be a valid URL or empty."), 400
            race.promo_image_url = promo_image_url


        if 'gender_category' in data:
            gender_category = data.get('gender_category')
            valid_gender_categories = ['MIXED', 'MALE_ONLY', 'FEMALE_ONLY', 'OTHER']
            if not isinstance(gender_category, str) or not gender_category.strip():
                 app.logger.warning(f"Invalid gender_category: {gender_category}")
                 return jsonify(message="Gender category must be a non-empty string."), 400
            if gender_category not in valid_gender_categories:
                app.logger.warning(f"Invalid gender_category: {gender_category}. Must be one of {valid_gender_categories}.")
                return jsonify(message=f"Invalid gender_category. Must be one of {valid_gender_categories}."), 400
            race.gender_category = gender_category

        if 'category' in data:
            race.category = data['category']

        if 'quiniela_close_date' in data:
            quiniela_close_date_str = data.get('quiniela_close_date')
            if quiniela_close_date_str and quiniela_close_date_str.strip(): # Check if not empty
                try:
                    # Ensure datetime is imported: from datetime import datetime
                    race.quiniela_close_date = datetime.strptime(quiniela_close_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    return jsonify(message="Invalid quiniela_close_date format. Use YYYY-MM-DDTHH:MM."), 400
            else: # If quiniela_close_date is explicitly set to empty string or null
                race.quiniela_close_date = None

        app.logger.info(f"Race object after modifications: {race.to_dict() if hasattr(race, 'to_dict') else race}")
        db.session.commit()

        # Use the model's to_dict() method for consistency, it now includes quiniela_close_date
        updated_race_data = race.to_dict()

        app.logger.info(f"Returning updated_race_data: {updated_race_data}")
        return jsonify(message="Race details updated successfully", race=updated_race_data), 200
    except ValueError as ve:
        db.session.rollback()
        app.logger.error(f"ValueError updating race details for race_id {race_id}: {ve}")
        return jsonify(message=str(ve)), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception updating race details for race_id {race_id}: {e}", exc_info=True)
        return jsonify(message="Error updating race details"), 500


@app.route('/api/races/<int:race_id>', methods=['DELETE'])
@login_required
def delete_race(race_id):
    app.logger.info(f"Logically deleting race_id: {race_id}")
    # 1. Check user role
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.username} forbidden to delete race {race_id}")
        return jsonify(message="Forbidden: You do not have permission to delete this race."), 403

    # 2. Fetch the Race object
    race = Race.query.get(race_id)
    if not race:
        app.logger.warning(f"Race with id {race_id} not found for logical deletion.")
        return jsonify(message="Race not found"), 404

    if race.is_deleted:
        app.logger.info(f"Race with id {race_id} is already logically deleted.")
        return jsonify(message="Race already deleted"), 200 # Or 404 if preferred for already deleted items

    app.logger.info(f"Fetched race object for logical deletion: {race.to_dict() if hasattr(race, 'to_dict') else race}")

    try:
        # 3. Perform logical delete
        race.is_deleted = True
        db.session.commit()
        app.logger.info(f"Race {race_id} logically deleted and session committed successfully.")
        return jsonify(message="Race deleted successfully"), 200
    except Exception as e:
        # 4. Handle potential errors
        db.session.rollback()
        app.logger.error(f"Exception logically deleting race {race_id}: {e}", exc_info=True)
        return jsonify(message="Error deleting race"), 500

@app.route('/api/races/<int:race_id>/archive', methods=['POST'])
@login_required
def archive_race(race_id):
    app.logger.info(f"Attempting to archive race_id: {race_id} by user {current_user.username}")

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        app.logger.warning(f"Race with id {race_id} not found for archiving.")
        return jsonify(message="Race not found or has been deleted"), 404

    # Authorization check: ADMIN can archive any race. LEAGUE_ADMIN can only archive their own races.
    if current_user.role.code == 'ADMIN':
        pass # Admin has permission
    elif current_user.role.code == 'LEAGUE_ADMIN':
        if race.user_id != current_user.id:
            app.logger.warning(f"User {current_user.username} (LEAGUE_ADMIN) forbidden to archive race {race_id} not owned by them.")
            return jsonify(message="Forbidden: You can only archive races you created."), 403
    else: # Other roles (e.g., PLAYER) cannot archive
        app.logger.warning(f"User {current_user.username} (Role: {current_user.role.code}) forbidden to archive race {race_id}.")
        return jsonify(message="Forbidden: You do not have permission to archive this race."), 403

    if race.status == RaceStatus.ARCHIVED:
        app.logger.info(f"Race {race_id} is already archived.")
        return jsonify(message="Race is already archived"), 200 # Or 400 if preferred

    try:
        race.status = RaceStatus.ARCHIVED
        race.updated_at = datetime.utcnow() # Explicitly update timestamp
        db.session.commit()
        app.logger.info(f"Race {race_id} successfully archived by user {current_user.username}.")
        # Return the updated race status or the full race object
        return jsonify(message="Race archived successfully", race_status=race.status.value), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception archiving race {race_id}: {e}", exc_info=True)
        return jsonify(message="Error archiving race"), 500


@app.route('/api/races/<int:race_id>/questions', methods=['GET'])
@login_required
def get_race_questions(race_id):
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    questions_query = race.questions.order_by(Question.id)

    # Fetch all official answers for the race once
    official_answers_list = OfficialAnswer.query.filter_by(race_id=race_id).all()
    official_answers_map = {oa.question_id: oa for oa in official_answers_list}

    # Pre-process official MC-multiple answers for efficiency
    official_mc_multiple_options_map = {}
    for oa_obj_loop in official_answers_list: # Renamed loop variable
        q_obj_for_oa = Question.query.get(oa_obj_loop.question_id)
        if q_obj_for_oa and q_obj_for_oa.question_type.name == 'MULTIPLE_CHOICE' and q_obj_for_oa.is_mc_multiple_correct:
            official_mc_multiple_options_map[q_obj_for_oa.id] = {
                sel_opt.question_option_id for sel_opt in oa_obj_loop.official_selected_mc_options
            }

    # Pre-process official ORDERING answers text map
    official_ordering_text_map = {}
    for q_id_loop, oa_obj_loop in official_answers_map.items(): # Renamed loop variables
        question_for_oa = Question.query.get(q_id_loop)
        if question_for_oa and question_for_oa.question_type.name == 'ORDERING':
            if oa_obj_loop and oa_obj_loop.answer_text:
                official_texts = [text.strip().lower() for text in oa_obj_loop.answer_text.split(',') if text.strip()]
                official_ordering_text_map[q_id_loop] = official_texts
            else:
                official_ordering_text_map[q_id_loop] = []


    # Fetch current user's answers for this race
    user_answers_for_race_list = UserAnswer.query.filter_by(user_id=current_user.id, race_id=race_id).all()
    user_answers_map = {ua.question_id: ua for ua in user_answers_for_race_list}

    output = []
    for question in questions_query:
        question_data = {
            "id": question.id,
            "text": question.text,
            "question_type": question.question_type.name,
            "is_active": question.is_active,
            "official_answer": None,
            "max_points_possible": 0,
            "user_answer_details": None # Initialize user answer details
        }

        # Add type-specific scoring fields and calculate max_points_possible
        if question.question_type.name == 'FREE_TEXT':
            question_data["max_score_free_text"] = question.max_score_free_text
            question_data["max_points_possible"] = question.max_score_free_text or 0
        elif question.question_type.name == 'MULTIPLE_CHOICE':
            question_data["is_mc_multiple_correct"] = question.is_mc_multiple_correct
            question_data["points_per_correct_mc"] = question.points_per_correct_mc
            question_data["points_per_incorrect_mc"] = question.points_per_incorrect_mc
            question_data["total_score_mc_single"] = question.total_score_mc_single
            if question.is_mc_multiple_correct:
                # Max points is sum of points_per_correct_mc for all *actually correct* options.
                # This requires knowing which options are officially correct.
                correct_option_ids_for_this_q = official_mc_multiple_options_map.get(question.id, set())
                question_data["max_points_possible"] = len(correct_option_ids_for_this_q) * (question.points_per_correct_mc or 0)
            else:
                question_data["max_points_possible"] = question.total_score_mc_single or 0
        elif question.question_type.name == 'ORDERING':
            question_data["points_per_correct_order"] = question.points_per_correct_order
            question_data["bonus_for_full_order"] = question.bonus_for_full_order
            # Max points = (points_per_correct_order * num_items) + bonus_for_full_order

            official_answer_obj_for_ordering = official_answers_map.get(question.id)
            if official_answer_obj_for_ordering and official_answer_obj_for_ordering.answer_text:
                # Assuming answer_text is a comma-separated string of option IDs or texts
                num_items_to_order = len(official_answer_obj_for_ordering.answer_text.split(','))
            else:
                num_items_to_order = len(question.options.all()) # Get all options for this question

            max_pts_ordering = (question.points_per_correct_order or 0) * num_items_to_order
            if num_items_to_order > 0: # Only add bonus if there are items to order
                 max_pts_ordering += (question.bonus_for_full_order or 0)
            question_data["max_points_possible"] = max_pts_ordering
        elif question.question_type.name == 'SLIDER':
            question_data["slider_unit"] = question.slider_unit
            question_data["slider_min_value"] = question.slider_min_value
            question_data["slider_max_value"] = question.slider_max_value
            question_data["slider_step"] = question.slider_step
            question_data["slider_points_exact"] = question.slider_points_exact
            question_data["slider_threshold_partial"] = question.slider_threshold_partial
            question_data["slider_points_partial"] = question.slider_points_partial
            question_data["max_points_possible"] = question.slider_points_exact or 0 # Max is typically for exact match

        options_output = []
        options_query_for_q = question.options.order_by(QuestionOption.id)
        for opt in options_query_for_q:
            option_data = {
                "id": opt.id,
                "option_text": opt.option_text,
                # These fields might not be directly relevant if official answer is provided separately
                # but keeping them for now as they are part of the QuestionOption model structure.
                "is_correct_mc_single": opt.is_correct_mc_single,
                "is_correct_mc_multiple": opt.is_correct_mc_multiple,
                "correct_order_index": opt.correct_order_index
            }
            options_output.append(option_data)
        question_data["options"] = options_output

        # Fetch and format official answer for this question
        official_answer_obj = official_answers_map.get(question.id)
        official_answer_formatted = None  # Initialize here
        if official_answer_obj:
            # official_answer_formatted = None # No longer needed here
            if question.question_type.name == 'FREE_TEXT':
                official_answer_formatted = official_answer_obj.answer_text
            elif question.question_type.name == 'ORDERING':
                # OfficialAnswer.answer_text for ORDERING questions stores comma-separated option IDs.
                # We need to convert these IDs to their corresponding texts.
                if official_answer_obj and official_answer_obj.answer_text:
                    ordered_option_ids_str = official_answer_obj.answer_text.split(',')
                    ordered_option_texts = []
                    for opt_id_str in ordered_option_ids_str:
                        try:
                            opt_id = int(opt_id_str.strip())
                            option_obj = QuestionOption.query.get(opt_id)
                            if option_obj and option_obj.question_id == question.id: # Ensure option belongs to the question
                                ordered_option_texts.append(option_obj.option_text)
                            else:
                                ordered_option_texts.append(f"[ID de opción inválido: {opt_id_str}]")
                        except ValueError:
                            ordered_option_texts.append(f"[ID de opción malformado: {opt_id_str}]")
                    official_answer_formatted = ", ".join(ordered_option_texts) # Join texts with comma and space for display
                else:
                    official_answer_formatted = None # No official answer or empty answer_text
            elif question.question_type.name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    # Get set of correct option IDs from pre-processed map
                    correct_option_ids = official_mc_multiple_options_map.get(question.id, set())
                    # Map these IDs back to text for display (similar to get_participant_answers)
                    formatted_mc_multiple = []
                    for opt_id in correct_option_ids:
                        opt_obj = QuestionOption.query.get(opt_id) # Fetch option object
                        if opt_obj:
                            formatted_mc_multiple.append({"id": opt_id, "text": opt_obj.option_text})
                    official_answer_formatted = formatted_mc_multiple
                elif official_answer_obj.selected_option_id:
                    opt = QuestionOption.query.get(official_answer_obj.selected_option_id)
                    if opt:
                        official_answer_formatted = {"id": opt.id, "text": opt.option_text}
            elif question.question_type.name == 'SLIDER':
                if official_answer_obj: # Added check for official_answer_obj
                     official_answer_formatted = official_answer_obj.correct_slider_value
                else:
                     official_answer_formatted = None


        question_data["official_answer"] = official_answer_formatted
        question_data["official_answer_question_type"] = question.question_type.name
        question_data["official_answer_is_mc_multiple_correct"] = question.is_mc_multiple_correct

        # Fetch and format user's answer and points for this question
        current_user_answer_obj = user_answers_map.get(question.id)
        if current_user_answer_obj:
            user_answer_formatted = None
            # Determine if quiniela is closed for players to see their scores
            can_see_score = False
            if race.quiniela_close_date and race.quiniela_close_date < datetime.utcnow():
                can_see_score = True
            elif current_user.role.code in ['ADMIN', 'LEAGUE_ADMIN']: # Admins can always see scores
                can_see_score = True

            points_obtained_for_q = 0
            is_correct_for_q = False

            if can_see_score and official_answer_obj: # Need official answer to calculate score
                # Pass the correct map for ordering questions
                current_official_ordering_texts_for_calc = official_ordering_text_map if question.question_type.name == 'ORDERING' else None
                points_obtained_for_q, is_correct_for_q = _calculate_score_for_answer(
                    current_user_answer_obj,
                    official_answer_obj,
                    question,
                    official_mc_multiple_options_map,
                    current_official_ordering_texts_for_calc
                )

            # Format user's answer for display (similar to get_participant_answers)
            if question.question_type.name == 'FREE_TEXT':
                user_answer_formatted = current_user_answer_obj.answer_text
            elif question.question_type.name == 'ORDERING':
                user_answer_formatted = current_user_answer_obj.answer_text # This is already comma-separated texts
            elif question.question_type.name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    user_answer_formatted = [{"id": opt.question_option_id, "text": opt.question_option.option_text} for opt in current_user_answer_obj.selected_mc_options]
                elif current_user_answer_obj.selected_option_id:
                    opt_ua = QuestionOption.query.get(current_user_answer_obj.selected_option_id)
                    if opt_ua:
                        user_answer_formatted = {"id": opt_ua.id, "text": opt_ua.option_text}
            elif question.question_type.name == 'SLIDER':
                user_answer_formatted = current_user_answer_obj.slider_answer_value

            question_data["user_answer_details"] = {
                "answer": user_answer_formatted,
                "points_obtained": points_obtained_for_q if can_see_score else None, # Only show points if allowed
                "is_correct": is_correct_for_q if can_see_score else None # Only show correctness if allowed
            }

        output.append(question_data)

    return jsonify(output), 200


@app.route('/api/races/<int:race_id>/share_link', methods=['GET'])
@login_required
def get_race_share_link(race_id):
    # 1. Role check
    if not current_user.is_authenticated or current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to generate share links."), 403

    # 2. Fetch the Race object, ensuring it's not deleted
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    # 3. Construct the shareable link
    try:
        # As per plan, constructing a relative path.
        # The actual frontend route /join_race/<race_id> will be created later.
        share_link_path = f"/join_race/{race.id}"

    except Exception as e:
        app.logger.error(f"Error generating share link for race {race_id}: {e}", exc_info=True)
        return jsonify(message="Error generating share link"), 500

    return jsonify(share_link=share_link_path), 200


@app.route('/api/races/<int:race_id>/basic_details', methods=['GET'])
@login_required
def get_race_basic_details(race_id):
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    return jsonify(id=race.id, title=race.title), 200


@app.route('/api/races/<int:race_id>/join', methods=['POST']) # POST request to create a resource
@login_required
def join_race_api(race_id):
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    # Check if already registered
    existing_registration = UserRaceRegistration.query.filter_by(user_id=current_user.id, race_id=race.id).first()
    if existing_registration:
        return jsonify(message="You are already registered for this race."), 409 # 409 Conflict

    new_registration = UserRaceRegistration(user_id=current_user.id, race_id=race.id)
    try:
        db.session.add(new_registration)
        db.session.commit()
        return jsonify(message="Successfully registered for the race!", registration_id=new_registration.id), 201
    except IntegrityError: # Should be caught by the explicit check above, but as a fallback
        db.session.rollback()
        # Log this occurrence as it might indicate a race condition or an issue with the pre-check
        app.logger.warning(f"IntegrityError on join_race: User {current_user.id}, Race {race.id}. Pre-check failed or race condition.")
        return jsonify(message="Database integrity error: You might already be registered or there was another issue."), 409
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error registering user {current_user.id} for race {race.id}: {e}", exc_info=True)
        return jsonify(message="An error occurred while trying to register for the race."), 500

@app.route('/api/races/join_by_code', methods=['POST'])
@login_required
def join_race_by_code_api():
    data = request.get_json()
    if not data or 'access_code' not in data:
        return jsonify(message="Access code is required."), 400

    access_code = data['access_code'].strip()
    if not access_code:
        return jsonify(message="Access code cannot be empty."), 400

    race = Race.query.filter_by(access_code=access_code, is_deleted=False).first()
    if not race:
        return jsonify(message="Invalid access code or race not found."), 404

    # Check if already registered
    existing_registration = UserRaceRegistration.query.filter_by(user_id=current_user.id, race_id=race.id).first()
    if existing_registration:
        # If already registered, still return success with race_id for redirection.
        # The frontend can decide if it wants to notify "already registered" or just redirect.
        return jsonify(message="You are already registered for this race.", race_id=race.id), 200

    new_registration = UserRaceRegistration(user_id=current_user.id, race_id=race.id)
    try:
        db.session.add(new_registration)
        db.session.commit()
        return jsonify(message="Successfully registered for the race!", race_id=race.id), 201
    except IntegrityError: # Should be caught by the explicit check above, but as a fallback
        db.session.rollback()
        app.logger.warning(f"IntegrityError on join_race_by_code: User {current_user.id}, Race {race.id} (Code: {access_code}). Pre-check failed or race condition.")
        return jsonify(message="Database integrity error: You might already be registered or there was another issue."), 409
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error registering user {current_user.id} for race {race.id} (Code: {access_code}): {e}", exc_info=True)
        return jsonify(message="An error occurred while trying to register for the race."), 500

@app.route('/api/races/<int:race_id>/participants', methods=['GET'])
@login_required
def get_race_participants(race_id):
    # Role check
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to view participants."), 403

    # Check if race exists and is not deleted
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    total_questions_in_race = Question.query.filter_by(race_id=race_id).count()

    registrations = UserRaceRegistration.query.filter_by(race_id=race_id).all()

    participants_list = []
    for reg in registrations:
        user = User.query.get(reg.user_id)
        if not user:
            # This case should ideally not happen if data integrity is maintained
            app.logger.warning(f"UserRaceRegistration {reg.id} refers to a non-existent user {reg.user_id}.")
            continue

        answered_questions_count = UserAnswer.query.filter_by(user_id=user.id, race_id=race_id).count()
        has_answered = answered_questions_count > 0

        participants_list.append({
            "user_id": user.id,
            "username": user.username,
            "has_answered": has_answered,
            "answered_questions_count": answered_questions_count
        })

    return jsonify(total_questions_in_race=total_questions_in_race, participants=participants_list), 200


# Helper function to calculate score for a single answer
def _calculate_score_for_answer(user_answer_obj, official_answer_obj, question_obj, official_mc_multiple_options_map=None, official_ordering_data_for_q_type=None):
    """
    Calculates the score for a single user answer against an official answer.

    Args:
        user_answer_obj (UserAnswer): The user's answer object.
        official_answer_obj (OfficialAnswer): The official answer object. (Still needed for non-ORDERING types)
        question_obj (Question): The question object.
        official_mc_multiple_options_map (dict, optional): Pre-processed official MC-multiple answers.
                                                            Map of {question_id: {set of correct_option_ids}}.
        official_ordering_data_for_q_type (dict, optional): For ORDERING questions, this is official_ordering_text_map.
                                                            Map of {question_id: [list of lowercased_ordered_option_texts]}.
                                                            For other question types, this argument can be None or ignored.
    Returns:
        tuple: (points_obtained, is_correct)
    """
    if not user_answer_obj or not question_obj: # official_answer_obj might be None if not found, but q_obj and user_ans are essential
        return 0, False

    # official_answer_obj is still needed for Free Text, MC-Single, Slider where official answer is directly on it.
    # For MC-Multiple, official_mc_multiple_options_map is used.
    # For Ordering, official_ordering_data_for_q_type (the text map) is used.

    points_obtained = 0
    is_correct = False
    question_type_name = question_obj.question_type.name

    if official_mc_multiple_options_map is None: # Defaulting for safety, though get_participant_answers should provide it.
        official_mc_multiple_options_map = {}
    # No need to default official_ordering_data_for_q_type to {} if it's specifically for ordering and passed when needed.

    try:
        if question_type_name == 'FREE_TEXT':
            if official_answer_obj and official_answer_obj.answer_text and user_answer_obj.answer_text:
                if user_answer_obj.answer_text.strip().lower() == official_answer_obj.answer_text.strip().lower():
                    points_obtained = question_obj.max_score_free_text or 0
                    is_correct = True

        elif question_type_name == 'MULTIPLE_CHOICE':
            if question_obj.is_mc_multiple_correct:
                user_selected_option_ids = {opt.question_option_id for opt in user_answer_obj.selected_mc_options}
                official_correct_option_ids = official_mc_multiple_options_map.get(question_obj.id, set())

                current_question_mc_multiple_score = 0
                correct_user_selections = 0

                for user_opt_id in user_selected_option_ids:
                    if user_opt_id in official_correct_option_ids:
                        current_question_mc_multiple_score += (question_obj.points_per_correct_mc or 0)
                        correct_user_selections +=1
                    else: # User selected an incorrect option
                        # If points_per_incorrect_mc is stored as a negative number (e.g., -5 for a penalty),
                        # we should ADD it to the score.
                        current_question_mc_multiple_score += (question_obj.points_per_incorrect_mc or 0)

                points_obtained = current_question_mc_multiple_score
                # Consider is_correct to be true if all selected options are correct AND all correct options are selected.
                # Or, if any points are gained (simpler version for now: at least one correct pick and no wrong picks)
                is_correct = (user_selected_option_ids == official_correct_option_ids) and bool(official_correct_option_ids)


            else: # Single Correct
                if user_answer_obj.selected_option_id and \
                   user_answer_obj.selected_option_id == official_answer_obj.selected_option_id:
                    points_obtained = question_obj.total_score_mc_single or 0
                    is_correct = True

        elif question_type_name == 'ORDERING':
            user_ordered_texts = []
            if user_answer_obj.answer_text:
                user_ordered_texts = [text.strip().lower() for text in user_answer_obj.answer_text.split(',')]

            # official_ordering_data_for_q_type is now official_ordering_text_map passed from get_participant_answers
            # It should already contain a list of lowercased texts for the specific question_obj.id
            official_ordered_texts_for_q = official_ordering_data_for_q_type.get(question_obj.id, []) if official_ordering_data_for_q_type else []
            # No further lowercasing needed here if map provides already lowercased texts.
            # For safety, if the map isn't structured as expected or not passed for ordering, this defaults to [].

            if user_ordered_texts and official_ordered_texts_for_q: # Both must be non-empty
                current_question_ordering_score = 0
                is_full_match = True # Assume full match until proven otherwise

                # Check if lengths are different first, if so, not a full match.
                if len(user_ordered_texts) != len(official_ordered_texts_for_q):
                    is_full_match = False

                # Iterate based on the length of the official correct order
                for i in range(len(official_ordered_texts_for_q)):
                    if i < len(user_ordered_texts): # Check if user provided an answer for this position
                        if user_ordered_texts[i] == official_ordered_texts_for_q[i]: # Already lowercased
                            current_question_ordering_score += (question_obj.points_per_correct_order or 0)
                        else:
                            is_full_match = False # Mismatch at this position
                    else: # User answer is shorter than official answer, so not a full match
                        is_full_match = False

                # Apply bonus with refined logic (consistent with calculate_and_store_scores)
                if is_full_match and len(user_ordered_texts) == len(official_ordered_texts_for_q):
                    # Ensure bonus is only added if there were items to order and points_per_correct_order was positive
                    # or if there are zero items but a bonus is defined (edge case)
                    if ((question_obj.points_per_correct_order or 0) > 0 and len(official_ordered_texts_for_q) > 0) or \
                       (len(official_ordered_texts_for_q) == 0 and (question_obj.bonus_for_full_order or 0) > 0):
                        current_question_ordering_score += (question_obj.bonus_for_full_order or 0)

                points_obtained = current_question_ordering_score
                # A response is "correct" if it's a full match and there was something to match
                is_correct = is_full_match and bool(official_ordered_texts_for_q)

        elif question_type_name == 'SLIDER':
            if not official_answer_obj: # Guard against missing official_answer_obj for SLIDER type
                return 0, False
            epsilon = 1e-9  # For floating point comparisons
            points_obtained = 0 # Initialize points for this question
            is_correct = False  # Initialize correctness for this question

            if user_answer_obj.slider_answer_value is None or official_answer_obj.correct_slider_value is None:
                app.logger.debug(f"Scoring SLIDER QID {question_obj.id}: User or official answer is None. User: {user_answer_obj.slider_answer_value}, Official: {official_answer_obj.correct_slider_value}. Points: 0")
                # points_obtained and is_correct remain 0 and False
            else:
                user_val = user_answer_obj.slider_answer_value
                user_val = user_answer_obj.slider_answer_value
                official_val = official_answer_obj.correct_slider_value

                points_exact = question_obj.slider_points_exact
                threshold_partial = question_obj.slider_threshold_partial
                points_partial = question_obj.slider_points_partial

                app.logger.debug(
                    f"Scoring SLIDER QID {question_obj.id} - Initial values: "
                    f"UserVal={user_val}, OfficialVal={official_val}, "
                    f"Q.slider_points_exact={points_exact}, "
                    f"Q.slider_threshold_partial={threshold_partial}, "
                    f"Q.slider_points_partial={points_partial}"
                )

                diff = abs(user_val - official_val)
                rule_met = "None"

                if diff < epsilon:  # Exact match
                    app.logger.debug(f"Scoring SLIDER QID {question_obj.id}: Checking Exact Match. Diff={diff}, Epsilon={epsilon}")
                    if points_exact is not None:
                        points_obtained = points_exact
                        is_correct = (points_exact > 0) # Correct if points are positive
                        rule_met = "Exact"
                        app.logger.debug(f"Scoring SLIDER QID {question_obj.id}: Exact Match met. PointsAwarded={points_obtained}, IsCorrect={is_correct}")
                    else:
                        app.logger.debug(f"Scoring SLIDER QID {question_obj.id}: Exact Match condition met, but points_exact is None.")
                elif threshold_partial is not None and threshold_partial >= 0 and \
                     points_partial is not None and points_partial >= 0 and \
                     diff <= (threshold_partial + epsilon):  # Partial match
                    app.logger.debug(
                        f"Scoring SLIDER QID {question_obj.id}: Checking Partial Match. "
                        f"Diff={diff}, ThresholdPartial={threshold_partial}, Epsilon={epsilon}, "
                        f"PointsPartial={points_partial}"
                    )
                    points_obtained = points_partial
                    is_correct = (points_partial > 0) # Correct if points are positive
                    rule_met = "Partial"
                    app.logger.debug(f"Scoring SLIDER QID {question_obj.id}: Partial Match met. PointsAwarded={points_obtained}, IsCorrect={is_correct}")
                else:
                    app.logger.debug(f"Scoring SLIDER QID {question_obj.id}: No match (Exact or Partial). Diff={diff}")
                # Else, no match, points_obtained remains 0, is_correct remains False

                app.logger.debug(f"Scoring SLIDER QID {question_obj.id} - Final: UserVal={user_val}, OfficialVal={official_val}, Diff={diff}, RuleMet='{rule_met}', PointsAwarded={points_obtained}, IsCorrect={is_correct}")

    except Exception as e:
        app.logger.error(f"Error calculating score for QID {question_obj.id}, UserAnswerID {user_answer_obj.id}: {e}", exc_info=True)
        return 0, False # Return 0 points and False for correctness in case of an error

    return points_obtained, is_correct


@app.route('/api/races/<int:race_id>/participants/<int:user_id>/answers', methods=['GET'])
@login_required
def get_participant_answers(race_id, user_id):
    app.logger.info(f"Request for participant answers: race_id={race_id}, user_id={user_id} by current_user={current_user.username} (Role: {current_user.role.code})")

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        app.logger.warning(f"Race not found or deleted: {race_id}")
        return jsonify(message="Race not found or has been deleted"), 404

    participant = User.query.get(user_id)
    if not participant:
        app.logger.warning(f"Participant not found: {user_id}")
        return jsonify(message="Participant not found"), 404

    # Permission Check
    is_admin_or_league_admin = current_user.role.code in ['ADMIN', 'LEAGUE_ADMIN']

    # For LEAGUE_ADMIN, ensure they own the race or it's a general race if they are trying to access non-owned.
    # Admins can access any. Players can only access if quiniela is closed.
    if is_admin_or_league_admin:
        if current_user.role.code == 'LEAGUE_ADMIN':
            # Check if the league admin is the creator of the race or if the race is general (accessible by ADMINs)
            # This logic might need refinement based on exact ownership rules for league admins vs general races.
            # Assuming league admins can only see their own races' participant answers.
            if race.user_id != current_user.id and not race.is_general: # A league admin cannot see another league admin's race answers.
                 # If it's a general race, an ADMIN can see it, but a LEAGUE_ADMIN who isn't the owner shouldn't, unless specified.
                 # For now, strict: LEAGUE_ADMIN only for their own races.
                 # If ADMIN role also has user_id set for races they create, this needs adjustment.
                 # Current model Race.user_id is creator.
                 pass # League admins can view answers for races they created. Admins have blanket access.
    else: # Regular user (e.g., PLAYER)
        if race.quiniela_close_date is None or race.quiniela_close_date > datetime.utcnow():
            app.logger.warning(f"User {current_user.username} (Role: {current_user.role.code}) attempted to access answers for race {race_id} before quiniela close date.")
            return jsonify(message="Answers are not available until the quiniela is closed."), 403
        # Additionally, a player should probably only be able to see their own answers unless specified otherwise.
        # The current endpoint structure /participants/<user_id>/answers implies viewing a specific user.
        # If current_user.id != participant.id, a PLAYER should be blocked.
        if current_user.id != participant.id:
            app.logger.warning(f"User {current_user.username} (Role: {current_user.role.code}) attempted to access answers for another user {participant.id}.")
            return jsonify(message="You are not authorized to view this participant's answers."), 403


    # Fetch all data
    race_questions = Question.query.filter_by(race_id=race_id).order_by(Question.id).all()

    user_answers_list = UserAnswer.query.filter_by(user_id=participant.id, race_id=race_id).all()
    user_answers_map = {ua.question_id: ua for ua in user_answers_list}

    official_answers_list = OfficialAnswer.query.filter_by(race_id=race_id).all()
    official_answers_map = {oa.question_id: oa for oa in official_answers_list}

    # Pre-process official MC-multiple answers
    official_mc_multiple_options_map = {}
    for oa_obj in official_answers_list:
        q_obj = Question.query.get(oa_obj.question_id)
        if q_obj and q_obj.question_type.name == 'MULTIPLE_CHOICE' and q_obj.is_mc_multiple_correct:
            official_mc_multiple_options_map[q_obj.id] = {sel_opt.question_option_id for sel_opt in oa_obj.official_selected_mc_options}

    # Pre-process official ORDERING answers:
    # Now, instead of building from QuestionOption.correct_order_index,
    # we will prepare the data source that _calculate_score_for_answer expects,
    # which is a map of question_id to a list of lowercased official ordered texts
    # derived from OfficialAnswer.answer_text.
    official_ordering_text_map = {}
    for q_id, oa_obj in official_answers_map.items():
        question_for_oa = Question.query.get(q_id) # Get the question object
        if question_for_oa and question_for_oa.question_type.name == 'ORDERING':
            if oa_obj and oa_obj.answer_text:
                # Parse comma-separated texts from OfficialAnswer.answer_text
                official_texts = [text.strip().lower() for text in oa_obj.answer_text.split(',') if text.strip()]
                official_ordering_text_map[q_id] = official_texts
            else:
                official_ordering_text_map[q_id] = [] # No official answer text or empty

    results = []

    for question in race_questions:
        user_answer_obj = user_answers_map.get(question.id)
        official_answer_obj = official_answers_map.get(question.id) # Used for non-ordering types and general info

        points, correct = 0, False
        if user_answer_obj and official_answer_obj: # official_answer_obj ensures there's an official entry
            # For ordering questions, _calculate_score_for_answer will now use official_ordering_text_map
            # For other types, it will use official_answer_obj directly or official_mc_multiple_options_map
            current_official_ordering_texts = official_ordering_text_map if question.question_type.name == 'ORDERING' else None

            points, correct = _calculate_score_for_answer(
                user_answer_obj,
                official_answer_obj, # Still needed for other types and accessing fields like correct_slider_value
                question,
                official_mc_multiple_options_map,
                current_official_ordering_texts # Pass the map of texts for ordering
            )

        # Format participant's answer
        participant_answer_formatted = None
        if user_answer_obj:
            if question.question_type.name == 'FREE_TEXT':
                participant_answer_formatted = user_answer_obj.answer_text
            elif question.question_type.name == 'ORDERING':
                # For ordering questions, UserAnswer.answer_text stores the comma-separated string of option texts.
                # So, we can use it directly.
                participant_answer_formatted = user_answer_obj.answer_text
            elif question.question_type.name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    participant_answer_formatted = [{"id": opt.question_option_id, "text": opt.question_option.option_text} for opt in user_answer_obj.selected_mc_options]
                elif user_answer_obj.selected_option_id:
                    opt = QuestionOption.query.get(user_answer_obj.selected_option_id)
                    if opt:
                        participant_answer_formatted = {"id": opt.id, "text": opt.option_text}
            elif question.question_type.name == 'SLIDER':
                participant_answer_formatted = user_answer_obj.slider_answer_value

        # Format official answer
        official_answer_formatted = None
        if official_answer_obj:
            if question.question_type.name == 'FREE_TEXT':
                official_answer_formatted = official_answer_obj.answer_text
            elif question.question_type.name == 'ORDERING':
                # For ordering questions, OfficialAnswer.answer_text should store the comma-separated string of correct option texts.
                if official_answer_obj and official_answer_obj.answer_text:
                    official_answer_formatted = official_answer_obj.answer_text
                else:
                    official_answer_formatted = None # No official answer set or answer_text is empty/None
            elif question.question_type.name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    official_answer_formatted = [{"id": opt_id, "text": QuestionOption.query.get(opt_id).option_text} for opt_id in official_mc_multiple_options_map.get(question.id, set())]
                elif official_answer_obj.selected_option_id:
                    opt = QuestionOption.query.get(official_answer_obj.selected_option_id)
                    if opt:
                        official_answer_formatted = {"id": opt.id, "text": opt.option_text}
            elif question.question_type.name == 'SLIDER':
                official_answer_formatted = official_answer_obj.correct_slider_value

        # Calculate max_points_possible
        max_points = 0
        if question.question_type.name == 'FREE_TEXT':
            max_points = question.max_score_free_text or 0
        elif question.question_type.name == 'MULTIPLE_CHOICE':
            if question.is_mc_multiple_correct:
                # Sum points for all correct options as defined in official_mc_multiple_options_map
                # This assumes points_per_correct_mc is positive.
                # Negative points for incorrect selections are handled by points_obtained.
                # Max points here is the sum of points for all *actually correct* options.
                correct_option_ids = official_mc_multiple_options_map.get(question.id, set())
                max_points = len(correct_option_ids) * (question.points_per_correct_mc or 0)
            else: # Single correct
                max_points = question.total_score_mc_single or 0
        elif question.question_type.name == 'ORDERING':
            # Max points = (points_per_correct_order * num_items) + bonus_for_full_order
            # Use official_ordering_text_map (derived from OfficialAnswer.answer_text) for num_items_to_order
            official_ordered_texts_for_max_points = official_ordering_text_map.get(question.id, [])
            num_items_to_order = len(official_ordered_texts_for_max_points)

            max_points = (question.points_per_correct_order or 0) * num_items_to_order
            # Consistent bonus logic for max points:
            # Add bonus if there are items and they would score points, or if it's the zero-item bonus case
            if num_items_to_order > 0 and (question.points_per_correct_order or 0) > 0:
                 max_points += (question.bonus_for_full_order or 0)
            elif num_items_to_order == 0 and (question.bonus_for_full_order or 0) > 0: # Bonus for ordering zero items
                 max_points += (question.bonus_for_full_order or 0)
        elif question.question_type.name == 'SLIDER':
            max_points = question.slider_points_exact or 0

        results.append({
            "question_id": question.id,
            "question_text": question.text,
            "question_type": question.question_type.name,
            "question_is_mc_multiple_correct": question.is_mc_multiple_correct, # ADDED THIS LINE
            "participant_answer": participant_answer_formatted,
            "official_answer": official_answer_formatted,
            "is_correct": correct,
            "points_obtained": points,
            "max_points_possible": max_points
        })

    return jsonify(results), 200

@app.route('/api/races/<int:race_id>/statistics', methods=['GET'])
@login_required
def get_race_statistics(race_id):
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    participant_count = UserRaceRegistration.query.filter_by(race_id=race.id).count()

    # Counts distinct users who have submitted at least one answer for this race.
    predictions_count = db.session.query(func.count(UserAnswer.user_id.distinct())) \
        .filter_by(race_id=race.id).scalar()

    quiniela_close_date_iso = race.quiniela_close_date.isoformat() if race.quiniela_close_date else None

    return jsonify(
        participant_count=participant_count,
        predictions_count=predictions_count,
        quiniela_close_date=quiniela_close_date_iso
    ), 200


@app.route('/api/races/<int:race_id>/favorite', methods=['POST'])
@login_required
def favorite_race(race_id):
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    existing_favorite = UserFavoriteRace.query.filter_by(user_id=current_user.id, race_id=race.id).first()
    if existing_favorite:
        return jsonify(message="Race already favorited"), 200

    new_favorite = UserFavoriteRace(user_id=current_user.id, race_id=race.id)
    try:
        db.session.add(new_favorite)
        db.session.commit()
        return jsonify(message="Race favorited successfully"), 201
    except IntegrityError: # Should ideally be caught by the check above
        db.session.rollback()
        app.logger.warning(f"IntegrityError on favorite_race: User {current_user.id}, Race {race.id}. Pre-check failed or race condition.")
        return jsonify(message="Race already favorited or database integrity error."), 409 # 409 Conflict
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error favoriting race {race.id} for user {current_user.id}: {e}", exc_info=True)
        return jsonify(message="An error occurred while favoriting the race."), 500


@app.route('/api/races/<int:race_id>/favorite', methods=['DELETE'])
@login_required
def unfavorite_race(race_id):
    # For unfavoriting, we might allow it even if the race is "deleted"
    # as the favorite entry still exists. Or, we can restrict it.
    # For now, let's assume we only care if the favorite entry itself exists.
    # Race existence check (is_deleted=False) is not strictly necessary here,
    # but could be added if desired to prevent unfavoriting an already deleted race.
    race = Race.query.get(race_id) # Keep this to ensure race_id is valid at least
    if not race:
        return jsonify(message="Race not found"), 404 # Or specific message if it was deleted

    favorite_entry = UserFavoriteRace.query.filter_by(user_id=current_user.id, race_id=race.id).first()
    if not favorite_entry:
        return jsonify(message="Race not favorited"), 404

    try:
        db.session.delete(favorite_entry)
        db.session.commit()
        return jsonify(message="Race unfavorited successfully"), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error unfavoriting race {race.id} for user {current_user.id}: {e}", exc_info=True)
        return jsonify(message="An error occurred while unfavoriting the race."), 500

# --- FavoriteLink API Endpoints ---

@app.route('/api/races/<int:race_id>/favorite_links', methods=['POST'])
@login_required
def create_favorite_link(race_id):
    app.logger.info(f"User {current_user.id} attempting to create favorite link for race {race_id}")
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.id} with role {current_user.role.code} forbidden to create favorite link for race {race_id}")
        return jsonify(message="Forbidden: You do not have permission to create favorite links."), 403

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        app.logger.warning(f"Race with id {race_id} not found or deleted when creating favorite link.")
        return jsonify(message="Race not found or has been deleted"), 404

    # LEAGUE_ADMIN can only add links to their own races
    if current_user.role.code == 'LEAGUE_ADMIN' and race.user_id != current_user.id:
        app.logger.warning(f"LEAGUE_ADMIN {current_user.id} forbidden to create favorite link for race {race_id} they do not own.")
        return jsonify(message="Forbidden: You can only add links to races you created."), 403

    data = request.get_json()
    if not data:
        app.logger.warning(f"No data provided for creating favorite link for race {race_id}")
        return jsonify(message="Invalid input: No data provided"), 400

    title = data.get('title')
    url = data.get('url')
    order = data.get('order', 0)

    if not title or not isinstance(title, str) or not title.strip():
        return jsonify(message="Title is required and must be a non-empty string."), 400
    if not url or not isinstance(url, str) or not url.strip():
        return jsonify(message="URL is required and must be a non-empty string."), 400
    if not isinstance(order, int):
        try:
            order = int(order)
        except (ValueError, TypeError):
            return jsonify(message="Order must be an integer."), 400

    # Basic URL validation (can be more sophisticated)
    if not (url.startswith('http://') or url.startswith('https://')):
        return jsonify(message="URL must start with http:// or https://"), 400


    new_link = FavoriteLink(
        race_id=race_id,
        title=title,
        url=url,
        order=order
    )

    try:
        db.session.add(new_link)
        db.session.commit()
        app.logger.info(f"FavoriteLink {new_link.id} created for race {race_id} by user {current_user.id}")
        return jsonify(new_link.to_dict()), 201
    except IntegrityError as e:
        db.session.rollback()
        app.logger.error(f"IntegrityError creating favorite link for race {race_id}: {e}", exc_info=True)
        # Check if it's a specific constraint violation if any unique constraints were on FavoriteLink (none specified for now beyond PK)
        return jsonify(message="Database integrity error while creating favorite link."), 500 # Or 409 if a unique constraint failed
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception creating favorite link for race {race_id}: {e}", exc_info=True)
        return jsonify(message="Error creating favorite link"), 500

@app.route('/api/races/<int:race_id>/favorite_links', methods=['GET'])
def get_favorite_links_for_race(race_id):
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        app.logger.info(f"Attempt to get favorite links for non-existent or deleted race {race_id}")
        return jsonify(message="Race not found or has been deleted"), 404

    links = FavoriteLink.query.filter_by(race_id=race_id).order_by(FavoriteLink.order, FavoriteLink.id).all()
    return jsonify([link.to_dict() for link in links]), 200

@app.route('/api/favorite_links/<int:link_id>', methods=['PUT'])
@login_required
def update_favorite_link(link_id):
    app.logger.info(f"User {current_user.id} attempting to update favorite link {link_id}")
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.id} with role {current_user.role.code} forbidden to update favorite link {link_id}")
        return jsonify(message="Forbidden: You do not have permission to update favorite links."), 403

    link = FavoriteLink.query.get(link_id)
    if not link:
        app.logger.warning(f"FavoriteLink with id {link_id} not found for update by user {current_user.id}")
        return jsonify(message="FavoriteLink not found"), 404

    race = Race.query.get(link.race_id)
    if not race: # Should not happen if DB integrity is maintained
        app.logger.error(f"Race with id {link.race_id} associated with FavoriteLink {link_id} not found.")
        return jsonify(message="Associated race not found, cannot update link."), 500

    # LEAGUE_ADMIN can only update links for their own races
    if current_user.role.code == 'LEAGUE_ADMIN' and race.user_id != current_user.id:
        app.logger.warning(f"LEAGUE_ADMIN {current_user.id} forbidden to update favorite link {link_id} for race {race.id} they do not own.")
        return jsonify(message="Forbidden: You can only update links for races you created."), 403

    data = request.get_json()
    if not data:
        app.logger.warning(f"No data provided for updating favorite link {link_id}")
        return jsonify(message="Invalid input: No data provided"), 400

    updated = False
    if 'title' in data:
        title = data.get('title')
        if not title or not isinstance(title, str) or not title.strip():
            return jsonify(message="Title must be a non-empty string if provided."), 400
        link.title = title
        updated = True

    if 'url' in data:
        url = data.get('url')
        if not url or not isinstance(url, str) or not url.strip():
            return jsonify(message="URL must be a non-empty string if provided."), 400
        if not (url.startswith('http://') or url.startswith('https://')):
            return jsonify(message="URL must start with http:// or https://"), 400
        link.url = url
        updated = True

    if 'order' in data:
        order = data.get('order')
        if not isinstance(order, int):
            try:
                order = int(order)
            except (ValueError, TypeError):
                return jsonify(message="Order must be an integer if provided."), 400
        link.order = order
        updated = True

    if not updated:
        return jsonify(message="No updatable fields provided."), 400

    try:
        db.session.commit()
        app.logger.info(f"FavoriteLink {link.id} updated by user {current_user.id}")
        return jsonify(link.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception updating favorite link {link.id}: {e}", exc_info=True)
        return jsonify(message="Error updating favorite link"), 500

@app.route('/api/favorite_links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_favorite_link(link_id):
    app.logger.info(f"User {current_user.id} attempting to delete favorite link {link_id}")
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.id} with role {current_user.role.code} forbidden to delete favorite link {link_id}")
        return jsonify(message="Forbidden: You do not have permission to delete favorite links."), 403

    link = FavoriteLink.query.get(link_id)
    if not link:
        app.logger.warning(f"FavoriteLink with id {link_id} not found for deletion by user {current_user.id}")
        return jsonify(message="FavoriteLink not found"), 404

    race = Race.query.get(link.race_id)
    if not race: # Should not happen
        app.logger.error(f"Race with id {link.race_id} associated with FavoriteLink {link_id} not found during delete.")
        # Link still exists so proceed with deletion of link, but log this anomaly.
    elif current_user.role.code == 'LEAGUE_ADMIN' and race.user_id != current_user.id:
        app.logger.warning(f"LEAGUE_ADMIN {current_user.id} forbidden to delete favorite link {link_id} for race {race.id} they do not own.")
        return jsonify(message="Forbidden: You can only delete links for races you created."), 403

    try:
        db.session.delete(link)
        db.session.commit()
        app.logger.info(f"FavoriteLink {link.id} deleted by user {current_user.id}")
        return jsonify(message="FavoriteLink deleted successfully"), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception deleting favorite link {link.id}: {e}", exc_info=True)
        return jsonify(message="Error deleting favorite link"), 500

@app.route('/api/races/<int:race_id>/favorite_links/reorder', methods=['POST'])
@login_required
def reorder_favorite_links(race_id):
    app.logger.info(f"User {current_user.id} attempting to reorder favorite links for race {race_id}")
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.id} forbidden to reorder links for race {race_id}")
        return jsonify(message="Forbidden: You do not have permission to reorder links."), 403

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        app.logger.warning(f"Race with id {race_id} not found or deleted when reordering links.")
        return jsonify(message="Race not found or has been deleted"), 404

    if current_user.role.code == 'LEAGUE_ADMIN' and race.user_id != current_user.id:
        app.logger.warning(f"LEAGUE_ADMIN {current_user.id} forbidden to reorder links for race {race_id} they do not own.")
        return jsonify(message="Forbidden: You can only reorder links for races you created."), 403

    data = request.get_json()
    if not data or 'link_ids' not in data or not isinstance(data['link_ids'], list):
        app.logger.warning(f"Invalid payload for reordering links for race {race_id}: {data}")
        return jsonify(message="Invalid input: 'link_ids' (list) is required."), 400

    link_ids = data['link_ids']

    try:
        with db.session.no_autoflush: # Avoid premature flushes that might cause issues with temp states
            links_to_reorder = FavoriteLink.query.filter(FavoriteLink.id.in_(link_ids), FavoriteLink.race_id == race_id).all()

            if len(links_to_reorder) != len(link_ids):
                 # This means some link_ids were not found or don't belong to this race
                app.logger.warning(f"Mismatch in link_ids for reorder. Provided: {link_ids}, Found for race {race_id}: {[l.id for l in links_to_reorder]}")
                # Find which ones are problematic
                valid_link_ids_for_race = {link.id for link in FavoriteLink.query.filter_by(race_id=race_id).with_entities(FavoriteLink.id).all()}
                problematic_ids = [lid for lid in link_ids if lid not in valid_link_ids_for_race]
                if problematic_ids:
                    return jsonify(message=f"Error: Some link IDs do not belong to this race or are invalid: {problematic_ids}."), 400
                # If all provided IDs are valid but some are missing from the database, it's a different issue.
                # For simplicity, we'll just error out if counts don't match after confirming all provided IDs are for this race.
                # This check is more complex than it needs to be if we assume client sends correct IDs.
                # A simpler check:
                # if any(link.race_id != race_id for link in links_to_reorder_map.values()):
                #    return jsonify(message="Error: One or more links do not belong to the specified race."), 400

            link_map = {link.id: link for link in links_to_reorder}

            for index, link_id in enumerate(link_ids):
                if link_id in link_map:
                    link_map[link_id].order = index
                else:
                    # This case should be caught by the length check above if all link_ids are unique
                    app.logger.error(f"Link ID {link_id} provided in reorder list not found in database for race {race_id}.")
                    # Not rolling back here, as some orders might be valid. Client should ensure valid list.
                    # Or, stricter: db.session.rollback(); return jsonify(message=f"Error: Link ID {link_id} not found for this race."), 400
                    continue

        db.session.commit()
        app.logger.info(f"FavoriteLinks for race {race_id} reordered successfully by user {current_user.id}")
        return jsonify(message="Favorite links reordered successfully."), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception reordering favorite links for race {race_id}: {e}", exc_info=True)
        return jsonify(message="Error reordering favorite links"), 500

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
    elif question.question_type.name == 'SLIDER':
        question_data["slider_unit"] = question.slider_unit
        question_data["slider_min_value"] = question.slider_min_value
        question_data["slider_max_value"] = question.slider_max_value
        question_data["slider_step"] = question.slider_step
        question_data["slider_points_exact"] = question.slider_points_exact
        question_data["slider_threshold_partial"] = question.slider_threshold_partial
        question_data["slider_points_partial"] = question.slider_points_partial

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

# --- Helper function for creating question and options from payload ---
def _create_question_and_options_from_payload(question_payload, race_id):
    """
    Creates a Question and its QuestionOption objects from a payload.
    Adds them to the db.session but does not commit.
    Returns the Question object or None if a critical error occurs.
    """
    question_type_name = question_payload.get('type')
    if not question_type_name:
        app.logger.warning(f"Skipping question due to missing type: {question_payload.get('text')}")
        return None

    question_type_obj = QuestionType.query.filter_by(name=question_type_name).first()
    if not question_type_obj:
        app.logger.warning(f"Skipping question due to invalid type '{question_type_name}': {question_payload.get('text')}")
        return None

    new_question = Question(
        race_id=race_id,
        question_type_id=question_type_obj.id,
        text=question_payload.get('text'),
        is_active=question_payload.get('is_active', True)
    )

    # Populate scoring fields based on type
    if question_type_name == 'FREE_TEXT':
        new_question.max_score_free_text = question_payload.get('max_score_free_text')
    elif question_type_name == 'MULTIPLE_CHOICE':
        new_question.is_mc_multiple_correct = question_payload.get('is_mc_multiple_correct')
        if new_question.is_mc_multiple_correct:
            new_question.points_per_correct_mc = question_payload.get('points_per_correct_mc')
            new_question.points_per_incorrect_mc = question_payload.get('points_per_incorrect_mc', 0)
        else:
            new_question.total_score_mc_single = question_payload.get('total_score_mc_single')
    elif question_type_name == 'ORDERING':
        new_question.points_per_correct_order = question_payload.get('points_per_correct_order')
        new_question.bonus_for_full_order = question_payload.get('bonus_for_full_order', 0)

    db.session.add(new_question)
    # db.session.flush() # Optional: if new_question.id is needed by options not using backref

    options_payload = question_payload.get('options', [])
    if options_payload:
        for index, option_data in enumerate(options_payload):
            option_text_value = option_data.get('option_text')
            if not option_text_value:
                app.logger.warning(f"Skipping option for question '{new_question.text}' due to missing option_text.")
                continue

            new_option = QuestionOption(
                question=new_question,  # Relies on SQLAlchemy to handle association
                option_text=option_text_value
            )
            if question_type_name == 'ORDERING':
                new_option.correct_order_index = index

            # Placeholder for future: MC option correctness if sent in payload
            # if question_type_name == 'MULTIPLE_CHOICE':
            #     if new_question.is_mc_multiple_correct:
            #         new_option.is_correct_mc_multiple = option_data.get('is_correct', False)
            #     else:
            #         new_option.is_correct_mc_single = option_data.get('is_correct', False)

            db.session.add(new_option)

    return new_question

# --- CRUD for Free Text Questions ---
@app.route('/api/races/<int:race_id>/questions/free-text', methods=['POST'])
@login_required
def create_free_text_question(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    if race.quiniela_close_date and race.quiniela_close_date < datetime.utcnow():
        app.logger.warning(f"Attempt to create question for closed quiniela race {race_id} by user {current_user.id}")
        return jsonify(message="La quiniela ya esta cerrada y no se pueden añadir nuevas preguntas"), 403

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
    app.logger.info(f"[login_api] Iniciando login. Request args: {request.args}")
    next_url_in_login_api = request.args.get('next')
    app.logger.info(f"[login_api] 'next' URL recibida en query args: {next_url_in_login_api}")

    data = request.get_json()
    if not data:
        app.logger.warning("[login_api] No data provided in JSON body.")
        return jsonify(message="Invalid input: No data provided"), 400

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

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    if race.quiniela_close_date and race.quiniela_close_date < datetime.utcnow():
        app.logger.warning(f"Attempt to create question for closed quiniela race {race_id} by user {current_user.id}")
        return jsonify(message="La quiniela ya esta cerrada y no se pueden añadir nuevas preguntas"), 403

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

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    if race.quiniela_close_date and race.quiniela_close_date < datetime.utcnow():
        app.logger.warning(f"Attempt to create question for closed quiniela race {race_id} by user {current_user.id}")
        return jsonify(message="La quiniela ya esta cerrada y no se pueden añadir nuevas preguntas"), 403

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

# --- CRUD for Slider Questions ---
@app.route('/api/races/<int:race_id>/questions/slider', methods=['POST'])
@login_required
def create_slider_question(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    if race.quiniela_close_date and race.quiniela_close_date < datetime.utcnow():
        app.logger.warning(f"Attempt to create question for closed quiniela race {race_id} by user {current_user.id}")
        return jsonify(message="La quiniela ya esta cerrada y no se pueden añadir nuevas preguntas"), 403

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    # Validate required fields
    text = data.get('text')
    slider_unit = data.get('slider_unit') # Can be None or empty string
    slider_min_value = data.get('slider_min_value')
    slider_max_value = data.get('slider_max_value')
    slider_step = data.get('slider_step')
    slider_points_exact = data.get('slider_points_exact')
    # Optional fields for partial scoring
    slider_threshold_partial = data.get('slider_threshold_partial')
    slider_points_partial = data.get('slider_points_partial')


    if not text or not isinstance(text, str) or not text.strip():
        return jsonify(message="Question text is required and must be a non-empty string"), 400
    if slider_unit is not None and not isinstance(slider_unit, str): # Allow empty string, but if present, must be string
        return jsonify(message="Slider unit must be a string if provided"), 400

    try:
        slider_min_value = float(slider_min_value)
        slider_max_value = float(slider_max_value)
        slider_step = float(slider_step)
    except (ValueError, TypeError):
        return jsonify(message="slider_min_value, slider_max_value, and slider_step must be valid numbers"), 400

    if not isinstance(slider_points_exact, int) or slider_points_exact < 0:
        return jsonify(message="slider_points_exact is required and must be a non-negative integer"), 400

    if slider_min_value >= slider_max_value:
        return jsonify(message="slider_min_value must be less than slider_max_value"), 400
    if slider_step <= 0:
        return jsonify(message="slider_step must be a positive number"), 400

    # Validate partial scoring fields if present
    if slider_threshold_partial is not None or slider_points_partial is not None:
        if slider_threshold_partial is None or slider_points_partial is None:
            return jsonify(message="For partial scoring, both threshold and points must be provided"), 400
        try:
            slider_threshold_partial = float(slider_threshold_partial)
        except (ValueError, TypeError):
            return jsonify(message="slider_threshold_partial must be a valid number if provided for partial scoring"),400
        if not isinstance(slider_points_partial, int):
             return jsonify(message="slider_points_partial must be an integer if provided for partial scoring"), 400

        if slider_threshold_partial < 0:
            return jsonify(message="slider_threshold_partial must be non-negative if provided"), 400
        if slider_points_partial < 0:
            return jsonify(message="slider_points_partial must be non-negative if provided"), 400
    else: # Ensure they are None if not provided for partial scoring
        slider_threshold_partial = None
        slider_points_partial = None


    question_type_slider = QuestionType.query.filter_by(name='SLIDER').first()
    if not question_type_slider:
        # This case should ideally not happen if DB is seeded correctly
        return jsonify(message="QuestionType 'SLIDER' not found. Please seed database."), 500

    new_question = Question(
        race_id=race_id,
        question_type_id=question_type_slider.id,
        text=text,
        is_active=data.get('is_active', True), # Default to True
        slider_unit=slider_unit if (slider_unit and slider_unit.strip()) else None, # Store None if empty string
        slider_min_value=slider_min_value,
        slider_max_value=slider_max_value,
        slider_step=slider_step,
        slider_points_exact=slider_points_exact,
        slider_threshold_partial=slider_threshold_partial,
        slider_points_partial=slider_points_partial
    )

    try:
        db.session.add(new_question)
        db.session.commit()
        return jsonify(_serialize_question(new_question)), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating slider question: {e}", exc_info=True)
        return jsonify(message="Error creating slider question"), 500

@app.route('/api/questions/slider/<int:question_id>', methods=['PUT'])
@login_required
def update_slider_question(question_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    question = Question.query.get(question_id)
    if not question:
        return jsonify(message="Question not found"), 404
    if question.question_type.name != 'SLIDER':
        return jsonify(message="Cannot update non-SLIDER question via this endpoint"), 400

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

    # Update slider-specific fields
    if 'slider_unit' in data:
        slider_unit = data.get('slider_unit')
        if slider_unit is not None and not isinstance(slider_unit, str): # Allow null or empty string to clear
             return jsonify(message="Slider unit must be a string if provided, or null/empty to clear"), 400
        question.slider_unit = slider_unit if (slider_unit and slider_unit.strip()) else None


    min_val_present = 'slider_min_value' in data
    max_val_present = 'slider_max_value' in data
    step_present = 'slider_step' in data

    # Temporary variables to hold new values for validation
    temp_min_value = question.slider_min_value
    temp_max_value = question.slider_max_value
    temp_step_value = question.slider_step

    if min_val_present:
        try:
            temp_min_value = float(data['slider_min_value'])
        except (ValueError, TypeError):
            return jsonify(message="slider_min_value must be a valid number if provided"), 400
    if max_val_present:
        try:
            temp_max_value = float(data['slider_max_value'])
        except (ValueError, TypeError):
            return jsonify(message="slider_max_value must be a valid number if provided"), 400
    if step_present:
        try:
            temp_step_value = float(data['slider_step'])
        except (ValueError, TypeError):
            return jsonify(message="slider_step must be a valid number if provided"), 400

    # Validate combined min/max/step
    if temp_min_value >= temp_max_value:
        return jsonify(message="slider_min_value must be less than slider_max_value"), 400
    if temp_step_value <= 0:
        return jsonify(message="slider_step must be a positive number"), 400

    # If validation passes, assign to question object
    if min_val_present: question.slider_min_value = temp_min_value
    if max_val_present: question.slider_max_value = temp_max_value
    if step_present: question.slider_step = temp_step_value


    if 'slider_points_exact' in data:
        points_exact = data.get('slider_points_exact')
        if not isinstance(points_exact, int) or points_exact < 0:
            return jsonify(message="slider_points_exact must be a non-negative integer if provided"), 400
        question.slider_points_exact = points_exact

    # Handle partial scoring fields - they must be provided together or not at all
    threshold_partial_present = 'slider_threshold_partial' in data
    points_partial_present = 'slider_points_partial' in data

    if threshold_partial_present and points_partial_present:
        threshold_partial = data.get('slider_threshold_partial')
        points_partial = data.get('slider_points_partial')
        if threshold_partial is None and points_partial is None: # Both explicitly set to null
            question.slider_threshold_partial = None
            question.slider_points_partial = None
        else:
            try:
                threshold_partial = float(threshold_partial)
            except (ValueError, TypeError):
                 return jsonify(message="slider_threshold_partial must be a valid number if provided for partial scoring"),400
            if not isinstance(points_partial, int):
                return jsonify(message="slider_points_partial must be an integer if provided for partial scoring"), 400

            if threshold_partial < 0:
                return jsonify(message="slider_threshold_partial must be non-negative if provided"), 400
            if points_partial < 0:
                return jsonify(message="slider_points_partial must be non-negative if provided"), 400
            question.slider_threshold_partial = threshold_partial
            question.slider_points_partial = points_partial
    elif threshold_partial_present or points_partial_present: # Only one is present
        return jsonify(message="For partial scoring, both slider_threshold_partial and slider_points_partial must be provided together, or neither."), 400


    try:
        db.session.commit()
        return jsonify(_serialize_question(question)), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating slider question {question_id}: {e}", exc_info=True)
        return jsonify(message="Error updating slider question"), 500


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
def tripredict_promo_page():
    return render_template('index.html')

@app.route('/TriCal')
def trical_events_page():
    # Obtienes TODOS los eventos de la base de datos
    events_list = Event.query.order_by(Event.event_date.asc()).all()
    return render_template('TriCal.html', events=events_list)

@app.route('/Faq')
def faq_page():
    return render_template('faq.html')

# The @app.route('/') for tripredict_promo_page is now defined above.
# We need to ensure the old root() redirect is removed or handled.
# The original root redirecting to login is no longer needed if / serves promo.
# @app.route('/')
# def root():
#    return redirect(url_for('serve_login_page'))

@app.route('/login')
def serve_login_page():
    # Assuming frontend folder is one level up from where app.py is (backend/app.py -> frontend/)
    return render_template('login.html')

@app.route('/register')
def register_page():
    all_roles = Role.query.all()
    return render_template('register.html', roles=all_roles)


@app.route('/join_race/<int:race_id>')
@login_required
def join_race_deep_link(race_id):
    """
    Gestiona el deep link para unirse a una carrera.
    Gracias al decorador @login_required, este código solo se ejecuta
    si el usuario ya está autenticado. Flask-Login maneja la redirección
    a la página de login si es necesario.
    """
    app.logger.info(f"[join_race_deep_link] Iniciando para race_id: {race_id}, user: {current_user.username}")
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()

    if not race:
        app.logger.warning(f"[join_race_deep_link] Carrera con ID {race_id} no encontrada o eliminada.")
        flash(f'La carrera con ID {race_id} a la que intentas unirte no existe o ha sido eliminada.', 'error')
        return redirect(url_for('serve_hello_world_page'))
    app.logger.info(f"[join_race_deep_link] Carrera encontrada: {race.title}")

    # Criterio de Aceptación: Usuario ya es participante
    is_already_registered = UserRaceRegistration.query.filter_by(
        user_id=current_user.id,
        race_id=race_id
    ).first()
    app.logger.info(f"[join_race_deep_link] Usuario ya registrado: {'Sí' if is_already_registered else 'No'}")

    if is_already_registered:
        flash(f'Ya estás inscrito en la carrera "{race.title}".', 'info')
        return redirect(url_for('serve_race_detail_page', race_id=race.id))

    # Criterio de Aceptación: Nuevo participante. Se guarda la intención en la sesión.
    # Esto es más robusto que pasar parámetros por la URL.
    app.logger.info(f"[join_race_deep_link] Intentando guardar en sesión: race_id={race.id}, race_title={race.title}")
    session['auto_join_race_id'] = race.id
    session['race_to_join_title'] = race.title
    # Para verificar si se guardó (esto es más para depuración local, en producción puede ser ruidoso)
    app.logger.info(f"[join_race_deep_link] Valores en sesión después de guardar: auto_join_race_id={session.get('auto_join_race_id')}, race_to_join_title={session.get('race_to_join_title')}")

    # Redirigimos al dashboard, que se encargará de leer la sesión y mostrar el pop-up.
    app.logger.info(f"[join_race_deep_link] Redirigiendo a serve_hello_world_page")
    return redirect(url_for('serve_hello_world_page'))


@app.route('/Hello-world') # This is the main dashboard route after login
@login_required
def serve_hello_world_page():
    app.logger.info(f"[serve_hello_world_page] Iniciando para user: {current_user.username}")
    app.logger.info(f"[serve_hello_world_page] Sesión ANTES de pop: {dict(session)}")
    # Lee la "intención" de la sesión y la elimina para que no se repita.
    auto_join_race_id_to_template = session.pop('auto_join_race_id', None)
    race_to_join_title_to_template = session.pop('race_to_join_title', None)
    app.logger.info(f"[serve_hello_world_page] Valores obtenidos de sesión (después de pop): auto_join_race_id={auto_join_race_id_to_template}, race_to_join_title={race_to_join_title_to_template}")
    app.logger.info(f"[serve_hello_world_page] Sesión DESPUÉS de pop: {dict(session)}")

    # Keep existing filter and data fetching logic
    filter_date_from_str = request.args.get('filter_date_from')
    filter_date_to_str = request.args.get('filter_date_to')
    filter_race_format_id_str = request.args.get('filter_race_format_id')
    filter_status_str = request.args.get('filter_status') # Comma-separated e.g., "PLANNED,ACTIVE"

    all_race_formats = RaceFormat.query.order_by(RaceFormat.name).all()
    all_race_statuses = [status.value for status in RaceStatus] # For the filter UI

    selected_statuses_for_query = []
    if filter_status_str:
        selected_statuses_for_query = [status_val.strip().upper() for status_val in filter_status_str.split(',') if status_val.strip()]
        # Validate against RaceStatus enum
        selected_statuses_for_query = [RaceStatus[status_enum_key] for status_enum_key in selected_statuses_for_query if hasattr(RaceStatus, status_enum_key)]
    else:
        # Default to PLANNED and ACTIVE if no filter is provided
        selected_statuses_for_query = [RaceStatus.PLANNED, RaceStatus.ACTIVE]

    app.logger.info(f"Selected statuses for query: {selected_statuses_for_query}")

    date_from_obj = None
    date_to_obj = None
    race_format_id_int = None

    if filter_date_from_str:
        try:
            date_from_obj = datetime.strptime(filter_date_from_str, '%Y-%m-%d')
        except ValueError:
            app.logger.warning(f"Invalid 'from' date format received: {filter_date_from_str}") # Added logger
            pass

    if filter_date_to_str:
        try:
            parsed_date_to = datetime.strptime(filter_date_to_str, '%Y-%m-%d')
            # To include events on the 'to' date, set time to end of day
            date_to_obj = datetime.combine(parsed_date_to.date(), datetime.max.time())
        except ValueError:
            app.logger.warning(f"Invalid 'to' date format received: {filter_date_to_str}") # Added logger
            pass

    if filter_race_format_id_str and filter_race_format_id_str.strip():
        try:
            race_format_id_int = int(filter_race_format_id_str)
        except ValueError:
            app.logger.warning(f"Invalid 'race_format_id' format received: {filter_race_format_id_str}") # Added logger
            pass

    current_year = datetime.utcnow().year
    app.logger.info(f"Serving dashboard for user {current_user.username} with role {current_user.role.code}")

    all_races = [] # Initialize all_races

    # --- Race Status Update Logic ---
    # Fetch all PLANNED races that are not deleted
    races_to_check_status = Race.query.filter(
        Race.status == RaceStatus.PLANNED,
        Race.is_deleted == False
    ).all()

    updated_races_count = 0
    for race_to_update in races_to_check_status:
        if race_to_update.quiniela_close_date and race_to_update.quiniela_close_date < datetime.utcnow():
            race_to_update.status = RaceStatus.ACTIVE
            updated_races_count += 1
            app.logger.info(f"Race ID {race_to_update.id} status updated from PLANNED to ACTIVE.")

    if updated_races_count > 0:
        try:
            db.session.commit()
            app.logger.info(f"Committed status updates for {updated_races_count} races.")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error committing race status updates: {e}", exc_info=True)
    # --- End Race Status Update Logic ---

    # Role-based rendering
    if current_user.role.code == 'ADMIN':
        # Query for general races (for cards), ensuring they are not deleted
        query_general_races = Race.query.filter_by(is_general=True, is_deleted=False)
        if date_from_obj:
            query_general_races = query_general_races.filter(Race.event_date >= date_from_obj)
        if date_to_obj:
            query_general_races = query_general_races.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None:
            query_general_races = query_general_races.filter(Race.race_format_id == race_format_id_int)
        if selected_statuses_for_query:
            query_general_races = query_general_races.filter(Race.status.in_(selected_statuses_for_query))

        general_races_for_cards_query_result = []
        try:
            general_races_for_cards_query_result = query_general_races.order_by(Race.event_date.desc()).all()
        except Exception as e:
            app.logger.error(f"Error fetching general races for admin dashboard cards: {e}")

        general_races_for_cards_dicts = []
        for race in general_races_for_cards_query_result:
            race_dict = race.to_dict()
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'):
                        close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else:
                        close_date_obj = datetime.fromisoformat(qcd_str)
                    # Assuming quiniela_close_date is stored as naive UTC
                    if close_date_obj > datetime.utcnow():
                        is_quiniela_actionable = False
                except ValueError as ve:
                    app.logger.error(f"Error parsing quiniela_close_date '{race_dict['quiniela_close_date']}' for race {race.id}: {ve}")
                    is_quiniela_actionable = True # Defaulting to true if parsing fails
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            general_races_for_cards_dicts.append(race_dict)

        # Query for all non-deleted races (for official answers dropdown)
        # Status filter might not be desired for this dropdown, as admins might need to select any race.
        # However, applying it for consistency for now. This can be revisited.
        all_races_for_official_answers_query = Race.query.filter_by(is_deleted=False)
        # If specific statuses are needed for this dropdown, apply them. Otherwise, remove this filter.
        # For now, let's assume it should list ALL non-deleted races regardless of status for admin tasks.
        # if selected_statuses_for_query:
        #     all_races_for_official_answers_query = all_races_for_official_answers_query.filter(Race.status.in_(selected_statuses_for_query))
        all_races_for_official_answers_query_result = []
        try:
            all_races_for_official_answers_query_result = all_races_for_official_answers_query.order_by(Race.event_date.desc()).all()
        except Exception as e:
            app.logger.error(f"Error fetching all non-deleted races for admin official answers: {e}")
        all_races_for_official_answers = [race.to_dict() for race in all_races_for_official_answers_query_result]

        return render_template('admin_dashboard.html',
                               races=general_races_for_cards_dicts, # Use the new list with actionable flag
                               races_for_official_answers=all_races_for_official_answers, # All races for dropdown
                               all_race_formats=all_race_formats,
                               filter_date_from_str=filter_date_from_str,
                               filter_date_to_str=filter_date_to_str,
                               filter_race_format_id_str=filter_race_format_id_str,
                                all_race_statuses=all_race_statuses,
                                selected_statuses_for_ui=[s.value for s in selected_statuses_for_query],
                               current_year=current_year,
                               auto_join_race_id=auto_join_race_id_to_template, # Mantener estos nombres para la plantilla
                               race_to_join_title=race_to_join_title_to_template) # Mantener estos nombres para la plantilla
    elif current_user.role.code == 'LEAGUE_ADMIN':
        # --- Active Players KPI Calculation ---
        active_players_count = 0
        # Get all non-deleted races created by this league admin, ordered by event date descending
        admin_races = Race.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Race.event_date.desc()).all()

        # Determine the races to consider for active players
        if admin_races:
            races_for_kpi = admin_races[:3] # Last 3 races (or fewer if less than 3 exist)
            race_ids_for_kpi = [r.id for r in races_for_kpi]

            if race_ids_for_kpi:
                # Count unique players who submitted at least one UserAnswer in these races
                active_players_count = db.session.query(func.count(UserAnswer.user_id.distinct())) \
                    .filter(UserAnswer.race_id.in_(race_ids_for_kpi)) \
                    .scalar() or 0 # Ensure 0 if scalar() returns None
        # --- End of Active Players KPI Calculation ---

        # 1. Organized Races (created by this league admin, not general)
        # Re-fetch organized_races_result if admin_races was only for KPI or adapt existing logic
        # For simplicity, we'll use the admin_races already fetched if no filters are applied,
        # otherwise, we need to re-apply filters.
        # The original code re-queries with filters, so we stick to that for organized_races_dicts.
        organized_races_query_for_display = Race.query.filter_by(user_id=current_user.id, is_general=False, is_deleted=False)
        if date_from_obj: organized_races_query_for_display = organized_races_query_for_display.filter(Race.event_date >= date_from_obj)
        if date_to_obj: organized_races_query_for_display = organized_races_query_for_display.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None: organized_races_query_for_display = organized_races_query_for_display.filter(Race.race_format_id == race_format_id_int)
        if selected_statuses_for_query:
            organized_races_query_for_display = organized_races_query_for_display.filter(Race.status.in_(selected_statuses_for_query))
        organized_races_result_for_display = organized_races_query_for_display.order_by(Race.event_date.desc()).all()

        organized_races_dicts = []
        for race in organized_races_result_for_display: # Use the filtered list for display
            race_dict = race.to_dict()
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'): close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else: close_date_obj = datetime.fromisoformat(qcd_str)
                    if close_date_obj.tzinfo is None:
                        if close_date_obj > datetime.utcnow(): is_quiniela_actionable = False
                    else:
                        if close_date_obj.replace(tzinfo=None) > datetime.utcnow(): is_quiniela_actionable = False
                except ValueError as ve:
                    app.logger.error(f"Error parsing quiniela_close_date '{race_dict['quiniela_close_date']}' for organized race {race.id}: {ve}")
                    is_quiniela_actionable = True
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            organized_races_dicts.append(race_dict)

        # 2. Participating Races
        registrations = UserRaceRegistration.query.filter_by(user_id=current_user.id).all()
        participating_race_ids = [reg.race_id for reg in registrations]
        participating_races_result = []
        if participating_race_ids:
            participating_races_query = Race.query.filter(Race.id.in_(participating_race_ids), Race.is_deleted==False)
            if date_from_obj: participating_races_query = participating_races_query.filter(Race.event_date >= date_from_obj)
            if date_to_obj: participating_races_query = participating_races_query.filter(Race.event_date <= date_to_obj)
            if race_format_id_int is not None: participating_races_query = participating_races_query.filter(Race.race_format_id == race_format_id_int)
            if selected_statuses_for_query:
                participating_races_query = participating_races_query.filter(Race.status.in_(selected_statuses_for_query))
            participating_races_result = participating_races_query.order_by(Race.event_date.desc()).all()

        participating_races_dicts = []
        for race in participating_races_result:
            race_dict = race.to_dict()
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'): close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else: close_date_obj = datetime.fromisoformat(qcd_str)
                    if close_date_obj.tzinfo is None:
                        if close_date_obj > datetime.utcnow(): is_quiniela_actionable = False
                    else:
                        if close_date_obj.replace(tzinfo=None) > datetime.utcnow(): is_quiniela_actionable = False
                except ValueError: is_quiniela_actionable = True
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            participating_races_dicts.append(race_dict)

        # 3. Favorite Races
        favorites = UserFavoriteRace.query.filter_by(user_id=current_user.id).all()
        favorite_race_ids = [fav.race_id for fav in favorites]
        favorite_races_result = []
        if favorite_race_ids:
            favorite_races_query = Race.query.filter(Race.id.in_(favorite_race_ids), Race.is_deleted==False)
            if date_from_obj: favorite_races_query = favorite_races_query.filter(Race.event_date >= date_from_obj)
            if date_to_obj: favorite_races_query = favorite_races_query.filter(Race.event_date <= date_to_obj)
            if race_format_id_int is not None: favorite_races_query = favorite_races_query.filter(Race.race_format_id == race_format_id_int)
            if selected_statuses_for_query:
                favorite_races_query = favorite_races_query.filter(Race.status.in_(selected_statuses_for_query))
            favorite_races_result = favorite_races_query.order_by(Race.event_date.desc()).all()

        favorite_races_dicts = []
        for race in favorite_races_result:
            race_dict = race.to_dict()
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'): close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else: close_date_obj = datetime.fromisoformat(qcd_str)
                    if close_date_obj.tzinfo is None:
                        if close_date_obj > datetime.utcnow(): is_quiniela_actionable = False
                    else:
                        if close_date_obj.replace(tzinfo=None) > datetime.utcnow(): is_quiniela_actionable = False
                except ValueError: is_quiniela_actionable = True
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            favorite_races_dicts.append(race_dict)

        return render_template('admin_dashboard.html',
                               organized_races=organized_races_dicts,
                               participating_races=participating_races_dicts,
                               favorite_races=favorite_races_dicts,
                               races_for_official_answers=organized_races_dicts,
                               all_race_formats=all_race_formats,
                               filter_date_from_str=filter_date_from_str,
                               filter_date_to_str=filter_date_to_str,
                               filter_race_format_id_str=filter_race_format_id_str,
                                all_race_statuses=all_race_statuses,
                                selected_statuses_for_ui=[s.value for s in selected_statuses_for_query],
                               current_year=current_year,
                               active_players_count=active_players_count, # Pass the count to the template
                                auto_join_race_id=auto_join_race_id_to_template, # Mantener estos nombres para la plantilla
                                race_to_join_title=race_to_join_title_to_template) # Mantener estos nombres para la plantilla
    elif current_user.role.code == 'PLAYER':
        # Query UserRaceRegistration for all race_ids for the current_user
        user_registrations = UserRaceRegistration.query.filter_by(user_id=current_user.id).all()
        registered_race_ids = [reg.race_id for reg in user_registrations]

        # Query Race model for these race_ids, ensuring they are not deleted
        query = Race.query.filter(Race.id.in_(registered_race_ids), Race.is_deleted==False)

        # Apply existing filters
        if date_from_obj:
            query = query.filter(Race.event_date >= date_from_obj)
        if date_to_obj:
            query = query.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None:
            query = query.filter(Race.race_format_id == race_format_id_int)
        if selected_statuses_for_query:
            query = query.filter(Race.status.in_(selected_statuses_for_query))

        registered_races_query_result = []
        try:
            registered_races_query_result = query.order_by(Race.event_date.desc()).all()
        except Exception as e:
            app.logger.error(f"Error fetching registered races for player {current_user.id}: {e}")

        registered_races_dicts = []
        for race in registered_races_query_result:
            race_dict = race.to_dict()
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'):
                        close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else:
                        close_date_obj = datetime.fromisoformat(qcd_str)
                    if close_date_obj > datetime.utcnow():
                        is_quiniela_actionable = False
                except ValueError as ve:
                    app.logger.error(f"Error parsing quiniela_close_date '{race_dict['quiniela_close_date']}' for race {race.id}: {ve}")
                    is_quiniela_actionable = True
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            registered_races_dicts.append(race_dict)

        # Fetch Favorite Races for Player
        favorites = UserFavoriteRace.query.filter_by(user_id=current_user.id).all()
        favorite_race_ids = [fav.race_id for fav in favorites]
        favorite_races_query_result = []
        if favorite_race_ids:
            query_fav_races = Race.query.filter(Race.id.in_(favorite_race_ids), Race.is_deleted==False)
            # Apply same filters to favorite races if needed, or decide to show all favorites regardless of filters
            if date_from_obj: query_fav_races = query_fav_races.filter(Race.event_date >= date_from_obj)
            if date_to_obj: query_fav_races = query_fav_races.filter(Race.event_date <= date_to_obj)
            if race_format_id_int is not None: query_fav_races = query_fav_races.filter(Race.race_format_id == race_format_id_int)
            if selected_statuses_for_query:
                query_fav_races = query_fav_races.filter(Race.status.in_(selected_statuses_for_query))

            try:
                favorite_races_query_result = query_fav_races.order_by(Race.event_date.desc()).all()
            except Exception as e:
                app.logger.error(f"Error fetching favorite races for player {current_user.id}: {e}")

        favorite_races_dicts = []
        for race in favorite_races_query_result:
            race_dict = race.to_dict()
            # is_quiniela_actionable logic can be copied if needed for favorite cards too
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'): close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else: close_date_obj = datetime.fromisoformat(qcd_str)
                    if close_date_obj > datetime.utcnow(): is_quiniela_actionable = False
                except ValueError as ve:
                    app.logger.error(f"Error parsing quiniela_close_date '{race_dict['quiniela_close_date']}' for fav race {race.id}: {ve}")
                    is_quiniela_actionable = True
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            favorite_races_dicts.append(race_dict)

        # Fetch "Carreras Destacadas" - these are general, non-deleted races not necessarily linked to the user
        # This logic is similar to the 'else' block's fallback, but specifically for the PLAYER role
        query_destacadas = Race.query.filter_by(is_general=True, is_deleted=False)
        if date_from_obj: query_destacadas = query_destacadas.filter(Race.event_date >= date_from_obj)
        if date_to_obj: query_destacadas = query_destacadas.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None: query_destacadas = query_destacadas.filter(Race.race_format_id == race_format_id_int)
        if selected_statuses_for_query:
            query_destacadas = query_destacadas.filter(Race.status.in_(selected_statuses_for_query))

        destacadas_races_query_result = []
        try:
            destacadas_races_query_result = query_destacadas.order_by(Race.event_date.desc()).limit(6).all() # Example: Limit to 6
        except Exception as e:
            app.logger.error(f"Error fetching destacadas races for player {current_user.id}: {e}")

        destacadas_races_dicts = []
        for race in destacadas_races_query_result:
            race_dict = race.to_dict()
            # is_quiniela_actionable logic can be copied if needed
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'): close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else: close_date_obj = datetime.fromisoformat(qcd_str)
                    if close_date_obj > datetime.utcnow(): is_quiniela_actionable = False
                except ValueError as ve:
                    app.logger.error(f"Error parsing quiniela_close_date '{race_dict['quiniela_close_date']}' for destacada race {race.id}: {ve}")
                    is_quiniela_actionable = True
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            destacadas_races_dicts.append(race_dict)

        return render_template('player.html',
                               registered_races=registered_races_dicts,
                               favorite_races=favorite_races_dicts, # Pass favorite races
                               races=destacadas_races_dicts, # Pass destacadas races as 'races' for the existing section
                               all_race_formats=all_race_formats,
                               filter_date_from_str=filter_date_from_str,
                               filter_date_to_str=filter_date_to_str,
                               filter_race_format_id_str=filter_race_format_id_str,
                                all_race_statuses=all_race_statuses,
                                selected_statuses_for_ui=[s.value for s in selected_statuses_for_query],
                               current_year=current_year,
                                auto_join_race_id=auto_join_race_id_to_template, # Mantener estos nombres para la plantilla
                                race_to_join_title=race_to_join_title_to_template) # Mantener estos nombres para la plantilla

    else:
        # Fallback for any other authenticated role, or if roles are added in the future
        # Defaulting to player view (general, non-deleted races) - This part remains unchanged
        app.logger.warning(f"User {current_user.username} with unhandled role {current_user.role.code} accessing dashboard. Defaulting to player view (general races).")
        query = Race.query.filter_by(is_general=True, is_deleted=False)
        if date_from_obj:
            query = query.filter(Race.event_date >= date_from_obj)
        if date_to_obj:
            query = query.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None:
            query = query.filter(Race.race_format_id == race_format_id_int)
        if selected_statuses_for_query:
            query = query.filter(Race.status.in_(selected_statuses_for_query))
        all_races_query_result = []
        try:
            all_races_query_result = query.order_by(Race.event_date.desc()).all() # Keep variable name all_races for consistency in this block
        except Exception as e:
            app.logger.error(f"Error fetching general races for fallback/unhandled role: {e}")

        all_races_dicts_fallback = []
        for race_obj in all_races_query_result: # Renamed to avoid conflict with outer all_races
            race_dict = race_obj.to_dict()
            is_quiniela_actionable = True
            if race_dict.get('quiniela_close_date'):
                try:
                    qcd_str = race_dict['quiniela_close_date']
                    if qcd_str.endswith('Z'):
                        close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                    else:
                        close_date_obj = datetime.fromisoformat(qcd_str)
                    if close_date_obj > datetime.utcnow():
                        is_quiniela_actionable = False
                except ValueError as ve:
                    app.logger.error(f"Error parsing quiniela_close_date '{race_dict['quiniela_close_date']}' for race {race_obj.id}: {ve}")
                    is_quiniela_actionable = True
            race_dict['is_quiniela_actionable'] = is_quiniela_actionable
            all_races_dicts_fallback.append(race_dict)

        return render_template('player.html',
                               races=all_races_dicts_fallback, # Use new list
                               all_race_formats=all_race_formats,
                               filter_date_from_str=filter_date_from_str,
                               filter_date_to_str=filter_date_to_str,
                               filter_race_format_id_str=filter_race_format_id_str,
                                all_race_statuses=all_race_statuses, # Pass all possible statuses
                                selected_statuses_for_ui=[s.value for s in selected_statuses_for_query], # Pass selected status values for UI
                                current_year=current_year,
                                auto_join_race_id=auto_join_race_id_to_template, # Mantener estos nombres para la plantilla
                                race_to_join_title=race_to_join_title_to_template) # Mantener estos nombres para la plantilla


@app.route('/races', methods=['GET'])
@login_required
def serve_races_list_page():
    filter_date_from_str = request.args.get('filter_date_from')
    filter_date_to_str = request.args.get('filter_date_to')
    filter_race_format_id_str = request.args.get('filter_race_format_id')

    all_race_formats = RaceFormat.query.order_by(RaceFormat.name).all()

    date_from_obj = None
    date_to_obj = None
    race_format_id_int = None

    if filter_date_from_str:
        try:
            date_from_obj = datetime.strptime(filter_date_from_str, '%Y-%m-%d')
        except ValueError:
            app.logger.warning(f"Invalid 'from' date format received for /races: {filter_date_from_str}")
            pass

    if filter_date_to_str:
        try:
            parsed_date_to = datetime.strptime(filter_date_to_str, '%Y-%m-%d')
            date_to_obj = datetime.combine(parsed_date_to.date(), datetime.max.time())
        except ValueError:
            app.logger.warning(f"Invalid 'to' date format received for /races: {filter_date_to_str}")
            pass

    if filter_race_format_id_str and filter_race_format_id_str.strip():
        try:
            race_format_id_int = int(filter_race_format_id_str)
        except ValueError:
            app.logger.warning(f"Invalid 'race_format_id' format received for /races: {filter_race_format_id_str}")
            pass

    # Query all public, non-deleted races
    query = Race.query.filter_by(is_general=True, is_deleted=False)

    if date_from_obj:
        query = query.filter(Race.event_date >= date_from_obj)
    if date_to_obj:
        query = query.filter(Race.event_date <= date_to_obj)
    if race_format_id_int is not None:
        query = query.filter(Race.race_format_id == race_format_id_int)

    races_query_result = []
    try:
        races_query_result = query.order_by(Race.event_date.desc()).all()
    except Exception as e:
        app.logger.error(f"Error fetching public races for /races page: {e}")

    processed_races = []
    for race in races_query_result:
        race_dict = race.to_dict()
        is_quiniela_actionable = True
        if race_dict.get('quiniela_close_date'):
            try:
                qcd_str = race_dict['quiniela_close_date']
                if qcd_str.endswith('Z'):
                    close_date_obj = datetime.fromisoformat(qcd_str.replace('Z', '+00:00'))
                else:
                    close_date_obj = datetime.fromisoformat(qcd_str)

                if close_date_obj.tzinfo is None:
                    if close_date_obj > datetime.utcnow():
                        is_quiniela_actionable = False
                else:
                    # This part might need `from datetime import timezone`
                    # For now, assuming quiniela_close_date is stored as naive UTC based on existing patterns
                    # If it's truly offset-aware, then `datetime.now(timezone.utc)` would be needed.
                    # Sticking to `datetime.utcnow()` for naive comparison as per existing code.
                    if close_date_obj.replace(tzinfo=None) > datetime.utcnow(): # Convert to naive for comparison
                        is_quiniela_actionable = False
            except ValueError as ve:
                app.logger.error(f"Error parsing quiniela_close_date '{race_dict['quiniela_close_date']}' for race {race.id} on /races: {ve}")
                is_quiniela_actionable = True
        race_dict['is_quiniela_actionable'] = is_quiniela_actionable
        processed_races.append(race_dict)

    current_year = datetime.utcnow().year

    return render_template('races_list.html',
                           races=processed_races,
                           all_race_formats=all_race_formats,
                           filter_date_from_str=filter_date_from_str,
                           filter_date_to_str=filter_date_to_str,
                           filter_race_format_id_str=filter_race_format_id_str,
                           current_year=current_year)

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
    race = Race.query.filter_by(id=race_id, is_deleted=False).first_or_404()
    current_year = datetime.utcnow().year
    current_time_utc = datetime.utcnow() # Get current UTC time

    user_role_code = 'GUEST' # Default role if not authenticated or no role
    is_user_registered_for_race = False # Default to false
    has_user_answered_pool = False # Initialize default for the new variable
    is_favorite = False # Initialize favorite status
    num_total_questions_pool = 0 # Initialize
    num_answered_questions_pool = 0 # Initialize

    if current_user and current_user.is_authenticated:
        user_role_code = current_user.role.code
        # Check if the current user is registered for this race
        registration = UserRaceRegistration.query.filter_by(user_id=current_user.id, race_id=race_id).first()
        if registration:
            is_user_registered_for_race = True

        # Check if the user has answered any questions for this race pool
        user_answers_list = UserAnswer.query.filter_by(user_id=current_user.id, race_id=race_id).all()
        if user_answers_list: # Check if the list is not empty
            has_user_answered_pool = True
            num_answered_questions_pool = len(user_answers_list)

        # Get total number of active questions for this race's pool
        num_total_questions_pool = Question.query.filter_by(race_id=race_id, is_active=True).count()


        # Check if this race is a favorite for the current user
        if UserFavoriteRace.query.filter_by(user_id=current_user.id, race_id=race.id).first():
            is_favorite = True
    else:
        # Ensure current_user.is_authenticated is False if current_user is None or not authenticated
        # This handles cases where current_user might be an AnonymousUserMixin without a 'role'
        pass

    # Determine quiniela actionability for the single race object
    is_quiniela_actionable_detail = True # Default to True
    if race.quiniela_close_date:
        # race.quiniela_close_date is a datetime object (naive UTC assumed as per model setup)
        # datetime.utcnow() is also naive UTC
        if race.quiniela_close_date > datetime.utcnow():
            is_quiniela_actionable_detail = False
    # No else needed, default is True if quiniela_close_date is None or in the past

    return render_template('race_detail.html',
                           race=race,
                           current_year=current_year,
                           currentUserRole=user_role_code,
                           is_user_registered_for_race=is_user_registered_for_race,
                           has_user_answered_pool=has_user_answered_pool,
                           num_total_questions_pool=num_total_questions_pool, # Add this
                           num_answered_questions_pool=num_answered_questions_pool, # Add this
                           is_quiniela_actionable=is_quiniela_actionable_detail,
                           is_favorite=is_favorite, # Add this new variable
                           current_time_utc=current_time_utc) # Pass current_time_utc to template

# --- API Endpoint for Saving User Answers ---
@app.route('/api/races/<int:race_id>/answers', methods=['POST'])
@login_required
def save_user_answers(race_id):
    app.logger.info(f"User {current_user.id} attempting to save answers for race {race_id}")

    # 1. Permissions Check: Fetch Race, ensuring it's not deleted
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        app.logger.warning(f"Attempt to save answers for non-existent or deleted race {race_id} by user {current_user.id}")
        return jsonify(message="Race not found or has been deleted"), 404

    # Check quiniela close date
    if race.quiniela_close_date and race.quiniela_close_date < datetime.utcnow():
        app.logger.warning(f"Attempt to save answers for closed quiniela race {race_id} by user {current_user.id}")
        return jsonify(message="La quiniela ya esta cerrada y no se pueden añadir nuevas predicciones"), 403

    # 2. Permissions Check: User Registration for this Race
    registration = UserRaceRegistration.query.filter_by(user_id=current_user.id, race_id=race_id).first()

    # Auto-register LEAGUE_ADMIN if they are not already registered
    if current_user.role.code == 'LEAGUE_ADMIN' and not registration:
        app.logger.info(f"LEAGUE_ADMIN {current_user.id} is not registered for race {race_id}. Auto-registering.")
        try:
            new_registration = UserRaceRegistration(user_id=current_user.id, race_id=race.id)
            db.session.add(new_registration)
            # The main db.session.commit() at the end of the function will handle saving this.
            registration = new_registration # Update the local 'registration' variable for the check below
        except IntegrityError: # Should not happen if 'not registration' check is correct, but as safeguard
            db.session.rollback()
            app.logger.error(f"IntegrityError during auto-registration of LEAGUE_ADMIN {current_user.id} for race {race_id}.")
            return jsonify(message="Error during auto-registration process."), 500

    # Now, perform the standard registration check
    if not registration:
        app.logger.warning(f"User {current_user.id} not registered for race {race_id}, cannot save answers.")
        # For non-LEAGUE_ADMINs, or if LEAGUE_ADMIN auto-registration failed unexpectedly.
        return jsonify(message="User not registered for this race"), 403

    # 3. Data Reception
    answers_payload = request.get_json()
    if not answers_payload:
        app.logger.warning(f"No payload received for saving answers for race {race_id} by user {current_user.id}")
        return jsonify(message="No data provided"), 400

    app.logger.debug(f"Received answers payload for race {race_id} from user {current_user.id}: {answers_payload}")

    try:
        # 4. Processing Answers
        for question_id_str, answer_data in answers_payload.items():
            try:
                question_id = int(question_id_str)
            except ValueError:
                app.logger.warning(f"Invalid question_id format '{question_id_str}' in payload for race {race_id}.")
                # Decide: skip this answer or fail the whole request? For now, skip.
                continue

            question = Question.query.get(question_id)
            if not question:
                app.logger.warning(f"Question with id {question_id} not found while saving answers for race {race_id}.")
                # Decide: skip or fail? For now, skip.
                continue

            # Check if the question belongs to the given race_id to prevent misuse
            if question.race_id != race_id:
                app.logger.warning(f"Question {question_id} does not belong to race {race_id}. User {current_user.id} attempting to answer.")
                continue


            # Fetch and delete existing answer and its MC options to ensure clean state and proper cascade
            existing_answer = UserAnswer.query.filter_by(user_id=current_user.id, question_id=question.id).first()
            if existing_answer:
                # Explicitly delete related UserAnswerMultipleChoiceOption records
                # This is belt-and-suspenders; cascade="all, delete-orphan" should handle it,
                # but direct deletion ensures it if there are any session synchronization issues.
                UserAnswerMultipleChoiceOption.query.filter_by(user_answer_id=existing_answer.id).delete()
                db.session.delete(existing_answer)
                db.session.flush() # Ensure deletion is processed before adding new answer

            new_user_answer = UserAnswer(
                user_id=current_user.id,
                race_id=race_id, # or race.id
                question_id=question.id
            )

            question_type_name = question.question_type.name
            app.logger.info(f"Processing answer for question {question.id} (type: {question_type_name})")


            if question_type_name == 'FREE_TEXT':
                new_user_answer.answer_text = answer_data.get('answer_text')
                if new_user_answer.answer_text is None: # Explicitly check for None if empty string is valid
                    app.logger.debug(f"No answer_text provided for FREE_TEXT question {question.id}")

            elif question_type_name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    selected_ids = answer_data.get('selected_option_ids', [])
                    if not isinstance(selected_ids, list): # Basic validation
                        app.logger.warning(f"selected_option_ids for Q {question.id} is not a list: {selected_ids}")
                        selected_ids = [] # Default to empty list to avoid iteration error

                    app.logger.debug(f"MC Multiple for Q {question.id}: selected_ids = {selected_ids}")
                    for opt_id in selected_ids:
                        # Optional: Validate if opt_id actually belongs to this question
                        option_exists = QuestionOption.query.filter_by(id=opt_id, question_id=question.id).first()
                        if option_exists:
                            mc_option = UserAnswerMultipleChoiceOption(question_option_id=opt_id)
                            new_user_answer.selected_mc_options.append(mc_option)
                        else:
                            app.logger.warning(f"Invalid option_id {opt_id} for question {question.id} submitted by user {current_user.id}")
                else: # Single correct
                    selected_id = answer_data.get('selected_option_id')
                    app.logger.debug(f"MC Single for Q {question.id}: selected_option_id = {selected_id}")
                    if selected_id is not None:
                        # Optional: Validate if selected_id actually belongs to this question
                        option_exists = QuestionOption.query.filter_by(id=selected_id, question_id=question.id).first()
                        if option_exists:
                            new_user_answer.selected_option_id = selected_id
                        else:
                            app.logger.warning(f"Invalid selected_option_id {selected_id} for question {question.id} submitted by user {current_user.id}")
                            new_user_answer.selected_option_id = None # Or skip setting it
                    else: # No option selected
                        new_user_answer.selected_option_id = None


            elif question_type_name == 'ORDERING':
                # Currently, frontend sends ordered_options_text
                new_user_answer.answer_text = answer_data.get('ordered_options_text')
                if new_user_answer.answer_text is None:
                     app.logger.debug(f"No ordered_options_text provided for ORDERING question {question.id}")

            elif question_type_name == 'SLIDER':
                slider_value = answer_data.get('slider_answer_value')
                if slider_value is not None:
                    try:
                        new_user_answer.slider_answer_value = float(slider_value)
                        # Ensure other fields are None for slider questions
                        new_user_answer.answer_text = None
                        new_user_answer.selected_option_id = None
                        # No UserAnswerMultipleChoiceOption for slider type
                    except (ValueError, TypeError):
                        app.logger.warning(f"Invalid slider_answer_value '{slider_value}' for SLIDER question {question.id}. Storing as None.")
                        new_user_answer.slider_answer_value = None
                else:
                    app.logger.debug(f"No slider_answer_value provided for SLIDER question {question.id}")
                    new_user_answer.slider_answer_value = None # Explicitly set to None if not provided or invalid

            else:
                app.logger.warning(f"Unsupported question type '{question_type_name}' encountered for question {question.id}")
                # Skip adding this answer if type is unknown or unhandled by this logic
                continue

            db.session.add(new_user_answer)
            app.logger.info(f"UserAnswer prepared for question {question.id} by user {current_user.id}")


        # 5. Commit and Respond
        db.session.commit()
        app.logger.info(f"Answers successfully saved for race {race_id} by user {current_user.id}")
        return jsonify(message="Answers saved successfully"), 201 # 201 Created (or 200 OK if updating)

    except IntegrityError as ie:
        db.session.rollback()
        app.logger.error(f"IntegrityError saving answers for race {race_id}, user {current_user.id}: {ie}", exc_info=True)
        return jsonify(message="Database integrity error while saving answers."), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception saving answers for race {race_id}, user {current_user.id}: {e}", exc_info=True)
        return jsonify(message="An error occurred while saving answers."), 500

@app.route('/api/races/<int:race_id>/user_answers', methods=['GET'])
@login_required
def get_user_answers(race_id):
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    user_answers = UserAnswer.query.filter_by(user_id=current_user.id, race_id=race_id).all()
    num_total_questions_pool = Question.query.filter_by(race_id=race_id, is_active=True).count()
    num_answered_questions_pool = len(user_answers)

    if not user_answers:
        # It's important to return an empty list if no answers, not a 404 or error
        return jsonify({
            "answers": [],
            "num_total_questions": num_total_questions_pool,
            "num_answered_questions": num_answered_questions_pool
        }), 200

    processed_answers_list = []
    for ua in user_answers:
        question = ua.question
        if not question:
            app.logger.error(f"UserAnswer {ua.id} has no associated question. Skipping.")
            continue

        all_q_options_list = []
        # Fetch all options for context, especially for MC and Ordering
        if question.question_type.name == "MULTIPLE_CHOICE" or question.question_type.name == "ORDERING":
            all_q_options = QuestionOption.query.filter_by(question_id=question.id).order_by(QuestionOption.id).all()
            all_q_options_list = [{"id": opt.id, "option_text": opt.option_text, "correct_order_index": opt.correct_order_index if question.question_type.name == "ORDERING" else None} for opt in all_q_options]


        answer_data = {
            "question_id": question.id,
            "question_text": question.text,
            "question_type": question.question_type.name,
            "user_answer_id": ua.id,
            "answer_text": ua.answer_text,
            "selected_option_id": ua.selected_option_id,
            "slider_answer_value": ua.slider_answer_value, # Added slider answer value
            "selected_option_text": None, # Initialize
            "selected_mc_options": [], # Initialize
            "all_question_options": all_q_options_list
        }

        if question.question_type.name == "MULTIPLE_CHOICE":
            if not question.is_mc_multiple_correct and ua.selected_option_id:
                # Single-choice MC: get the text of the selected option
                selected_option = QuestionOption.query.get(ua.selected_option_id)
                if selected_option:
                    answer_data["selected_option_text"] = selected_option.option_text
            elif question.is_mc_multiple_correct:
                # Multiple-choice MC: get text for all selected options
                selected_mc_options_list = []
                for mc_opt_assoc in ua.selected_mc_options: # This is UserAnswerMultipleChoiceOption
                    option = QuestionOption.query.get(mc_opt_assoc.question_option_id)
                    if option:
                        selected_mc_options_list.append({
                            "option_id": option.id,
                            "option_text": option.option_text
                        })
                answer_data["selected_mc_options"] = selected_mc_options_list

        # For ORDERING, the user's raw answer (sequence of texts) is already in ua.answer_text.
        # all_question_options provides the list of original items that were ordered.

        processed_answers_list.append(answer_data)

    return jsonify({
        "answers": processed_answers_list,
        "num_total_questions": num_total_questions_pool,
        "num_answered_questions": num_answered_questions_pool
    }), 200

@app.route('/api/user_answers/<int:user_answer_id>', methods=['PUT'])
@login_required
def update_user_answer(user_answer_id):
    try:
        user_answer = UserAnswer.query.get(user_answer_id)
        if not user_answer:
            return jsonify(message="Answer not found"), 404

        if user_answer.user_id != current_user.id:
            # Also check if the current user is an admin/league_admin of the race?
            # For now, only the user who owns the answer can modify it.
            return jsonify(message="Forbidden: You cannot modify this answer"), 403

        race = Race.query.filter_by(id=user_answer.race_id, is_deleted=False).first()
        if not race:
            app.logger.error(f"Race not found or deleted for UserAnswer {user_answer_id}.")
            return jsonify(message="Internal server error: Race context not found or deleted for the answer."), 500

        if race.quiniela_close_date and race.quiniela_close_date < datetime.utcnow():
            app.logger.warning(f"Attempt to update answer for closed quiniela race {race.id} by user {current_user.id}")
            return jsonify(message="La quiniela ya esta cerrada y no se pueden modificar las predicciones"), 403

        data = request.get_json()
        if not data:
            return jsonify(message="Invalid input: No data provided"), 400

        question = user_answer.question
        if not question:
            app.logger.error(f"UserAnswer {user_answer_id} is orphaned or its question was deleted.")
            return jsonify(message="Internal error: Question associated with this answer not found."), 500

        question_type_name = question.question_type.name
        app.logger.info(f"Attempting to update UserAnswer ID: {user_answer_id} for Question ID: {question.id} (Type: {question_type_name}) by User ID: {current_user.id}")


        if question_type_name == 'FREE_TEXT':
            new_answer_text = data.get('answer_text')
            if new_answer_text is None:
                app.logger.warning(f"Missing 'answer_text' in payload for UserAnswer {user_answer_id} (FREE_TEXT)")
                return jsonify(message="Missing 'answer_text' for FREE_TEXT question"), 400
            user_answer.answer_text = new_answer_text
            user_answer.selected_option_id = None
            UserAnswerMultipleChoiceOption.query.filter_by(user_answer_id=user_answer.id).delete()
            app.logger.info(f"Updated FREE_TEXT for UserAnswer {user_answer_id} to: '{new_answer_text[:50]}...'")

        elif question_type_name == 'ORDERING':
            new_ordered_text = data.get('ordered_options_text') # Matching JS
            if new_ordered_text is None:
                app.logger.warning(f"Missing 'ordered_options_text' in payload for UserAnswer {user_answer_id} (ORDERING)")
                return jsonify(message="Missing 'ordered_options_text' for ORDERING question"), 400
            user_answer.answer_text = new_ordered_text
            user_answer.selected_option_id = None
            UserAnswerMultipleChoiceOption.query.filter_by(user_answer_id=user_answer.id).delete()
            app.logger.info(f"Updated ORDERING for UserAnswer {user_answer_id} to: '{new_ordered_text[:50]}...'")

        elif question_type_name == 'MULTIPLE_CHOICE':
            user_answer.answer_text = None
            if question.is_mc_multiple_correct: # Multi-select
                new_selected_option_ids = data.get('selected_option_ids')
                if not isinstance(new_selected_option_ids, list):
                    app.logger.warning(f"Invalid 'selected_option_ids' (not a list) for UserAnswer {user_answer_id} (MC Multi)")
                    return jsonify(message="Invalid 'selected_option_ids': must be a list for multi-select MC question"), 400

                UserAnswerMultipleChoiceOption.query.filter_by(user_answer_id=user_answer.id).delete()
                valid_option_ids_for_question = {opt.id for opt in question.options}
                for opt_id in new_selected_option_ids:
                    if opt_id not in valid_option_ids_for_question:
                        db.session.rollback()
                        app.logger.error(f"Invalid opt_id {opt_id} for multi-select MC UserAnswer {user_answer_id}, Question {question.id}")
                        return jsonify(message=f"Invalid option_id {opt_id} provided."), 400
                    db.session.add(UserAnswerMultipleChoiceOption(user_answer_id=user_answer.id, question_option_id=opt_id))
                user_answer.selected_option_id = None
                app.logger.info(f"Updated MC Multi for UserAnswer {user_answer_id} with options: {new_selected_option_ids}")

            else: # Single-select
                if 'selected_option_id' not in data:
                     app.logger.warning(f"Missing 'selected_option_id' in payload for UserAnswer {user_answer_id} (MC Single)")
                     return jsonify(message="Missing 'selected_option_id' for single-choice MC question"), 400

                new_selected_option_id = data.get('selected_option_id')

                if new_selected_option_id is not None:
                    if not isinstance(new_selected_option_id, int):
                        app.logger.warning(f"Invalid 'selected_option_id' (not int/null) for UserAnswer {user_answer_id} (MC Single)")
                        return jsonify(message="Invalid 'selected_option_id': must be an integer or null"), 400

                    valid_option = QuestionOption.query.filter_by(id=new_selected_option_id, question_id=question.id).first()
                    if not valid_option:
                        app.logger.error(f"Invalid option_id {new_selected_option_id} for single-select MC UserAnswer {user_answer_id}, Question {question.id}")
                        return jsonify(message=f"Invalid option_id {new_selected_option_id} for question {question.id}"), 400

                user_answer.selected_option_id = new_selected_option_id
                UserAnswerMultipleChoiceOption.query.filter_by(user_answer_id=user_answer.id).delete()
                app.logger.info(f"Updated MC Single for UserAnswer {user_answer_id} to option_id: {new_selected_option_id}")

        elif question_type_name == 'SLIDER':
            new_slider_value = data.get('slider_answer_value')
            if new_slider_value is None: # Explicitly allow null to clear the answer
                user_answer.slider_answer_value = None
            else:
                try:
                    user_answer.slider_answer_value = float(new_slider_value)
                except (ValueError, TypeError):
                    app.logger.warning(f"Invalid 'slider_answer_value' format for UserAnswer {user_answer_id} (SLIDER)")
                    return jsonify(message="Invalid 'slider_answer_value': must be a number or null."), 400

            # Clear other answer type fields
            user_answer.answer_text = None
            user_answer.selected_option_id = None
            UserAnswerMultipleChoiceOption.query.filter_by(user_answer_id=user_answer.id).delete()
            app.logger.info(f"Updated SLIDER for UserAnswer {user_answer_id} to value: {user_answer.slider_answer_value}")

        else:
            app.logger.error(f"Unsupported question type '{question_type_name}' for update on UserAnswer {user_answer_id}")
            return jsonify(message=f"Unsupported question type for update: {question_type_name}"), 400

        db.session.commit()
        app.logger.info(f"UserAnswer {user_answer_id} updated successfully by User {current_user.id}")
        return jsonify(message="Answer updated successfully", userAnswerId=user_answer.id), 200 # Matched key from spec

    except IntegrityError as e:
        db.session.rollback()
        app.logger.error(f"IntegrityError updating UserAnswer {user_answer_id}: {e}", exc_info=True)
        return jsonify(message="Database integrity error during update."), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception updating UserAnswer {user_answer_id}: {e}", exc_info=True)
        return jsonify(message="An error occurred while updating the answer."), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

@app.route('/api/races/<int:race_id>/quiniela_leaderboard', methods=['GET'])
@login_required
def get_quiniela_leaderboard(race_id):
    app.logger.info(f"Fetching quiniela leaderboard for race_id: {race_id} by user {current_user.username}")

    # 1. Check if the race exists and is not deleted
    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        app.logger.warning(f"Quiniela leaderboard request for non-existent or deleted race {race_id}")
        return jsonify(message="Race not found or has been deleted"), 404

    # 2. Query UserScore, join with User, filter by race_id, and order by score
    try:
        leaderboard_data = db.session.query(
            UserScore.user_id,
            User.username,
            UserScore.score
        ).join(User, UserScore.user_id == User.id)\
         .filter(UserScore.race_id == race_id)\
         .order_by(UserScore.score.desc())\
         .all()

        # 3. Format the results into a list of dictionaries
        leaderboard_list = [
            {"user_id": item.user_id, "username": item.username, "score": item.score}
            for item in leaderboard_data
        ]

        app.logger.info(f"Successfully fetched quiniela leaderboard for race_id: {race_id}, found {len(leaderboard_list)} entries.")
        return jsonify(leaderboard_list), 200

    except Exception as e:
        db.session.rollback() # Rollback in case of query errors or other exceptions
        app.logger.error(f"Error fetching quiniela leaderboard for race_id {race_id}: {e}", exc_info=True)
        return jsonify(message="Error fetching quiniela leaderboard"), 500

# --- Scoring Algorithm ---
def calculate_and_store_scores(race_id):
    app.logger.info(f"Starting score calculation for race_id: {race_id}")
    try:
        race = Race.query.filter_by(id=race_id, is_deleted=False).first()
        if not race:
            app.logger.error(f"Scoring calculation: Race with id {race_id} not found or has been deleted.")
            return {"success": False, "message": "Race not found or has been deleted"}

        questions = Question.query.filter_by(race_id=race.id).all()
        if not questions:
            app.logger.info(f"Scoring calculation: No questions found for race_id: {race_id}. No scores to calculate.")
            return {"success": True, "message": "No questions found for race, no scores calculated."}

        official_answers_list = OfficialAnswer.query.filter_by(race_id=race.id).all()
        official_answers_map = {oa.question_id: oa for oa in official_answers_list}

        # Pre-process official MC-multiple answers
        official_mc_multiple_options_map = {}
        for oa in official_answers_list:
            question = Question.query.get(oa.question_id) # Get question to check type
            if question and question.question_type.name == 'MULTIPLE_CHOICE' and question.is_mc_multiple_correct:
                options_set = set()
                for selected_opt in oa.official_selected_mc_options:
                    options_set.add(selected_opt.question_option_id)
                official_mc_multiple_options_map[oa.question_id] = options_set

        # Pre-process official ORDERING answers - REMOVED as official_answer.answer_text for ORDERING questions
        # now stores comma-separated option IDs, which will be resolved to texts within the loop.
        # official_ordering_answers_map = {}
        # for q in questions:
        #     if q.question_type.name == 'ORDERING':
        #         correctly_ordered_options = QuestionOption.query.filter_by(question_id=q.id)\
        #                                                       .order_by(QuestionOption.correct_order_index.asc())\
        #                                                       .all()
        #         if correctly_ordered_options:
        #             official_ordering_answers_map[q.id] = [opt.option_text for opt in correctly_ordered_options]

        registrations = UserRaceRegistration.query.filter_by(race_id=race.id).all()
        if not registrations:
            app.logger.info(f"Scoring calculation: No users registered for race_id: {race_id}. No scores to calculate.")
            return {"success": True, "message": "No registered users for race, no scores calculated."}

        for reg in registrations:
            user_id = reg.user_id
            total_user_score_for_race = 0

            user_answers_list = UserAnswer.query.filter_by(user_id=user_id, race_id=race.id).all()
            user_answers_map = {ua.question_id: ua for ua in user_answers_list}

            for q in questions:
                question_score = 0
                user_answer = user_answers_map.get(q.id)
                official_answer = official_answers_map.get(q.id)

                if not user_answer or not official_answer:
                    # If user didn't answer or no official answer, score for this question is 0
                    total_user_score_for_race += question_score
                    continue

                question_type_name = q.question_type.name

                if question_type_name == 'FREE_TEXT':
                    if official_answer.answer_text and user_answer.answer_text:
                        if user_answer.answer_text.strip().lower() == official_answer.answer_text.strip().lower():
                            question_score = q.max_score_free_text or 0

                elif question_type_name == 'MULTIPLE_CHOICE':
                    if q.is_mc_multiple_correct:
                        # Multiple Correct
                        user_selected_option_ids = set()
                        for selected_opt in user_answer.selected_mc_options:
                            user_selected_option_ids.add(selected_opt.question_option_id)

                        official_correct_option_ids = official_mc_multiple_options_map.get(q.id, set())

                        current_question_mc_multiple_score = 0
                        for user_opt_id in user_selected_option_ids:
                            if user_opt_id in official_correct_option_ids:
                                current_question_mc_multiple_score += (q.points_per_correct_mc or 0)
                            else:
                                current_question_mc_multiple_score -= (q.points_per_incorrect_mc or 0)
                        # Consider if points should be deducted for *missed* correct options - current spec doesn't say so.
                        question_score = current_question_mc_multiple_score
                    else:
                        # Single Correct
                        if user_answer.selected_option_id and \
                           user_answer.selected_option_id == official_answer.selected_option_id:
                            question_score = q.total_score_mc_single or 0

                elif question_type_name == 'ORDERING':
                    user_ordered_texts = []
                    if user_answer.answer_text:
                        # User answers for ordering questions are comma-separated texts
                        user_ordered_texts = [text.strip().lower() for text in user_answer.answer_text.split(',')]

                    # Official answers for ordering questions are stored as comma-separated texts.
                    official_ordered_texts = []
                    if official_answer and official_answer.answer_text:
                        official_ordered_texts = [text.strip().lower() for text in official_answer.answer_text.split(',')]

                    if user_ordered_texts and official_ordered_texts: # Both must be non-empty to score
                        current_question_ordering_score = 0
                        is_full_match = True # Assume full match until proven otherwise

                        # Check if lengths are different first, if so, not a full match.
                        if len(user_ordered_texts) != len(official_ordered_texts):
                            is_full_match = False

                        # Iterate based on the length of the official correct order
                        for i in range(len(official_ordered_texts)):
                            if i < len(user_ordered_texts): # Check if user provided an answer for this position
                                if user_ordered_texts[i].lower() == official_ordered_texts[i].lower():
                                    current_question_ordering_score += (q.points_per_correct_order or 0)
                                else:
                                    is_full_match = False # Mismatch at this position
                            else: # User answer is shorter than official answer, so not a full match
                                is_full_match = False

                        # If after checking all items, it's still considered a full match and lengths were initially same
                        if is_full_match and len(user_ordered_texts) == len(official_ordered_texts):
                             # Ensure bonus is only added if there were items to order and points_per_correct_order was positive
                            if (q.points_per_correct_order or 0) > 0 and len(official_ordered_texts) > 0:
                                current_question_ordering_score += (q.bonus_for_full_order or 0)
                            elif len(official_ordered_texts) == 0 and (q.bonus_for_full_order or 0) > 0: # Edge case: bonus for ordering zero items?
                                current_question_ordering_score += (q.bonus_for_full_order or 0)


                        question_score = current_question_ordering_score

                elif question_type_name == 'SLIDER':
                    app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: Processing. Initial total_user_score_for_race for this question: {total_user_score_for_race}")
                    app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: User answer: {user_answer.slider_answer_value}, Official answer: {official_answer.correct_slider_value if official_answer else 'N/A'}")
                    app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: Question config - points_exact: {q.slider_points_exact}, threshold_partial: {q.slider_threshold_partial}, points_partial: {q.slider_points_partial}")

                    if user_answer.slider_answer_value is not None and official_answer and official_answer.correct_slider_value is not None:
                        user_val = user_answer.slider_answer_value
                        official_val = official_answer.correct_slider_value
                        epsilon = 1e-9

                        points_exact = q.slider_points_exact
                        threshold_partial = q.slider_threshold_partial
                        points_partial = q.slider_points_partial

                        # This existing log is good
                        app.logger.debug(
                            f"calculate_and_store_scores - SLIDER QID {q.id} for User {user_id}: "
                            f"UserVal={user_val}, OfficialVal={official_val}, "
                            f"Q.slider_points_exact={points_exact}, "
                            f"Q.slider_threshold_partial={threshold_partial}, "
                            f"Q.slider_points_partial={points_partial}"
                        )

                        diff = abs(user_val - official_val)

                        if diff < epsilon:  # Exact match
                            if points_exact is not None:
                                app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: Exact match condition met. Configured points_exact: {points_exact}")
                                question_score = points_exact
                                app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: Exact Match. Assigned question_score = {question_score}")
                        elif threshold_partial is not None and threshold_partial >= 0 and \
                             points_partial is not None and points_partial >= 0 and \
                             diff <= (threshold_partial + epsilon):  # Partial match
                            app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: Partial match condition met. Configured points_partial: {points_partial}")
                            question_score = points_partial
                            app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: Partial Match. Assigned question_score = {question_score}")
                        else:
                            app.logger.debug(f"calculate_and_store_scores - SLIDER QID {q.id} User {user_id}: No Match. Diff={diff}. Assigned question_score = 0 (implicitly)")
                    else:
                        app.logger.debug(
                            f"calculate_and_store_scores - SLIDER QID {q.id} for User {user_id}: "
                            f"User or official slider value is None or official_answer missing. UserVal: {user_answer.slider_answer_value}, OfficialVal: {official_answer.correct_slider_value if official_answer else 'N/A'}. Assigned question_score = 0 (implicitly)"
                        )

                app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: Final question_score for this question (type {question_type_name}) before adding to total: {question_score}")
                app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: total_user_score_for_race BEFORE '{question_type_name}' Q_Score addition: {total_user_score_for_race}")
                app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: question_score ('{question_type_name}') to be added: {question_score}")
                total_user_score_for_race += question_score
                app.logger.debug(f"SLIDER DIAGNOSTIC - QID {q.id}, User {user_id}: total_user_score_for_race AFTER '{question_type_name}' Q_Score addition: {total_user_score_for_race}")
                # Existing general log line after processing all question types.
                # app.logger.debug(f"User {user_id}, Q {q.id}, Type {question_type_name}, Q_Score {question_score}, Total_Score {total_user_score_for_race}") # This is a bit redundant now but harmless


            # Store or update UserScore
            user_score_entry = UserScore.query.filter_by(user_id=user_id, race_id=race.id).first()
            if user_score_entry:
                user_score_entry.score = total_user_score_for_race
                user_score_entry.updated_at = datetime.utcnow()
                app.logger.info(f"Updating UserScore for user_id {user_id}, race_id {race.id} to {total_user_score_for_race}")
            else:
                user_score_entry = UserScore(
                    user_id=user_id,
                    race_id=race.id,
                    score=total_user_score_for_race,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(user_score_entry)
                app.logger.info(f"Creating UserScore for user_id {user_id}, race_id {race.id} with score {total_user_score_for_race}")

        db.session.commit()
        app.logger.info(f"Successfully calculated and stored scores for race_id: {race_id}")
        return {"success": True, "message": "Scores calculated and stored successfully."}

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error during score calculation for race_id {race_id}: {e}", exc_info=True)
        return {"success": False, "message": f"An error occurred: {str(e)}"}

# --- Official Answer Endpoints ---

@app.route('/api/races/<int:race_id>/official_answers', methods=['GET'])
@login_required
def get_official_answers(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to view official answers."), 403

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    official_answers_query = OfficialAnswer.query.filter_by(race_id=race_id).all()

    output = []
    for oa in official_answers_query:
        question = oa.question
        if not question:
            app.logger.error(f"OfficialAnswer {oa.id} has no associated question. Skipping.")
            continue

        all_q_options_list = []
        for opt in question.options.order_by(QuestionOption.id): # Ensure consistent order
            all_q_options_list.append({
                "id": opt.id,
                "option_text": opt.option_text,
                "correct_order_index": opt.correct_order_index if question.question_type.name == "ORDERING" else None
            })

        answer_details = {
            "question_id": question.id,
            "question_text": question.text,
            "question_type": question.question_type.name,
            "answer_text": oa.answer_text,
            "selected_option_id": oa.selected_option_id,
            "correct_slider_value": oa.correct_slider_value, # Added for slider questions
            "selected_option_text": None,
            "selected_mc_options": [],
            "all_question_options": all_q_options_list
        }

        if question.question_type.name == "MULTIPLE_CHOICE":
            if not question.is_mc_multiple_correct and oa.selected_option_id:
                selected_option = QuestionOption.query.get(oa.selected_option_id)
                if selected_option:
                    answer_details["selected_option_text"] = selected_option.option_text
            elif question.is_mc_multiple_correct:
                selected_mc_options_list = []
                for mc_opt_assoc in oa.official_selected_mc_options: # Relationship name from OfficialAnswer model
                    option = mc_opt_assoc.question_option # Relationship from OfficialAnswerMultipleChoiceOption to QuestionOption
                    if option:
                        selected_mc_options_list.append({
                            "option_id": option.id,
                            "option_text": option.option_text
                        })
                answer_details["selected_mc_options"] = selected_mc_options_list

        output.append(answer_details)

    return jsonify(output), 200


@app.route('/api/races/<int:race_id>/official_answers', methods=['POST'])
@login_required
def save_official_answers(race_id):
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to save official answers."), 403

    race = Race.query.filter_by(id=race_id, is_deleted=False).first()
    if not race:
        return jsonify(message="Race not found or has been deleted"), 404

    answers_payload = request.get_json()
    if not answers_payload:
        return jsonify(message="No data provided"), 400

    app.logger.info(f"User {current_user.id} attempting to save official answers for race {race_id}")
    app.logger.debug(f"Received official answers payload for race {race_id}: {answers_payload}")

    try:
        # Delete existing official answers for this race
        existing_official_answers = OfficialAnswer.query.filter_by(race_id=race_id).all()
        for old_oa in existing_official_answers:
            # Delete associated OfficialAnswerMultipleChoiceOption first
            OfficialAnswerMultipleChoiceOption.query.filter_by(official_answer_id=old_oa.id).delete()
            db.session.delete(old_oa)
        db.session.flush() # Process deletes before adds

        for question_id_str, answer_data in answers_payload.items():
            try:
                question_id = int(question_id_str)
            except ValueError:
                app.logger.warning(f"Invalid question_id format '{question_id_str}' in official answers payload for race {race_id}.")
                continue

            question = Question.query.get(question_id)
            if not question or question.race_id != race_id:
                app.logger.warning(f"Invalid or mismatched question_id {question_id} for race {race_id}.")
                continue

            new_official_answer = OfficialAnswer(
                race_id=race_id,
                question_id=question.id
            )

            question_type_name = question.question_type.name
            app.logger.info(f"Processing official answer for question {question.id} (type: {question_type_name})")

            if question_type_name == 'FREE_TEXT':
                new_official_answer.answer_text = answer_data.get('answer_text')
            elif question_type_name == 'ORDERING':
                # Assuming payload provides 'ordered_options_text' similar to user answers
                new_official_answer.answer_text = answer_data.get('ordered_options_text')
            elif question_type_name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    selected_ids = answer_data.get('selected_option_ids', [])
                    if not isinstance(selected_ids, list):
                        app.logger.warning(f"selected_option_ids for official answer Q {question.id} is not a list: {selected_ids}")
                        selected_ids = []

                    for opt_id in selected_ids:
                        if not isinstance(opt_id, int): continue # Skip non-integer ids
                        option_exists = QuestionOption.query.filter_by(id=opt_id, question_id=question.id).first()
                        if option_exists:
                            mc_option = OfficialAnswerMultipleChoiceOption(question_option_id=opt_id)
                            new_official_answer.official_selected_mc_options.append(mc_option)
                        else:
                            app.logger.warning(f"Invalid option_id {opt_id} for official answer to question {question.id}")
                else: # Single correct
                    selected_id = answer_data.get('selected_option_id')
                    if selected_id is not None:
                        if not isinstance(selected_id, int):
                            app.logger.warning(f"selected_option_id for official answer Q {question.id} is not an int: {selected_id}")
                            new_official_answer.selected_option_id = None
                        else:
                            option_exists = QuestionOption.query.filter_by(id=selected_id, question_id=question.id).first()
                            if option_exists:
                                new_official_answer.selected_option_id = selected_id
                            else:
                                app.logger.warning(f"Invalid selected_option_id {selected_id} for official answer to question {question.id}")
                                new_official_answer.selected_option_id = None
                    else:
                        new_official_answer.selected_option_id = None
            elif question_type_name == 'SLIDER':
                correct_value = answer_data.get('correct_slider_value')
                if correct_value is not None:
                    try:
                        new_official_answer.correct_slider_value = float(correct_value)
                    except (ValueError, TypeError):
                        app.logger.warning(f"Invalid correct_slider_value '{correct_value}' for SLIDER question {question.id}. Storing as None.")
                        new_official_answer.correct_slider_value = None
                else: # If null is sent, store null.
                    new_official_answer.correct_slider_value = None

                # Ensure other type-specific fields are None
                new_official_answer.answer_text = None
                new_official_answer.selected_option_id = None
                # Clear any potential OfficialAnswerMultipleChoiceOption if type changed
                OfficialAnswerMultipleChoiceOption.query.filter_by(official_answer_id=new_official_answer.id).delete()

            else:
                app.logger.warning(f"Unsupported question type '{question_type_name}' for official answer to question {question.id}")
                continue

            db.session.add(new_official_answer)
            app.logger.info(f"OfficialAnswer prepared for question {question.id} for race {race_id}")

        db.session.commit()
        app.logger.info(f"Official answers successfully saved for race {race_id} by user {current_user.id}")

        # Trigger score calculation
        app.logger.info(f"Attempting to trigger score calculation for race {race_id} after saving official answers.")
        scoring_result = calculate_and_store_scores(race_id)
        if not scoring_result.get("success"):
            app.logger.error(f"Scoring calculation failed for race {race_id} after official answers were saved. Reason: {scoring_result.get('message')}")
        else:
            app.logger.info(f"Scoring calculation triggered successfully for race {race_id}. Message: {scoring_result.get('message')}")

        return jsonify(message="Official answers saved successfully. Scoring process initiated."), 201

    except IntegrityError as ie:
        db.session.rollback()
        app.logger.error(f"IntegrityError saving official answers for race {race_id}, user {current_user.id}: {ie}", exc_info=True)
        return jsonify(message="Database integrity error while saving official answers."), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception saving official answers for race {race_id}, user {current_user.id}: {e}", exc_info=True)
        return jsonify(message="An error occurred while saving official answers."), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    """
    Provides a list of all available events (from TriCal definitions).
    Does not require authentication.
    """
    try:
        events = Event.query.order_by(Event.event_date.desc()).all()

        output = []
        for event in events:
            output.append({
                "id": event.id,
                "name": event.name,
                "event_date": event.event_date.strftime('%Y-%m-%d') if event.event_date else None,
                "city": event.city,
                "province": event.province,
                "discipline": event.discipline,
                "distance": event.distance,
                "source_url": event.source_url,
                "is_good_for_debutants": event.is_good_for_debutants,
                "is_challenging": event.is_challenging,
                "has_great_views": event.has_great_views,
                "has_good_atmosphere": event.has_good_atmosphere,
                "is_world_qualifier": event.is_world_qualifier,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "updated_at": event.updated_at.isoformat() if event.updated_at else None
            })
        return jsonify(output), 200
    except Exception as e:
        app.logger.error(f"Error fetching events: {e}", exc_info=True)
        return jsonify(message="Error fetching events"), 500

@app.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event_api(event_id):
    if current_user.role.code != 'ADMIN':
        return jsonify(message="Forbidden: Solo los administradores pueden actualizar eventos."), 403

    event = Event.query.get(event_id)
    if not event:
        return jsonify(message="Evento no encontrado"), 404

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    # Validar y actualizar campos
    if 'name' in data:
        name = data.get('name')
        if not name or not name.strip():
            return jsonify(message="El nombre del evento es obligatorio."), 400
        event.name = name

    if 'event_date' in data:
        event_date_str = data.get('event_date')
        if not event_date_str:
            return jsonify(message="La fecha del evento es obligatoria."), 400
        try:
            event.event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify(message="Formato de fecha inválido. Use YYYY-MM-DD."), 400

    # Campos opcionales (si no están en data, no se actualizan, se mantiene el valor existente)
    if 'city' in data:
        event.city = data.get('city').strip() if data.get('city') and data.get('city').strip() else None
    if 'province' in data:
        event.province = data.get('province').strip() if data.get('province') and data.get('province').strip() else None
    if 'discipline' in data:
        event.discipline = data.get('discipline').strip() if data.get('discipline') and data.get('discipline').strip() else None
    if 'distance' in data:
        event.distance = data.get('distance').strip() if data.get('distance') and data.get('distance').strip() else None
    if 'source_url' in data:
        event.source_url = data.get('source_url').strip() if data.get('source_url') and data.get('source_url').strip() else None

    # Campos booleanos de curación
    # Si la clave está en `data`, se actualiza el valor. Si no, se mantiene el existente.
    if 'is_good_for_debutants' in data:
        event.is_good_for_debutants = bool(data.get('is_good_for_debutants'))
    if 'is_challenging' in data:
        event.is_challenging = bool(data.get('is_challenging'))
    if 'has_great_views' in data:
        event.has_great_views = bool(data.get('has_great_views'))
    if 'has_good_atmosphere' in data:
        event.has_good_atmosphere = bool(data.get('has_good_atmosphere'))
    if 'is_world_qualifier' in data:
        event.is_world_qualifier = bool(data.get('is_world_qualifier'))

    event.updated_at = datetime.utcnow() # Actualizar timestamp

    try:
        db.session.commit()
        return jsonify(message="Evento actualizado con éxito", event_id=event.id), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify(message="Error de integridad: Conflicto al actualizar el evento."), 409
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error actualizando evento {event_id} vía API: {e}", exc_info=True)
        return jsonify(message="Error interno del servidor al actualizar el evento."), 500


# --- Event Management Routes (Admin only) ---

@app.route('/admin/events_management')
@login_required
def serve_events_management_page():
    if current_user.role.code != 'ADMIN':
        flash("Acceso denegado. Esta sección es solo para administradores.", "error")
        return redirect(url_for('serve_hello_world_page'))

    # Proporcionar valores por defecto para las variables que espera admin_dashboard.html
    # para evitar el error de 'Undefined'.
    # Estas variables pueden no ser directamente relevantes para events_management.html,
    # pero son necesarias si admin_dashboard.html las usa.
    return render_template(
        'events_management.html',
        current_year=datetime.utcnow().year,
        races=[], # Para la tabla principal de carreras en admin_dashboard si se renderiza
        races_for_official_answers=[], # Para el modal de respuestas oficiales
        all_race_formats=RaceFormat.query.order_by(RaceFormat.name).all(), # Necesario para filtros
        filter_date_from_str=None,
        filter_date_to_str=None,
        filter_race_format_id_str=None,
        all_race_statuses=[status.value for status in RaceStatus], # Para filtros de estado
        selected_statuses_for_ui=[], # Para filtros de estado
        # Añade aquí cualquier otra variable que admin_dashboard.html espere y
        # que pueda causar un error 'Undefined' si no está presente.
        # Por ejemplo, si admin_dashboard.html tiene secciones específicas para LEAGUE_ADMIN
        # que esperan otras variables, podrían necesitarse aquí también con valores por defecto.
        organized_races=[],
        participating_races=[],
        favorite_races=[],
        active_players_count=0,
        auto_join_race_id=None, # Añadido para el modal join by link
        race_to_join_title=None # Añadido para el modal join by link
    )

@app.route('/api/events', methods=['POST'])
@login_required
def create_event_api():
    if current_user.role.code != 'ADMIN':
        return jsonify(message="Forbidden: Solo los administradores pueden crear eventos."), 403

    data = request.get_json()
    if not data:
        return jsonify(message="Invalid input: No data provided"), 400

    # Campos requeridos
    name = data.get('name')
    event_date_str = data.get('event_date')

    if not name or not name.strip():
        return jsonify(message="El nombre del evento es obligatorio."), 400
    if not event_date_str:
        return jsonify(message="La fecha del evento es obligatoria."), 400

    try:
        event_date_obj = datetime.strptime(event_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify(message="Formato de fecha inválido. Use YYYY-MM-DD."), 400

    # Campos opcionales
    city = data.get('city')
    province = data.get('province')
    discipline = data.get('discipline')
    distance = data.get('distance')
    source_url = data.get('source_url')

    # Campos booleanos de curación (default a False si no vienen)
    is_good_for_debutants = data.get('is_good_for_debutants', False)
    is_challenging = data.get('is_challenging', False)
    has_great_views = data.get('has_great_views', False)
    has_good_atmosphere = data.get('has_good_atmosphere', False)
    is_world_qualifier = data.get('is_world_qualifier', False)

    new_event = Event(
        name=name,
        event_date=event_date_obj,
        city=city if city and city.strip() else None,
        province=province if province and province.strip() else None,
        discipline=discipline if discipline and discipline.strip() else None,
        distance=distance if distance and distance.strip() else None,
        source_url=source_url if source_url and source_url.strip() else None,
        is_good_for_debutants=is_good_for_debutants,
        is_challenging=is_challenging,
        has_great_views=has_great_views,
        has_good_atmosphere=has_good_atmosphere,
        is_world_qualifier=is_world_qualifier
    )

    try:
        db.session.add(new_event)
        db.session.commit()
        # Devolver el evento creado podría ser útil, o solo un mensaje de éxito
        return jsonify(message="Evento creado con éxito", event_id=new_event.id), 201
    except IntegrityError:
        db.session.rollback()
        # Esto podría pasar si hay una constraint unique en 'name' y 'event_date' por ejemplo.
        return jsonify(message="Error de integridad: El evento ya podría existir o hubo un conflicto."), 409
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creando evento vía API: {e}", exc_info=True)
        return jsonify(message="Error interno del servidor al crear el evento."), 500


# @app.route('/api/events/<int:event_id>', methods=['PUT']) # API para actualizar evento - Eliminada
# @login_required
# def update_event(event_id):
#     # Funcionalidad eliminada
#     return jsonify(message="Funcionalidad de actualización de eventos no disponible."), 405

# La ruta GET /api/events/<int:event_id> para obtener detalles de un evento específico se mantiene si es necesaria para otros propósitos.
# Si solo se usaba para el modal de edición, también podría eliminarse. Por ahora se conserva.
@app.route('/api/events/<int:event_id>', methods=['GET']) # API para obtener un evento específico
@login_required # Opcional, dependiendo si quieres que solo admins vean detalles por API
def get_event_detail_api(event_id):
    if current_user.role.code != 'ADMIN': # O ajusta el permiso como necesites
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    event = Event.query.get(event_id)
    if not event:
        return jsonify(message="Evento no encontrado"), 404

    event_dict = {f.name: getattr(event, f.name) for f in event.__table__.columns}
    if event_dict.get('event_date') and isinstance(event_dict['event_date'], datetime.date):
        event_dict['event_date'] = event_dict['event_date'].isoformat()

    return jsonify(event_dict), 200

# La ruta DELETE /api/events/<int:event_id> se mantiene para permitir la eliminación de eventos si es necesario.
@app.route('/api/events/<int:event_id>', methods=['DELETE']) # API para eliminar evento
@login_required
def delete_event_api(event_id): # Renombrado para evitar conflicto con delete_event
    if current_user.role.code != 'ADMIN':
        return jsonify(message="Forbidden: Insufficient permissions"), 403

    event = Event.query.get(event_id)
    if not event:
        return jsonify(message="Evento no encontrado"), 404

    # Comprobar si hay carreras asociadas
    if event.races: # Asume que la relación 'races' está definida en el modelo Event
        return jsonify(message="No se puede eliminar el evento porque tiene carreras asociadas. Por favor, desasigna o elimina esas carreras primero."), 409 # 409 Conflict

    try:
        db.session.delete(event)
        db.session.commit()
        return jsonify(message="Evento eliminado con éxito"), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Excepción eliminando evento {event_id}: {e}", exc_info=True)
        return jsonify(message="Error al eliminar el evento"), 500


@app.route('/event/<int:event_id>/<string:event_name_slug>')
def event_detail_page(event_id, event_name_slug):
    """
    Serves the detail page for a specific event.
    The event_name_slug is for SEO purposes and not used to fetch the event.
    """
    try:
        event = Event.query.get(event_id)
        if not event:
            app.logger.warning(f"Event with id {event_id} (slug: {event_name_slug}) not found.")
            return render_template('event_detail.html', event=None, current_year=datetime.utcnow().year), 404

        # El event_name_slug no se usa para la consulta, pero podría usarse para una redirección
        # canónica si el slug no coincide con el nombre del evento, aunque esto es más avanzado.
        # Por ahora, simplemente lo aceptamos en la ruta.

        return render_template('event_detail.html', event=event, current_year=datetime.utcnow().year)
    except Exception as e:
        app.logger.error(f"Error fetching event detail for event_id {event_id} (slug: {event_name_slug}): {e}", exc_info=True)
        return render_template('event_detail.html', event=None, current_year=datetime.utcnow().year), 500
