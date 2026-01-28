# OneTap Social Media Video Downloader Server

## Overview
A Flask-based backend API for downloading videos from social media platforms including TikTok, Facebook, Instagram, and Twitter/X.

## Tech Stack
- **Language**: Python 3.11
- **Framework**: Flask 3.0.0
- **Dependencies**: flask-cors, yt-dlp (from GitHub master), requests
- **System**: ffmpeg (for video processing)

## Running the Server
The server runs on port 5000 (configured via PORT environment variable).
```bash
python server.py
```

## API Endpoints
- `GET /` - Health check and API info
- `GET /health` - Detailed health check
- `GET /version` - App update endpoint
- `POST /download` - Download video from URL (body: `{"url": "..."}`)
- `POST /upload_cookies` - Upload cookies file for authenticated downloads
- `GET /files/<filename>` - Retrieve downloaded file
- `POST /cleanup` - Clean up downloaded files

## Project Structure
- `server.py` - Main Flask application
- `tiktok_extractor.py` - TikTok mobile API extractor
- `tiktok_mobile_api.py` - TikTok mobile API implementation
- `tiktok_config.py` - TikTok configuration
- `device_fingerprint.py` - Device fingerprinting for TikTok API
- `requirements.txt` - Python dependencies

## Environment Variables
- `PORT` - Server port (default: 5000 for Replit)
- `RENDER` - Set to detect Render environment

## Deployment
For production, use a WSGI server like gunicorn instead of Flask's development server.
