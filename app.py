"""VisionAI Eye Hospital - AI-Powered Retinal Screening Backend"""

import logging
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import torch
from transformers import AutoImageProcessor, AutoModelForImageClassification
from PIL import Image

from authlib.integrations.flask_client import OAuth
from supabase import create_client, Client

# --- Configuration ---

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', '')
    LOCAL_MODEL_ID = 'NeuronZero/EyeDiseaseClassifier'
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            'ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000'
        ).split(',')
        if origin.strip()
    ]

# --- Environment Validation ---

logger = logging.getLogger(__name__)

def validate_config(config_obj):
    """Validate that all mandatory configuration variables are present and non-empty.

    Raises RuntimeError with a descriptive message listing all missing variables
    if any required configuration is absent or whitespace-only.
    Optional OAuth variables trigger a warning but allow startup to continue.

    Args:
        config_obj: The Config class or object to validate.
    """
    required_keys = ['SECRET_KEY', 'SUPABASE_URL', 'SUPABASE_KEY']
    optional_keys = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET']
    errors = []

    for key in required_keys:
        value = getattr(config_obj, key, None)
        if not value or not str(value).strip():
            errors.append(f"  - {key} is missing or empty. Set it in your .env file or environment.")

    # Enforce minimum entropy for SECRET_KEY (at least 128-bit / 16-character random string)
    secret_key = getattr(config_obj, 'SECRET_KEY', '') or ''
    if secret_key.strip() and len(secret_key.strip()) < 16:
        errors.append(
            "  - SECRET_KEY is too short (must be at least 16 characters). "
            "Use a high-entropy random string for secure session signing."
        )

    for key in optional_keys:
        value = getattr(config_obj, key, None)
        if not value or not str(value).strip():
            logger.warning("Optional config '%s' is not set. Related features (e.g., Google OAuth) will be disabled.", key)

    if errors:
        raise RuntimeError(
            "Critical Configuration Error — the following required environment "
            "variables are missing or empty:\n" + "\n".join(errors) + "\n\n"
            "Hint: Copy .env.example to .env and fill in all required values."
        )

    logger.info("✅ Environment configuration validated successfully.")
    print("✅ Environment configuration validated successfully.")

