import pandas as pd
import numpy as np
import hmac
import os
import secrets
import csv
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from io import StringIO
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, flash, redirect, render_template, request, session, url_for, abort, Response, jsonify
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_migrate import Migrate
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
from threading import Lock                         
from extensions import db
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

def get_nepal_time():
    """Returns the current naive datetime converted to Nepal Standard Time (UTC+5:45)."""
    nepal_tz = timezone(timedelta(hours=5, minutes=45))
    return datetime.now(nepal_tz).replace(tzinfo=None)

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-development-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:Messi.100@localhost:5432/car_resell_db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

# Set this to the public HTTPS address of the deployed application (for
# example, https://example.vercel.app). eSewa must be able to redirect the
# customer back to this address after checkout.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

db.init_app(app)
migrate = Migrate(app, db)

from models import User, Estimate, Listing, ListingImage, Order, Payment
from services.esewa_service import (
    EsewaConfigurationError, EsewaVerificationError, check_transaction_status,
    config as esewa_config, create_payment_payload, decode_success_response, money, verify_response_signature,
)

DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@gmail.com").strip().lower()
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin@123")

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please log in to view your profile."
login_manager.login_message_category = "error"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]

def csrf_is_valid():
    expected = session.get("_csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def payment_callback_url(endpoint, **values):
    """Build a public callback URL for eSewa without trusting proxy headers."""
    path = url_for(endpoint, **values)
    if not PUBLIC_BASE_URL:
        return url_for(endpoint, _external=True, **values)

    parsed = urlsplit(PUBLIC_BASE_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise EsewaConfigurationError(
            "PUBLIC_BASE_URL must be an absolute base URL, for example https://example.com."
        )
    return f"{PUBLIC_BASE_URL}{path}"

def safe_next_url(next_url):
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for("profile")

def ensure_default_admin():
    """Create the initial administrator without requiring a signup flow."""
    admin = User.query.filter(func.lower(User.email) == DEFAULT_ADMIN_EMAIL).first()
    if admin is not None:
        if not admin.is_admin:
            admin.is_admin = True
            db.session.commit()
        return admin

    admin = User(
        name="Car Resell Price Prediction and Recommendation System Administrator",
        email=DEFAULT_ADMIN_EMAIL,
        is_admin=True,
    )
    admin.set_password(DEFAULT_ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    return admin

app.jinja_env.globals["csrf_token"] = csrf_token

BASE_DIR = Path(__file__).resolve().parent

CURRENT_YEAR = datetime.now().year
pipeline_instance = None
model_instance = None
model_metrics = {}
reference_data = None           
feature_importances = []
training_samples_count = 0
feature_count = 0
vehicle_validation_rules = {}
vehicle_dataset_catalog = {}
vehicle_static_catalog = {}

model_lock = Lock()

def build_vehicle_validation_rules(df):
    rules = {}
    fields = {
        'km_driven': {
            'label': 'Kilometers driven',
            'unit': 'km',
            'min_quantile': 0.0,
            'max_quantile': 0.99,
            'min_floor': 0,
            'integer': True,
        },
        'mileage': {
            'label': 'Mileage',
            'unit': 'kmpl',
            'min_quantile': 0.01,
            'max_quantile': 0.99,
        },
        'engine': {
            'label': 'Engine size',
            'unit': 'CC',
            'min_quantile': 0.01,
            'max_quantile': 0.99,
        },
        'max_power': {
            'label': 'Maximum power',
            'unit': 'bhp',
            'min_quantile': 0.01,
            'max_quantile': 0.99,
        },
    }

    for name, config in fields.items():
        values = pd.to_numeric(df[name], errors='coerce').dropna()
        values = values[values > 0] if name != 'km_driven' else values[values >= 0]
        if values.empty:
            continue

        min_value = float(values.quantile(config['min_quantile']))
        max_value = float(values.quantile(config['max_quantile']))
        if 'min_floor' in config:
            min_value = max(float(config['min_floor']), min_value)

        rules[name] = {
            'label': config['label'],
            'unit': config['unit'],
            'min': round(min_value, 1),
            'max': round(max_value, 1),
            'average': round(float(values.mean()), 1),
            'integer': config.get('integer', False),
        }

    return rules

def build_vehicle_catalog(df):
    catalog_df = df.copy()
    catalog_df['brand'] = catalog_df['brand'].astype(str).str.strip()
    catalog_df['model'] = catalog_df['model'].astype(str).str.strip()
    catalog_df = catalog_df[(catalog_df['brand'] != '') & (catalog_df['model'] != '')]

    brands = sorted(catalog_df['brand'].dropna().unique().tolist())
    models_by_brand = {}
    for brand in brands:
        models = sorted(catalog_df.loc[catalog_df['brand'] == brand, 'model'].dropna().unique().tolist())
        if "Other" in models:
            models = [model for model in models if model != "Other"] + ["Other"]
        else:
            models.append("Other")
        models_by_brand[brand] = models

    return {
        "source": "dataset",
        "sourceFile": "UsedCars.csv",
        "rowCount": int(len(catalog_df)),
        "brandCount": len(brands),
        "brands": brands,
        "modelsByBrand": models_by_brand,
    }

def load_static_vehicle_catalog():
    catalog_path = BASE_DIR / "static" / "data" / "vehicle_catalog.json"
    try:
        with open(catalog_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"brands": [], "modelsByBrand": {}}

def normalize_catalog_value(value):
    return str(value or "").strip().lower()

def find_catalog_brand(catalog, brand):
    wanted = normalize_catalog_value(brand)
    for candidate in catalog.get("brands", []):
        if normalize_catalog_value(candidate) == wanted:
            return candidate
    return None

def get_catalog_models(catalog, brand):
    matched_brand = find_catalog_brand(catalog, brand)
    if not matched_brand:
        return []
    models = catalog.get("modelsByBrand", {}).get(matched_brand, [])
    return models if isinstance(models, list) else []

def find_catalog_model(models, model):
    wanted = normalize_catalog_value(model)
    for candidate in models:
        if normalize_catalog_value(candidate) == wanted:
            return candidate
    return None

def validate_catalog_vehicle(brand, model):
    dataset_brand = find_catalog_brand(vehicle_dataset_catalog, brand)
    static_brand = find_catalog_brand(vehicle_static_catalog, brand)
    canonical_brand = dataset_brand or static_brand
    if not canonical_brand:
        return None, None, "Choose a brand from the suggestions."

    dataset_models = get_catalog_models(vehicle_dataset_catalog, canonical_brand)
    static_models = get_catalog_models(vehicle_static_catalog, canonical_brand)
    available_models = dataset_models + [
        item for item in static_models
        if normalize_catalog_value(item) not in {normalize_catalog_value(m) for m in dataset_models}
    ]
    canonical_model = find_catalog_model(available_models, model)
    if not canonical_model:
        return canonical_brand, None, "Choose a valid model for the selected brand."

    return canonical_brand, canonical_model, None

class FullPipeline:
    def __init__(self):
        self.numeric_cols = []
        self.mean_std = {}
        self.fill_values = {}
        self.feature_columns = []
        self.luxury_brands = ['BMW', 'Audi', 'Mercedes-Benz', 'Jaguar', 'Land', 'Volvo']

    def feature_engineering(self, df):
        df = df.copy()
        df['car_age'] = CURRENT_YEAR - df['year']
        df['km_per_year'] = df['km_driven'] / (df['car_age'] + 1)
        df['is_7_seater'] = (df['seats'] >= 7).astype(int)
        df['engine_power_ratio'] = df['engine'] / (df['max_power'] + 1)
        df['power_per_cc'] = df['max_power'] / (df['engine'] + 1)
        df['is_luxury'] = df['brand'].isin(self.luxury_brands).astype(int)
        return df

    def fit(self, df):
        df = self.feature_engineering(df)
        df = df.drop(columns=['selling_price'], errors='ignore')
        df = pd.get_dummies(df, drop_first=True)
        self.numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        self.fill_values = df.mean(numeric_only=True)
        df = df.fillna(self.fill_values)
        
        for col in self.numeric_cols:
            mean = df[col].mean()
            std = df[col].std()
            if std == 0: std = 1
            self.mean_std[col] = (mean, std)
            df[col] = (df[col] - mean) / std
            
        self.feature_columns = df.columns.tolist()
        return df

    def transform(self, df):
        df = self.feature_engineering(df)
        df = pd.get_dummies(df, drop_first=True)
        
        missing_cols = list(set(self.feature_columns) - set(df.columns))
        if missing_cols:
            df_missing = pd.DataFrame(0, index=df.index, columns=missing_cols)
            df = pd.concat([df, df_missing], axis=1)
            
        df = df[self.feature_columns].copy()
        
        for col in self.numeric_cols:
            mean, std = self.mean_std[col]
            df[col] = (df[col] - mean) / std
        return df

class SGDRegressor:
    def __init__(self, lr=0.01, epochs=450, l2=0.01, batch_size=32):
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self.batch_size = batch_size
        self.coef_ = None
        self.intercept_ = 0

    def partial_fit(self, X, y):
        """Updates the model's weights using a single new, corrected data point."""
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        
        y_pred = np.dot(X, self.coef_) + self.intercept_
        error = y_pred - y
        
        grad_w = 2 * np.dot(X.T, error) + 2 * self.l2 * self.coef_
        grad_b = 2 * np.mean(error)
        
        fine_tune_lr = self.lr * 0.05 
        
        self.coef_ -= fine_tune_lr * grad_w
        self.intercept_ -= fine_tune_lr * grad_b
        
    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        n, m = X.shape
        self.coef_ = np.zeros(m)

        for epoch in range(self.epochs):
            lr = self.lr / (1 + 0.01 * epoch)
            indices = np.random.permutation(n)
            X = X[indices]
            y = y[indices]

            for start in range(0, n, self.batch_size):
                end = start + self.batch_size
                X_batch = X[start:end]
                y_batch = y[start:end]
                y_pred = np.dot(X_batch, self.coef_) + self.intercept_
                error = y_pred - y_batch
                grad_w = (2 / len(X_batch)) * np.dot(X_batch.T, error) + 2 * self.l2 * self.coef_
                grad_b = 2 * np.mean(error)
                self.coef_ -= lr * grad_w
                self.intercept_ -= lr * grad_b

    def predict(self, X):
        X = np.asarray(X, dtype=np.float64)
        return np.dot(X, self.coef_) + self.intercept_
  
def initialize_and_train():
    global pipeline_instance, model_instance, model_metrics, reference_data
    global feature_importances, training_samples_count, feature_count
    global vehicle_validation_rules, vehicle_dataset_catalog, vehicle_static_catalog
    
    print("Loading data and training model... This may take a moment.")
    np.random.seed(42)
    df = pd.read_csv(BASE_DIR / "UsedCars.csv")
    df['selling_price'] = df['selling_price'] * 2.2
    df = df.drop(columns=['torque'], errors='ignore')
    df = df.drop_duplicates()
    
    df['brand'] = df['name'].str.split().str[0]
    df['model'] = df['name'].str.split().str[1:].str.join(' ')
    vehicle_dataset_catalog = build_vehicle_catalog(df)
    vehicle_static_catalog = load_static_vehicle_catalog()
    
    for col, suffix in [('mileage', ' kmpl'), ('engine', ' CC'), ('max_power', ' bhp')]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(suffix, '', regex=False), errors='coerce')
        
    q1 = df['selling_price'].quantile(0.01)
    q99 = df['selling_price'].quantile(0.99)
    df = df[(df['selling_price'] >= q1) & (df['selling_price'] <= q99)]
    
    top_models = df['model'].value_counts().head(25).index
    df['model'] = df['model'].apply(lambda x: x if x in top_models else "Other")
    df['brand_model'] = df['brand'] + "_" + df['model']
    
    reference_data = df.copy()
    vehicle_validation_rules = build_vehicle_validation_rules(reference_data)
    
    train = df.sample(frac=0.8, random_state=42)
    test = df.drop(train.index)

    pipeline_instance = FullPipeline()
    X_train = pipeline_instance.fit(train)
    X_test = pipeline_instance.transform(test)

    y_train = np.log1p(train['selling_price'])
    y_test = np.log1p(test['selling_price'])

    model_instance = SGDRegressor()
    model_instance.fit(X_train, y_train)

    y_pred_log = model_instance.predict(X_test)
    y_pred = np.expm1(y_pred_log)
    y_true = np.expm1(y_test)

    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)
    mae = np.mean(np.abs(y_true - y_pred))
    r2 = 1 - (np.sum((y_true - y_pred) ** 2) / np.sum((y_true - np.mean(y_true)) ** 2))
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

    model_metrics = {
        'R2': round(r2, 4),
        'MAE': round(mae, 2),
        'MSE': round(mse, 2),
        'RMSE': round(rmse, 2),
        'MAPE': f"{round(mape, 2)}%"
    }
    
    training_samples_count = len(train)
    feature_count = len(pipeline_instance.feature_columns)
    
    importances = list(zip(pipeline_instance.feature_columns, model_instance.coef_))
    importances.sort(key=lambda x: abs(x[1]), reverse=True)
    feature_importances = importances[:10]

    print("Training complete! Server ready.")

initialize_and_train()

def render_page(template_name, active_page, **context):
    context["active_page"] = active_page
    return render_template(template_name, **context)

def render_estimate_page(**context):
    context.setdefault("metrics", model_metrics)
    context.setdefault("price", None)
    context.setdefault("error", None)
    context.setdefault("form_data", {})
    context["vehicle_validation_rules"] = vehicle_validation_rules
    context["current_year"] = CURRENT_YEAR 
    return render_page('estimate.html', 'estimate', **context)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
LISTING_STATUSES = {'ACTIVE', 'RESERVED', 'SOLD', 'REMOVED'}


def listing_image_url(image):
    return url_for('static', filename=image.image_path) if image else None


def validate_listing_form():
    location = request.form.get('location', '').strip()
    phone = request.form.get('contact_phone', '').strip()
    description = request.form.get('description', '').strip()
    condition_notes = request.form.get('condition_notes', '').strip()
    errors = []
    if not location or len(location) > 120:
        errors.append('Enter a location of 120 characters or fewer.')
    if not phone or len(phone) > 30 or not all(char.isdigit() or char in '+- ()' for char in phone):
        errors.append('Enter a valid contact phone number.')
    if len(description) > 2000 or len(condition_notes) > 1000:
        errors.append('Description or condition notes are too long.')
    return errors, location, phone, description, condition_notes


def save_listing_images(listing, files):
    saved = []
    upload_dir = BASE_DIR / 'static' / 'uploads' / 'listings'
    upload_dir.mkdir(parents=True, exist_ok=True)
    for display_order, image in enumerate(files):
        if not image or not image.filename:
            continue
        filename = secure_filename(image.filename)
        extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError('Images must be JPG, PNG, or WebP files.')
        # A browser MIME type is not authoritative, but rejecting non-images adds a useful boundary.
        if image.mimetype and not image.mimetype.startswith('image/'):
            raise ValueError('Only image uploads are allowed.')
        unique_name = f'{uuid4().hex}.{extension}'
        image.save(upload_dir / unique_name)
        saved.append(ListingImage(listing=listing, image_path=f'uploads/listings/{unique_name}', display_order=display_order))
    return saved


def release_listing_if_pending(order, payment_status, order_status='FAILED'):
    """Release a vehicle only when this unfinished order still owns the reservation."""
    order.status = order_status
    if order.payment is not None:
        order.payment.status = payment_status
    if order.listing.status == 'RESERVED' and order.listing.buyer_id is None:
        order.listing.status = 'ACTIVE'
        order.listing.reserved_at = None


def status_field(payload, *names):
    for name in names:
        if name in payload:
            return payload[name]
    return None


def normalized_esewa_status(status):
    """Normalize the minor spelling variants used by payment providers."""
    value = str(status or '').strip().upper()
    return 'CANCELED' if value == 'CANCELLED' else value


def validate_esewa_status_for_order(order, status_data):
    """Ensure eSewa's server-to-server status response belongs to this order."""
    settings = esewa_config()
    provider_status = normalized_esewa_status(status_data.get('status'))
    provider_product = str(status_field(status_data, 'product_code', 'scd') or '')
    provider_transaction = str(status_field(status_data, 'transaction_uuid', 'pid') or '')
    provider_amount = status_field(status_data, 'total_amount', 'totalAmount')

    if provider_product != settings['product_code']:
        raise EsewaVerificationError('The eSewa merchant code does not match this order.')
    if provider_transaction != order.transaction_uuid:
        raise EsewaVerificationError('The eSewa transaction ID does not match this order.')
    if money(provider_amount) != money(order.amount):
        raise EsewaVerificationError('The eSewa payment amount does not match this order.')
    return provider_status


def save_pending_payment_status(order_id, provider_status, status_data):
    """Persist a verified non-final eSewa result without changing ownership."""
    db.session.rollback()
    try:
        order = Order.query.filter_by(id=order_id).with_for_update().one()
        if order.status == 'PENDING_PAYMENT' and order.payment:
            order.payment.status = provider_status or 'PENDING'
            order.payment.raw_response = json.dumps({'status_check': status_data}, default=str)
        db.session.commit()
        return order
    except Exception:
        db.session.rollback()
        raise


def finalize_verified_payment(order_id, status_data, callback_data=None):
    """Idempotently mark an order paid after a verified eSewa status response."""
    # Flask-Login may already have opened a SQLAlchemy transaction while loading
    # current_user. Start this critical section from a clean transaction state.
    db.session.rollback()
    try:
        order = Order.query.filter_by(id=order_id).with_for_update().one()
        listing = Listing.query.filter_by(id=order.listing_id).with_for_update().one()
        payment = Payment.query.filter_by(order_id=order.id).with_for_update().one()

        if order.status == 'PAID' and payment.status == 'COMPLETE' and listing.status == 'SOLD':
            db.session.commit()
            return order

        if order.status != 'PENDING_PAYMENT' or listing.status != 'RESERVED':
            raise EsewaVerificationError('This order is no longer eligible for payment confirmation.')

        provider_status = validate_esewa_status_for_order(order, status_data)
        if provider_status != 'COMPLETE':
            raise EsewaVerificationError(f'eSewa payment is {provider_status or "not complete"}.')

        if callback_data is not None:
            settings = esewa_config()
            callback_amount = status_field(callback_data, 'total_amount')
            if str(callback_data.get('transaction_uuid', '')) != order.transaction_uuid:
                raise EsewaVerificationError('The eSewa callback transaction does not match this order.')
            if str(callback_data.get('product_code', '')) != settings['product_code']:
                raise EsewaVerificationError('The eSewa callback merchant code does not match this order.')
            if money(callback_amount) != money(order.amount):
                raise EsewaVerificationError('The eSewa callback amount does not match this order.')

        now = get_nepal_time()
        payment.status = 'COMPLETE'
        payment.provider_transaction_code = str(
            status_field(status_data, 'ref_id', 'refId')
            or (callback_data or {}).get('transaction_code')
            or ''
        )[:100] or None
        payment.raw_response = json.dumps(
            {'callback': callback_data, 'status_check': status_data}, default=str
        )
        payment.verified_at = now
        order.status = 'PAID'
        order.paid_at = now
        listing.status = 'SOLD'
        listing.buyer_id = order.buyer_id
        listing.sold_at = now
        listing.reserved_at = None
        db.session.commit()
        return order
    except Exception:
        db.session.rollback()
        raise

def find_similar_cars(user_input, pred_price, top_n=5):
    if reference_data is None or reference_data.empty:
        return []
    
    df = reference_data.copy()
    
   
    df = df[(df['brand'] == user_input['brand']) & 
            (df['fuel'] == user_input['fuel'])]
    
    if len(df) == 0:
        df = reference_data[(reference_data['fuel'] == user_input['fuel']) &
                            (reference_data['transmission'] == user_input['transmission'])].copy()

    df['sim_score'] = (
        abs(df['year'] - user_input['year']) * 1000 + 
        abs(df['engine'] - user_input['engine']) * 10 +
        abs(df['selling_price'] - pred_price) * 0.1
    )
    
    recommendations = df.sort_values('sim_score').head(top_n)
    
    results = []
    for _, row in recommendations.iterrows():
        diff = row['selling_price'] - pred_price
        results.append({
            'name': row.get('name', f"{row['brand']} {row['model']}"),
            'year': row['year'],
            'mileage': row.get('mileage', 'N/A'),
            'fuel': row['fuel'],
            'transmission': row['transmission'],
            'actual_price': f"NPR {int(row['selling_price']):,}",
            'diff': f"+NPR {int(diff):,}" if diff > 0 else f"-NPR {abs(int(diff)):,}"
        })
    return results

def record_purchase(estimate, actual_price):
    """Store a completed purchase and use the confirmed value for future learning."""
    estimate.is_bought = True
    estimate.actual_price = actual_price
    db.session.commit()

    try:
        car_data = {
            'year': estimate.year, 'km_driven': estimate.km_driven,
            'fuel': estimate.fuel, 'seller_type': estimate.seller_type,
            'transmission': estimate.transmission, 'owner': estimate.owner,
            'mileage': estimate.mileage, 'engine': estimate.engine,
            'max_power': estimate.max_power, 'seats': estimate.seats,
            'brand': estimate.brand, 'model': estimate.model,
        }
        if any(value is None for value in car_data.values()):
            raise AttributeError('Vehicle specifications are incomplete')

        user_df = pd.DataFrame([car_data])
        user_df['brand_model'] = user_df['brand'] + '_' + user_df['model']
        with model_lock:
            X_new = pipeline_instance.transform(user_df)
            model_instance.partial_fit(X_new, [np.log1p(actual_price / 2.2)])

        with open(BASE_DIR / "UsedCars.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                f"{estimate.brand} {estimate.model}", estimate.year, actual_price / 2.2,
                estimate.km_driven, estimate.fuel, estimate.seller_type,
                estimate.transmission, estimate.owner, f"{estimate.mileage} kmpl",
                f"{estimate.engine} CC", f"{estimate.max_power} bhp", "", estimate.seats,
            ])
        return True
    except (AttributeError, ValueError) as error:
        print(f"Model retraining skipped: {error}")
        return False

