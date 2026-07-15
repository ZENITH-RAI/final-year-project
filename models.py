# models.py
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to the Estimate model
    estimates = db.relationship('Estimate', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Estimate(db.Model):
    __tablename__ = 'estimates'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    fuel = db.Column(db.String(20), nullable=False)
    transmission = db.Column(db.String(20), nullable=False)
    predicted_price = db.Column(db.Float, nullable=False)
    min_price = db.Column(db.Float, nullable=False)
    max_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_bought = db.Column(db.Boolean, default=False)
    actual_price = db.Column(db.Float, nullable=True)

    # ------------------------------------------------------------
    # NEW COLUMNS – required for the model re‑training in mark_bought
    # Set nullable=True so existing records stay valid until you
    # backfill or re‑generate estimates.
    # ------------------------------------------------------------
    km_driven = db.Column(db.Float, nullable=True)
    seller_type = db.Column(db.String(30), nullable=True)
    owner = db.Column(db.String(30), nullable=True)
    mileage = db.Column(db.Float, nullable=True)      # in kmpl
    engine = db.Column(db.Float, nullable=True)       # in CC
    max_power = db.Column(db.Float, nullable=True)    # in bhp
    seats = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<Estimate {self.brand} {self.model} ({self.year})>'