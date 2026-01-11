#!/usr/bin/env python3
"""
OneTap Server - Clean Production Version
Supports: YouTube, TikTok, Instagram, Twitter, Facebook
"""

import os
import json
import uuid
import logging
import socket
import yt_dlp
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")
GOOGLE_COOKIES_FILE = os.path.join(os.getcwd(), "google_cookies.txt")

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route("/")
def home():
    return f"OneTap Backend Running 🚀 (yt-dlp v{yt_dlp.version.__version__})"

@app.route("/update_cookies", methods=["POST"])
def update_cookies():
    """Upload cookies for social media platforms"""
    try:
        if 'file' not in request.files: 
            return jsonify({"error": "No file"}), 400
        file = request.files['file']
        file.save(COOKIES_FILE)
        return jsonify({"message": "Cookies updated", "size": os.path.getsize(COOKIES_FILE)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_google_cookies", methods=["POST"])
def update_google_cookies():
    """Upload Google cookies for YouTube"""
    try:
        if 'file' not in request.files: 
            return jsonify({"error": "No file"}), 400
        file = request.files['file']
        file.save(GOOGLE_COOKIES_FILE)
        return jsonify({"message": "Google cookies updated", "size": os.path.getsize(GOOGLE_COOKIES_FILE)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download_video():
    """Main download endpoint with platform-specific optimization"""
    logger.info("🚀 Download request received")
    try:
        data = request.get_json()
        url = data.get("url") if data else None
        if not url: 
            return jsonify({"error": "No URL provided"}), 400

        # Generate unique filename
        uid = str(uuid.uuid4())
        output_template = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        # Base yt-dlp options
        ydl_opts = {
            "outtmpl": output_template,
            "format": "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[ext=m4a]/bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[vcodec^=avc1]/best[ext=mp4]/best",
            "noplaylist": True,
            "retries": 5,
            "fragment_retries": 5,
            "quiet": False,
            "noprogress": True,
            "merge_output_format": "mp4",
            "sleep_interval": 1,
            "max_sleep_interval": 3,
        }

        # Platform-specific configuration
        if "youtube.com" in url or "youtu.be" in url:
            logger.info("📺 YouTube URL detected")
            
            # Try Google cookies first
            if os.path.exists(GOOGLE_COOKIES_FILE):
                logger.info("🍪 Using Google cookies for YouTube")
                ydl_opts["cookiefile"] = GOOGLE_COOKIES_FILE
            else:
                logger.info("📱 Using iOS client for YouTube (no cookies)")
                # iOS client with android_tv fallback
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": ["ios", "android_tv", "web"]
                    }
                }
                
        elif any(platform in url for platform in ["tiktok.com", "instagram.com", "twitter.com", "x.com", "facebook.com"]):
            logger.info("🍪 Social Media: Using cookies if available")
            
            # Skip TikTok photo posts
            if "tiktok.com" in url and "/photo/" in url:
                return jsonify({"error": "TikTok photo posts not supported. Only videos allowed."}), 400
            
            # Use cookies if available
            if os.path.exists(COOKIES_FILE):
                ydl_opts["cookiefile"] = COOKIES_FILE
            
            # Set user agent for social media
            ydl_opts["user_agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        # Start download
        logger.info("⬇️ Starting download...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = os.path.basename(ydl.prepare_filename(info))

            # Get video info
            video_codec = info.get('vcodec', 'unknown')
            audio_codec = info.get('acodec', 'unknown')
            container = info.get('ext', 'unknown')
            
            logger.info(f"📹 Downloaded: {filename}")
            logger.info(f"🎥 Video codec: {video_codec}")
            logger.info(f"🔊 Audio codec: {audio_codec}")
            logger.info(f"📦 Container: {container}")
            logger.info(f"✅ Download complete: {filename}")

            return jsonify({
                "message": "Download successful",
                "filename": filename,
                "video_codec": video_codec,
                "audio_codec": audio_codec,
                "container": container
            })

    except yt_dlp.DownloadError as e:
        error_msg = str(e)
        logger.error(f"❌ Download failed: {error_msg}")
        
        # Provide helpful error messages
        if "Sign in to confirm your age" in error_msg:
            return jsonify({"error": "Age-restricted video. Please upload Google cookies."}), 400
        elif "Private video" in error_msg:
            return jsonify({"error": "Private video. Please upload appropriate cookies."}), 400
        elif "Video unavailable" in error_msg:
            return jsonify({"error": "Video unavailable or region-blocked."}), 400
        else:
            return jsonify({"error": f"Download failed: {error_msg}"}), 400
            
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route("/check_formats", methods=["POST"])
def check_formats():
    """Check available formats for a URL"""
    try:
        data = request.get_json()
        url = data.get("url") if data else None
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "listformats": True,
        }
        
        # Add cookies if available
        if "youtube.com" in url or "youtu.be" in url:
            if os.path.exists(GOOGLE_COOKIES_FILE):
                ydl_opts["cookiefile"] = GOOGLE_COOKIES_FILE
        elif os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for fmt in info.get('formats', []):
                formats.append({
                    'format_id': fmt.get('format_id'),
                    'ext': fmt.get('ext'),
                    'resolution': fmt.get('resolution'),
                    'filesize': fmt.get('filesize'),
                    'vcodec': fmt.get('vcodec'),
                    'acodec': fmt.get('acodec'),
                })

            return jsonify({
                "title": info.get('title'),
                "duration": info.get('duration'),
                "formats": formats[:20]  # Limit to first 20 formats
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/files/<filename>")
def files(filename):
    """Serve downloaded files"""
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/version")
def check_version():
    """App version check for mobile clients"""
    return jsonify({
        "latest_version": 3, 
        "apk_url": "https://github.com/EasWay/OneTap/releases/download/v1.2/app-release.apk",
        "release_notes": "Improved stability and performance"
    })

@app.route("/status")
def system_status():
    """System status endpoint"""
    try:
        status = {
            "status": "online",
            "yt_dlp_version": yt_dlp.version.__version__,
            "downloads_dir": {
                "exists": os.path.exists(DOWNLOAD_DIR),
                "files_count": len(os.listdir(DOWNLOAD_DIR)) if os.path.exists(DOWNLOAD_DIR) else 0
            },
            "cookies": {
                "social_media": os.path.exists(COOKIES_FILE),
                "google": os.path.exists(GOOGLE_COOKIES_FILE)
            }
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def find_free_port():
    """Find a free port for the server"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

if __name__ == "__main__":
    # Get port from environment or find free port
    port = int(os.environ.get("PORT", find_free_port()))
    
    logger.info(f"🦖 yt-dlp Version: {yt_dlp.version.__version__}")
    logger.info(f"🚀 Starting OneTap Server on port {port}")
    
    # Run the server
    app.run(host="0.0.0.0", port=port, debug=False)