def format_rule_value(value):
    if float(value).is_integer():
        return str(int(value))
    return str(value)

def validate_estimate_form(form_data):
    errors = {}
    allowed_choices = {
        'fuel': {'CNG', 'Petrol', 'Diesel', 'LPG'},
        'transmission': {'Manual', 'Automatic'},
        'seller_type': {'Individual', 'Dealer', 'Trustmark Dealer'},
        'owner': {'First Owner', 'Second Owner', 'Third Owner', 'Fourth & Above Owner'},
        'seats': {'4', '6', '7'},
    }

    for field in ['brand', 'model']:
        if not form_data.get(field, '').strip():
            errors[field] = f"Enter a {field}."

    if 'brand' not in errors and 'model' not in errors:
        brand, model, catalog_error = validate_catalog_vehicle(
            form_data.get('brand', ''),
            form_data.get('model', '')
        )
        if catalog_error:
            errors['model' if brand else 'brand'] = catalog_error
        else:
            form_data['brand'] = brand
            form_data['model'] = model

    try:
        year = int(form_data.get('year', ''))
        # This condition and message control the red text
        if year < 1980 or year > 2026:
            errors['year'] = "Use a year between 1980 and 2026." 
    except (TypeError, ValueError):
        errors['year'] = "Enter a valid manufacturing year."

    for field, choices in allowed_choices.items():
        if form_data.get(field, '') not in choices:
            errors[field] = "Choose a valid option."

    for field, rule in vehicle_validation_rules.items():
        raw_value = form_data.get(field, '').strip()
        if not raw_value:
            errors[field] = f"Enter {rule['label'].lower()}."
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            errors[field] = f"{rule['label']} must be a number."
            continue

        if rule.get('integer') and not value.is_integer():
            errors[field] = f"{rule['label']} must be a whole number."
            continue

        if value < rule['min'] or value > rule['max']:
            errors[field] = (
                f"{rule['label']} should be between {format_rule_value(rule['min'])} "
                f"and {format_rule_value(rule['max'])} {rule['unit']}."
            )

    return errors

