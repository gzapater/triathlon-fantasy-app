import os
from flask import Flask, jsonify, request, redirect, url_for, send_from_directory
# Updated model imports
from backend.models import db, User, Role, Race, RaceFormat, Segment, RaceSegmentDetail, QuestionType, Question, QuestionOption, UserRaceRegistration, UserAnswer, UserAnswerMultipleChoiceOption, OfficialAnswer, OfficialAnswerMultipleChoiceOption # Added UserRaceRegistration, UserAnswer, UserAnswerMultipleChoiceOption
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError # Import for handling unique constraint violations
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

# Seeding functions (create_initial_roles, create_initial_race_data, create_initial_question_types)
# have been moved to backend/seed.py and will be run via CLI.

# The with app.app_context() block that called these functions is also removed
# as it's no longer needed here for initial data seeding.
# If it was used for other purposes like db.create_all(), ensure those are handled
# appropriately (e.g., by Flask-Migrate).

# --- Official Answers API ---

@app.route('/api/races/<int:race_id>/official_answers', methods=['GET'])
@login_required
def get_official_answers(race_id):
    # 1. Authenticated: Handled by @login_required

    # 2. Race Validation
    race = Race.query.get(race_id)
    if not race:
        app.logger.warning(f"User {current_user.username} attempted to fetch official answers for non-existent race {race_id}.")
        return jsonify(message="Race not found"), 404

    # 3. Race Status Check: Ensure the race's event_date has passed
    # Allow admins to see/set answers anytime, but public access only after event.
    # For this GET endpoint, we strictly enforce that event must have passed for anyone.
    if race.event_date and race.event_date > datetime.utcnow():
        app.logger.warning(f"User {current_user.username} attempted to fetch official answers for race {race_id} (Event Date: {race.event_date}) which has not concluded.")
        return jsonify(message="Official results are not yet available for this race as it has not concluded."), 403

    official_answers_response = {}
    try:
        # 4. Data Retrieval: Fetch all OfficialAnswer records for the given race
        # This assumes OfficialAnswer has a relationship to Question, and Question to Race.
        official_answers_for_race = OfficialAnswer.query.join(Question).filter(Question.race_id == race_id).all()

        if not official_answers_for_race:
            # No official answers set yet for any question in this race.
            # Return empty JSON object, which is fine. Frontend will see no pre-filled data.
            return jsonify(official_answers_response), 200

        # 5. Response Formatting
        for oa in official_answers_for_race:
            question = oa.question # Get the associated question
            if not question: # Should not happen if data integrity is maintained
                app.logger.error(f"OfficialAnswer {oa.id} is orphaned or its question was deleted.")
                continue

            question_id_str = str(question.id)
            answer_detail = {
                "official_answer_id": oa.id,
                "question_type": question.question_type.name,
                # Add question.is_mc_multiple_correct for frontend convenience if needed
                # "is_mc_multiple_correct": question.is_mc_multiple_correct
            }

            if question.question_type.name == 'FREE_TEXT' or question.question_type.name == 'ORDERING':
                answer_detail["answer_text"] = oa.answer_text
            elif question.question_type.name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    selected_options_details = []
                    # oa.selected_mc_options is the relationship to OfficialAnswerMultipleChoiceOption
                    for oamc_option in oa.selected_mc_options:
                        # oamc_option.question_option is the relationship to QuestionOption model
                        if oamc_option.question_option:
                            selected_options_details.append({
                                "option_id": oamc_option.question_option.id,
                                "option_text": oamc_option.question_option.option_text
                            })
                        else: # Should not happen
                            app.logger.warning(f"OfficialAnswerMultipleChoiceOption {oamc_option.id} has no associated QuestionOption.")
                    answer_detail["selected_options"] = selected_options_details
                else: # Single correct
                    answer_detail["selected_option_id"] = oa.selected_option_id
                    if oa.selected_option_id:
                        # Fetch the text for the selected option
                        selected_option_obj = QuestionOption.query.get(oa.selected_option_id)
                        if selected_option_obj:
                            answer_detail["selected_option_text"] = selected_option_obj.option_text
                        else:
                            answer_detail["selected_option_text"] = None # ID was invalid
                    else: # No option was selected as official answer
                         answer_detail["selected_option_text"] = None


            official_answers_response[question_id_str] = answer_detail

        return jsonify(official_answers_response), 200

    except Exception as e:
        db.session.rollback() # Not strictly necessary for GET but good practice if any complex logic could write
        app.logger.error(f"Exception fetching official answers for race {race_id}, user {current_user.username}: {e}", exc_info=True)
        return jsonify(message="An error occurred while fetching official answers."), 500


