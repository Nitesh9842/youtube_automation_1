"""
Authentication Blueprint for YouTube Automation platform.
Handles registration, login, logout, profile management.
"""

import re
import os
import requests
import secrets
import string
from functools import wraps
from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import bcrypt
from models import create_user, get_user_by_email, get_user_by_id, get_user_by_username, update_user

auth_bp = Blueprint('auth', __name__)

# ─── Flask-Login User Class ──────────────────────────────────────────────────

class User(UserMixin):
    def __init__(self, user_dict):
        self.id = user_dict['id']
        self.email = user_dict['email']
        self.username = user_dict['username']
        self.plan = user_dict.get('plan', 'free')
        self.tokens_balance = user_dict.get('tokens_balance', 0)
        self.avatar_url = user_dict.get('avatar_url', '')
        self.created_at = user_dict.get('created_at', '')

    def get_id(self):
        return str(self.id)


def init_login_manager(app):
    """Initialize Flask-Login with the app."""
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = ''
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        user_dict = get_user_by_id(int(user_id))
        if user_dict:
            return User(user_dict)
        return None

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
        return redirect(url_for('auth.login'))

    return login_manager


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def _validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def _validate_registration(email, username, password, confirm_password):
    errors = []
    if not email or not _validate_email(email):
        errors.append('Valid email is required')
    if not username or len(username) < 3:
        errors.append('Username must be at least 3 characters')
    if not re.match(r'^[a-zA-Z0-9_]+$', username or ''):
        errors.append('Username can only contain letters, numbers, and underscores')
    if not password or len(password) < 6:
        errors.append('Password must be at least 6 characters')
    if password != confirm_password:
        errors.append('Passwords do not match')
    return errors