@app.route('/', methods=['GET'])
def index():
    return render_page('index.html', 'home', metrics=model_metrics, price=None)

@app.route('/about')
def about():
    return render_page('about.html', 'about')

@app.route('/metrics')
def metrics():
    labels = [f[0] for f in feature_importances]
    data = [round(f[1], 4) for f in feature_importances]
    
    return render_page('metrics.html', 'metrics', 
                       metrics=model_metrics, 
                       samples=training_samples_count,
                       features=feature_count,
                       chart_labels=labels,
                       chart_data=data)

@app.route('/api/vehicle-catalog')
def vehicle_catalog_api():
    if not vehicle_dataset_catalog:
        return jsonify({
            "source": "dataset",
            "brands": [],
            "modelsByBrand": {},
            "brandCount": 0,
            "rowCount": 0,
        })
    return jsonify(vehicle_dataset_catalog)

@app.route('/estimate/<int:estimate_id>/buy', methods=['POST'])
@login_required
def mark_bought(estimate_id):
    estimate = Estimate.query.get_or_404(estimate_id)
    
    if estimate.user_id != current_user.id:
        abort(403)
    if not csrf_is_valid():
        flash('Your purchase form expired. Please try again.', 'error')
        return redirect(url_for('profile'))
    
    actual_price = request.form.get('actual_price', type=float)
    
    if actual_price and actual_price > 0:
        learned = record_purchase(estimate, actual_price)
        flash('Purchase recorded! The AI model has learned from your data.' if learned else 'Purchase saved, but model could not update (missing vehicle specs).', 'success')

    else:
        flash('Please enter a valid price.', 'error')
        
    return redirect(url_for('profile'))

