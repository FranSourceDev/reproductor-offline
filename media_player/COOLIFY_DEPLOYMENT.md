# Coolify Deployment Guide

Complete guide to deploy the YouTube Media Player to your Coolify home server.

## Prerequisites

1. **Coolify Instance**: Running Coolify v4+ on your home server
2. **Domain**: Configured domain/subdomain pointing to your server (e.g., `media.yourdomain.com`)
3. **GitHub**: Repository pushed to GitHub with all deployment files

## Step 1: Create PostgreSQL Database in Coolify

1. Log into your Coolify dashboard
2. Click **+ New Resource** → **Database** → **PostgreSQL**
3. Configure database:
   - **Name**: `media-player-db`
   - **PostgreSQL Version**: `15`
   - **Database Name**: `mediadb`
   - **Username**: Auto-generated or set your own
   - **Password**: Auto-generated (save this securely)
4. Click **Deploy** and wait for database to be ready
5. **Copy the Internal Connection URL** from the database details page
   - Format: `postgresql://username:password@postgres-service-name:5432/mediadb`

## Step 2: Create Application in Coolify

1. Click **+ New Resource** → **Application**
2. Choose **Public Repository** (or Private if you have access configured)
3. Repository configuration:
   - **Git Repository URL**: `https://github.com/yourusername/youtube-downloader`
   - **Branch**: `main`
   - **Base Directory**: Leave empty (Dockerfile is in repository root)
   - **Build Pack**: Select **Dockerfile**
4. Click **Continue**

## Step 3: Configure Environment Variables

In the Coolify application settings, go to **Environment Variables** and add:

| Variable | Value | Description |
|----------|-------|-------------|
| `FLASK_ENV` | `production` | Sets Flask to production mode |
| `SECRET_KEY` | `[random-string]` | Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `[from Step 1]` | PostgreSQL connection URL from database service |

**Example SECRET_KEY generation:**
```bash
# Run this locally to generate a secure key
python -c "import secrets; print(secrets.token_hex(32))"
# Copy the output to Coolify
```

## Step 4: Configure Persistent Storage

1. In your application settings, go to **Storages** tab
2. Click **+ Add Storage** (or **+ Add Volume**)
3. Configure volume:
   - **Name**: `media-downloads`
   - **Source Path**: Leave default (Coolify manages this)
   - **Destination Path**: `/app/static/downloads`
   - **Is Persistent**: ✅ Checked
4. Save the volume configuration

## Step 5: Configure Networking and Domain

1. Go to **Domains** tab in your application
2. Click **+ Add Domain**
3. Enter your domain: `media.yourdomain.com`
4. Enable **HTTPS** toggle
5. Coolify will automatically:
   - Configure reverse proxy
   - Request Let's Encrypt SSL certificate
   - Set up automatic HTTPS redirect

## Step 6: Deploy Application

1. Click the **Deploy** button in the application dashboard
2. Watch the build logs in real-time
3. Deployment process:
   - ✅ Pull code from GitHub
   - ✅ Build Docker image (installs FFmpeg, Python deps)
   - ✅ Start container with Gunicorn
   - ✅ Health check passes
   - ✅ Application is live

**Estimated build time**: 3-5 minutes

## Step 7: Verify Installation

### Check Health Endpoint
```bash
curl https://media.yourdomain.com/health
```

**Expected response:**
```json
{"status": "healthy", "database": "connected"}
```

### Test the Application
1. Visit `https://media.yourdomain.com`
2. Click **Register** and create a new user account
3. Login with your credentials
4. Try downloading an audio file from YouTube
5. Verify the file appears in your library

## Troubleshooting

### Deploy successful but site not loading
**Symptom**: Deployment logs show success ("New container started"), but site shows "Bad Gateway" or loads forever.

**Solutions**:
1. **Check Internal Port**:
   - Go to Coolify → Application → **Configuration**
   - Verify **Port Exposes** (or Internal Port) is set to `8000`.
   - Your application listens on port `8000`. If Coolify tries to connect to 3000 or 80, it will fail.
   
2. **Check Application Logs**:
   - Go to **Logs** tab in Coolify (not just Build Logs).
   - Look for Python errors like `ModuleNotFoundError` or `OperationalError`.
   - Common error: `sqlalchemy.exc.OperationalError` means database connection failed.

3. **Verify Database Connection**:
   - Ensure `DATABASE_URL` starts with `postgresql://` and not `postgres://`.
   - Check if the database username and password are correct.
   - Using `CTRL+F` in logs for "Error" helps find the issue quickly.

