import os
from flask import Flask, jsonify, request, redirect, url_for, send_from_directory
# Updated model imports
from backend.models import db, User, Role, Race, RaceFormat, Segment, RaceSegmentDetail
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
app.config['DEBUG_LOGIN'] = True     # <--- AÑADE ESTA LÍNEA TEMPORALMENTE para depuración

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_initial_roles():
    #Checks for existing roles and creates them if not present, using code and description."""
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
    """Seeds RaceFormat and Segment tables with initial data."""
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

with app.app_context():
    db.create_all() # Ensures all tables are created based on models
    create_initial_roles()
    create_initial_race_data() # Call the function to seed race data

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
        return jsonify(message="Invalid event_date format. Required format: YYYY-MM-DD."), 400

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
        # AÑADE ESTO TEMPORALMENTE PARA DEPURACIÓN

    return render_template('index.html')

@app.route('/create-race')
@login_required
def serve_create_race_page():
    if current_user.role.code not in ['LEAGUE_ADMIN', 'ADMIN']:
        return jsonify(message="Forbidden: You do not have permission to access this page."), 403
        # Or redirect to a more user-friendly error page:
        # return render_template('errors/403.html'), 403
        # For now, returning JSON as it's simpler for this step.
        # A better UX would be to show an error page or redirect.
    return render_template('create_race.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