@app.route('/marketplace')
def marketplace():
    query = Listing.query.join(Estimate).filter(Listing.status == 'ACTIVE')
    filters = {key: request.args.get(key, '').strip() for key in ('brand', 'model', 'fuel', 'transmission', 'year', 'location', 'min_price', 'max_price', 'sort')}
    if filters['brand']:
        query = query.filter(Estimate.brand.ilike(f"%{filters['brand']}%"))
    if filters['model']:
        query = query.filter(Estimate.model.ilike(f"%{filters['model']}%"))
    if filters['fuel']:
        query = query.filter(Estimate.fuel == filters['fuel'])
    if filters['transmission']:
        query = query.filter(Estimate.transmission == filters['transmission'])
    if filters['year'].isdigit():
        query = query.filter(Estimate.year == int(filters['year']))
    if filters['location']:
        query = query.filter(Listing.location.ilike(f"%{filters['location']}%"))
    if filters['min_price']:
        try:
            query = query.filter(Listing.price >= Decimal(filters['min_price']))
        except InvalidOperation:
            flash('Ignore invalid minimum price.', 'error')
    if filters['max_price']:
        try:
            query = query.filter(Listing.price <= Decimal(filters['max_price']))
        except InvalidOperation:
            flash('Ignore invalid maximum price.', 'error')
    sort_options = {
        'price_asc': Listing.price.asc(), 'price_desc': Listing.price.desc(),
        'year_desc': Estimate.year.desc(), 'newest': Listing.created_at.desc(),
    }
    listings = query.order_by(sort_options.get(filters['sort'], Listing.created_at.desc())).all()
    return render_page('marketplace.html', 'marketplace', listings=listings, filters=filters)