### Build Fails - FFmpeg Not Found
**Symptom**: Error during download: `ffmpeg not found`

**Solution**:
- Check `Dockerfile` includes FFmpeg installation
- Rebuild container: Click **Redeploy** in Coolify

### Database Connection Error
**Symptom**: Error 500, logs show `connection refused` or `database not found`

**Solutions**:
1. Verify `DATABASE_URL` environment variable is set correctly
2. Ensure PostgreSQL service is running (check database dashboard)
3. Confirm URL format: `postgresql://` not `postgres://`
4. Check database and application are in the same network

### Downloads Not Persisting After Restart
**Symptom**: Downloaded files disappear after container restarts

**Solutions**:
1. Verify persistent volume is configured
2. Check destination path is `/app/static/downloads`
3. Inspect volume in Coolify storage settings
4. Check container logs for permission errors

### SSL Certificate Fails
**Symptom**: HTTPS not working, certificate error

**Solutions**:
1. Verify domain DNS points to your server's public IP
2. Ensure ports 80 and 443 are open in firewall
3. Check Coolify's Traefik logs for certificate errors
4. Wait a few minutes for Let's Encrypt validation

### Application Crashes on Startup
**Symptom**: Container restarts repeatedly

**Solutions**:
1. Check logs in Coolify for Python errors
2. Verify all environment variables are set
3. Test database connection: `curl http://localhost:8000/health` (inside container)
4. Check resource limits (CPU/memory) in Coolify

## Backup Strategy

### Database Backups
Coolify provides automatic PostgreSQL backups:
1. Go to your PostgreSQL service
2. Click **Backups** tab
3. Configure:
   - **Backup Frequency**: Daily
   - **Retention**: 7-30 days
   - **Backup Location**: Local or S3

### Media Files Backup
SSH into your Coolify server and backup the volume:

```bash
# Find your volume path (usually in /var/lib/docker/volumes)
docker volume inspect media-downloads

# Backup to a tar file
sudo tar -czf media-backup-$(date +%Y%m%d).tar.gz \
    /var/lib/docker/volumes/media-downloads/_data/

# Optional: Copy to remote backup location
scp media-backup-*.tar.gz user@backup-server:/backups/
```

## Updating the Application

### Automatic Deployment (Recommended)
1. Enable **Auto Deploy** in Coolify application settings
2. Push changes to GitHub `main` branch
3. Coolify automatically rebuilds and redeploys

### Manual Deployment
1. Push changes to GitHub
2. Click **Redeploy** button in Coolify dashboard
3. Monitor build logs

## Performance Optimization

### Increase Workers
Edit environment variables or Dockerfile:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "app:app"]
```

### Resource Limits
In Coolify application settings:
- **Memory Limit**: 1GB minimum, 2GB recommended
- **CPU Limit**: 1-2 cores recommended

### Enable Caching
Consider adding Redis for session caching in future updates.

## Monitoring

### View Logs
- **Application Logs**: Coolify → Application → Logs tab
- **Real-time logs**: Click "Follow Logs" toggle

### Check Resource Usage
- **Container Stats**: Coolify → Application → Metrics tab
- **Disk Usage**: Monitor persistent volume size

### Alerts
Set up Coolify notifications:
- Application crashes
- Certificate expiration warnings
- Backup failures

## Security Best Practices

✅ Use strong `SECRET_KEY` (generated randomly)
✅ HTTPS enabled with Let's Encrypt
✅ Database credentials stored securely in Coolify
✅ Regular updates: `docker pull python:3.12-slim`
✅ Firewall configured: Only ports 80, 443 exposed

## Common Commands

### SSH into Container
```bash
# SSH into your Coolify server first
ssh user@your-coolify-server

# Find container ID
docker ps | grep media-player

# Access container shell
docker exec -it <container-id> /bin/bash
```

### Check Database Connection
```bash
# Inside container
python -c "from app import db; print('DB OK' if db.session.execute('SELECT 1') else 'DB ERROR')"
```

### View Downloaded Files
```bash
# Inside container
ls -lah /app/static/downloads/
```

## Support

If you encounter issues:
1. Check application logs in Coolify
2. Verify all environment variables are set
3. Test health endpoint: `/health`
4. Review Coolify documentation: https://coolify.io/docs
5. Check yt-dlp compatibility with latest YouTube changes

---

**Deployment Complete! 🎉**

Your YouTube Media Player is now live at `https://media.yourdomain.com`
