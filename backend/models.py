from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt
import enum # Import enum
from flask_login import UserMixin # Import UserMixin

db = SQLAlchemy()

# Define an enum for user roles
class RoleEnum(enum.Enum):
    USER = 'user'
    LEAGUE_ADMIN = 'league_admin'
    GENERAL_ADMIN = 'general_admin'

class User(db.Model, UserMixin): # Inherit from UserMixin
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.Enum(RoleEnum), default=RoleEnum.USER, nullable=False) # Add role attribute
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def set_password(self, password):
        # Salt is generated automatically by bcrypt.hashpw
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.username}>'
