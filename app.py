"""
YouTube Automation — Main Flask Application
Full web platform with auth, payments, token system, and video pipeline.
"""

from flask import Flask, render_template, request, jsonify, send_file, session, url_for, redirect
import os
import uuid
import threading
import tempfile
import time
from datetime import datetime
from typing import Optional
import logging
import secrets
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import login_required, current_user

load_dotenv()

# Allow HTTP OAuth locally
if os.getenv('OAUTHLIB_INSECURE_TRANSPORT'):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
elif os.getenv('ENVIRONMENT') != 'production':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from downloader import download_reel_with_audio
from uploader import upload_to_youtube, check_authentication, get_channel_info
from ai_genrator import AIMetadataGenerator
from video_editor import VideoEditor
from models import init_db, get_user_stats, get_recent_uploads, get_user_by_id, increment_uploads
from auth import auth_bp, init_login_manager
from payments import payments_bp
from token_system import (
    check_balance, use_tokens, refill_daily_tokens,
    get_all_plans, get_token_packs, calculate_upload_cost, TOKEN_COSTS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── App Setup ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
_sess_dir = os.path.join(tempfile.gettempdir(), 'flask_session')
os.makedirs(_sess_dir, exist_ok=True)
app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_FILE_DIR=_sess_dir,
    SESSION_PERMANENT=True,
    SESSION_USE_SIGNER=True,
    PERMANENT_SESSION_LIFETIME=2592000,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('ENVIRONMENT') == 'production',
    MAX_CONTENT_LENGTH=600 * 1024 * 1024,
)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(payments_bp)

# Initialize Flask-Login
init_login_manager(app)

# Initialize database
init_db()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')
TOKENS_DIR = os.path.join(BASE_DIR, 'user_tokens')
CLIENT_SECRET = os.path.join(BASE_DIR, 'client_secret.json')

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(TOKENS_DIR, exist_ok=True)

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')

# Task store
tasks: dict = {}


class Task:
    def __init__(self, task_id):
        self.id = task_id
        self.status = 'started'
        self.progress = 0
        self.message = 'Starting...'
        self.error = None
        self.yt_url = None
        self.metadata = None


def set_task(task_id, status, message, progress=None, **kw):
    t = tasks.get(task_id)
    if not t:
        return
    t.status = status
    t.message = message
    if progress is not None:
        t.progress = progress
    for k, v in kw.items():
        setattr(t, k, v)
    logger.info(f"[{task_id[:8]}] {status} {progress or ''}% - {message}")


def token_path():
    """Get YouTube token path bound to the authenticated user ID for security."""
    if current_user.is_authenticated:
        # Bind token to user ID — prevents token hijacking between users
        user_id = current_user.id
    elif 'uid' in session:
        user_id = session['uid']
    else:
        session['uid'] = str(uuid.uuid4())
        user_id = session['uid']
    return os.path.join(TOKENS_DIR, f'token_{user_id}.json')


def _secure_write_token(path, content):
    """Write token file with restricted permissions."""
    import stat
    with open(path, 'w') as f:
        f.write(content)
    try:
        # Restrict token file to owner-only read/write (Windows best-effort)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass  # Windows may not fully support POSIX permissions


def get_redirect_uri():
    explicit = os.getenv('GOOGLE_REDIRECT_URI') or os.getenv('OAUTH_REDIRECT_URI')
    if explicit:
        return explicit.strip().rstrip('/')
    scheme = 'https' if os.getenv('ENVIRONMENT') == 'production' else request.scheme
    return url_for('auth_callback', _external=True, _scheme=scheme)


@app.before_request
def _before():
    session.permanent = True
    # Auto-refill daily tokens for logged-in users
    if current_user.is_authenticated:
        try:
            refill_daily_tokens(current_user.id)
        except Exception:
            pass
    # Security: enforce HTTPS in production
    if os.getenv('ENVIRONMENT') == 'production':
        if request.headers.get('X-Forwarded-Proto', 'http') != 'https':
            from urllib.parse import urlparse, urlunparse
            url = urlparse(request.url)
            if url.scheme == 'http':
                return redirect(urlunparse(url._replace(scheme='https')), code=301)


