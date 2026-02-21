from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
import os
import uuid
import threading
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from dotenv import load_dotenv
import secrets

# Load environment variables from .env file
load_dotenv()

# ✅ FIX: Allow insecure transport for local OAuth (development only)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Import our modules
from downloader import download_reel_with_audio  # ✅ Now properly connected
from uploader import upload_to_youtube, check_authentication, authenticate_youtube, get_youtube_service, get_channel_info, logout_youtube
from ai_genrator import AIMetadataGenerator
from video_editor import VideoEditor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) 

app = Flask(__name__)

# Configuration
DOWNLOAD_FOLDER = 'downloads'
GALLERY_FOLDER = 'gallery'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
# ✅ NEW: Store user tokens in a separate folder
USER_TOKENS_FOLDER = 'user_tokens'
os.makedirs(USER_TOKENS_FOLDER, exist_ok=True)

# Ensure folders exist
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(GALLERY_FOLDER, exist_ok=True)

# Task storage (in production, use Redis or database)
tasks = {}

class TaskStatus:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = 'started'
        self.progress = 0
        self.message = 'Task started'
        self.error = None
        self.result = None
        self.metadata = None
        self.youtube_url = None
        self.created_at = datetime.now()

def update_task_status(task_id: str, status: str, message: str = '', progress: int = 0, **kwargs):
    """Update task status"""
    if task_id in tasks:
        task = tasks[task_id]
        task.status = status
        task.message = message
        task.progress = progress
        
        # Update additional fields
        for key, value in kwargs.items():
            setattr(task, key, value)
        
        logger.info(f"Task {task_id}: {status} - {message}")

# ✅ IMPROVED: Helper function to get user-specific token path
def get_user_token_path():
    """Get token path for current user session - creates isolated sessions"""
    if 'user_id' not in session:
        # Create new unique session for this browser
        session['user_id'] = str(uuid.uuid4())
        session['created_at'] = datetime.now().isoformat()
        logger.info(f"🆕 Created new isolated session: {session['user_id']}")
    
    user_id = session['user_id']
    token_path = os.path.join(USER_TOKENS_FOLDER, f'token_{user_id}.json')
    
    # ✅ REMOVED: No auto-expiration - session stays active until manual logout
    # Token file will only be removed when user explicitly logs out
    
    return token_path

