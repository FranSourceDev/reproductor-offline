from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import threading
import yt_dlp
from pathlib import Path
import glob
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Secret key from environment
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Production: PostgreSQL
    # Fix common postgres:// to postgresql:// (Railway/Heroku compatibility)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    
    # PostgreSQL connection pool settings
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
else:
    # Development: SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///media.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Constants
DOWNLOAD_FOLDER = os.environ.get('DOWNLOAD_FOLDER', os.path.join(app.root_path, 'static', 'downloads'))
Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    media_items = db.relationship('Media', backref='owner', lazy=True)
    playlists = db.relationship('Playlist', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_url = db.Column(db.String(500))
    title = db.Column(db.String(255))
    type = db.Column(db.String(10)) # 'video' or 'audio'
    path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    items = db.relationship('PlaylistItem', backref='playlist', cascade="all, delete-orphan", lazy=True)

class PlaylistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), nullable=False)
    media = db.relationship('Media')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Global Download Status ---
current_download_status = {
    'status': 'idle',
    'percentage': 0, 'filename': '', 'speed': '', 'eta': '', 'user_id': None, 'should_cancel': False
}

def progress_hook(d):
    global current_download_status
    if current_download_status.get('should_cancel', False):
        raise Exception("Download cancelled by user")
    if d['status'] == 'downloading':
        current_download_status['status'] = 'downloading'
        current_download_status['percentage'] = d.get('_percent_str', '0%').strip()
        current_download_status['filename'] = os.path.basename(d.get('filename', ''))
        current_download_status['speed'] = d.get('_speed_str', 'N/A')
        current_download_status['eta'] = d.get('_eta_str', 'N/A')
    elif d['status'] == 'finished':
        current_download_status['status'] = 'processing'
        current_download_status['percentage'] = '100%'

def run_download(url, type_format, user_id):
    global current_download_status
    current_download_status = {
        'status': 'starting', 'percentage': '0%', 'filename': 'Initializing...', 
        'speed': '', 'eta': '', 'user_id': user_id, 'should_cancel': False
    }
    
    with app.app_context():
        try:
            ydl_opts = {
                'progress_hooks': [progress_hook],
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'ignoreerrors': True,
                'no_warnings': True,
                'noplaylist': True, # Ensure only the single video is downloaded
                'writethumbnail': True, # Download thumbnail
            }

            # Enforce Audio + Thumbnail Embedding
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [
                    {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'},
                    {'key': 'EmbedThumbnail'},
                    {'key': 'FFmpegMetadata'},
                ],
            })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Metadata extraction for DB
                if 'entries' in info:
                    entries = info['entries']
                else:
                    entries = [info]

                for entry in entries:
                    if not entry: continue
                    title = entry.get('title', 'Unknown')
                    # Filename logic is tricky with yt-dlp outtmpl, relying on what we find or reconstructing it
                    # Simplified: Re-scan directory or trust yt-dlp return (often messy). 
                    # Better approach: Check what file was created.
                    # For this implementation, we will use the 'requested_downloads' or search for the title.
                    # Fallback: We will just save what we know.
                    
                    # Get actual filename from yt-dlp
                    # We need to run prepare_filename on the entry to see what it *would* be
                    # But post-processing might change extension (e.g. mkv -> mp4, or mp4 -> mp3)
                    # For audio, we force mp3 in postprocessor.
                    
                    # Try to get the exact final filename from yt-dlp's internal state
                    if 'requested_downloads' in entry and entry['requested_downloads']:
                        final_path = entry['requested_downloads'][0]['filepath']
                        final_filename = os.path.basename(final_path)
                    else:
                        # Fallback: Prepare filename and guess extension if requested_downloads is missing
                        try:
                            filepath_from_ydl = ydl.prepare_filename(entry)
                            base_name = os.path.splitext(os.path.basename(filepath_from_ydl))[0]
                            final_filename = f"{base_name}.mp3"
                        except Exception as e:
                            print(f"Error preparing filename: {e}")
                            final_filename = f"{title}.mp3"

                    # Final verification
                    expected_path = os.path.join(DOWNLOAD_FOLDER, final_filename)
                    if not os.path.exists(expected_path):
                         # Try to find a match by globbing title if strict match fails (due to sanitization)
                        # This is a fallback
                        try:
                            candidates = glob.glob(os.path.join(DOWNLOAD_FOLDER, f"{glob.escape(os.path.splitext(final_filename)[0])}*"))
                            if not candidates:
                               candidates = glob.glob(os.path.join(DOWNLOAD_FOLDER, f"{glob.escape(title)}*"))
                            
                            if candidates:
                                # Pick the newest or best match
                                expected_path = candidates[0]
                                final_filename = os.path.basename(expected_path)
                            else:
                                print(f"Warning: Could not locate file for {title}")
                                continue
                        except Exception as e:
                            print(f"Error in fallback search: {e}")
                            continue

                    # Insert into DB
                    new_media = Media(
                        user_id=user_id,
                        filename=final_filename, 
                        original_url=url,
                        title=title,
                        type='audio', # Force type to audio
                        path=f'/static/downloads/{final_filename}'
                    )
                    db.session.add(new_media)
                
                db.session.commit()

            current_download_status['status'] = 'completed'
            
        except Exception as e:
            current_download_status['status'] = 'error'
            current_download_status['filename'] = str(e)

# --- Routes ---

