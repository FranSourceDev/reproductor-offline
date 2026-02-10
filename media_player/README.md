# YouTube Media Player

Self-hosted offline media player for downloading and streaming YouTube audio files. Built with Flask, PostgreSQL, and yt-dlp.

## Features

- 🎵 Download YouTube audio as MP3
- 📱 Beautiful, responsive dark UI
- 🎨 Playlist management
- 👥 Multi-user support with authentication
- 🔄 Sync local files to library
- 🎯 Audio player with controls
- 🐳 Docker-ready for Coolify/self-hosted deployment

## Tech Stack

- **Backend**: Flask + SQLAlchemy
- **Database**: PostgreSQL (production) / SQLite (development)
- **Frontend**: Tailwind CSS + Vanilla JS
- **Audio Processing**: yt-dlp + FFmpeg
- **Deployment**: Docker + Gunicorn

## Quick Start (Development)

### Prerequisites
- Python 3.12+
- FFmpeg installed
- PostgreSQL (optional, uses SQLite by default)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/youtube-downloader.git
cd youtube-downloader/media_player

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

Visit `http://localhost:5000`

## Deployment

### Coolify (Recommended)

Complete step-by-step guide: [COOLIFY_DEPLOYMENT.md](COOLIFY_DEPLOYMENT.md)

**Quick overview:**
1. Create PostgreSQL database in Coolify
2. Create application from GitHub repository
3. Set environment variables (`DATABASE_URL`, `SECRET_KEY`)
4. Configure persistent volume for downloads
5. Deploy with one click

### Docker Compose (Local Testing)

```bash
# Build and run
docker-compose up -d

# Access application
open http://localhost:8000

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Configuration

### Environment Variables

Create `.env` file (use `.env.example` as template):

```env
SECRET_KEY=your-random-secret-key
DATABASE_URL=postgresql://user:pass@host:5432/db
FLASK_ENV=production
```

### Generate Secret Key
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Project Structure

```
media_player/
├── app.py                  # Main application
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Local testing
├── requirements.txt       # Python dependencies
├── static/
│   └── downloads/        # Downloaded audio files
├── templates/
│   ├── index.html        # Main player interface
│   ├── login.html
│   └── register.html
└── COOLIFY_DEPLOYMENT.md # Deployment guide
```

## API Endpoints

- `GET /` - Main player interface
- `GET /health` - Health check (for Docker)
- `POST /download` - Download audio from URL
- `POST /cancel` - Cancel active download
- `GET /status` - Download progress
- `GET /files` - List user's media files
- `POST /files/sync` - Sync filesystem with database

## Development

### Running Tests

```bash
# Local development with SQLite
python app.py

# Test with PostgreSQL (Docker)
docker run -d --name postgres-test \
  -e POSTGRES_PASSWORD=test \
  -p 5432:5432 postgres:15

export DATABASE_URL=postgresql://postgres:test@localhost:5432/test
python app.py
```

## License

MIT License - feel free to use for personal or commercial projects.

## Credits

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Tailwind CSS](https://tailwindcss.com/) - UI styling
