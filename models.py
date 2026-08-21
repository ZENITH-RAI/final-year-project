# models.py
from datetime import datetime

from extensions import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    estimates = db.relationship('Estimate', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    listings = db.relationship('Listing', foreign_keys='Listing.seller_id', backref='seller', lazy='dynamic')
    purchases = db.relationship('Order', foreign_keys='Order.buyer_id', backref='buyer', lazy='dynamic')

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
    km_driven = db.Column(db.Float, nullable=True)
    seller_type = db.Column(db.String(30), nullable=True)
    owner = db.Column(db.String(30), nullable=True)
    mileage = db.Column(db.Float, nullable=True)
    engine = db.Column(db.Float, nullable=True)
    max_power = db.Column(db.Float, nullable=True)
    seats = db.Column(db.Float, nullable=True)
    listing = db.relationship('Listing', backref='prediction', uselist=False)

    def __repr__(self):
        return f'<Estimate {self.brand} {self.model} ({self.year})>'


class Listing(db.Model):
    __tablename__ = 'listings'
    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey('estimates.id', ondelete='RESTRICT'), nullable=False, unique=True, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    price = db.Column(db.Numeric(14, 2), nullable=False)
    description = db.Column(db.Text, nullable=True)
    condition_notes = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(16), nullable=False, default='ACTIVE', index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    sold_at = db.Column(db.DateTime, nullable=True)
    reserved_at = db.Column(db.DateTime, nullable=True)
    images = db.relationship('ListingImage', backref='listing', lazy='select', cascade='all, delete-orphan', order_by='ListingImage.display_order')
    orders = db.relationship('Order', backref='listing', lazy='dynamic')
    buyer = db.relationship('User', foreign_keys=[buyer_id])


class ListingImage(db.Model):
    __tablename__ = 'listing_images'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id', ondelete='CASCADE'), nullable=False, index=True)
    image_path = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id', ondelete='RESTRICT'), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    status = db.Column(db.String(24), nullable=False, default='PENDING_PAYMENT', index=True)
    transaction_uuid = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    seller_payment_status = db.Column(db.String(20), nullable=False, default='PENDING')
    payment = db.relationship('Payment', backref='order', uselist=False, cascade='all, delete-orphan')


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    provider = db.Column(db.String(32), nullable=False, default='ESEWA')
    transaction_uuid = db.Column(db.String(64), nullable=False, unique=True, index=True)
    provider_transaction_code = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='INITIATED', index=True)
    raw_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)