# ─── Public Pages ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', plans=get_all_plans())


@app.route('/pricing')
def pricing():
    return render_template('pricing.html',
                           plans=get_all_plans(),
                           token_packs=get_token_packs())


# ─── Protected Pages ─────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    stats = get_user_stats(current_user.id)
    recent = get_recent_uploads(current_user.id)
    tp = token_path()
    yt_connected = check_authentication(tp)
    channel = get_channel_info(tp) if yt_connected else None
    return render_template('dashboard.html',
                           stats=stats,
                           recent_uploads=recent,
                           yt_connected=yt_connected,
                           channel=channel)


@app.route('/upload')
@login_required
def upload_page():
    tp = token_path()
    yt_connected = check_authentication(tp)
    channel = get_channel_info(tp) if yt_connected else None
    user = get_user_by_id(current_user.id)
    return render_template('upload.html',
                           yt_connected=yt_connected,
                           channel=channel,
                           tokens_balance=user['tokens_balance'] if user else 0,
                           token_costs=TOKEN_COSTS)


@app.route('/settings')
@login_required
def settings():
    tp = token_path()
    yt_connected = check_authentication(tp)
    channel = get_channel_info(tp) if yt_connected else None
    user = get_user_by_id(current_user.id)
    return render_template('settings.html',
                           yt_connected=yt_connected,
                           channel=channel,
                           user=user)


# ─── API: Stats ──────────────────────────────────────────────────────────────

@app.route('/api/stats')
@login_required
def api_stats():
    stats = get_user_stats(current_user.id)
    if not stats:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(stats)


@app.route('/api/token-balance')
@login_required
def api_token_balance():
    user = get_user_by_id(current_user.id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'tokens_balance': user['tokens_balance'],
        'plan': user['plan'],
    })


# ─── YouTube OAuth (Secured) ─────────────────────────────────────────────────

@app.route('/auth/youtube/start')
@login_required
def auth_start():
    import google_auth_oauthlib.flow as fm
    import hashlib
    if not os.path.exists(CLIENT_SECRET):
        return jsonify({'error': 'client_secret.json not found'}), 500
    scopes = ['https://www.googleapis.com/auth/youtube.upload']
    flow = fm.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, scopes)
    redirect_uri = get_redirect_uri()
    flow.redirect_uri = redirect_uri

    # Generate CSRF nonce bound to user's session
    nonce = secrets.token_urlsafe(32)
    auth_url, state = flow.authorization_url(
        prompt='consent',
        access_type='offline',
        state=nonce,
        include_granted_scopes='true',
    )

    # Store security context in session
    session['oauth_state'] = nonce
    session['oauth_user_id'] = current_user.id
    session['oauth_timestamp'] = time.time()
    session['oauth_data'] = {'redirect_uri': redirect_uri, 'scopes': scopes}

    logger.info(f"YouTube OAuth started for user {current_user.id}")
    return jsonify({'auth_url': auth_url})