def background_upload_task(task_id: str, reel_url: str, editing_options: Optional[dict] = None, token_path: str = 'token.json'):
    """Background task for downloading, editing, and uploading"""
    video_path = None
    edited_video_path = None
    uploaded_music_path = None
    
    try:
        update_task_status(task_id, 'downloading', 'Downloading reel from Instagram...', 10)
        
        # ✅ FIXED: Use RapidAPI downloader instead of sessionid
        if not os.getenv("RAPIDAPI_KEY"):
            raise Exception("RAPIDAPI_KEY not configured in .env file")
        
        # Download the reel using RapidAPI
        try:
            video_path = download_reel_with_audio(reel_url, DOWNLOAD_FOLDER)
        except Exception as download_error:
            error_msg = str(download_error)
            if "RAPIDAPI_KEY" in error_msg:
                raise Exception("RapidAPI key not configured. Please add RAPIDAPI_KEY to your .env file")
            else:
                raise Exception(f"Failed to download reel: {error_msg}")
        
        if not video_path or not os.path.exists(video_path):
            raise Exception("Failed to download video file")
        
        logger.info(f"✅ Video downloaded: {video_path}")
        
        # Determine final video path
        final_video_path = video_path
        
        # ✅ Video Editing Step (FIXED to support local files)
        if editing_options and editing_options.get('enabled'):
            try:
                update_task_status(task_id, 'editing', 'Editing video (adding music & text overlays)...', 30)
                
                logger.info(f"🎬 Starting video editing with options: {editing_options}")
                
                # Initialize video editor
                editor = VideoEditor()
                
                # Generate edited video filename
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                edited_video_path = os.path.join(DOWNLOAD_FOLDER, f"{base_name}_edited.mp4")
                
                # ✅ NEW: Determine music source (URL or local file)
                music_source = editing_options.get('music_url') or editing_options.get('music_file')
                uploaded_music_path = editing_options.get('music_file')  # Track for cleanup
                
                # Apply edits
                editor.edit_video(
                    video_path=video_path,
                    output_path=edited_video_path,
                    music_url=music_source,  # Can be either YouTube URL or local file path
                    music_volume=editing_options.get('music_volume', 0.3),
                    text_overlays=editing_options.get('text_overlays')
                )
                
                logger.info(f"✅ Video editing completed: {edited_video_path}")
                
                # Use edited video for upload
                final_video_path = edited_video_path
                
            except Exception as edit_error:
                error_msg = str(edit_error)
                logger.error(f"❌ Video editing failed: {error_msg}")
                
                # If editing fails, use original video
                logger.warning("⚠️ Using original video due to editing failure")
                final_video_path = video_path
                
                # Update status to show editing was skipped
                update_task_status(
                    task_id, 
                    'generating_metadata', 
                    f'Skipped editing (error: {error_msg[:50]}...). Using original video...', 
                    50
                )
        
        update_task_status(task_id, 'generating_metadata', 'AI analyzing video content and generating metadata...', 60)
        
        # Generate metadata using AI with actual video analysis
        try:
            # Create AI Metadata Generator instance
            ai_generator = AIMetadataGenerator(GEMINI_API_KEY)
            
            # Generate metadata based on actual video content
            generated_metadata = ai_generator.generate_complete_metadata(
                video_path=final_video_path
            )
            
            # Extract needed fields for YouTube upload
            metadata = {
                'title': generated_metadata['title'],
                'description': generated_metadata['description'],
                'tags': generated_metadata['tags'],
                'keywords': generated_metadata['keywords'],
                'hashtags': generated_metadata['hashtags'],
                'video_analysis': generated_metadata.get('video_analysis', 'Content analysis unavailable')
            }
            
            logger.info(f"✅ AI metadata generated successfully")
            logger.info(f"📝 Title: {metadata['title']}")
            
        except Exception as e:
            logger.warning(f"AI metadata generation failed: {str(e)}. Using fallback metadata.")
            # Fallback metadata
            filename = os.path.basename(final_video_path)
            metadata = {
                'title': f'Amazing Social Media Content - {filename}',
                'description': f'Check out this amazing content!\n\nOriginal source: {reel_url}\n\n#SocialMedia #Viral #Content #Entertainment',
                'tags': ['social media', 'viral', 'entertainment', 'content', 'video'],
                'keywords': ['social media video', 'viral content', 'entertainment'],
                'hashtags': ['#SocialMedia', '#Viral', '#Content']
            }
        
        update_task_status(task_id, 'uploading', 'Uploading to YouTube...', 85, metadata=metadata)
        
        # ✅ FIX: Pass token_path to upload_to_youtube
        try:
            video_id = upload_to_youtube(
                video_path=final_video_path,
                title=metadata['title'],
                description=metadata['description'],
                tags=metadata['tags'],
                privacy_status="public",
                token_path=token_path  # ✅ FIXED: Now passing token_path
            )
            
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            
            update_task_status(
                task_id, 
                'completed', 
                'Upload completed successfully!', 
                100,
                result={'video_id': video_id},
                youtube_url=youtube_url,
                metadata=metadata
            )
            
        except Exception as upload_error:
            raise Exception(f"YouTube upload failed: {str(upload_error)}")
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        update_task_status(task_id, 'failed', str(e), error=str(e))
    finally:
        # Clean up downloaded files after successful upload or failure
        for path in [video_path, edited_video_path, uploaded_music_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"🧹 Cleaned up temporary file: {path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Could not clean up file {path}: {cleanup_error}")

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/downloader')
def downloader_page():
    """Render the downloader page"""
    return render_template('downloader.html')

@app.route('/metadata-generator')
def metadata_generator_page():
    """Render the metadata generator page"""
    return render_template('metadata_generator.html')

@app.route('/uploader')
def uploader_page():
    """Render the uploader page"""
    # ✅ Check authentication using persistent token
    token_path = get_user_token_path()
    is_authenticated = check_authentication(token_path)
    return render_template('uploader.html', authenticated=is_authenticated)

@app.route('/check-auth')
def check_auth():
    """Check YouTube authentication status for current user"""
    try:
        # ✅ Pass user-specific token path
        token_path = get_user_token_path()
        is_authenticated = check_authentication(token_path)
        channel_info = None
        
        if is_authenticated:
            channel_info = get_channel_info(token_path)
            logger.info(f"✅ User authenticated: {channel_info.get('title', 'Unknown') if channel_info else 'Unknown'}")
        else:
            logger.info("⚠️ User not authenticated")
            
        return jsonify({
            'authenticated': is_authenticated,
            'channel': channel_info
        })
    except Exception as e:
        logger.error(f"Error checking authentication: {str(e)}")
        return jsonify({'authenticated': False, 'error': str(e)})

