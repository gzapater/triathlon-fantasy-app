from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Text, Float, ForeignKey, Enum as SQLAlchemyEnum # Added ForeignKey and Enum
import enum # Added enum
from datetime import datetime
import bcrypt
import uuid # Added for generating access codes
from flask_login import UserMixin

db = SQLAlchemy()

class RaceStatus(enum.Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    ARCHIVED = "archived"

class EventStatus(enum.Enum):
    PENDIENTE = "pendiente"
    VALIDADO = "validado"
    RECHAZADO = "rechazado"

# New Role Model
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<Role {self.code}>' # Changed from name to code for consistency

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    role = db.relationship('Role', backref=db.backref('users', lazy=True))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship for UserRaceRegistration
    registrations = db.relationship('UserRaceRegistration', backref='user', lazy=True, cascade="all, delete-orphan")
    answers = db.relationship('UserAnswer', backref='user', lazy=True, cascade="all, delete-orphan")
    scores = db.relationship('UserScore', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.username}>'


class RaceFormat(db.Model):
    __tablename__ = 'race_formats'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    def __repr__(self):
        return f'<RaceFormat {self.name}>'


class Segment(db.Model):
    __tablename__ = 'segments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    def __repr__(self):
        return f'<Segment {self.name}>'


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
    gender_category = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # --- AÑADIR ESTAS DOS LÍNEAS  para trical---
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    event = db.relationship("Event", back_populates="races")
    # --------------------------------------------
    user = db.relationship('User', backref=db.backref('created_races', lazy=True)) # Changed backref to created_races
    is_general = db.Column(db.Boolean, nullable=False, default=False)
    quiniela_close_date = db.Column(db.DateTime, nullable=True) # New field for Quiniela close date
    is_deleted = db.Column(db.Boolean, default=False, nullable=False) # For logical deletion
    status = db.Column(SQLAlchemyEnum(RaceStatus), default=RaceStatus.PLANNED, nullable=False) # New status field
    access_code = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())) # New access code field
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship for UserRaceRegistration
    registrations = db.relationship('UserRaceRegistration', backref='race', lazy=True, cascade="all, delete-orphan")
    segment_details = db.relationship('RaceSegmentDetail', backref='race', lazy=True, cascade="all, delete-orphan") # Added cascade
    questions = db.relationship('Question', backref='race', lazy='dynamic', cascade="all, delete-orphan") # Added cascade
    answers = db.relationship('UserAnswer', backref='race', lazy=True, cascade="all, delete-orphan")
    favorite_links = db.relationship('FavoriteLink', backref='race', lazy=True, cascade='all, delete-orphan')
    scores = db.relationship('UserScore', backref='race', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'race_format_name': self.race_format.name if self.race_format else None, # Changed here
            'race_format': {
                'id': self.race_format.id,
                'name': self.race_format.name
            } if self.race_format else None,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'event_date_formatted': self.event_date.strftime('%d %b %Y') if self.event_date else 'Fecha no disp.',
            'location': self.location,
            'promo_image_url': self.promo_image_url,
            'category': self.category,
            'gender_category': self.gender_category,
            'user_username': self.user.username if self.user else None,
            'is_general': self.is_general,
            'quiniela_close_date': self.quiniela_close_date.isoformat() if self.quiniela_close_date else None,
            'is_deleted': self.is_deleted, # Added for logical deletion
            'status': self.status.value if self.status else None, # Added status field
            'access_code': self.access_code, # Added access code
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Race {self.title}>'

class UserRaceRegistration(db.Model):
    __tablename__ = 'user_race_registrations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Unique constraint to prevent duplicate registrations
    __table_args__ = (db.UniqueConstraint('user_id', 'race_id', name='_user_race_uc'),)

    def __repr__(self):
        return f'<UserRaceRegistration user_id={self.user_id} race_id={self.race_id}>'


class UserScore(db.Model):
    __tablename__ = 'user_scores'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Unique constraint for user_id and race_id
    __table_args__ = (db.UniqueConstraint('user_id', 'race_id', name='_user_race_score_uc'),)

    def __repr__(self):
        return f'<UserScore user_id={self.user_id} race_id={self.race_id} score={self.score}>'


class UserFavoriteRace(db.Model):
    __tablename__ = 'user_favorite_races'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'race_id', name='_user_race_favorite_uc'),)

    user = db.relationship('User', backref=db.backref('favorite_races_assoc', lazy='dynamic')) # Changed backref name to avoid conflict
    race = db.relationship('Race', backref=db.backref('favored_by_users_assoc', lazy='dynamic')) # Changed backref name to avoid conflict

    def __repr__(self):
        return f'<UserFavoriteRace user_id={self.user_id} race_id={self.race_id}>'