@app.route('/auth/callback')
def auth_callback():
    import google_auth_oauthlib.flow as fm

    # ─── Security checks ─────────────────────────────────────────────
    flow_data = session.get('oauth_data')
    if not flow_data:
        logger.warning("OAuth callback with no session data — possible session hijack")
        return '''<html><body style="font-family:sans-serif;background:#0a0a1a;color:#fff;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center">
                <div style="font-size:72px">⚠️</div>
                <h2 style="color:#f43f5e">Session Expired</h2>
                <p style="color:rgba(255,255,255,0.7)">Please go back and try connecting YouTube again.</p>
                <a href="/settings" style="color:#8b5cf6;margin-top:16px;display:inline-block;">← Back to Settings</a>
            </div>
        </body></html>''', 400

    # CSRF state verification — prevent cross-site request forgery
    received_state = request.args.get('state', '')
    expected_state = session.get('oauth_state', '')
    if not received_state or received_state != expected_state:
        logger.warning(f"OAuth CSRF mismatch: expected={expected_state[:8]}... got={received_state[:8]}...")
        session.pop('oauth_state', None)
        session.pop('oauth_data', None)
        return '''<html><body style="font-family:sans-serif;background:#0a0a1a;color:#fff;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center">
                <div style="font-size:72px">🛡️</div>
                <h2 style="color:#f43f5e">Security Check Failed</h2>
                <p style="color:rgba(255,255,255,0.7)">The request could not be verified. Please try again.</p>
                <a href="/settings" style="color:#8b5cf6;margin-top:16px;display:inline-block;">← Back to Settings</a>
            </div>
        </body></html>''', 403

    # Token expiry check — OAuth flow should complete within 10 minutes
    oauth_ts = session.get('oauth_timestamp', 0)
    if time.time() - oauth_ts > 600:
        logger.warning("OAuth callback timed out (>10 min)")
        session.pop('oauth_state', None)
        session.pop('oauth_data', None)
        return '''<html><body style="font-family:sans-serif;background:#0a0a1a;color:#fff;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center">
                <div style="font-size:72px">⏱️</div>
                <h2 style="color:#f59e0b">Authorization Expired</h2>
                <p style="color:rgba(255,255,255,0.7)">The authorization window timed out. Please try again.</p>
                <a href="/settings" style="color:#8b5cf6;margin-top:16px;display:inline-block;">← Back to Settings</a>
            </div>
        </body></html>''', 408

    # ─── Process the callback ─────────────────────────────────────────
    flow = fm.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, flow_data['scopes'])
    flow.redirect_uri = flow_data['redirect_uri']

    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        logger.error(f"YouTube OAuth denied: {error}")
        session.pop('oauth_state', None)
        session.pop('oauth_data', None)
        return f'''<html><body style="font-family:sans-serif;background:#0a0a1a;color:#fff;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center">
                <div style="font-size:72px">❌</div>
                <h2 style="color:#f43f5e">Authorization Denied</h2>
                <p style="color:rgba(255,255,255,0.7)">{error}</p>
                <a href="/settings" style="color:#8b5cf6;margin-top:16px;display:inline-block;">← Back to Settings</a>
            </div>
        </body></html>''', 400

    if not code:
        return '<h2>No authorization code received.</h2>', 400

    try:
        flow.fetch_token(code=code)
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return f'''<html><body style="font-family:sans-serif;background:#0a0a1a;color:#fff;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
            <div style="text-align:center">
                <div style="font-size:72px">⚠️</div>
                <h2 style="color:#f43f5e">Connection Failed</h2>
                <p style="color:rgba(255,255,255,0.7)">Token exchange error. Please try again.</p>
                <a href="/settings" style="color:#8b5cf6;margin-top:16px;display:inline-block;">← Back to Settings</a>
            </div>
        </body></html>''', 500

    # Save token bound to the original authenticated user
    oauth_user_id = session.get('oauth_user_id')
    if oauth_user_id:
        tok = os.path.join(TOKENS_DIR, f'token_{oauth_user_id}.json')
    else:
        tok = token_path()

    _secure_write_token(tok, flow.credentials.to_json())
    logger.info(f"YouTube token saved for user {oauth_user_id}")

    # Clean up ALL OAuth session data
    for key in ['oauth_state', 'oauth_data', 'oauth_user_id', 'oauth_timestamp']:
        session.pop(key, None)

    return '''<html><body style="font-family:sans-serif;background:#0a0a1a;color:#fff;
        display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
        <div style="text-align:center">
            <div style="font-size:72px">&#x2705;</div>
            <h2 style="color:#00E676">YouTube Connected Securely!</h2>
            <p style="color:rgba(255,255,255,0.7)">Your channel is now linked. You can close this tab.</p>
        </div>
        <script>setTimeout(()=>window.close(),2500)</script>
    </body></html>'''


