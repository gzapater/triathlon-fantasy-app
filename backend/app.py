import os # For path joining if needed, though send_from_directory handles relative paths
from flask import Flask, jsonify, request, redirect, url_for, send_from_directory # Updated imports
from backend.models import db, User
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = 'your_very_secret_and_random_key_please_change_me'

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://your_db_user:your_db_password@localhost:5432/your_db_name'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Flask-Login Configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'serve_login_page' # Crucial for @login_required redirection

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
    if not all([name, username, email, password]): return jsonify(message="Missing required fields"), 400
    if User.query.filter_by(username=username).first(): return jsonify(message="Username already exists"), 409
    if User.query.filter_by(email=email).first(): return jsonify(message="Email already exists"), 409
    new_user = User(name=name, username=username, email=email)
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
        return jsonify(message="Login successful", user_id=user.id, username=user.username), 200
    elif user and not user.is_active: return jsonify(message="Account disabled. Please contact support."), 403
    else: return jsonify(message="Invalid username or password"), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout_api():
    logout_user()
    return jsonify(message="Logout successful"), 200

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
    return send_from_directory('../frontend', 'register.js')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