@app.route('/marketplace/<int:listing_id>')
def listing_detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    buyer_order = None
    if current_user.is_authenticated:
        buyer_order = (
            Order.query.filter_by(listing_id=listing.id, buyer_id=current_user.id)
            .filter(Order.status.in_(['PENDING_PAYMENT', 'PAID']))
            .order_by(Order.created_at.desc())
            .first()
        )
    if listing.status != 'ACTIVE':
        can_view = False
        if current_user.is_authenticated:
            can_view = (
                current_user.is_admin
                or current_user.id in {listing.seller_id, listing.buyer_id}
                or buyer_order is not None
            )
        if not can_view:
            abort(404)
    return render_page('listing_detail.html', 'marketplace', listing=listing, buyer_order=buyer_order)


@app.route('/sell/<int:prediction_id>', methods=['GET', 'POST'])
@login_required
def sell_prediction(prediction_id):
    estimate = Estimate.query.get_or_404(prediction_id)
    if estimate.user_id != current_user.id:
        abort(403)
    existing = Listing.query.filter_by(prediction_id=estimate.id).first()
    if existing:
        flash('This prediction already has a marketplace listing.', 'info')
        return redirect(url_for('listing_detail', listing_id=existing.id))
    if request.method == 'POST':
        if not csrf_is_valid():
            flash('Your listing form expired. Please try again.', 'error')
            return redirect(url_for('sell_prediction', prediction_id=estimate.id))
        errors, location, phone, description, condition_notes = validate_listing_form()
        images = [image for image in request.files.getlist('images') if image and image.filename]
        if len(images) > 6:
            errors.append('Add at most six car images.')
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_page('sell_listing.html', 'profile', estimate=estimate, form_data=request.form)
        listing = Listing(prediction_id=estimate.id, seller_id=current_user.id, price=Decimal(str(estimate.predicted_price)).quantize(Decimal('0.01')), location=location, contact_phone=phone, description=description or None, condition_notes=condition_notes or None, status='ACTIVE')
        try:
            db.session.add(listing)
            db.session.flush()
            db.session.add_all(save_listing_images(listing, images))
            db.session.commit()
        except (SQLAlchemyError, ValueError) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error, ValueError) else 'Your listing could not be published. Please try again.', 'error')
            return render_page('sell_listing.html', 'profile', estimate=estimate, form_data=request.form)
        flash('Your car is now listed in the marketplace.', 'success')
        return redirect(url_for('listing_detail', listing_id=listing.id))
    return render_page('sell_listing.html', 'profile', estimate=estimate, form_data={})