@app.route('/check-auth')
@login_required
def check_auth():
    tp = token_path()
    ok = check_authentication(tp)
    ch = get_channel_info(tp) if ok else None
    return jsonify({'authenticated': ok, 'channel': ch})


@app.route('/youtube/logout', methods=['POST'])
@login_required
def youtube_logout():
    try:
        tp = token_path()
        if os.path.exists(tp):
            try:
                from google.oauth2.credentials import Credentials
                import requests as req
                creds = Credentials.from_authorized_user_file(tp)
                req.post('https://oauth2.googleapis.com/revoke',
                         params={'token': creds.token},
                         headers={'content-type': 'application/x-www-form-urlencoded'})
            except Exception:
                pass
            os.remove(tp)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ─── Upload Pipeline ─────────────────────────────────────────────────────────

def run_upload(task_id: str, video_path: str, is_temp: bool,
               editing: Optional[dict], tok: str, user_id: int = None):
    edited_path = None
    music_path = None
    final_path = video_path
    try:
        if editing and editing.get('enabled'):
            set_task(task_id, 'editing', 'Editing video...', 20)
            try:
                editor = VideoEditor()
                base = os.path.splitext(os.path.basename(video_path))[0]
                edited_path = os.path.join(DOWNLOAD_DIR, f'{base}_edited.mp4')
                music_src = editing.get('music_url') or editing.get('music_file')
                music_path = editing.get('music_file')
                editor.edit_video(
                    video_path=video_path,
                    output_path=edited_path,
                    music_url=music_src,
                    music_volume=editing.get('music_volume', 0.3),
                    text_overlays=editing.get('text_overlays'),
                )
                final_path = edited_path
            except Exception as e:
                logger.warning(f'Editing failed ({e}), using original.')
                edited_path = None

        set_task(task_id, 'analyzing', 'AI analyzing video and generating metadata...', 55)
        try:
            gen = AIMetadataGenerator(GROQ_API_KEY)
            meta = gen.generate_complete_metadata(video_path=final_path)
        except Exception as e:
            logger.warning(f'AI failed ({e}), using fallback.')
            meta = {
                'title': 'Amazing Video Content',
                'description': 'Check out this amazing content! #Video #Content',
                'tags': ['video', 'content', 'entertainment'],
                'keywords': ['video'],
                'hashtags': ['#Video', '#Content'],
            }

        set_task(task_id, 'uploading', 'Uploading to YouTube...', 80, metadata=meta)
        video_id = upload_to_youtube(
            video_path=final_path,
            title=meta['title'],
            description=meta['description'],
            tags=meta.get('tags', []),
            privacy_status='public',
            token_path=tok,
        )
        yt_url = f'https://www.youtube.com/watch?v={video_id}'
        set_task(task_id, 'done', 'Upload complete!', 100, yt_url=yt_url, metadata=meta)

        # Track success
        if user_id:
            increment_uploads(user_id, success=True)

    except Exception as e:
        logger.error(f'Task failed: {e}')
        set_task(task_id, 'failed', str(e), error=str(e))
        if user_id:
            increment_uploads(user_id, success=False)
    finally:
        for p in filter(None, [edited_path, music_path, video_path if is_temp else None]):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
MUSIC_EXTS = {'.mp3', '.wav', '.m4a', '.aac'}


@app.route('/upload-video', methods=['POST'])
@login_required
def upload_video():
    f = request.files.get('video')
    if not f or not f.filename:
        return jsonify({'success': False, 'error': 'No file'})
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in VIDEO_EXTS:
        return jsonify({'success': False, 'error': 'Unsupported video format'})
    fname = f'local_{int(time.time())}{ext}'
    path = os.path.join(DOWNLOAD_DIR, fname)
    f.save(path)
    return jsonify({'success': True, 'filepath': path, 'filename': fname})