# --- App Initialization ---

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/*": {"origins": Config.ALLOWED_ORIGINS}}, supports_credentials=True)
csrf = CSRFProtect(app)

# Validate configuration before any dependent initialisation
validate_config(Config)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access eye screening features.'
login_manager.login_message_category = 'info'

@login_manager.unauthorized_handler
def unauthorized_callback():
    if request.headers.get('Accept', '').find('application/json') != -1 or \
       request.content_type == 'multipart/form-data' or request.is_json:
        return jsonify({'success': False, 'error': 'Authentication required. Please login.'}), 401
    return redirect(url_for('login'))

oauth = OAuth(app)
google = oauth.register(
    name='google', client_id=Config.GOOGLE_CLIENT_ID, client_secret=Config.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
) if Config.GOOGLE_CLIENT_ID else None

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
print(f"✅ Supabase client initialized: {Config.SUPABASE_URL}")

# --- AI Model ---

print(f"🧠 Loading AI model: {Config.LOCAL_MODEL_ID}")
try:
    image_processor = AutoImageProcessor.from_pretrained(Config.LOCAL_MODEL_ID)
    eye_model = AutoModelForImageClassification.from_pretrained(Config.LOCAL_MODEL_ID)
    eye_model.eval()
    MODEL_LOADED = True
    print(f"✅ AI model loaded! Classes: {list(eye_model.config.id2label.values())}")
except Exception as e:
    print(f"❌ Failed to load AI model: {e}")
    image_processor = eye_model = None
    MODEL_LOADED = False

# --- User Model & Database ---

class User(UserMixin):
    def __init__(self, id, email, name, phone=None, password_hash=None, login_method='password',
                 role='patient', active=True, last_login=None, created_at=None):
        self.id, self.email, self.name, self.phone = id, email, name, phone
        self.password_hash, self.login_method, self.role = password_hash, login_method, role
        self._active = active
        self.last_login = last_login or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.created_at = created_at or datetime.now()

    @property
    def is_active(self):
        return self._active

    def check_password(self, password):
        return check_password_hash(self.password_hash, password) if self.password_hash else False

def _row_to_user(row):
    """Convert a Supabase row dict to a User object."""
    return User(
        id=row['id'], email=row['email'], name=row['name'], phone=row.get('phone'),
        password_hash=row.get('password_hash'), login_method=row.get('login_method', 'password'),
        role=row.get('role', 'patient'), active=row.get('is_active', True),
        last_login=row.get('last_login'), created_at=row.get('created_at')
    )

def save_user_to_db(user):
    """Insert a new user record into Supabase.

    Uses .insert() instead of .upsert() to prevent silent overwrites on
    primary-key or unique-constraint collisions.

    Returns:
        True on success, False on failure.

    Raises:
        Exception: Re-raises the database error after logging so callers
            can react (e.g. return an HTTP error response).
    """
    try:
        response = supabase.table('users').insert({
            'id': user.id, 'email': user.email, 'name': user.name, 'phone': user.phone,
            'password_hash': user.password_hash, 'login_method': user.login_method,
            'role': user.role, 'is_active': user.is_active, 'last_login': user.last_login,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(user.created_at, datetime) else user.created_at
        }).execute()
        if not response.data:
            logger.error("Supabase insert returned empty data for %s", user.email)
            raise RuntimeError(f"Database did not confirm insert for {user.email}")
        print(f"✅ User saved to Supabase: {user.email} | Response: {response.data}")
        return True
    except Exception as e:
        logger.error("SUPABASE INSERT FAILED for %s: %s", user.email, e)
        raise

def get_user_by_id(user_id):
    result = supabase.table('users').select('*').eq('id', user_id).execute()
    return _row_to_user(result.data[0]) if result.data else None

def get_user_by_email(email):
    result = supabase.table('users').select('*').eq('email', email).execute()
    return _row_to_user(result.data[0]) if result.data else None

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)


# --- Authentication Routes ---

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('screening'))
    return render_template('login.html')

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    name = data.get('name', '').strip()

    if not email or not password or not name:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
    if get_user_by_email(email):
        return jsonify({'success': False, 'error': 'Email already registered'}), 400

    user = User(id=str(uuid.uuid4()), email=email, name=name,
                password_hash=generate_password_hash(password), login_method='Password')
    try:
        save_user_to_db(user)
    except Exception:
        return jsonify({'success': False, 'error': 'Account creation failed due to storage error. Please try again.'}), 500
    login_user(user)
    return jsonify({'success': True, 'message': 'Account created successfully',
                    'user': {'name': user.name, 'email': user.email}})

@app.route('/auth/login', methods=['POST'])
def login_post():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    user = get_user_by_email(email)
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    login_user(user)
    return jsonify({'success': True, 'message': 'Login successful',
                    'user': {'name': user.name, 'email': user.email}})

@app.route('/auth/google')
def google_login():
    if not google:
        flash('Google Sign-In is not configured', 'error')
        return redirect(url_for('login'))
    redirect_uri = 'http://localhost:5000/auth/google/callback'
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def google_callback():
    if not google:
        flash('Google Sign-In is not configured', 'error')
        return redirect(url_for('login'))
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo') or google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()
        email = user_info.get('email', '').lower()
        name = user_info.get('name', email.split('@')[0])
        print(f"🔑 Google OAuth: {name} ({email})")

        existing_user = get_user_by_email(email)
        if existing_user:
            print(f"✅ Existing Google user found: {existing_user.id}")
            login_user(existing_user)
        else:
            user_id = str(uuid.uuid4())
            print(f"🆕 Creating new Google user: {user_id}")
            user = User(id=user_id, email=email, name=name, login_method='Google')
            try:
                save_user_to_db(user)
            except Exception:
                flash('Failed to save user account. Please try again.', 'error')
                return redirect(url_for('login'))
            login_user(user)
            print(f"✅ Google user logged in: {user_id}")

        return redirect(url_for('screening'))
    except Exception as e:
        import traceback
        print(f"❌ Google OAuth error: {e}")
        traceback.print_exc()
        flash('Google Sign-In failed. Please try again.', 'error')
        return redirect(url_for('login'))

@app.route('/auth/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/auth/status')
def auth_status():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True, 'user': {
            'name': current_user.name, 'email': current_user.email,
            'login_method': current_user.login_method}})
    return jsonify({'authenticated': False})

# --- Main Routes ---

@app.route('/')
def home():
    return render_template('index.html', user=current_user if current_user.is_authenticated else None)

@app.route('/screening')
@login_required
def screening():
    return render_template('screening.html', user=current_user)

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    if not MODEL_LOADED:
        return jsonify({'success': False, 'error': 'AI model is not loaded. Please restart the server.'}), 503
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Empty file'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in Config.ALLOWED_EXTENSIONS:
        return jsonify({'success': False, 'error': f'Invalid format. Use: {", ".join(Config.ALLOWED_EXTENSIONS)}'}), 400

    saved_path = None
    try:
        filename = secure_filename(file.filename)
        saved_path = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(saved_path)

        image = Image.open(saved_path).convert('RGB')
        inputs = image_processor(images=image, return_tensors='pt')
        with torch.no_grad():
            outputs = eye_model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1)[0]
        predictions = sorted(
            [{'label': eye_model.config.id2label.get(i, f'Class {i}'),
              'confidence': round(probs[i].item() * 100, 2)} for i in range(len(probs))],
            key=lambda x: x['confidence'], reverse=True
        )

        print(f"✅ Prediction: {predictions[0]['label']} ({predictions[0]['confidence']}%)")
        return jsonify({'success': True, 'predictions': predictions,
                        'model': Config.LOCAL_MODEL_ID, 'inference': 'local', 'user': current_user.name})
    except Exception as e:
        print(f"❌ Predict error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if saved_path and os.path.exists(saved_path):
            try: os.remove(saved_path)
            except OSError: pass

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'model': Config.LOCAL_MODEL_ID,
                    'model_loaded': MODEL_LOADED, 'inference': 'local',
                    'google_oauth_configured': bool(Config.GOOGLE_CLIENT_ID)})

@app.route('/config')
def get_config():
    return jsonify({'model': Config.LOCAL_MODEL_ID, 'inference': 'local', 'model_loaded': MODEL_LOADED,
                    'maxFileSize': Config.MAX_CONTENT_LENGTH, 'allowedFormats': list(Config.ALLOWED_EXTENSIONS),
                    'googleOAuthEnabled': bool(Config.GOOGLE_CLIENT_ID)})

# --- Error Handlers ---

@app.errorhandler(401)
def unauthorized(e):
    if request.is_json or request.path.startswith('/api'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    return redirect(url_for('login'))

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# --- Run ---

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