# ─── Routes ──────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        return render_template('login.html')

    # POST — handle login
    data = request.form if request.form else (request.get_json(silent=True) or {})
    login_id = data.get('login_id') or data.get('email')
    login_id = (login_id or '').strip()
    password = data.get('password', '')
    remember = data.get('remember', False)

    if not login_id or not password:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Email/Username and password are required'}), 400
        flash('Email/Username and password are required', 'error')
        return render_template('login.html'), 400

    user_dict = get_user_by_email(login_id)
    if not user_dict:
        user_dict = get_user_by_username(login_id)

    if not user_dict or not _check_password(password, user_dict['password_hash']):
        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        flash('Invalid credentials', 'error')
        return render_template('login.html'), 401

    user = User(user_dict)
    login_user(user, remember=bool(remember))

    if request.is_json:
        return jsonify({'success': True, 'redirect': '/dashboard'})
    return redirect(url_for('dashboard'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        return render_template('register.html')

    # POST — handle registration
    data = request.form if request.form else (request.get_json(silent=True) or {})
    email = data.get('email', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    errors = _validate_registration(email, username, password, confirm_password)

    # Check uniqueness
    if not errors:
        if get_user_by_email(email):
            errors.append('Email is already registered')
        if get_user_by_username(username):
            errors.append('Username is already taken')

    if errors:
        if request.is_json:
            return jsonify({'success': False, 'errors': errors}), 400
        for e in errors:
            flash(e, 'error')
        return render_template('register.html'), 400

    # Create user
    hashed = _hash_password(password)
    user_id = create_user(email, username, hashed)
    user_dict = get_user_by_id(user_id)
    user = User(user_dict)
    login_user(user)

    if request.is_json:
        return jsonify({'success': True, 'redirect': '/dashboard'})
    return redirect(url_for('dashboard'))


@auth_bp.route('/login/google')
def login_google():
    """Initializes Google OAuth flow for user login."""
    from google_auth_oauthlib.flow import Flow
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CLIENT_SECRET = os.path.join(BASE_DIR, 'client_secret.json')
    
    if not os.path.exists(CLIENT_SECRET):
        flash('Google Login is not configured (client_secret.json missing).', 'error')
        return redirect(url_for('auth.login'))
        
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET,
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
    )
    
    # We must construct an absolute URI explicitly for Render
    scheme = request.headers.get('X-Forwarded-Proto', 'http')
    redirect_uri = url_for('auth.login_google_callback', _external=True, _scheme=scheme)
    
    # Explicit override for local development if HTTPS isn't enabled
    if '127.0.0.1' in request.host or 'localhost' in request.host:
        redirect_uri = url_for('auth.login_google_callback', _external=True)
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        
    flow.redirect_uri = redirect_uri
    
    authorization_url, state = flow.authorization_url(prompt='consent')
    session['google_login_state'] = state
    return redirect(authorization_url)


@auth_bp.route('/login/google/callback')
def login_google_callback():
    """Handles callback from Google OAuth for user login."""
    from google_auth_oauthlib.flow import Flow
    
    state = session.get('google_login_state')
    
    # Allow bypass of state check in local dev due to session flakiness sometimes, 
    # but keep it strict in production.
    incoming_state = request.args.get('state')
    if (not state or state != incoming_state) and os.getenv('ENVIRONMENT') == 'production':
        flash('Invalid state parameter. Please try logging in again.', 'error')
        return redirect(url_for('auth.login'))
        
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CLIENT_SECRET = os.path.join(BASE_DIR, 'client_secret.json')
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET,
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile'],
        state=incoming_state
    )
    
    scheme = request.headers.get('X-Forwarded-Proto', 'http')
    redirect_uri = url_for('auth.login_google_callback', _external=True, _scheme=scheme)
    if '127.0.0.1' in request.host or 'localhost' in request.host:
        redirect_uri = url_for('auth.login_google_callback', _external=True)
        
    flow.redirect_uri = redirect_uri
    
    try:
        # Pass the full URL to fetch the token
        authorization_response = request.url
        if scheme == 'https':
            authorization_response = authorization_response.replace('http:', 'https:')
        flow.fetch_token(authorization_response=authorization_response)
    except Exception as e:
        print(f"Token fetch error: {e}")
        flash('Authentication failed during Google callback.', 'error')
        return redirect(url_for('auth.login'))
        
    credentials = flow.credentials
    
    try:
        userinfo_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
    except Exception as e:
        print(f"Userinfo fetch error: {e}")
        flash('Failed to fetch profile from Google.', 'error')
        return redirect(url_for('auth.login'))
        
    email = userinfo.get('email')
    name = userinfo.get('name', '')
    picture = userinfo.get('picture', '')
    
    if not email:
        flash("Google didn't provide an email address.", "error")
        return redirect(url_for('auth.login'))
        
    user_dict = get_user_by_email(email)
    
    if user_dict:
        user = User(user_dict)
        login_user(user)
        if picture and not user_dict.get('avatar_url'):
            update_user(user.id, avatar_url=picture)
    else:
        # Create a randomized strong password for OAuth users
        alphabet = string.ascii_letters + string.digits
        secure_password = ''.join(secrets.choice(alphabet) for i in range(32))
        hashed = _hash_password(secure_password)
        
        # Determine username
        base_username = name.lower().replace(' ', '_')
        base_username = re.sub(r'[^a-zA-Z0-9_]', '', base_username)
        if not base_username:
            base_username = 'user'
            
        username = base_username
        counter = 1
        while get_user_by_username(username):
            username = f"{base_username}_{counter}"
            counter += 1
            
        user_id = create_user(email, username, hashed)
        update_user(user_id, avatar_url=picture)
        
        user_dict = get_user_by_id(user_id)
        user = User(user_dict)
        login_user(user)
        
    return redirect(url_for('dashboard'))


@auth_bp.route('/logout', methods=['POST', 'GET'])
@login_required
def logout_user_route():
    logout_user()
    if request.is_json:
        return jsonify({'success': True})
    return redirect(url_for('index'))


@auth_bp.route('/api/me')
@login_required
def get_me():
    """Get current user info."""
    user_dict = get_user_by_id(current_user.id)
    if not user_dict:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'id': user_dict['id'],
        'email': user_dict['email'],
        'username': user_dict['username'],
        'plan': user_dict['plan'],
        'tokens_balance': user_dict['tokens_balance'],
        'total_uploads': user_dict['total_uploads'],
        'avatar_url': user_dict['avatar_url'],
        'created_at': user_dict['created_at'],
    })


@auth_bp.route('/api/profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()

    if username:
        if len(username) < 3:
            return jsonify({'success': False, 'error': 'Username must be at least 3 characters'}), 400
        existing = get_user_by_username(username)
        if existing and existing['id'] != current_user.id:
            return jsonify({'success': False, 'error': 'Username is already taken'}), 400
        update_user(current_user.id, username=username)

    return jsonify({'success': True})


@auth_bp.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    data = request.get_json(silent=True) or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    confirm_pw = data.get('confirm_password', '')

    user_dict = get_user_by_id(current_user.id)
    if not _check_password(current_pw, user_dict['password_hash']):
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400
    if len(new_pw) < 6:
        return jsonify({'success': False, 'error': 'New password must be at least 6 characters'}), 400
    if new_pw != confirm_pw:
        return jsonify({'success': False, 'error': 'Passwords do not match'}), 400

    hashed = _hash_password(new_pw)
    update_user(current_user.id, password_hash=hashed)
    return jsonify({'success': True})