@app.route('/api/races/<int:race_id>/official_answers', methods=['POST'])
@login_required
def manage_official_answers(race_id):
    # 1. Permissions: Ensure only users with ADMIN or LEAGUE_ADMIN roles can access
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.username} (Role: {current_user.role.code}) forbidden to manage official answers for race {race_id}.")
        return jsonify(message="Forbidden: You do not have permission to manage official answers."), 403

    # 2. Race Validation: Check if the race with race_id exists
    race = Race.query.get(race_id)
    if not race:
        app.logger.warning(f"Attempt to manage official answers for non-existent race {race_id} by user {current_user.username}.")
        return jsonify(message="Race not found"), 404

    # 3. Race Status Check: Ensure the race's event_date has passed
    if race.event_date and race.event_date > datetime.utcnow():
        app.logger.warning(f"Attempt to submit official answers for race {race_id} (Event Date: {race.event_date}) which has not concluded, by user {current_user.username}.")
        return jsonify(message="Official results can only be submitted after the race has concluded."), 403

    # 4. Data Reception
    payload = request.get_json()
    if not payload:
        app.logger.warning(f"No payload received for official answers for race {race_id} by user {current_user.username}.")
        return jsonify(message="No data provided in JSON payload"), 400

    app.logger.info(f"User {current_user.username} submitting official answers for race {race_id}. Payload: {payload}")

    try:
        processed_question_ids = set()
        # 5. Process Each Answer
        for question_id_str, answer_data in payload.items():
            try:
                question_id = int(question_id_str)
            except ValueError:
                app.logger.warning(f"Invalid question_id format '{question_id_str}' in official answers payload for race {race_id}.")
                # Consider whether to fail all or skip. For now, skip.
                continue

            question = Question.query.filter_by(id=question_id, race_id=race_id).first()
            if not question:
                app.logger.warning(f"Question ID {question_id} not found or does not belong to race {race_id} in official answers submission.")
                # Consider whether to fail all or skip. For now, skip.
                continue

            processed_question_ids.add(question_id)

            # Find or create an OfficialAnswer record
            official_answer = OfficialAnswer.query.filter_by(question_id=question.id).first()
            if not official_answer:
                official_answer = OfficialAnswer(question_id=question.id, created_by_id=current_user.id)
                db.session.add(official_answer)
            else:
                official_answer.updated_at = datetime.utcnow() # Explicitly set updated_at

            # Clear previous answer fields before setting new ones
            official_answer.answer_text = None
            official_answer.selected_option_id = None
            # Delete existing OfficialAnswerMultipleChoiceOption for this OfficialAnswer
            OfficialAnswerMultipleChoiceOption.query.filter_by(official_answer_id=official_answer.id).delete()
            # db.session.flush() # Ensure deletes are processed before adds if needed, usually handled by commit ordering

            question_type_name = question.question_type.name
            app.logger.info(f"Processing official answer for QID {question.id} (Type: {question_type_name}) in Race {race_id}")

            if question_type_name == 'FREE_TEXT':
                if not isinstance(answer_data, dict) or 'answer_text' not in answer_data:
                    app.logger.warning(f"Invalid answer_data for FREE_TEXT QID {question.id}: {answer_data}")
                    # Potentially raise error or skip
                    continue
                official_answer.answer_text = answer_data.get('answer_text')
                if official_answer.answer_text is None:
                     app.logger.debug(f"No answer_text provided for FREE_TEXT QID {question.id} in official submission.")


            elif question_type_name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct: # Multiple correct
                    if not isinstance(answer_data, dict) or 'selected_option_ids' not in answer_data or not isinstance(answer_data.get('selected_option_ids'), list):
                        app.logger.warning(f"Invalid answer_data for MC_MULTIPLE QID {question.id}: {answer_data}")
                        continue
                    selected_ids = answer_data.get('selected_option_ids', [])
                    app.logger.debug(f"Official MC Multiple for QID {question.id}: selected_ids = {selected_ids}")
                    for opt_id in selected_ids:
                        option_exists = QuestionOption.query.filter_by(id=opt_id, question_id=question.id).first()
                        if option_exists:
                            db.session.add(OfficialAnswerMultipleChoiceOption(official_answer=official_answer, question_option_id=opt_id))
                        else:
                            app.logger.warning(f"Invalid official option_id {opt_id} for MC_MULTIPLE QID {question.id}")
                            # Decide on error handling: raise, skip option, or skip question's answer
                            # For now, we are skipping this specific invalid option.
                else: # Single correct
                    if not isinstance(answer_data, dict) or 'selected_option_id' not in answer_data:
                        app.logger.warning(f"Invalid answer_data for MC_SINGLE QID {question.id}: {answer_data}")
                        continue
                    selected_id = answer_data.get('selected_option_id')
                    app.logger.debug(f"Official MC Single for QID {question.id}: selected_option_id = {selected_id}")
                    if selected_id is not None:
                        option_exists = QuestionOption.query.filter_by(id=selected_id, question_id=question.id).first()
                        if option_exists:
                            official_answer.selected_option_id = selected_id
                        else:
                            app.logger.warning(f"Invalid official selected_option_id {selected_id} for MC_SINGLE QID {question.id}")
                            # Decide on error handling. For now, we are effectively clearing it if invalid.
                            official_answer.selected_option_id = None
                    else: # No option selected by admin
                        official_answer.selected_option_id = None

            elif question_type_name == 'ORDERING':
                if not isinstance(answer_data, dict) or 'ordered_options_text' not in answer_data: # Assuming text like "OptA, OptB, OptC"
                    app.logger.warning(f"Invalid answer_data for ORDERING QID {question.id}: {answer_data}")
                    continue
                official_answer.answer_text = answer_data.get('ordered_options_text')
                if official_answer.answer_text is None:
                     app.logger.debug(f"No ordered_options_text provided for ORDERING QID {question.id} in official submission.")

            else:
                app.logger.warning(f"Unsupported question type '{question_type_name}' for official answer processing of QID {question.id}")
                # Skip this question's answer or raise error
                continue

        # After iterating through payload, check if any questions from the race were NOT in the payload.
        # This could mean those questions should have their official answers cleared if they previously existed.
        # However, the current loop only processes questions present in the payload.
        # If a question_id is NOT in the payload, its existing official answer (if any) is untouched.
        # This seems acceptable for a POST/PUT-like batch update.

        # 6. Database Commit
        db.session.commit()
        app.logger.info(f"Official answers successfully saved/updated for race {race_id} by user {current_user.username}.")
        # 7. Response: Status 201 if new resources were created, 200 if existing updated.
        # For simplicity, 200 OK is generally fine for batch updates.
        return jsonify(message="Official answers saved successfully"), 200

    except IntegrityError as ie:
        db.session.rollback()
        app.logger.error(f"IntegrityError managing official answers for race {race_id}, user {current_user.username}: {ie}", exc_info=True)
        return jsonify(message="Database integrity error while saving official answers."), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Exception managing official answers for race {race_id}, user {current_user.username}: {e}", exc_info=True)
        return jsonify(message="An error occurred while saving official answers."), 500

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
        is_general=is_general, # Add the new field here
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

        app.logger.info(f"Race object after modifications: {race.to_dict() if hasattr(race, 'to_dict') else race}")
        db.session.commit()

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
        }
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
    app.logger.info(f"delete_race called for race_id: {race_id}")
    # 1. Check user role
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        app.logger.warning(f"User {current_user.username} forbidden to delete race {race_id}")
        return jsonify(message="Forbidden: You do not have permission to delete this race."), 403

    # 2. Fetch the Race object
    race = Race.query.get(race_id)
    if not race:
        app.logger.warning(f"Race with id {race_id} not found for deletion.")
        return jsonify(message="Race not found"), 404
    app.logger.info(f"Fetched race object for deletion: {race.to_dict() if hasattr(race, 'to_dict') else race}")

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

        # Flush the session to execute the delete operations for related objects in the DB
        db.session.flush()
        # Note: Using synchronize_session='fetch' or 'evaluate' can be important
        # if the session is to be used further before commit. 'fetch' is generally safer.

        # 5. Delete the Race object itself
        app.logger.info(f"Attempting to delete race object: {race.id}")
        db.session.delete(race)

        # 6. Commit the database session
        db.session.commit()
        app.logger.info(f"Race {race_id} deleted and session committed successfully.")
        # HTTP 204 No Content is also appropriate for DELETE success if no message body is needed.
        # Returning 200 with a message is also common and acceptable.
        return jsonify(message="Race deleted successfully"), 200
    except Exception as e:
        # 7. Handle potential errors
        db.session.rollback()
        app.logger.error(f"Exception deleting race {race_id}: {e}", exc_info=True)
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