@app.route('/listing/<int:listing_id>/buy', methods=['POST'])
@login_required
def buy_listing(listing_id):
    """Create one marketplace order and redirect the buyer to eSewa."""
    if not csrf_is_valid():
        flash('Your checkout form expired. Please try again.', 'error')
        return redirect(url_for('listing_detail', listing_id=listing_id))

    try:
        # Validate merchant configuration before reserving a vehicle.
        esewa_config()

        # current_user can trigger SQLAlchemy autobegin. Clear that read-only
        # transaction before taking the row lock used to prevent double buying.
        db.session.rollback()
        listing = Listing.query.filter_by(id=listing_id).with_for_update().one_or_none()
        if listing is None:
            abort(404)
        if listing.seller_id == current_user.id:
            db.session.rollback()
            flash('You cannot purchase your own listing.', 'error')
            return redirect(url_for('listing_detail', listing_id=listing.id))
        if listing.status != 'ACTIVE':
            db.session.rollback()
            flash('This car is no longer available for checkout.', 'info')
            return redirect(url_for('marketplace'))

        transaction_uuid = f'CRPP-{uuid4().hex[:27]}'
        order = Order(
            listing_id=listing.id,
            buyer_id=current_user.id,
            seller_id=listing.seller_id,
            amount=listing.price,
            status='PENDING_PAYMENT',
            transaction_uuid=transaction_uuid,
        )
        payment = Payment(
            order=order,
            provider='ESEWA',
            transaction_uuid=transaction_uuid,
            amount=listing.price,
            status='AWAITING_ESEWA_LOGIN',
        )
        listing.status = 'RESERVED'
        listing.reserved_at = get_nepal_time()
        db.session.add_all([order, payment])
        db.session.flush()  # gives order.id for the failure callback URL

        payment_url, payload = create_payment_payload(
            order,
            payment_callback_url('esewa_success'),
            payment_callback_url('esewa_failure', order_id=order.id),
        )
        db.session.commit()
    except EsewaConfigurationError as error:
        db.session.rollback()
        flash(str(error), 'error')
        return redirect(url_for('listing_detail', listing_id=listing_id))
    except SQLAlchemyError:
        db.session.rollback()
        flash('Checkout could not be started. Please try again.', 'error')
        return redirect(url_for('listing_detail', listing_id=listing_id))

    return render_page(
        'payment_redirect.html',
        'marketplace',
        payment_url=payment_url,
        payload=payload,
        order=order,
        esewa_environment=esewa_config()['environment'],
    )


@app.route('/payment/esewa/success')
@login_required
def esewa_success():
    """Verify eSewa's signed callback and confirm it again with the status API."""
    encoded_data = request.args.get('data', '')
    order = None
    try:
        callback_data = decode_success_response(encoded_data)
        verify_response_signature(callback_data)
        if str(callback_data.get('status', '')).upper() != 'COMPLETE':
            raise EsewaVerificationError('eSewa did not mark this transaction as complete.')

        transaction_uuid = str(callback_data.get('transaction_uuid', ''))
        order = Order.query.filter_by(transaction_uuid=transaction_uuid).first_or_404()
        if order.buyer_id != current_user.id:
            abort(403)

        order_id = order.id
        order_transaction_uuid = order.transaction_uuid
        order_amount = order.amount
        db.session.rollback()
        status_data = check_transaction_status(order_transaction_uuid, order_amount)
        provider_status = validate_esewa_status_for_order(order, status_data)
        if provider_status == 'COMPLETE':
            completed_order = finalize_verified_payment(order_id, status_data, callback_data)
        else:
            # eSewa can redirect the customer before its status API reflects the
            # completed transaction. Keep the signed success callback pending
            # instead of incorrectly reporting that the payment failed.
            pending_order = save_pending_payment_status(order_id, 'PENDING', status_data)
            flash('eSewa is confirming your payment. Please check the status again shortly.', 'info')
            return render_page(
                'payment_result.html', 'marketplace',
                successful=False, pending=True, order=pending_order,
            )
    except (EsewaVerificationError, EsewaConfigurationError) as error:
        flash(str(error), 'error')
        return render_page(
            'payment_result.html', 'marketplace',
            successful=False, pending=False, order=order,
        )

    return render_page(
        'payment_result.html', 'marketplace',
        successful=True, pending=False, order=completed_order,
    )


@app.route('/payment/esewa/failure/<int:order_id>')
@login_required
def esewa_failure(order_id):
    """Handle eSewa failure/pending redirects without falsely completing a sale."""
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        abort(403)
    if order.status != 'PENDING_PAYMENT':
        return render_page(
            'payment_result.html', 'marketplace',
            successful=(order.status == 'PAID'), pending=False, order=order,
        )

    transaction_uuid = order.transaction_uuid
    amount = order.amount
    db.session.rollback()

    try:
        status_data = check_transaction_status(transaction_uuid, amount)
        provider_status = validate_esewa_status_for_order(order, status_data)

        if provider_status == 'COMPLETE':
            completed_order = finalize_verified_payment(order_id, status_data)
            flash('Payment was confirmed by eSewa.', 'success')
            return render_page(
                'payment_result.html', 'marketplace',
                successful=True, pending=False, order=completed_order,
            )

        if provider_status in {'PENDING', 'AMBIGUOUS'}:
            order = save_pending_payment_status(order_id, provider_status, status_data)
            return render_page(
                'payment_result.html', 'marketplace',
                successful=False, pending=True, order=order,
            )

        db.session.rollback()
        locked_order = Order.query.filter_by(id=order_id).with_for_update().one()
        Listing.query.filter_by(id=locked_order.listing_id).with_for_update().one()
        if locked_order.status == 'PENDING_PAYMENT':
            release_listing_if_pending(
                locked_order,
                provider_status or 'FAILED',
                'CANCELLED' if provider_status in {'CANCELED', 'NOT_FOUND'} else 'FAILED',
            )
            if locked_order.payment:
                locked_order.payment.raw_response = json.dumps({'status_check': status_data}, default=str)
        db.session.commit()
        order = locked_order
    except (EsewaVerificationError, EsewaConfigurationError):
        # If eSewa cannot be reached, do not guess that the payment failed.
        db.session.rollback()
        order = Order.query.get_or_404(order_id)
        return render_page(
            'payment_result.html', 'marketplace',
            successful=False, pending=True, order=order,
        )
    except SQLAlchemyError:
        db.session.rollback()
        order = Order.query.get_or_404(order_id)

    return render_page(
        'payment_result.html', 'marketplace',
        successful=False, pending=False, order=order,
    )