class RaceSegmentDetail(db.Model):
    __tablename__ = 'race_segment_details'
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    segment_id = db.Column(db.Integer, db.ForeignKey('segments.id'), nullable=False)
    distance_km = db.Column(Float, nullable=False)
    # Removed explicit race relationship, covered by Race.segment_details backref
    segment = db.relationship('Segment', backref=db.backref('race_details', lazy=True))

    def __repr__(self):
        return f'<RaceSegmentDetail race_id={self.race_id} segment_id={self.segment_id} distance_km={self.distance_km}>'


class QuestionType(db.Model):
    __tablename__ = 'question_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    # description = db.Column(db.String(255), nullable=True) # Reverted: Removed description

    @classmethod
    def get_or_create(cls, name): # Reverted: Removed description from params
        instance = cls.query.filter_by(name=name).first()
        if instance:
            return instance, False
        else:
            instance = cls(name=name) # Reverted: Removed description from instantiation
            db.session.add(instance)
            db.session.commit()
            return instance, True

    def __repr__(self):
        return f'<QuestionType {self.name}>'

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    # Removed explicit race relationship, covered by Race.questions backref

    question_type_id = db.Column(db.Integer, db.ForeignKey('question_types.id'), nullable=False)
    question_type = db.relationship('QuestionType', backref=db.backref('questions', lazy=True))

    text = db.Column(Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    max_score_free_text = db.Column(db.Integer, nullable=True)
    is_mc_multiple_correct = db.Column(db.Boolean, nullable=True)
    points_per_correct_mc = db.Column(db.Integer, nullable=True)
    points_per_incorrect_mc = db.Column(db.Integer, nullable=True)
    total_score_mc_single = db.Column(db.Integer, nullable=True)
    points_per_correct_order = db.Column(db.Integer, nullable=True)
    bonus_for_full_order = db.Column(db.Integer, nullable=True)

    # Slider question type fields
    slider_unit = db.Column(db.String(50), nullable=True)
    slider_min_value = db.Column(db.Float, nullable=True)
    slider_max_value = db.Column(db.Float, nullable=True)
    slider_step = db.Column(db.Float, nullable=True)
    slider_points_exact = db.Column(db.Integer, nullable=True)
    slider_threshold_partial = db.Column(db.Float, nullable=True)
    slider_points_partial = db.Column(db.Integer, nullable=True)

    options = db.relationship('QuestionOption', backref='question', lazy='dynamic', cascade="all, delete-orphan") # Added cascade
    answers = db.relationship('UserAnswer', backref='question', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Question {self.id}: {self.text[:50]}...>'

class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    # Removed explicit question relationship, covered by Question.options backref

    option_text = db.Column(db.String(500), nullable=False)
    is_correct_mc_single = db.Column(db.Boolean, default=False, nullable=True)
    is_correct_mc_multiple = db.Column(db.Boolean, default=False, nullable=True)
    correct_order_index = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user_answers = db.relationship('UserAnswer', backref='selected_option', lazy=True)
    user_selections = db.relationship('UserAnswerMultipleChoiceOption', backref='question_option', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<QuestionOption {self.id}: {self.option_text[:50]}... (QID: {self.question_id})>'


# UserAnswer and UserAnswerMultipleChoiceOption Models

class UserAnswer(db.Model):
    __tablename__ = 'user_answers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer_text = db.Column(Text, nullable=True)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    slider_answer_value = db.Column(db.Float, nullable=True) # New field for slider answer
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships are defined in User, Race, Question, QuestionOption models
    # For selected_mc_options relationship:
    selected_mc_options = db.relationship('UserAnswerMultipleChoiceOption', backref='user_answer', lazy=True, cascade="all, delete-orphan")


    __table_args__ = (db.UniqueConstraint('user_id', 'question_id', name='_user_question_uc'),)

    def __repr__(self):
        return f'<UserAnswer id={self.id} user_id={self.user_id} question_id={self.question_id}>'


class UserAnswerMultipleChoiceOption(db.Model):
    __tablename__ = 'user_answer_multiple_choice_options'

    id = db.Column(db.Integer, primary_key=True)
    user_answer_id = db.Column(db.Integer, db.ForeignKey('user_answers.id'), nullable=False)
    question_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships are defined in UserAnswer and QuestionOption models

    __table_args__ = (db.UniqueConstraint('user_answer_id', 'question_option_id', name='_user_answer_option_uc'),)

    def __repr__(self):
        return f'<UserAnswerMultipleChoiceOption id={self.id} user_answer_id={self.user_answer_id} option_id={self.question_option_id}>'


# OfficialAnswer and OfficialAnswerMultipleChoiceOption Models

class OfficialAnswer(db.Model):
    __tablename__ = 'official_answers'

    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer_text = db.Column(Text, nullable=True)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    correct_slider_value = db.Column(db.Float, nullable=True) # New field for correct slider value
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    race = db.relationship('Race', backref=db.backref('official_answers', lazy=True, cascade="all, delete-orphan"))
    question = db.relationship('Question', backref=db.backref('official_answers', lazy=True, cascade="all, delete-orphan"))
    selected_option = db.relationship('QuestionOption', backref=db.backref('official_answers', lazy=True))
    official_selected_mc_options = db.relationship('OfficialAnswerMultipleChoiceOption', backref='official_answer', lazy=True, cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint('race_id', 'question_id', name='_race_question_uc'),)

    def __repr__(self):
        return f'<OfficialAnswer id={self.id} race_id={self.race_id} question_id={self.question_id}>'


class OfficialAnswerMultipleChoiceOption(db.Model):
    __tablename__ = 'official_answer_multiple_choice_options'

    id = db.Column(db.Integer, primary_key=True)
    official_answer_id = db.Column(db.Integer, db.ForeignKey('official_answers.id'), nullable=False)
    question_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    # The backref 'official_selected_mc_options' is already defined in OfficialAnswer.official_selected_mc_options
    # official_answer = db.relationship('OfficialAnswer', backref=db.backref('official_selected_mc_options', lazy=True))
    question_option = db.relationship('QuestionOption', backref=db.backref('official_answer_selections', lazy=True))

    __table_args__ = (db.UniqueConstraint('official_answer_id', 'question_option_id', name='_official_answer_option_uc'),)

    def __repr__(self):
        return f'<OfficialAnswerMultipleChoiceOption id={self.id} official_answer_id={self.official_answer_id} option_id={self.question_option_id}>'


class FavoriteLink(db.Model):
    __tablename__ = 'favorite_links'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(2048), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # The 'race' attribute is automatically created by the backref in Race.favorite_links
    # race = db.relationship('Race', backref=db.backref('race_favorite_links', lazy=True)) # Changed backref to avoid conflict

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'order': self.order,
            'race_id': self.race_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<FavoriteLink {self.title}>'

#--------------------------------------------#
#--- AÑADIR ESTE MODELO NUEVO para trical ---#
#--------------------------------------------#

class Event(db.Model):
    """
    Tabla de Eventos (Plantillas de TriCal).
    Contiene la información 'oficial' y curada de los eventos del mundo real.
    """
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    event_date = db.Column(db.Date, nullable=False)
    city = db.Column(db.String(100), nullable=True)
    province = db.Column(db.String(100), nullable=True, index=True)
    discipline = db.Column(db.String(50), nullable=True, index=True)
    distance = db.Column(db.String(100), nullable=True, index=True)
    source_url = db.Column(db.String(512), nullable=True)
    
    # Campos de Curación ("Puntuación TriCal")
    is_good_for_debutants = db.Column(db.Boolean, default=False, server_default='f')
    is_challenging = db.Column(db.Boolean, default=False, server_default='f')
    has_great_views = db.Column(db.Boolean, default=False, server_default='f')
    has_good_atmosphere = db.Column(db.Boolean, default=False, server_default='f')
    is_world_qualifier = db.Column(db.Boolean, default=False, server_default='f')

    # Nuevo campo para el estado del evento
    status = db.Column(SQLAlchemyEnum(EventStatus), default=EventStatus.PENDIENTE, nullable=False, server_default=EventStatus.PENDIENTE.value)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relación inversa: Un evento puede tener muchas 'Races' (quinielas) basadas en él
    races = db.relationship("Race", back_populates="event")

    def __repr__(self):
        return f'<Event {self.name}>'

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++ MODELOS PARA LAS LIGAS ++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# Tabla de asociación para la relación muchos a muchos entre Ligas y Carreras
league_races_table = db.Table('league_races',
    db.Column('league_id', db.Integer, db.ForeignKey('leagues.id'), primary_key=True),
    db.Column('race_id', db.Integer, db.ForeignKey('races.id'), primary_key=True),
    db.Column('added_at', db.DateTime, default=datetime.utcnow, nullable=False) # Opcional: para saber cuándo se añadió una carrera a la liga
)

class League(db.Model):
    __tablename__ = 'leagues'

    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String(255), index=True, nullable=False, unique=True) # Nombre único para la liga
    description = db.Column(db.Text, nullable=True) # Descripción opcional
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # Usuario que creó la liga

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False) # Para activar/desactivar ligas
    is_deleted = db.Column(db.Boolean, default=False, nullable=False) # Para borrado lógico

    # Relación con el usuario creador
    creator = db.relationship("User", backref=db.backref("created_leagues", lazy="dynamic"))

    # Relación muchos a muchos con Carreras (Races)
    # Las carreras que pertenecen a esta liga
    races = db.relationship("Race",
                            secondary=league_races_table,
                            # primaryjoin=(league_races_table.c.league_id == id), # No es necesario si las FK están bien definidas
                            # secondaryjoin=(league_races_table.c.race_id == Race.id), # No es necesario
                            backref=db.backref("member_of_leagues", lazy="dynamic"), # Carreras pueden pertenecer a múltiples ligas
                            lazy="dynamic") # Carga las carreras bajo demanda

    def __repr__(self):
        return f"<League {self.id}: {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'creator_id': self.creator_id,
            'creator_username': self.creator.username if self.creator else None,
            'is_active': self.is_active,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'race_ids': [race.id for race in self.races] # Lista de IDs de carreras en la liga
        }