@app.route('/api/races/<int:race_id>/share_link', methods=['GET'])
@login_required
def get_race_share_link(race_id):
    # 1. Role check
    if not current_user.is_authenticated or current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to generate share links."), 403

    # 2. Fetch the Race object
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

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
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    return jsonify(id=race.id, title=race.title), 200


@app.route('/api/races/<int:race_id>/join', methods=['POST']) # POST request to create a resource
@login_required
def join_race_api(race_id):
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

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


@app.route('/api/races/<int:race_id>/participants', methods=['GET'])
@login_required
def get_race_participants(race_id):
    # Role check
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to view participants."), 403

    # Check if race exists
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    registrations = UserRaceRegistration.query.filter_by(race_id=race_id).all()

    participants_list = []
    for reg in registrations:
        user = User.query.get(reg.user_id)
        if not user:
            # This case should ideally not happen if data integrity is maintained
            app.logger.warning(f"UserRaceRegistration {reg.id} refers to a non-existent user {reg.user_id}.")
            continue

        # Check if the user has answered any question for this race
        has_answered = UserAnswer.query.filter_by(user_id=user.id, race_id=race_id).first() is not None

        participants_list.append({
            "user_id": user.id,
            "username": user.username,
            "has_answered": has_answered
        })

    return jsonify(participants_list), 200