@app.route('/upload-music', methods=['POST'])
@login_required
def upload_music():
    f = request.files.get('music')
    if not f or not f.filename:
        return jsonify({'success': False, 'error': 'No file'})
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in MUSIC_EXTS:
        return jsonify({'success': False, 'error': 'Unsupported music format'})
    music_dir = os.path.join(DOWNLOAD_DIR, 'music')
    os.makedirs(music_dir, exist_ok=True)
    fname = f'music_{int(time.time())}{ext}'
    path = os.path.join(music_dir, fname)
    f.save(path)
    return jsonify({'success': True, 'filepath': path})


@app.route('/start-upload', methods=['POST'])
@login_required
def start_upload():
    tp = token_path()
    if not check_authentication(tp):
        return jsonify({'success': False, 'error': 'Not signed in to YouTube'}), 401

    data = request.get_json(silent=True) or {}
    source = data.get('source')
    editing = data.get('editing')

    # Check token balance
    has_editing = editing and editing.get('enabled')
    cost = calculate_upload_cost(has_editing=has_editing)
    ok, _, balance = check_balance(current_user.id, 'upload')

    if balance < cost:
        return jsonify({
            'success': False,
            'error': f'Insufficient tokens. Need {cost}, have {balance}.',
            'tokens_needed': cost,
            'tokens_balance': balance,
        }), 402

    # Deduct tokens
    use_tokens(current_user.id, 'upload', details=f'source:{source}')
    if has_editing:
        use_tokens(current_user.id, 'video_edit')
    use_tokens(current_user.id, 'ai_analyze')

    task_id = str(uuid.uuid4())
    tasks[task_id] = Task(task_id)

    if source == 'instagram':
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'success': False, 'error': 'URL is required'})
        if not RAPIDAPI_KEY:
            return jsonify({'success': False, 'error': 'RAPIDAPI_KEY not set in .env'})

        def ig_flow():
            try:
                set_task(task_id, 'downloading', 'Downloading from Instagram...', 10)
                vpath = download_reel_with_audio(url, DOWNLOAD_DIR)
                if not vpath or not os.path.exists(vpath):
                    raise RuntimeError('Download failed')
                run_upload(task_id, vpath, True, editing, tp, current_user.id)
            except Exception as e:
                set_task(task_id, 'failed', str(e), error=str(e))

        threading.Thread(target=ig_flow, daemon=True).start()

    elif source == 'device':
        vpath = data.get('video_path', '').strip()
        if not vpath or not os.path.exists(vpath):
            return jsonify({'success': False, 'error': 'Video file not found'})
        threading.Thread(
            target=run_upload,
            args=(task_id, vpath, True, editing, tp, current_user.id),
            daemon=True
        ).start()
    else:
        return jsonify({'success': False, 'error': 'source must be instagram or device'})

    return jsonify({'success': True, 'task_id': task_id})


@app.route('/task/<task_id>')
@login_required
def task_status(task_id):
    t = tasks.get(task_id)
    if not t:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'status': t.status,
        'progress': t.progress,
        'message': t.message,
        'error': t.error,
        'yt_url': t.yt_url,
        'metadata': t.metadata,
    })


# ─── Error Handlers ──────────────────────────────────────────────────────────

@app.errorhandler(404)
def e404(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def e500(e):
    return render_template('500.html'), 500


@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'groq': bool(GROQ_API_KEY),
        'rapidapi': bool(RAPIDAPI_KEY),
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    is_prod = os.getenv('ENVIRONMENT') == 'production'
    host = '0.0.0.0' if is_prod else '127.0.0.1'
    print('Starting YouTube Automation Platform')
    print(f'   -> http://{host}:{port}')
    app.run(debug=not is_prod, host=host, port=port)