@app.route('/payment/esewa/status/<int:order_id>')
@login_required
def esewa_status(order_id):
    """Let the buyer/admin re-check a pending transaction with eSewa."""
    order = Order.query.get_or_404(order_id)
    if not current_user.is_admin and order.buyer_id != current_user.id:
        abort(403)

    transaction_uuid = order.transaction_uuid
    amount = order.amount
    order_status = order.status
    db.session.rollback()

    try:
        status_data = check_transaction_status(transaction_uuid, amount)
        provider_status = validate_esewa_status_for_order(order, status_data)

        if provider_status == 'COMPLETE' and order_status == 'PENDING_PAYMENT':
            completed_order = finalize_verified_payment(order_id, status_data)
            flash(f'eSewa payment confirmed for order #{completed_order.id}.', 'success')
        elif provider_status in {'NOT_FOUND', 'CANCELED'} and order_status == 'PENDING_PAYMENT':
            db.session.rollback()
            locked_order = Order.query.filter_by(id=order_id).with_for_update().one()
            Listing.query.filter_by(id=locked_order.listing_id).with_for_update().one()
            if locked_order.status == 'PENDING_PAYMENT':
                release_listing_if_pending(locked_order, provider_status, 'CANCELLED')
                if locked_order.payment:
                    locked_order.payment.raw_response = json.dumps({'status_check': status_data}, default=str)
            db.session.commit()
            flash('The payment was not completed and the car is available again.', 'info')
        else:
            order = save_pending_payment_status(order_id, provider_status, status_data)
            flash(f'eSewa status: {provider_status or "PENDING"}.', 'info')
    except (EsewaVerificationError, EsewaConfigurationError) as error:
        db.session.rollback()
        flash(str(error), 'error')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Payment status could not be updated. Please try again.', 'error')

    return redirect(url_for('profile'))


@app.route('/listing/<int:listing_id>/remove', methods=['POST'])
@login_required
def remove_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id != current_user.id:
        abort(403)
    if not csrf_is_valid():
        flash('Your form expired. Please try again.', 'error')
    elif listing.status != 'ACTIVE':
        flash('Only active listings can be removed.', 'error')
    else:
        listing.status = 'REMOVED'
        db.session.commit()
        flash('Listing removed from the marketplace.', 'success')
    return redirect(url_for('profile'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users = User.query.filter(User.is_admin.is_(False)).count()
    total_preds = Estimate.query.count()
    
    
    today_start = get_nepal_time().replace(hour=0, minute=0, second=0, microsecond=0)
    today_preds = Estimate.query.filter(Estimate.created_at >= today_start).count()
    
    avg_price = db.session.query(func.avg(Estimate.predicted_price)).scalar()
    avg_price = f"NPR {int(avg_price):,}" if avg_price else "NPR 0"
    
    recent_estimates = Estimate.query.order_by(Estimate.created_at.desc()).limit(10).all()
    marketplace_summary = {
        'active': Listing.query.filter_by(status='ACTIVE').count(),
        'sold': Listing.query.filter_by(status='SOLD').count(),
        'transactions': Order.query.count(),
    }
    return render_page('admin.html', 'admin',
                       total_users=total_users,
                       total_preds=total_preds,
                       today_preds=today_preds,
                       avg_price=avg_price,
                       recent_estimates=recent_estimates,
                       marketplace_summary=marketplace_summary)

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.filter(User.is_admin.is_(False)).order_by(User.id.asc()).all()
    return render_page('admin_records.html', 'admin', view='users', users=users)

@app.route('/admin/predictions')
@admin_required
def admin_predictions():
    estimates = Estimate.query.order_by(Estimate.id.asc()).all()
    return render_page('admin_records.html', 'admin', view='predictions', estimates=estimates)

@app.route('/admin/listings')
@admin_required
def admin_listings():
    listings = Listing.query.order_by(Listing.created_at.desc()).all()
    return render_page('admin_marketplace.html', 'admin', listings=listings, orders=[])


@app.route('/admin/transactions')
@admin_required
def admin_transactions():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_page('admin_marketplace.html', 'admin', listings=[], orders=orders)

@app.route('/admin/export')
@admin_required
def export_csv():
    estimates = Estimate.query.all()
    
    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(['ID', 'User ID', 'Brand', 'Model', 'Year', 'Fuel', 'Transmission', 'Predicted Price', 'Min Price', 'Max Price', 'Date'])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)
        
        for est in estimates:
            writer.writerow([est.id, est.user_id, est.brand, est.model, est.year, est.fuel, est.transmission, 
                             est.predicted_price, est.min_price, est.max_price, est.created_at.strftime('%Y-%m-%d %H:%M:%S')])
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    response = Response(generate(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="prediction_history.csv")
    return response

@app.route('/estimate')
def estimate():
    return render_estimate_page()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard') if current_user.is_admin else url_for('profile'))

    next_url = request.args.get('next', '')
    form_data = {'email': ''}

    try:
        ensure_default_admin()
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"DEFAULT ADMIN SETUP ERROR: {e}")
        return "Database Error: Could not set up the default administrator.", 503

    if request.method == 'POST':
        form_data['email'] = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not csrf_is_valid():
            return render_page(
                'login.html', 'login', form_data=form_data, next_url=next_url,
                error='Your form expired. Please try again.'
            ), 400
        if not form_data['email'] or not password:
            return render_page(
                'login.html', 'login', form_data=form_data, next_url=next_url,
                error='Email and password are required.'
            ), 400

        try:
            user = User.query.filter(func.lower(User.email) == form_data['email']).first()
        except SQLAlchemyError as e:
            print(f"DEBUG ERROR: {e}")
            db.session.rollback()
            return "Database Error: " + str(e), 503

        
        try:
            valid_credentials = user is not None and user.check_password(password)
        except (TypeError, ValueError):
            valid_credentials = False

        if not valid_credentials:
            return render_page(
                'login.html', 'login', form_data=form_data, next_url=next_url,
                error='Invalid email or password.'
            ), 401

        login_user(user)

        session.pop('_csrf_token', None)
        flash('Welcome back, {}.'.format(user.name), 'success')
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(safe_next_url(next_url))

    return render_page('login.html', 'login', form_data=form_data, next_url=next_url, error=None)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))

    form_data = {'name': '', 'email': ''}
    if request.method == 'POST':
        form_data['name'] = request.form.get('name', '').strip()
        form_data['email'] = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not csrf_is_valid():
            return render_page('signup.html', 'signup', form_data=form_data, error='Your form expired. Please try again.'), 400
        if not form_data['name'] or not form_data['email'] or not password or not confirm_password:
            return render_page('signup.html', 'signup', form_data=form_data, error='Complete all required fields.'), 400
        if len(form_data['name']) > 100:
            return render_page('signup.html', 'signup', form_data=form_data, error='Name must be 100 characters or fewer.'), 400
        if len(form_data['email']) > 100 or '@' not in form_data['email']:
            return render_page('signup.html', 'signup', form_data=form_data, error='Enter a valid email address.'), 400
        if len(password) < 8:
            return render_page('signup.html', 'signup', form_data=form_data, error='Password must be at least 8 characters.'), 400
        if password != confirm_password:
            return render_page('signup.html', 'signup', form_data=form_data, error='Passwords do not match.'), 400

        try:
            existing_user = User.query.filter(func.lower(User.email) == form_data['email']).first()
            if existing_user:
                return render_page('signup.html', 'signup', form_data=form_data, error='An account with that email already exists.'), 409

            user = User(name=form_data['name'], email=form_data['email'])
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return render_page('signup.html', 'signup', form_data=form_data, error='An account with that email already exists.'), 409
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"DATABASE ERROR: {str(e)}") 
            return render_page(
                'signup.html', 
                'signup', 
                form_data=form_data, 
                error=f'Database error: {str(e)}'
            ), 503

        login_user(user)
        
        session.pop('_csrf_token', None)
        flash('Your account has been created. Welcome to Car Resell Price Prediction and Recommendation System.', 'success')
        return redirect(url_for('index'))

    return render_page('signup.html', 'signup', form_data=form_data, error=None)