@app.route('/authenticate', methods=['POST'])
def authenticate():
    """Authenticate with YouTube for current user"""
    try:
        token_path = get_user_token_path()
        credentials = authenticate_youtube(token_path)
        if credentials:
            return jsonify({'success': True, 'message': 'Authentication successful'})
        else:
            return jsonify({'success': False, 'error': 'Authentication failed'})
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/auth/start')
def start_auth():
    """Start OAuth flow for current user"""
    try:
        import google_auth_oauthlib.flow
        
        scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        client_secrets_file = "client_secret.json"
        
        if not os.path.exists(client_secrets_file):
            return jsonify({'error': 'client_secret.json not found'})
        
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, scopes)
        
        redirect_uri = request.url_root.rstrip('/') + '/auth/callback'
        
        if os.getenv('ENVIRONMENT') != 'production':
            if 'localhost' in redirect_uri or '127.0.0.1' in redirect_uri:
                redirect_uri = redirect_uri.replace('https://', 'http://')
        
        flow.redirect_uri = redirect_uri
        
        auth_url, state = flow.authorization_url(
            prompt='consent',
            access_type='offline',
            include_granted_scopes='true'
        )
        
        # ✅ Store flow in user session (not shared globally)
        session['oauth_flow_state'] = state
        # Store flow data in a temporary file for this user
        flow_data = {
            'client_secrets_file': client_secrets_file,
            'redirect_uri': redirect_uri,
            'scopes': scopes
        }
        session['oauth_flow_data'] = flow_data
        
        return jsonify({'auth_url': auth_url})
        
    except Exception as e:
        logger.error(f"Error starting auth: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback for current user"""
    try:
        # ✅ Reconstruct flow from session data
        flow_data = session.get('oauth_flow_data')
        state = session.get('oauth_flow_state')
        
        if not flow_data:
            return "OAuth flow not found. Please restart the authentication process.", 400
        
        import google_auth_oauthlib.flow
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            flow_data['client_secrets_file'], flow_data['scopes'])
        flow.redirect_uri = flow_data['redirect_uri']
        
        auth_code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            return f"Authentication failed: {error}", 400
            
        if not auth_code:
            return "No authorization code received", 400
        
        try:
            flow.fetch_token(code=auth_code)
            credentials = flow.credentials
        except Exception as token_error:
            logger.error(f"Token exchange failed: {str(token_error)}")
            return f"Token exchange failed: {str(token_error)}", 500
        
        # ✅ Save credentials to user-specific token file
        token_path = get_user_token_path()
        with open(token_path, 'w') as token:
            token.write(credentials.to_json())
        
        # Clean up session
        session.pop('oauth_flow_state', None)
        session.pop('oauth_flow_data', None)
        
        return """
        <html>
        <head>
            <style>
                body {
                    font-family: 'Inter', sans-serif;
                    background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
                    color: white;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .container {
                    text-align: center;
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(20px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    padding: 50px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                }
                h2 {
                    color: #00E676;
                    font-size: 32px;
                    margin-bottom: 20px;
                }
                p {
                    font-size: 18px;
                    color: rgba(255, 255, 255, 0.7);
                }
                .icon {
                    font-size: 80px;
                    margin-bottom: 20px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">✅</div>
                <h2>Authentication Successful!</h2>
                <p>You can now close this tab and return to the application.</p>
            </div>
            <script>
                setTimeout(function() {
                    window.close();
                }, 3000);
            </script>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Error in auth callback: {str(e)}")
        return f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Inter', sans-serif;
                    background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
                    color: white;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}
                .container {{
                    text-align: center;
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(20px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    padding: 50px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                }}
                h2 {{
                    color: #FF1744;
                    font-size: 32px;
                    margin-bottom: 20px;
                }}
                p {{
                    font-size: 16px;
                    color: rgba(255, 255, 255, 0.7);
                }}
                .icon {{
                    font-size: 80px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">❌</div>
                <h2>Authentication Failed</h2>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """, 500