# Asegurarse de que Race tenga la relación inversa si no se usó backref antes o para más control
# Si en Race.member_of_leagues (creado por el backref de League.races) es suficiente, no se necesita esto.
# Si quieres definirlo explícitamente en Race:
# Race.leagues = db.relationship("League",
#                               secondary=league_races_table,
#                               back_populates="races", # Si League.races usa back_populates
#                               lazy="dynamic")
# Sin embargo, el backref "member_of_leagues" ya debería crear esta colección en Race.

# Nota: El campo Race.status ya existe y es un SQLAlchemyEnum(RaceStatus)
# RaceStatus.PLANNED será usado para filtrar carreras elegibles para una liga.

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++ MODELOS ADICIONALES PARA PARTICIPANTES Y CÓDIGOS DE INVITACIÓN DE LIGA ++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class LeagueParticipant(db.Model):
    __tablename__ = 'league_participants'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    league_id = db.Column(db.Integer, db.ForeignKey('leagues.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('league_participations', lazy='dynamic', cascade="all, delete-orphan"))
    league = db.relationship('League', backref=db.backref('participants', lazy='dynamic', cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint('user_id', 'league_id', name='_user_league_uc'),)

    def __repr__(self):
        return f'<LeagueParticipant user_id={self.user_id} league_id={self.league_id}>'

class LeagueInvitationCode(db.Model):
    __tablename__ = 'league_invitation_codes'
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('leagues.id'), nullable=False)
    code = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    expires_at = db.Column(db.DateTime, nullable=True) # Puede ser nulo para códigos que no expiran
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    league = db.relationship('League', backref=db.backref('invitation_codes', lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<LeagueInvitationCode code={self.code} league_id={self.league_id} active={self.is_active}>'

# Actualizar relaciones en User y League si es necesario (backrefs ya lo hacen implícitamente)
# User.league_participations (ya creado por backref)
# League.participants (ya creado por backref)
# League.invitation_codes (ya creado por backref)
