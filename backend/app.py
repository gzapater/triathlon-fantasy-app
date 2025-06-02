import osMore actions
from flask import Flask, jsonify, request, redirect, url_for, send_from_directory
from backend.models import db, User, RoleEnum # Import RoleEnum
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.middleware.proxy_fix import ProxyFix # <--- Añade esta importación

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

with app.app_context():
    db.create_all()

# --- API Routes ---
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
    role_str = data.get('role') # Get role from request

    if not all([name, username, email, password]): return jsonify(message="Missing required fields"), 400

    # Validate role
    user_role = RoleEnum.USER # Default role
    if role_str and role_str.strip(): # If role is provided and not empty
        try:
            user_role = RoleEnum(role_str)
        except ValueError:
            allowed_roles = [r.value for r in RoleEnum]
            return jsonify(message=f"Invalid role '{role_str}'. Allowed roles are: {allowed_roles}"), 400
    
    if User.query.filter_by(username=username).first(): return jsonify(message="Username already exists"), 409
    if User.query.filter_by(email=email).first(): return jsonify(message="Email already exists"), 409
    
    new_user = User(name=name, username=username, email=email, role=user_role) # Add role to User constructor
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
    # current_user.role is an Enum object, access .value for the string
    return jsonify(
        username=current_user.username,
        role=current_user.role.value
    ), 200

@app.route('/api/admin/general_data', methods=['GET'])
@login_required
def general_admin_data():
    if current_user.role.value == RoleEnum.GENERAL_ADMIN.value:
        return jsonify(message="Data for General Admin"), 200
    else:
        return jsonify(message="Forbidden: You do not have the required permissions."), 403

@app.route('/api/admin/league_data', methods=['GET'])
@login_required
def league_admin_data():
    if current_user.role.value == RoleEnum.LEAGUE_ADMIN.value or \
       current_user.role.value == RoleEnum.GENERAL_ADMIN.value:
        return jsonify(message="Data for League Admin (accessible by League and General Admins)"), 200
    else:
        return jsonify(message="Forbidden: You do not have the required permissions."), 403

@app.route('/api/user/personal_data', methods=['GET'])
@login_required
def user_personal_data():
    if current_user.role.value == RoleEnum.USER.value:
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
    return send_from_directory('../frontend', 'login.html')

@app.route('/register')
def serve_register_page():
    return send_from_directory('../frontend', 'register.html')


@app.route('/Hello-world')
@login_required
def serve_hello_world_page():
        # AÑADE ESTO TEMPORALMENTE PARA DEPURACIÓN
    print(f"DEBUG: current_user.is_authenticated: {current_user.is_authenticated}")
    print(f"DEBUG: current_user.id: {current_user.id if current_user.is_authenticated else 'None'}")
    print(f"DEBUG: current_user.username: {current_user.username if current_user.is_authenticated else 'None'}")
    # FIN DEBUG
    # DEBUG COMPLETO
    print("=== HELLO-WORLD ENDPOINT DEBUG ===")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request cookies: {request.cookies}")
    print(f"Session data: {dict(session) if 'session' in globals() else 'No session'}")
    print(f"current_user.is_authenticated: {current_user.is_authenticated}")
    print(f"current_user.id: {current_user.id if current_user.is_authenticated else 'None'}")
    print(f"current_user.username: {current_user.username if current_user.is_authenticated else 'None'}")
    print(f"Request remote_addr: {request.remote_addr}")
    print(f"Request environ REMOTE_ADDR: {request.environ.get('REMOTE_ADDR')}")
    print(f"Request environ HTTP_X_FORWARDED_FOR: {request.environ.get('HTTP_X_FORWARDED_FOR')}")
    print("===================================")
    
    return send_from_directory('../frontend', 'index.html')

# --- Static File Serving Routes (for JS files in this case) ---
@app.route('/script.js')
def serve_script_js():
    return send_from_directory('../frontend', 'script.js')

@app.route('/login.js')
def serve_login_js():
    return send_from_directory('../frontend', 'login.js')

@app.route('/register.js')
def serve_register_js():
    return send_from_directory('../frontend', 'register.js')More actions

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