@app.route('/download', methods=['POST'])
def download_reel():
    """Download reel only"""
    try:
        data = request.get_json(silent=True) or {}
        reel_url = data.get('url') or request.form.get('url') or request.args.get('url')
        
        if not reel_url:
            return jsonify({'success': False, 'error': 'URL is required'})
        
        # Check RapidAPI key
        if not RAPIDAPI_KEY:
            return jsonify({
                'success': False, 
                'error': 'RAPIDAPI_KEY not configured. Please add it to your .env file.'
            })
        
        # Download the reel using RapidAPI
        try:
            video_path = download_reel_with_audio(reel_url, DOWNLOAD_FOLDER)
        except Exception as download_error:
            error_msg = str(download_error)
            return jsonify({'success': False, 'error': f'Download failed: {error_msg}'})
        
        if not video_path or not os.path.exists(video_path):
            return jsonify({'success': False, 'error': 'Failed to download video'})
        
        filename = os.path.basename(video_path)
        
        return jsonify({
            'success': True,
            'message': 'Download completed',
            'filename': filename,
            'filepath': video_path
        })
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/auto-upload-async', methods=['POST'])
def auto_upload_async():
    """Start async upload process for current user"""
    try:
        # ✅ Check user-specific authentication
        token_path = get_user_token_path()
        if not check_authentication(token_path):
            return jsonify({'success': False, 'error': 'Not authenticated with YouTube'}), 401
        
        data = request.get_json(silent=True) or {}
        reel_url = data.get('url') or request.form.get('url') or request.args.get('url')
        editing_options = data.get('editing')
        
        if not reel_url:
            return jsonify({'success': False, 'error': 'URL is required'})
        
        task_id = str(uuid.uuid4())
        tasks[task_id] = TaskStatus(task_id)
        
        # ✅ Pass user token path to background task
        thread = threading.Thread(
            target=background_upload_task,
            args=(task_id, reel_url, editing_options, token_path)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Upload process started'
        })
        
    except Exception as e:
        logger.error(f"Auto upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/task-status/<task_id>')
def get_task_status(task_id):
    """Get task status"""
    try:
        if task_id not in tasks:
            return jsonify({'success': False, 'error': 'Task not found'})
        
        task = tasks[task_id]
        
        return jsonify({
            'success': True,
            'task': {
                'id': task.task_id,
                'status': task.status,
                'message': task.message,
                'progress': task.progress,
                'error': task.error,
                'result': task.result,
                'metadata': task.metadata,
                'youtube_url': task.youtube_url
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get-video/<filename>')
def get_video(filename):
    """Download video file"""
    try:
        # Security: Only allow files from downloads folder
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(DOWNLOAD_FOLDER, safe_filename)
        
        logger.info(f"Serving video request for: {safe_filename}")
        logger.info(f"Full path: {file_path}")
        logger.info(f"File exists: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            # List available files for debugging
            available_files = os.listdir(DOWNLOAD_FOLDER) if os.path.exists(DOWNLOAD_FOLDER) else []
            logger.error(f"Available files: {available_files}")
            return jsonify({
                'error': 'File not found',
                'requested': safe_filename,
                'available': available_files
            }), 404
        
        # Verify it's a video file
        if not file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            logger.error(f"Invalid file type: {file_path}")
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Get file size for logging
        file_size = os.path.getsize(file_path)
        logger.info(f"Serving file: {safe_filename} ({file_size} bytes)")
        
        # Serve the file with proper headers
        return send_file(
            file_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=safe_filename
        )
        
    except Exception as e:
        logger.error(f"Error serving video: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/cleanup/<filename>', methods=['POST'])
def cleanup_file(filename):
    """Clean up downloaded file after user has downloaded it"""
    try:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(DOWNLOAD_FOLDER, safe_filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
            return jsonify({'success': True, 'message': 'File cleaned up'})
        else:
            return jsonify({'success': False, 'error': 'File not found'})
            
    except Exception as e:
        logger.error(f"Error cleaning up file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/list-downloads')
def list_downloads():
    """List all files in downloads folder (for debugging)"""
    try:
        files = os.listdir(DOWNLOAD_FOLDER)
        files_info = []
        for f in files:
            filepath = os.path.join(DOWNLOAD_FOLDER, f)
            files_info.append({
                'name': f,
                'size': os.path.getsize(filepath),
                'exists': os.path.exists(filepath)
            })   
        return jsonify({'files': files_info})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/generate-preview', methods=['POST'])
def generate_preview():
    """Generate metadata preview by downloading and analyzing video"""
    try:
        data = request.get_json(silent=True) or {}
        reel_url = data.get('url') or request.form.get('url') or request.args.get('url')
        
        if not reel_url:
            return jsonify({'success': False, 'error': 'URL is required'})
        
        # Check RapidAPI key
        if not RAPIDAPI_KEY:
            return jsonify({
                'success': False, 
                'error': 'RAPIDAPI_KEY not configured in .env file'
            })
        
        # Download video temporarily for analysis
        temp_video_path = None
        try:
            # Download the video for analysis
            try:
                temp_video_path = download_reel_with_audio(reel_url, DOWNLOAD_FOLDER)
            except Exception as download_error:
                error_msg = str(download_error)
                return jsonify({
                    'success': False,
                    'error': f'Download failed: {error_msg}'
                })
            
            # Verify video was downloaded successfully
            if not temp_video_path:
                raise Exception("Failed to download video for analysis")
            
            # Create AI Metadata Generator instance
            ai_generator = AIMetadataGenerator(GEMINI_API_KEY)
            
            # Generate metadata based on actual video content
            generated_metadata = ai_generator.generate_complete_metadata(
                video_path=temp_video_path
            )
            
            # Get video filename for download option
            video_filename = os.path.basename(temp_video_path)
            
            return jsonify({
                'success': True,
                'title': generated_metadata['title'],
                'description': generated_metadata['description'],
                'tags': generated_metadata['tags'],
                'hashtags': generated_metadata['hashtags'],
                'video_analysis': generated_metadata.get('video_analysis', 'Analysis unavailable'),
                'video_file': video_filename  # ✅ NEW: Include video filename
            })
            
        except Exception as e:
            logger.warning(f"AI metadata generation preview failed: {str(e)}")
            # Fallback metadata
            return jsonify({
                'success': True,
                'title': 'Amazing Social Media Content',
                'description': f'Check out this amazing content from social media!\n\nSource: {reel_url}\n\n#SocialMedia #Viral #Content',
                'tags': ['social media', 'viral', 'entertainment', 'content'],
                'hashtags': ['#SocialMedia', '#Viral', '#Content', '#Entertainment'],
                'video_analysis': 'AI analysis unavailable - using fallback metadata'
            })
        # ✅ REMOVED: Don't cleanup video file - keep it for download option
        
    except Exception as e:
        logger.error(f"Preview generation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate-metadata-instagram', methods=['POST'])
def generate_metadata_instagram():
    """Download Instagram video to gallery and generate metadata"""
    try:
        data = request.get_json(silent=True) or {}
        reel_url = data.get('url')
        
        if not reel_url:
            return jsonify({'success': False, 'error': 'URL is required'})
        
        # Check RapidAPI key
        if not RAPIDAPI_KEY:
            return jsonify({
                'success': False, 
                'error': 'RAPIDAPI_KEY not configured in .env file'
            })
        
        # Download video to gallery
        try:
            video_path = download_reel_with_audio(reel_url, GALLERY_FOLDER)
        except Exception as download_error:
            error_msg = str(download_error)
            return jsonify({
                'success': False,
                'error': f'Download failed: {error_msg}'
            })
        
        # Verify video was downloaded successfully
        if not video_path or not os.path.exists(video_path):
            raise Exception("Failed to download video to gallery")
        
        logger.info(f"✅ Video downloaded to gallery: {video_path}")
        
        # Create AI Metadata Generator instance
        ai_generator = AIMetadataGenerator(GEMINI_API_KEY)
        
        # Generate metadata based on actual video content
        generated_metadata = ai_generator.generate_complete_metadata(
            video_path=video_path
        )
        
        # Get video filename
        video_filename = os.path.basename(video_path)
        
        return jsonify({
            'success': True,
            'title': generated_metadata['title'],
            'description': generated_metadata['description'],
            'tags': generated_metadata.get('tags', []),
            'hashtags': generated_metadata.get('hashtags', []),
            'video_analysis': generated_metadata.get('video_analysis', 'Analysis unavailable'),
            'video_file': video_filename,
            'saved_to_gallery': True,
            'gallery_path': 'gallery',
            'message': f'Video downloaded to gallery as {video_filename}'
        })
        
    except Exception as e:
        logger.error(f"Instagram metadata generation failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate-metadata-gallery', methods=['POST'])
def generate_metadata_gallery():
    """Generate metadata for video already in gallery"""
    try:
        data = request.get_json(silent=True) or {}
        video_file = data.get('video_file')
        
        if not video_file:
            return jsonify({'success': False, 'error': 'Video file is required'})
        
        # Build full path to gallery video
        video_path = os.path.join(GALLERY_FOLDER, video_file)
        
        # Verify video exists
        if not os.path.exists(video_path):
            return jsonify({'success': False, 'error': 'Video not found in gallery'})
        
        logger.info(f"✅ Analyzing gallery video: {video_path}")
        
        # Create AI Metadata Generator instance
        ai_generator = AIMetadataGenerator(GEMINI_API_KEY)
        
        # Generate metadata based on actual video content
        generated_metadata = ai_generator.generate_complete_metadata(
            video_path=video_path
        )
        
        return jsonify({
            'success': True,
            'title': generated_metadata['title'],
            'description': generated_metadata['description'],
            'tags': generated_metadata.get('tags', []),
            'hashtags': generated_metadata.get('hashtags', []),
            'video_analysis': generated_metadata.get('video_analysis', 'Analysis unavailable'),
            'video_file': video_file
        })
        
    except Exception as e:
        logger.error(f"Gallery metadata generation failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/list-gallery-videos')
def list_gallery_videos():
    """List all videos in gallery folder"""
    try:
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
        videos = [f for f in os.listdir(GALLERY_FOLDER) 
                 if os.path.isfile(os.path.join(GALLERY_FOLDER, f)) 
                 and any(f.lower().endswith(ext) for ext in video_extensions)]
        
        videos.sort(key=lambda x: os.path.getmtime(os.path.join(GALLERY_FOLDER, x)), reverse=True)
        
        return jsonify({
            'success': True,
            'videos': videos,
            'count': len(videos)
        })
    except Exception as e:
        logger.error(f"Failed to list gallery videos: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload-to-gallery', methods=['POST'])
def upload_to_gallery():
    """Upload video file from device to gallery"""
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'})
        
        video_file = request.files['video']
        
        if video_file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Validate file extension
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
        file_ext = os.path.splitext(video_file.filename)[1].lower() # type: ignore
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload a video file.'})
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"device_upload_{timestamp}{file_ext}"
        filepath = os.path.join(GALLERY_FOLDER, safe_filename)
        
        # Save file to gallery
        video_file.save(filepath)
        
        logger.info(f"✅ Video uploaded to gallery: {filepath}")
        
        return jsonify({
            'success': True,
            'filename': safe_filename,
            'message': 'Video uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"Upload to gallery failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get-channel-info')
def channel_info():
    """Get information about the connected YouTube channel for current user"""
    try:
        token_path = get_user_token_path()
        if not check_authentication(token_path):
            return jsonify({'authenticated': False})
            
        channel_data = get_channel_info(token_path)
        if channel_data:
            return jsonify({
                'authenticated': True,
                'channel': channel_data
            })
        else:
            return jsonify({'authenticated': True, 'channel': None})
    except Exception as e:
        logger.error(f"Error getting channel info: {str(e)}")
        return jsonify({'authenticated': False, 'error': str(e)})

@app.route('/logout', methods=['POST'])
def logout():
    """Logout from YouTube for current user - complete cleanup"""
    try:
        token_path = get_user_token_path()
        
        # ✅ Try to revoke the token from Google
        if os.path.exists(token_path):
            try:
                from google.oauth2.credentials import Credentials
                import requests
                
                creds = Credentials.from_authorized_user_file(token_path)
                
                # Revoke the token at Google
                requests.post(
                    'https://oauth2.googleapis.com/revoke',
                    params={'token': creds.token},
                    headers={'content-type': 'application/x-www-form-urlencoded'
                })
                logger.info(f"✅ Revoked token at Google for session: {session.get('user_id')}")
            except Exception as e:
                logger.warning(f"Could not revoke token at Google: {e}")
            
            # Delete the token file
            try:
                os.remove(token_path)
                logger.info(f"🗑️ Deleted token file: {token_path}")
            except Exception as e:
                logger.error(f"Failed to delete token file: {e}")
        
        # ✅ Clear session completely
        user_id = session.get('user_id', 'unknown')
        session.clear()
        
        logger.info(f"👋 User logged out successfully: {user_id}")
        
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload-music', methods=['POST'])
def upload_music():
    """Upload music file for video editing"""
    try:
        if 'music' not in request.files:
            return jsonify({'success': False, 'error': 'No music file provided'})
        
        music_file = request.files['music']
        
        if not music_file.filename or music_file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Validate file type
        allowed_extensions = {'.mp3', '.wav', '.m4a', '.aac'}
        file_ext = os.path.splitext(music_file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Invalid file type. Only MP3, WAV, M4A, AAC allowed'})
        
        # Save uploaded music file
        music_folder = os.path.join(DOWNLOAD_FOLDER, 'uploaded_music')
        os.makedirs(music_folder, exist_ok=True)
        
        # Generate unique filename
        import time
        music_filename = f"music_{int(time.time())}_{music_file.filename}"
        music_path = os.path.join(music_folder, music_filename)
        
        music_file.save(music_path)
        
        logger.info(f"✅ Music file uploaded: {music_path}")
        
        return jsonify({
            'success': True,
            'filepath': music_path,
            'filename': music_filename
        })
        
    except Exception as e:
        logger.error(f"Music upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload-local-video', methods=['POST'])
def upload_local_video():
    """Upload video file from local device"""
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'})
        
        video_file = request.files['video']
        
        if not video_file.filename or video_file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Validate file type
        allowed_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        filename = video_file.filename
        if filename is None:
            return jsonify({'success': False, 'error': 'Invalid filename'})
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Invalid file type. Only MP4, MOV, AVI, MKV, WEBM, M4V allowed'})
        
        # Check file size (max 500MB)
        video_file.seek(0, os.SEEK_END)
        file_size = video_file.tell()
        video_file.seek(0)
        
        if file_size > 500 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'File size too large. Maximum 500MB allowed.'})
        
        # Save uploaded video file
        import time
        video_filename = f"local_{int(time.time())}_{video_file.filename}"
        video_path = os.path.join(DOWNLOAD_FOLDER, video_filename)
        
        video_file.save(video_path)
        
        logger.info(f"✅ Local video uploaded: {video_path} ({file_size / 1024 / 1024:.2f} MB)")
        
        return jsonify({
            'success': True,
            'filepath': video_path,
            'filename': video_filename,
            'size': file_size
        })
        
    except Exception as e:
        logger.error(f"Video upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload-local-async', methods=['POST'])
def upload_local_async():
    """Upload local video to YouTube with AI metadata"""
    try:
        # ✅ Check user-specific authentication
        token_path = get_user_token_path()
        if not check_authentication(token_path):
            return jsonify({'success': False, 'error': 'Not authenticated with YouTube'}), 401
        
        data = request.get_json(silent=True) or {}
        video_filepath = data.get('video_filepath')
        editing_options = data.get('editing')
        
        if not video_filepath:
            return jsonify({'success': False, 'error': 'Video filepath is required'})
        
        if not os.path.exists(video_filepath):
            return jsonify({'success': False, 'error': 'Video file not found'})
        
        task_id = str(uuid.uuid4())
        tasks[task_id] = TaskStatus(task_id)
        
        # Start background task
        thread = threading.Thread(
            target=background_local_upload_task,
            args=(task_id, video_filepath, editing_options, token_path)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Upload process started'
        })
        
    except Exception as e:
        logger.error(f"Local upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def background_local_upload_task(task_id: str, video_path: str, editing_options: Optional[dict] = None, token_path: str = 'token.json'):
    """Background task for processing and uploading local video"""
    edited_video_path = None
    uploaded_music_path = None
    
    try:
        # Verify video file exists
        if not os.path.exists(video_path):
            raise Exception("Video file not found")
        
        logger.info(f"✅ Local video ready: {video_path}")
        update_task_status(task_id, 'processing', 'Processing local video...', 10)
        
        # Determine final video path
        final_video_path = video_path
        
        # Video Editing Step (if enabled)
        if editing_options and editing_options.get('enabled'):
            try:
                update_task_status(task_id, 'editing', 'Editing video (adding music & text overlays)...', 20)
                
                logger.info(f"🎬 Starting video editing with options: {editing_options}")
                
                # Initialize video editor
                editor = VideoEditor()
                
                # Generate edited video filename
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                edited_video_path = os.path.join(DOWNLOAD_FOLDER, f"{base_name}_edited.mp4")
                
                # Determine music source
                music_source = editing_options.get('music_url') or editing_options.get('music_file')
                uploaded_music_path = editing_options.get('music_file')
                
                # Apply edits
                editor.edit_video(
                    video_path=video_path,
                    output_path=edited_video_path,
                    music_url=music_source,
                    music_volume=editing_options.get('music_volume', 0.3),
                    text_overlays=editing_options.get('text_overlays')
                )
                
                logger.info(f"✅ Video editing completed: {edited_video_path}")
                
                # Use edited video for upload
                final_video_path = edited_video_path
                
            except Exception as edit_error:
                error_msg = str(edit_error)
                logger.error(f"❌ Video editing failed: {error_msg}")
                
                # If editing fails, use original video
                logger.warning("⚠️ Using original video due to editing failure")
                final_video_path = video_path
                
                update_task_status(
                    task_id, 
                    'generating_metadata', 
                    f'Skipped editing (error: {error_msg[:50]}...). Using original video...', 
                    40
                )
        
        update_task_status(task_id, 'generating_metadata', 'AI analyzing video content and generating metadata...', 60)
        
        # Generate metadata using AI
        try:
            ai_generator = AIMetadataGenerator(GEMINI_API_KEY)
            
            generated_metadata = ai_generator.generate_complete_metadata(
                video_path=final_video_path
            )
            
            metadata = {
                'title': generated_metadata['title'],
                'description': generated_metadata['description'],
                'tags': generated_metadata['tags'],
                'keywords': generated_metadata['keywords'],
                'hashtags': generated_metadata['hashtags'],
                'video_analysis': generated_metadata.get('video_analysis', 'Content analysis unavailable')
            }
            
            logger.info(f"✅ AI metadata generated successfully")
            logger.info(f"📝 Title: {metadata['title']}")
            
        except Exception as e:
            logger.warning(f"AI metadata generation failed: {str(e)}. Using fallback metadata.")
            # Fallback metadata
            filename = os.path.basename(final_video_path)
            metadata = {
                'title': f'Amazing Video Content - {filename}',
                'description': f'Check out this amazing video!\n\n#Video #Content #Entertainment',
                'tags': ['video', 'content', 'entertainment'],
                'keywords': ['video content', 'entertainment'],
                'hashtags': ['#Video', '#Content', '#Entertainment']
            }
        
        update_task_status(task_id, 'uploading', 'Uploading to YouTube...', 85, metadata=metadata)
        
        # Upload to YouTube
        try:
            video_id = upload_to_youtube(
                video_path=final_video_path,
                title=metadata['title'],
                description=metadata['description'],
                tags=metadata['tags'],
                privacy_status="public",
                token_path=token_path
            )
            
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            
            update_task_status(
                task_id, 
                'completed', 
                'Upload completed successfully!', 
                100,
                result={'video_id': video_id},
                youtube_url=youtube_url,
                metadata=metadata
            )
            
        except Exception as upload_error:
            raise Exception(f"YouTube upload failed: {str(upload_error)}")
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        update_task_status(task_id, 'failed', str(e), error=str(e))
    finally:
        # Clean up files
        for path in [edited_video_path, uploaded_music_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"🧹 Cleaned up temporary file: {path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Could not clean up file {path}: {cleanup_error}")

@app.route('/offline')
def offline_page():
    """Offline fallback page for PWA"""
    return render_template('offline.html')

@app.route('/privacy-policy')
def privacy_policy():
    """Privacy policy page"""
    from datetime import datetime
    return render_template('privacy_policy.html', current_date=datetime.now().strftime('%B %d, %Y'))

@app.route('/terms')
def terms():
    """Terms of service page"""
    return render_template('terms.html')

# Secret key for sessions - MUST be set for production
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# ✅ Session configuration - UPDATED: Sessions persist until logout
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
app.config['SESSION_PERMANENT'] = True  # ✅ Changed to True - session persists
app.config['SESSION_USE_SIGNER'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 2592000  # ✅ 30 days max (safety limit)

# Create session directory
os.makedirs('/tmp/flask_session', exist_ok=True)

# ✅ Cookie security settings
if os.getenv('ENVIRONMENT') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
else:
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ✅ Global error handlers
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error', 'message': 'Please try again later'}), 500
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    import traceback
    logger.error(traceback.format_exc())
    
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'An unexpected error occurred',
            'message': str(e) if app.debug else 'Please try again later'
        }), 500
    
    return render_template('500.html'), 500

# ✅ Health check with detailed status
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        health_status = {
            'status': 'healthy',
            'version': '1.0.0',
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'checks': {
                'downloads_folder': os.path.exists(DOWNLOAD_FOLDER),
                'user_tokens_folder': os.path.exists(USER_TOKENS_FOLDER),
                'gemini_configured': bool(GEMINI_API_KEY and GEMINI_API_KEY != 'your-gemini-api-key-here'),
                'rapidapi_configured': bool(RAPIDAPI_KEY)
            }
        }
        
        # Check if all critical services are OK
        if not all(health_status['checks'].values()):
            health_status['status'] = 'degraded'
            return jsonify(health_status), 503
        
        return jsonify(health_status), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

# ✅ Request logging middleware - UPDATED
@app.before_request
def log_request():
    """Log incoming requests and manage sessions"""
    if not request.path.startswith('/static/'):
        logger.info(f"{request.method} {request.path} - Session: {session.get('user_id', 'none')[:8]}...")
    
    # ✅ Make session permanent - stays active until logout
    session.permanent = True

@app.after_request
def log_response(response):
    """Log responses"""
    if not request.path.startswith('/static/'):
        logger.info(f"{request.method} {request.path} - {response.status_code}")
    return response

# ✅ SIMPLIFIED: Only run if main (development)
if __name__ == "__main__":
    print(f"🚀 YouTube Automation Machine Starting...")
    print(f"📁 Downloads folder: {DOWNLOAD_FOLDER}")
    print(f"🎨 Gallery folder: {GALLERY_FOLDER}")
    print(f"📁 User tokens folder: {USER_TOKENS_FOLDER}")
    print(f"🤖 Gemini AI: {'Configured' if GEMINI_API_KEY else 'Not configured'}")
    print(f"🔑 RapidAPI: {'Configured' if RAPIDAPI_KEY else 'NOT CONFIGURED'}")
    print(f"🌐 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    
    # ✅ REMOVED: No cleanup on startup
    
    # Development server only
    app.run(debug=True)