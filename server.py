#!/usr/bin/env python3
"""
OneTap Social Media Video Downloader Server
Supports TikTok, Facebook, Instagram, and Twitter/X
Optimized for speed, efficiency, and quality
"""

import os
import uuid
import yt_dlp
import logging
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/onetap_server.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Suppress verbose logging from dependencies
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Cookie file for social media platforms
SOCIAL_COOKIES_FILE = os.path.join(os.getcwd(), "social_cookies.txt")

# Detect environment
IS_RENDER = os.environ.get('RENDER') is not None

# User agent for consistency across platforms
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Platform detection patterns
PLATFORM_PATTERNS = {
    'tiktok': ['tiktok.com', 'vm.tiktok.com'],
    'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
    'instagram': ['instagram.com', 'instagr.am'],
    'twitter': ['twitter.com', 'x.com', 't.co']
}


def detect_platform(url):
    """Detect platform from URL with improved accuracy"""
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc
        
        # Remove common prefixes
        for prefix in ['www.', 'm.', 'mobile.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
                break
        
        for platform, patterns in PLATFORM_PATTERNS.items():
            if any(pattern in domain for pattern in patterns):
                logger.info(f"✅ Detected platform: {platform}")
                return platform
        
        logger.warning(f"⚠️ Unknown platform for URL: {url}")
        return "generic"
    except Exception as e:
        logger.error(f"❌ Error detecting platform: {e}")
        return "generic"


def get_platform_config(platform):
    """Get optimized platform-specific yt-dlp configuration"""
    
    # Base configuration with industry best practices
    base_config = {
        "user_agent": USER_AGENT,
        "quiet": False,
        "no_warnings": False,
        "merge_output_format": "mp4",
        "retries": 5,
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
        "socket_timeout": 30,
        "http_chunk_size": 10485760,  # 10MB chunks
        "concurrent_fragment_downloads": 4,  # Parallel downloads for speed
        "http_headers": {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    }
    
    # Platform-specific optimizations
    if platform == "tiktok":
        config = {
            **base_config,
            "format": "best[ext=mp4]/best",
            "extractor_args": {
                "tiktok": {
                    "webpage_url_basename": "video",
                    "api_hostname": "api22-normal-c-useast2a.tiktokv.com"
                }
            }
        }
        
    elif platform == "facebook":
        # Use minimal config for Facebook (proven to work reliably)
        config = {
            "format": "best",
            "quiet": False,
            "no_warnings": False,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "http_chunk_size": 10485760,
            "concurrent_fragment_downloads": 4
        }
        
    elif platform == "instagram":
        config = {
            **base_config,
            "format": "best[ext=mp4]/best",
            "extractor_args": {
                "instagram": {
                    "comment_count": 0
                }
            },
            "http_headers": {
                **base_config["http_headers"],
                "Referer": "https://www.instagram.com/",
                "X-IG-App-ID": "936619743392459"
            }
        }
        
    elif platform == "twitter":
        config = {
            **base_config,
            "format": "best[ext=mp4]/best"
        }
        
    else:
        # Generic fallback
        config = base_config.copy()
        config["format"] = "best[ext=mp4]/best"
    
    # Add cookies if available
    if os.path.exists(SOCIAL_COOKIES_FILE):
        config["cookiefile"] = SOCIAL_COOKIES_FILE
        logger.info(f"🍪 Using authenticated cookies for {platform}")
    else:
        logger.warning(f"⚠️ No cookies found - some content may be unavailable")
    
    return config


@app.route("/", methods=["GET"])
def index():
    """Health check and API info"""
    return jsonify({
        "status": "online",
        "service": "OneTap Social Media Downloader",
        "version": "2.0.0",
        "supported_platforms": ["tiktok", "facebook", "instagram", "twitter"],
        "environment": "render" if IS_RENDER else "local",
        "cookies_loaded": os.path.exists(SOCIAL_COOKIES_FILE),
        "endpoints": {
            "download": "/download (POST)",
            "upload_cookies": "/upload_cookies (POST)",
            "files": "/files/<filename> (GET)",
            "health": "/health (GET)"
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Detailed health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "download_dir": os.path.exists(DOWNLOAD_DIR),
        "cookies_available": os.path.exists(SOCIAL_COOKIES_FILE),
        "disk_space_mb": get_disk_space()
    })


def get_disk_space():
    """Get available disk space in MB"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
        return free // (1024 * 1024)
    except:
        return -1


@app.route("/download", methods=["POST"])
def download_video():
    """Download video from supported social media platforms"""
    logger.info(f"🚀 Download request received ({'Render' if IS_RENDER else 'Local'} mode)")
    
    start_time = time.time()
    
    try:
        # Parse request
        data = request.get_json()
        url = data.get("url")
        
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        # Detect platform
        platform = detect_platform(url)
        
        if platform == "generic":
            return jsonify({
                "error": "Unsupported platform",
                "message": "Only TikTok, Facebook, Instagram, and Twitter are supported"
            }), 400

        # Generate unique filename
        uid = str(uuid.uuid4())[:8]
        
        # Get platform-specific configuration
        ydl_opts = get_platform_config(platform)
        ydl_opts["outtmpl"] = os.path.join(DOWNLOAD_DIR, f"{uid}_%(title)s.%(ext)s")
        
        # Execute download
        logger.info(f"⬇️ Starting download from {platform}...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = os.path.basename(ydl.prepare_filename(info))
        
        # Clean filename for safety
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        if safe_filename != filename:
            old_path = os.path.join(DOWNLOAD_DIR, filename)
            new_path = os.path.join(DOWNLOAD_DIR, safe_filename)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                filename = safe_filename
        
        # Calculate download time
        download_time = time.time() - start_time
        
        # Build download URL
        base_url = request.host_url.rstrip("/")
        if IS_RENDER:
            base_url = base_url.replace("http://", "https://")
        
        logger.info(f"✅ Download complete: {filename} ({download_time:.2f}s)")
        
        return jsonify({
            "status": "success",
            "message": "Download successful",
            "platform": platform,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "filename": filename,
            "download_url": f"{base_url}/files/{filename}",
            "uploader": info.get("uploader", "Unknown"),
            "view_count": info.get("view_count", 0),
            "download_time": round(download_time, 2),
            "environment": "render" if IS_RENDER else "local",
            "file_size_mb": round(os.path.getsize(os.path.join(DOWNLOAD_DIR, filename)) / (1024 * 1024), 2)
        })

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"❌ Download failed: {error_msg}")
        
        # Provide helpful error messages
        if "login" in error_msg.lower() or "private" in error_msg.lower():
            return jsonify({
                "error": f"Authentication required for {platform}",
                "message": "Please upload valid cookies using /upload_cookies endpoint",
                "platform": platform
            }), 401
        elif "not available" in error_msg.lower() or "removed" in error_msg.lower():
            return jsonify({
                "error": "Content not available",
                "message": "The video may be private, deleted, or geo-restricted",
                "platform": platform
            }), 404
        elif "unsupported url" in error_msg.lower():
            return jsonify({
                "error": "Unsupported URL format",
                "message": f"This {platform} URL format is not supported",
                "platform": platform
            }), 400
        else:
            return jsonify({
                "error": f"Download failed: {error_msg}",
                "platform": platform
            }), 500
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        logger.exception("Full error traceback:")
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/upload_cookies", methods=["POST"])
def upload_cookies():
    """Upload social media cookies in Netscape format"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Save cookies file
        file.save(SOCIAL_COOKIES_FILE)
        
        # Validate and count cookies
        cookie_stats = validate_cookies(SOCIAL_COOKIES_FILE)
        
        if cookie_stats['total'] == 0:
            return jsonify({"error": "No valid cookies found in file"}), 400
        
        logger.info(f"✅ Uploaded {cookie_stats['total']} cookies")
        
        return jsonify({
            "message": "Cookies uploaded successfully",
            "statistics": cookie_stats,
            "platforms": ["tiktok", "facebook", "instagram", "twitter"]
        })
        
    except Exception as e:
        logger.error(f"❌ Cookie upload failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


def validate_cookies(cookie_file):
    """Validate and analyze cookies file"""
    stats = {
        'total': 0,
        'tiktok': 0,
        'facebook': 0,
        'instagram': 0,
        'twitter': 0,
        'other': 0
    }
    
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain = parts[0].lower()
                        stats['total'] += 1
                        
                        if 'tiktok' in domain:
                            stats['tiktok'] += 1
                        elif 'facebook' in domain or 'fb' in domain:
                            stats['facebook'] += 1
                        elif 'instagram' in domain:
                            stats['instagram'] += 1
                        elif 'twitter' in domain or 'x.com' in domain:
                            stats['twitter'] += 1
                        else:
                            stats['other'] += 1
    except Exception as e:
        logger.error(f"❌ Error validating cookies: {e}")
    
    return stats


@app.route("/files/<filename>", methods=["GET"])
def serve_file(filename):
    """Serve downloaded files"""
    try:
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404


@app.route("/cleanup", methods=["POST"])
def cleanup_downloads():
    """Clean up old downloaded files"""
    try:
        import shutil
        
        if os.path.exists(DOWNLOAD_DIR):
            file_count = len([f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))])
            shutil.rmtree(DOWNLOAD_DIR)
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            
            logger.info(f"🧹 Cleaned up {file_count} files")
            
            return jsonify({
                "message": "Cleanup successful",
                "files_removed": file_count
            })
        else:
            return jsonify({"message": "Nothing to clean up"})
            
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


def get_port():
    """Get port from environment or use default"""
    return int(os.environ.get("PORT", 10000))


if __name__ == "__main__":
    port = get_port()
    logger.info(f"🚀 Starting OneTap Social Media Downloader on port {port}")
    logger.info(f"📁 Download directory: {DOWNLOAD_DIR}")
    logger.info(f"🍪 Cookies file: {SOCIAL_COOKIES_FILE}")
    logger.info(f"🌍 Environment: {'Render' if IS_RENDER else 'Local'}")
    logger.info(f"✅ Supported platforms: TikTok, Facebook, Instagram, Twitter")
    
    app.run(host="0.0.0.0", port=port, debug=False)