@app.route('/profile')
@login_required
def profile():
    try:
        estimates = current_user.estimates.order_by(Estimate.created_at.desc()).all()
        listings = Listing.query.filter_by(seller_id=current_user.id).order_by(Listing.created_at.desc()).all()
        purchases = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    except SQLAlchemyError:
        db.session.rollback()
        estimates, listings, purchases = [], [], []
        flash('We could not load your estimate history. Please try again.', 'error')
    return render_page('profile.html', 'profile', estimates=estimates, listings=listings, purchases=purchases)

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    if not csrf_is_valid():
        flash('Your form expired. Please try again.', 'error')
        return redirect(url_for('profile'))
    logout_user()
    session.pop('_csrf_token', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/predict', methods=['POST'])
def predict():
    form_data = request.form.to_dict(flat=True)
    if not csrf_is_valid():
        return render_estimate_page(
            error='Your form expired. Please submit the estimate again.',
            form_data=form_data
        ), 400

    validation_errors = validate_estimate_form(form_data)
    if validation_errors:
        first_error = next(iter(validation_errors.values()))
        return render_estimate_page(
            error=first_error,
            form_data=form_data,
            validation_errors=validation_errors
        ), 400

    
    session.pop('_csrf_token', None)

    try:
        user_input = {
            'year': int(form_data['year']),
            'km_driven': float(form_data['km_driven']),
            'fuel': form_data['fuel'],
            'seller_type': form_data['seller_type'],
            'transmission': form_data['transmission'],
            'owner': form_data['owner'],
            'mileage': float(form_data['mileage']) if form_data.get('mileage') else None,
            'engine': float(form_data['engine']),
            'max_power': float(form_data['max_power']),
            'seats': float(form_data['seats']),
            'brand': form_data['brand'].strip(),
            'model': form_data['model'].strip(),
            'brand_model': f"{form_data['brand'].strip()}_{form_data['model'].strip()}"
        }

        user_df = pd.DataFrame([user_input])
        with model_lock:               # FIXED: thread-safe prediction
            processed = pipeline_instance.transform(user_df)
            pred_log = model_instance.predict(processed)
        price = float(np.expm1(pred_log[0]))
        
        mae_value = float(model_metrics['MAE'])
        min_price = max(0, price - mae_value)
        max_price = price + mae_value
        
        formatted_price = f"NPR {int(price):,}"
        formatted_min = f"NPR {int(min_price):,}"
        formatted_max = f"NPR {int(max_price):,}"

        similar_cars = find_similar_cars(user_input, price)

        save_error = None
        estimate_record = None
        if current_user.is_authenticated:
            try:
                estimate_record = Estimate(
                    user_id=current_user.id,
                    brand=user_input['brand'],
                    model=user_input['model'],
                    year=user_input['year'],
                    fuel=user_input['fuel'],
                    transmission=user_input['transmission'],
                    predicted_price=price,
                    min_price=min_price,
                    max_price=max_price,
                    created_at=get_nepal_time(),
                    km_driven=user_input['km_driven'],
                    seller_type=user_input['seller_type'],
                    owner=user_input['owner'],
                    mileage=user_input['mileage'],
                    engine=user_input['engine'],
                    max_power=user_input['max_power'],
                    seats=user_input['seats'],
                )
                db.session.add(estimate_record)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                save_error = 'Your estimate was generated, but it could not be saved to history.'
        
        return render_estimate_page(
            price=formatted_price, min_price=formatted_min, max_price=formatted_max,
            similar_cars=similar_cars, error=None, save_error=save_error, form_data=form_data,
            estimate_saved=current_user.is_authenticated and save_error is None,
            estimate_record=estimate_record
        )
    
    except Exception as e:
        return render_estimate_page(
            error='Could not generate an estimate from those details. Please check the fields and try again.',
            form_data=form_data
        )

if __name__ == '__main__':
    app.run(debug=True)
