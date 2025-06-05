from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Text, Float # Added Text and Float
from datetime import datetime
import bcrypt
# Removed: import enum
from flask_login import UserMixin # Import UserMixin

db = SQLAlchemy()

# New Role Model
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False) 

    def __repr__(self):
        return f'<Role {self.name}>'

class User(db.Model, UserMixin): # Inherit from UserMixin
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Removed old role enum column
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False) # New Foreign Key
    role = db.relationship('Role', backref=db.backref('users', lazy=True)) # New Relationship
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


# RaceFormat Model
class RaceFormat(db.Model):
    __tablename__ = 'race_formats'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)  # e.g., "Triathlon", "Duathlon"

    def __repr__(self):
        return f'<RaceFormat {self.name}>'


# Segment Model
class Segment(db.Model):
    __tablename__ = 'segments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)  # e.g., "Swimming", "Cycling", "Running"

    def __repr__(self):
        return f'<Segment {self.name}>'


# Race Model
class Race(db.Model):
    __tablename__ = 'races'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(Text, nullable=True)
    race_format_id = db.Column(db.Integer, db.ForeignKey('race_formats.id'), nullable=False)
    race_format = db.relationship('RaceFormat', backref=db.backref('races', lazy=True))
    event_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(255), nullable=True)
    promo_image_url = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(255), default="Elite", nullable=False)
    gender_category = db.Column(db.String(255), nullable=False)  # e.g., "Masculino", "Femenino", "Ambos"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('races', lazy=True))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Race {self.title}>'


# RaceSegmentDetail Model
class RaceSegmentDetail(db.Model):
    __tablename__ = 'race_segment_details'
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    segment_id = db.Column(db.Integer, db.ForeignKey('segments.id'), nullable=False)
    distance_km = db.Column(Float, nullable=False)
    race = db.relationship('Race', backref=db.backref('segment_details', lazy=True))
    segment = db.relationship('Segment', backref=db.backref('race_details', lazy=True))

    def __repr__(self):
        return f'<RaceSegmentDetail race_id={self.race_id} segment_id={self.segment_id} distance_km={self.distance_km}>'


# Question Models

class QuestionType(db.Model):
    __tablename__ = 'question_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # e.g., 'FREE_TEXT', 'MULTIPLE_CHOICE', 'ORDERING'

    def __repr__(self):
        return f'<QuestionType {self.name}>'

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    race = db.relationship('Race', backref=db.backref('questions', lazy='dynamic')) # Changed to lazy='dynamic' for questions

    question_type_id = db.Column(db.Integer, db.ForeignKey('question_types.id'), nullable=False)
    question_type = db.relationship('QuestionType', backref=db.backref('questions', lazy=True))

    text = db.Column(Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Scoring fields - Nullable depending on question type
    max_score_free_text = db.Column(db.Integer, nullable=True)
    is_mc_multiple_correct = db.Column(db.Boolean, nullable=True) # True if checkboxes (multiple correct), False if radio (single correct)
    points_per_correct_mc = db.Column(db.Integer, nullable=True) # For MC multiple correct
    points_per_incorrect_mc = db.Column(db.Integer, nullable=True) # For MC multiple correct (e.g., -3)
    total_score_mc_single = db.Column(db.Integer, nullable=True) # For MC single correct
    points_per_correct_order = db.Column(db.Integer, nullable=True) # For Ordering
    bonus_for_full_order = db.Column(db.Integer, nullable=True) # For Ordering

    def __repr__(self):
        return f'<Question {self.id}: {self.text[:50]}...>'

class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    question = db.relationship('Question', backref=db.backref('options', lazy='dynamic', cascade="all, delete-orphan"))

    option_text = db.Column(db.String(500), nullable=False)
    is_correct_mc_single = db.Column(db.Boolean, default=False, nullable=True) # For MC single answer type
    is_correct_mc_multiple = db.Column(db.Boolean, default=False, nullable=True) # For MC multiple answer type
    correct_order_index = db.Column(db.Integer, nullable=True) # For Ordering questions

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<QuestionOption {self.id}: {self.option_text[:50]}... (QID: {self.question_id})>'
