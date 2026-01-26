from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import threading
import yt_dlp
from pathlib import Path
import glob
import json
import shutil

app = Flask(__name__)

# Configuration
DOWNLOAD_FOLDER = os.path.join(app.root_path, 'static', 'downloads')
PLAYLISTS_FILE = os.path.join(app.root_path, 'playlists.json')
Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

# Helper to manage playlists
def load_playlists():
    if not os.path.exists(PLAYLISTS_FILE):
        return {}
    try:
        with open(PLAYLISTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_playlists(data):
    with open(PLAYLISTS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Global status for progress tracking (simple implementation)
current_download_status = {
    'status': 'idle',
    'percentage': 0,
    'filename': '',
    'speed': '',
    'eta': ''
}

def progress_hook(d):
    global current_download_status
    if d['status'] == 'downloading':
        current_download_status['status'] = 'downloading'
        current_download_status['percentage'] = d.get('_percent_str', '0%').strip()
        current_download_status['filename'] = os.path.basename(d.get('filename', ''))
        current_download_status['speed'] = d.get('_speed_str', 'N/A')
        current_download_status['eta'] = d.get('_eta_str', 'N/A')
    elif d['status'] == 'finished':
        current_download_status['status'] = 'processing'
        current_download_status['percentage'] = '100%'

def run_download(url, type_format):
    global current_download_status
    current_download_status = {
        'status': 'starting',
        'percentage': '0%',
        'filename': 'Initializing...',
        'speed': '',
        'eta': ''
    }
    
    try:
        ydl_opts = {
            'progress_hooks': [progress_hook],
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'ignoreerrors': True,
        }

        if type_format == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else: # video
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        current_download_status['status'] = 'completed'
        
    except Exception as e:
        current_download_status['status'] = 'error'
        current_download_status['filename'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    type_format = data.get('type', 'video') # 'video' or 'audio'
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    if current_download_status['status'] == 'downloading':
        return jsonify({'error': 'Download already in progress'}), 409

    # Start download in a separate thread
    thread = threading.Thread(target=run_download, args=(url, type_format))
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Download started'})

@app.route('/status')
def status():
    return jsonify(current_download_status)

@app.route('/files')
def list_files():
    # List all files in downloads folder
    files = []
    # simple globs for mp4 and mp3
    for ext in ['*.mp4', '*.mp3', '*.m4a']:
        for filepath in glob.glob(os.path.join(DOWNLOAD_FOLDER, ext)):
            filename = os.path.basename(filepath)
            # determine type based on extension
            ftype = 'audio' if filename.endswith(('.mp3', '.m4a')) else 'video'
            files.append({
                'filename': filename,
                'path': f'/static/downloads/{filename}',
                'type': ftype
            })
    return jsonify(files)

@app.route('/delete', methods=['POST'])
def delete_file():
    data = request.json
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
        
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    # Security check to prevent traversing directories
    if not os.path.abspath(filepath).startswith(os.path.abspath(DOWNLOAD_FOLDER)):
         return jsonify({'error': 'Invalid path'}), 403

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
             # Also remove from playlists
            playlists = load_playlists()
            changed = False
            for pl in playlists:
                if filename in playlists[pl]:
                    playlists[pl].remove(filename)
                    changed = True
            if changed:
                save_playlists(playlists)
            
            return jsonify({'message': 'File deleted successfully'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'File not found'}), 404

# Playlist APIs
@app.route('/playlists', methods=['GET'])
def get_playlists():
    return jsonify(load_playlists())

@app.route('/playlists', methods=['POST'])
def create_playlist():
    data = request.json
    name = data.get('name')
    if not name:
         return jsonify({'error': 'Name required'}), 400
    
    playlists = load_playlists()
    if name in playlists:
        return jsonify({'error': 'Playlist already exists'}), 409
    
    playlists[name] = []
    save_playlists(playlists)
    return jsonify({'message': 'Playlist created', 'playlists': playlists})

@app.route('/playlists/<name>', methods=['DELETE'])
def delete_playlist(name):
    playlists = load_playlists()
    if name in playlists:
        del playlists[name]
        save_playlists(playlists)
        return jsonify({'message': 'Playlist deleted'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/playlists/<name>/add', methods=['POST'])
def add_to_playlist(name):
    data = request.json
    filename = data.get('filename')
    
    playlists = load_playlists()
    if name not in playlists:
        return jsonify({'error': 'Playlist not found'}), 404
        
    if filename not in playlists[name]:
        playlists[name].append(filename)
        save_playlists(playlists)
        
    return jsonify({'message': 'Added'})

@app.route('/playlists/<name>/remove', methods=['POST'])
def remove_from_playlist(name):
    data = request.json
    filename = data.get('filename')
    
    playlists = load_playlists()
    if name not in playlists:
        return jsonify({'error': 'Playlist not found'}), 404
        
    if filename in playlists[name]:
        playlists[name].remove(filename)
        save_playlists(playlists)
        
    return jsonify({'message': 'Removed'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