@app.before_request
def create_tables():
    db.create_all()

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/health')
def health():
    """Health check endpoint for Docker and Coolify"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


@app.route('/download', methods=['POST'])
@login_required
def download():
    data = request.json
    url = data.get('url')
    type_format = data.get('type', 'video')
    
    if not url: return jsonify({'error': 'No URL provided'}), 400
    if current_download_status['status'] == 'downloading':
        return jsonify({'error': 'Download already in progress'}), 409

    thread = threading.Thread(target=run_download, args=(url, type_format, current_user.id))
    thread.daemon = True
    thread.start()
    return jsonify({'message': 'Download started'})

@app.route('/cancel', methods=['POST'])
@login_required
def cancel_download():
    global current_download_status
    if current_download_status['status'] in ['starting', 'downloading']:
        current_download_status['should_cancel'] = True
        return jsonify({'message': 'Cancellation requested'})
    return jsonify({'error': 'No active download'}), 400

@app.route('/status')
def status():
    return jsonify(current_download_status)

@app.route('/files')
@login_required
def list_files():
    # Helper: Sync DB with filesystem on list (Optional but good for integrity)
    # For now, just list DB items
    media_items = Media.query.filter_by(user_id=current_user.id).order_by(Media.created_at.desc()).all()
    files = []
    for item in media_items:
        files.append({
            'id': item.id,
            'filename': item.filename,
            'path': item.path,
            'type': item.type,
            'title': item.title
        })
    return jsonify(files)

@app.route('/delete', methods=['POST'])
@login_required
def delete_file():
    data = request.json
    filename = data.get('filename') # or ID
    
    # We should delete by ID ideally, but sticking to filename for now or switch to ID
    # Let's accept filename for backward compat with frontend or upgrade frontend.
    # Actually, let's look up by filename + user_id
    
    media = Media.query.filter_by(filename=filename, user_id=current_user.id).first()
    
    if not media:
        return jsonify({'error': 'File not found'}), 404
        
    try:
        # Remove from Disk
        full_path = os.path.join(DOWNLOAD_FOLDER, media.filename)
        if os.path.exists(full_path):
            os.remove(full_path)
        
        # Remove from DB (Cascade will handle playlist items)
        db.session.delete(media)
        db.session.commit()
        return jsonify({'message': 'Deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/files/sync', methods=['POST'])
@login_required
def sync_files():
    """Endpoint to discover files on disk not in DB and add them to current user"""
    # Simple logic: Scan directory, if not in DB, add it.
    # Note: This assigns ALL stray files to the current user. Valid for single-user migration.
    
    disk_files = glob.glob(os.path.join(DOWNLOAD_FOLDER, '*'))
    count = 0
    for file_path in disk_files:
        filename = os.path.basename(file_path)
        if filename.endswith(('.mp4', '.mp3', '.m4a')):
            exists = Media.query.filter_by(filename=filename).first()
            if not exists:
                ftype = 'audio' if filename.endswith(('.mp3', '.m4a')) else 'video'
                new_media = Media(
                    user_id=current_user.id,
                    filename=filename,
                    title=filename,
                    type=ftype,
                    path=f'/static/downloads/{filename}'
                )
                db.session.add(new_media)
                count += 1
    db.session.commit()
    return jsonify({'message': f'Synced {count} files'})

# --- Playlist DB Routes ---
@app.route('/playlists', methods=['GET'])
@login_required
def get_playlists():
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    result = {}
    for pl in playlists:
        # Get filenames for this playlist
        items = [item.media.filename for item in pl.items if item.media] # check if media still exists
        result[pl.name] = items
    return jsonify(result)

@app.route('/playlists', methods=['POST'])
@login_required
def create_playlist():
    data = request.json
    name = data.get('name')
    if not name: return jsonify({'error': 'Name required'}), 400
    
    if Playlist.query.filter_by(user_id=current_user.id, name=name).first():
        return jsonify({'error': 'Playlist already exists'}), 409
        
    new_pl = Playlist(name=name, user_id=current_user.id)
    db.session.add(new_pl)
    db.session.commit()
    
    # Return full list format
    # Actually just success message is enough usually, but let's stick to old API format if possible or standard
    return jsonify({'message': 'Created'})

@app.route('/playlists/<name>', methods=['DELETE'])
@login_required
def delete_playlist(name):
    pl = Playlist.query.filter_by(user_id=current_user.id, name=name).first()
    if pl:
        db.session.delete(pl)
        db.session.commit()
        return jsonify({'message': 'Deleted'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/playlists/<name>/add', methods=['POST'])
@login_required
def add_to_playlist(name):
    data = request.json
    filename = data.get('filename')
    
    pl = Playlist.query.filter_by(user_id=current_user.id, name=name).first()
    media = Media.query.filter_by(user_id=current_user.id, filename=filename).first()
    
    if not pl or not media:
        return jsonify({'error': 'Playlist or Media not found'}), 404
        
    # Check duplicate
    exists = PlaylistItem.query.filter_by(playlist_id=pl.id, media_id=media.id).first()
    if not exists:
        item = PlaylistItem(playlist_id=pl.id, media_id=media.id)
        db.session.add(item)
        db.session.commit()
        
    return jsonify({'message': 'Added'})

if __name__ == '__main__':
    # Initial DB Create handled by before_request first run or manual
    # But better to do it here
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