@app.route('/api/races/<int:race_id>/participants/<int:user_id>/answers', methods=['GET'])
@login_required
def get_participant_answers(race_id, user_id):
    # Role check
    if current_user.role.code not in ['ADMIN', 'LEAGUE_ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to view participant answers."), 403

    # Fetch Race
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    # Fetch User (participant)
    participant = User.query.get(user_id)
    if not participant:
        return jsonify(message="Participant not found"), 404

    # Optional: Check if the participant is actually registered for this race
    registration = UserRaceRegistration.query.filter_by(user_id=participant.id, race_id=race.id).first()
    if not registration:
        # This means the user_id provided is not a participant of the specified race_id
        return jsonify(message=f"User {participant.username} is not registered for race {race.title}."), 404


    # Fetch all questions for the race
    race_questions = Question.query.filter_by(race_id=race_id).order_by(Question.id).all()

    participant_answers_details = []

    for question in race_questions:
        user_answer_obj = UserAnswer.query.filter_by(
            user_id=participant.id,
            question_id=question.id,
            race_id=race_id # Ensure answer is for this specific race context
        ).first()

        answer_data = None
        if user_answer_obj:
            if question.question_type.name == 'FREE_TEXT':
                answer_data = user_answer_obj.answer_text
            elif question.question_type.name == 'ORDERING':
                answer_data = user_answer_obj.answer_text # Stores comma-separated ordered text
            elif question.question_type.name == 'MULTIPLE_CHOICE':
                if question.is_mc_multiple_correct:
                    selected_options = []
                    for mc_option_assoc in user_answer_obj.selected_mc_options:
                        option = QuestionOption.query.get(mc_option_assoc.question_option_id)
                        if option:
                            selected_options.append({"id": option.id, "text": option.option_text})
                    answer_data = selected_options # List of {"id": id, "text": text}
                else: # Single correct
                    if user_answer_obj.selected_option_id:
                        option = QuestionOption.query.get(user_answer_obj.selected_option_id)
                        if option:
                            answer_data = {"id": option.id, "text": option.option_text}
                        else:
                            answer_data = None # Selected option ID was invalid
                    else:
                        answer_data = None # No option selected

        # Get all possible options for this question
        options_for_question = []
        for qo in question.options.order_by(QuestionOption.id): # Assuming backref is 'options' and ordered
            options_for_question.append({
                "id": qo.id,
                "option_text": qo.option_text,
                "correct_order_index": qo.correct_order_index # Relevant for ORDERING type
            })

        participant_answers_details.append({
            "question_id": question.id,
            "question_text": question.text,
            "question_type": question.question_type.name,
            "is_mc_multiple_correct": question.is_mc_multiple_correct, # Important for MC rendering
            "options": options_for_question,
            "participant_answer": answer_data # This can be string, dict, list of dicts, or null
        })

    return jsonify(participant_answers_details), 200

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


@app.route('/join_race/<int:race_id>')
def handle_join_race_link(race_id):
    race = Race.query.get(race_id)
    if not race:
        # If race not found, redirect appropriately
        if current_user.is_authenticated:
            # Redirect to dashboard with an error hint (frontend can show a message)
            return redirect(url_for('serve_hello_world_page', error='race_not_found', original_race_id=race_id))
        else:
            # Redirect to login page with an error hint
            return redirect(url_for('serve_login_page', error='race_not_found', original_race_id=race_id))

    if current_user.is_authenticated:
        # User is logged in, redirect to their dashboard with race_id for modal
        app.logger.info(f"User {current_user.username} authenticated, joining race {race.id}. Redirecting to dashboard.")
        return redirect(url_for('serve_hello_world_page', join_race_id=race.id))
    else:
        # User is not logged in, redirect to login page.
        # After login, they should be redirected back to this /join_race/<race_id> URL.
        # url_for generates a relative path by default. _external=True can make it absolute if needed elsewhere.
        # For the 'next' param, a relative path is usually fine and preferred.
        login_url_with_next = url_for('serve_login_page', next=url_for('handle_join_race_link', race_id=race.id))
        app.logger.info(f"User not authenticated for join_race {race.id}. Redirecting to login: {login_url_with_next}")
        return redirect(login_url_with_next)


@app.route('/Hello-world') # This is the main dashboard route after login
@login_required
def serve_hello_world_page():
    # Keep existing filter and data fetching logic
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

    # Role-based rendering
    if current_user.role.code == 'ADMIN':
        query = Race.query.filter_by(is_general=True) # Filter for general races
        if date_from_obj:
            query = query.filter(Race.event_date >= date_from_obj)
        if date_to_obj:
            query = query.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None:
            query = query.filter(Race.race_format_id == race_format_id_int)
        try:
            all_races = query.order_by(Race.event_date.desc()).all()
        except Exception as e:
            app.logger.error(f"Error fetching general races for admin dashboard: {e}")

        return render_template('admin_dashboard.html',
                               races=all_races,
                               all_race_formats=all_race_formats,
                               filter_date_from_str=filter_date_from_str,
                               filter_date_to_str=filter_date_to_str,
                               filter_race_format_id_str=filter_race_format_id_str,
                               current_year=current_year)
    elif current_user.role.code == 'LEAGUE_ADMIN':
        query = Race.query.filter_by(is_general=False, user_id=current_user.id) # Filter for their local races
        if date_from_obj:
            query = query.filter(Race.event_date >= date_from_obj)
        if date_to_obj:
            query = query.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None:
            query = query.filter(Race.race_format_id == race_format_id_int)
        try:
            all_races = query.order_by(Race.event_date.desc()).all()
        except Exception as e:
            app.logger.error(f"Error fetching local races for league admin: {e}")

        return render_template('index.html',
                               races=all_races,
                               all_race_formats=all_race_formats,
                               filter_date_from_str=filter_date_from_str,
                               filter_date_to_str=filter_date_to_str,
                               filter_race_format_id_str=filter_race_format_id_str,
                               current_year=current_year)
    elif current_user.role.code == 'PLAYER':
        # Query UserRaceRegistration for all race_ids for the current_user
        user_registrations = UserRaceRegistration.query.filter_by(user_id=current_user.id).all()
        registered_race_ids = [reg.race_id for reg in user_registrations]

        # Query Race model for these race_ids
        query = Race.query.filter(Race.id.in_(registered_race_ids))

        # Apply existing filters
        if date_from_obj:
            query = query.filter(Race.event_date >= date_from_obj)
        if date_to_obj:
            query = query.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None:
            query = query.filter(Race.race_format_id == race_format_id_int)

        registered_races = []
        try:
            registered_races = query.order_by(Race.event_date.desc()).all()
        except Exception as e:
            app.logger.error(f"Error fetching registered races for player {current_user.id}: {e}")

        return render_template('player.html',
                               registered_races=registered_races, # Pass registered_races
                               all_race_formats=all_race_formats,
                               filter_date_from_str=filter_date_from_str,
                               filter_date_to_str=filter_date_to_str,
                               filter_race_format_id_str=filter_race_format_id_str,
                               current_year=current_year)
    else:
        # Fallback for any other authenticated role, or if roles are added in the future
        # Defaulting to player view (general races) - This part remains unchanged
        app.logger.warning(f"User {current_user.username} with unhandled role {current_user.role.code} accessing dashboard. Defaulting to player view (general races).")
        query = Race.query.filter_by(is_general=True)
        if date_from_obj:
            query = query.filter(Race.event_date >= date_from_obj)
        if date_to_obj:
            query = query.filter(Race.event_date <= date_to_obj)
        if race_format_id_int is not None:
            query = query.filter(Race.race_format_id == race_format_id_int)
        try:
            all_races = query.order_by(Race.event_date.desc()).all() # Keep variable name all_races for consistency in this block
        except Exception as e:
            app.logger.error(f"Error fetching general races for fallback/unhandled role: {e}")

        return render_template('player.html',
                               races=all_races, # Keep races=all_races for this fallback block
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
    race = Race.query.get_or_404(race_id)
    current_year = datetime.utcnow().year

    user_role_code = 'GUEST' # Default role if not authenticated or no role
    is_user_registered_for_race = False # Default to false
    has_user_answered_pool = False # Initialize default for the new variable

    if current_user and current_user.is_authenticated:
        user_role_code = current_user.role.code
        # Check if the current user is registered for this race
        registration = UserRaceRegistration.query.filter_by(user_id=current_user.id, race_id=race_id).first()
        if registration:
            is_user_registered_for_race = True

        # Check if the user has answered any questions for this race pool
        user_answers = UserAnswer.query.filter_by(user_id=current_user.id, race_id=race_id).first()
        if user_answers:
            has_user_answered_pool = True
    else:
        # Ensure current_user.is_authenticated is False if current_user is None or not authenticated
        # This handles cases where current_user might be an AnonymousUserMixin without a 'role'
        pass


    return render_template('race_detail.html',
                           race=race,
                           current_year=current_year,
                           currentUserRole=user_role_code,
                           is_user_registered_for_race=is_user_registered_for_race,
                           has_user_answered_pool=has_user_answered_pool)

# --- API Endpoint for Saving User Answers ---
@app.route('/api/races/<int:race_id>/answers', methods=['POST'])
@login_required
def save_user_answers(race_id):
    app.logger.info(f"User {current_user.id} attempting to save answers for race {race_id}")

    # 1. Permissions Check: Fetch Race
    race = Race.query.get(race_id)
    if not race:
        app.logger.warning(f"Attempt to save answers for non-existent race {race_id} by user {current_user.id}")
        return jsonify(message="Race not found"), 404

    # 2. Permissions Check: User Registration for this Race
    registration = UserRaceRegistration.query.filter_by(user_id=current_user.id, race_id=race_id).first()
    if not registration:
        app.logger.warning(f"User {current_user.id} not registered for race {race_id}, cannot save answers.")
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


            # Delete existing answers for this user and question
            # This also handles deletion of UserAnswerMultipleChoiceOption due to cascade
            UserAnswer.query.filter_by(user_id=current_user.id, question_id=question.id).delete()
            # db.session.flush() # Ensure deletes are processed before adds if there are unique constraints or complex interactions

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
    race = Race.query.get(race_id)
    if not race:
        return jsonify(message="Race not found"), 404

    user_answers = UserAnswer.query.filter_by(user_id=current_user.id, race_id=race_id).all()

    if not user_answers:
        # It's important to return an empty list if no answers, not a 404 or error
        return jsonify([]), 200

    processed_answers = []
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

        processed_answers.append(answer_data)

    return jsonify(processed_answers), 200

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
