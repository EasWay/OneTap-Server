#!/usr/bin/env python3
"""
OneTap Multi-Platform Video Downloader Server
Supports YouTube, TikTok, Facebook, Instagram, Twitter/X
"""

import os
import uuid
import yt_dlp
import logging
import shutil
import socket
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Cookie files for different platforms
GOOGLE_COOKIES_FILE = os.path.join(os.getcwd(), "google_cookies.txt")
SOCIAL_COOKIES_FILE = os.path.join(os.getcwd(), "social_cookies.txt")
RENDER_COOKIES_FILE = os.path.join(os.getcwd(), "render_cookies.txt")

# Detect environment
IS_RENDER = os.environ.get('RENDER') is not None

# User agent for consistency
EXACT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_deno_path():
    """Locate Deno for YouTube challenges"""
    paths = [
        shutil.which("deno"),
        os.path.expanduser("~/.deno/bin/deno"),
        "/opt/render/.deno/bin/deno",
        "/usr/local/bin/deno",
        "/root/.deno/bin/deno"
    ]
    for p in paths:
        if p and os.path.exists(p):
            return p
    return "deno"

def detect_platform(url):
    """Detect video platform from URL"""
    domain = urlparse(url).netloc.lower()
    
    if "youtube" in domain or "youtu.be" in domain:
        return "youtube"
    elif "tiktok" in domain:
        return "tiktok"
    elif "facebook" in domain or "fb.watch" in domain or "fb.com" in domain:
        return "facebook"
    elif "instagram" in domain:
        return "instagram"
    elif "twitter" in domain or "x.com" in domain:
        return "twitter"
    elif "twitch.tv" in domain:
        return "twitch"
    elif "vimeo" in domain:
        return "vimeo"
    elif "dailymotion" in domain:
        return "dailymotion"
    else:
        return "generic"

def get_platform_config(platform):
    """Get platform-specific yt-dlp configuration"""
    base_config = {
        "user_agent": EXACT_UA,
        "quiet": False,
        "no_warnings": False,
        "merge_output_format": "mp4",
        "http_headers": {
            "User-Agent": EXACT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
        }
    }
    
    if platform == "youtube":
        deno_exe = get_deno_path()
        config = {
            **base_config,
            "format": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "js_engine": "deno",
            "js_runtimes": [deno_exe],
            "remote_components": "ejs:github",
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "web"],
                    "remote_components": ["ejs:github"]
                }
            }
        }
        
        # Add Google cookies if available
        if os.path.exists(GOOGLE_COOKIES_FILE):
            config["cookiefile"] = GOOGLE_COOKIES_FILE
            logger.info("🍪 Using Google cookies for YouTube")
        elif os.path.exists(RENDER_COOKIES_FILE):
            config["cookiefile"] = RENDER_COOKIES_FILE
            logger.info("🍪 Using render cookies for YouTube")
            
    elif platform == "tiktok":
        config = {
            **base_config,
            "format": "best[ext=mp4]/best",
            "extractor_args": {
                "tiktok": {
                    "webpage_url_basename": "video"
                }
            }
        }
        
        # Add social cookies if available
        if os.path.exists(SOCIAL_COOKIES_FILE):
            config["cookiefile"] = SOCIAL_COOKIES_FILE
            logger.info("🍪 Using social cookies for TikTok")
            
    elif platform == "facebook":
        config = {
            **base_config,
            "format": "best[ext=mp4]/best",
            "extractor_args": {
                "facebook": {
                    "legacy_ssl": True
                }
            }
        }
        
        # Add social cookies if available
        if os.path.exists(SOCIAL_COOKIES_FILE):
            config["cookiefile"] = SOCIAL_COOKIES_FILE
            logger.info("🍪 Using social cookies for Facebook")
            
    elif platform == "instagram":
        config = {
            **base_config,
            "format": "best[ext=mp4]/best",
            "extractor_args": {
                "instagram": {
                    "comment_count": 0
                }
            }
        }
        
        # Add social cookies if available
        if os.path.exists(SOCIAL_COOKIES_FILE):
            config["cookiefile"] = SOCIAL_COOKIES_FILE
            logger.info("🍪 Using social cookies for Instagram")
            
    elif platform == "twitter":
        config = {
            **base_config,
            "format": "best[ext=mp4]/best",
            "extractor_args": {
                "twitter": {
                    "legacy_api": False
                }
            }
        }
        
        # Add social cookies if available
        if os.path.exists(SOCIAL_COOKIES_FILE):
            config["cookiefile"] = SOCIAL_COOKIES_FILE
            logger.info("🍪 Using social cookies for Twitter/X")
            
    else:
        # Generic configuration for other platforms
        config = {
            **base_config,
            "format": "best[ext=mp4]/best"
        }
    
    return config

@app.route("/")
def home():
    """Server status page"""
    env_info = "Render" if IS_RENDER else "Local"
    return jsonify({
        "server": "OneTap Multi-Platform Video Downloader",
        "version": "2.0",
        "environment": env_info,
        "supported_platforms": [
            "YouTube", "TikTok", "Facebook", "Instagram", 
            "Twitter/X", "Twitch", "Vimeo", "Dailymotion"
        ],
        "status": "online"
    })

@app.route("/download", methods=["POST"])
def download_video():
    """Download video from supported platforms"""
    logger.info(f"🚀 Download request received ({'Render' if IS_RENDER else 'Local'} mode)")
    
    try:
        data = request.get_json()
        url = data.get("url")
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        platform = detect_platform(url)
        logger.info(f"🌍 Detected platform: {platform}")

        # Generate unique filename
        uid = str(uuid.uuid4())[:8]
        
        # Get platform-specific configuration
        ydl_opts = get_platform_config(platform)
        ydl_opts["outtmpl"] = os.path.join(DOWNLOAD_DIR, f"{uid}_%(title)s.%(ext)s")
        
        # Execute download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if platform == "youtube":
                logger.info(f"Using Deno at: {get_deno_path()}")
            
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
        
        base_url = request.host_url.rstrip("/")
        if IS_RENDER:
            base_url = base_url.replace("http://", "https://")
        
        logger.info(f"✅ Download complete: {filename}")
        
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
            "environment": "render" if IS_RENDER else "local"
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Download failed: {error_msg}")
        
        # Provide helpful error messages
        if "confirm you're not a bot" in error_msg.lower():
            return jsonify({
                "error": "Bot detection triggered",
                "suggestion": "Please refresh your cookies or try again later",
                "platform": platform
            }), 403
        elif "login" in error_msg.lower() or "private" in error_msg.lower():
            return jsonify({
                "error": f"Authentication required for {platform}",
                "suggestion": f"Please upload {platform} cookies using the appropriate endpoint",
                "platform": platform
            }), 401
        elif "not available" in error_msg.lower():
            return jsonify({
                "error": "Video not available",
                "suggestion": "The video may be private, deleted, or geo-restricted",
                "platform": platform
            }), 404
        else:
            return jsonify({
                "error": f"Download failed: {error_msg}",
                "platform": platform
            }), 500

@app.route("/upload_google_cookies", methods=["POST"])
def upload_google_cookies():
    """Upload Google/YouTube cookies"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        file.save(GOOGLE_COOKIES_FILE)
        
        # Count cookies
        cookie_count = 0
        with open(GOOGLE_COOKIES_FILE, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    cookie_count += 1
        
        logger.info(f"✅ Uploaded {cookie_count} Google cookies")
        
        return jsonify({
            "message": "Google cookies uploaded successfully",
            "cookie_count": cookie_count,
            "file_size": os.path.getsize(GOOGLE_COOKIES_FILE),
            "platform": "youtube"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/upload_social_cookies", methods=["POST"])
def upload_social_cookies():
    """Upload social media cookies (TikTok, Facebook, Instagram, Twitter)"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        file.save(SOCIAL_COOKIES_FILE)
        
        # Count cookies
        cookie_count = 0
        with open(SOCIAL_COOKIES_FILE, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    cookie_count += 1
        
        logger.info(f"✅ Uploaded {cookie_count} social media cookies")
        
        return jsonify({
            "message": "Social media cookies uploaded successfully",
            "cookie_count": cookie_count,
            "file_size": os.path.getsize(SOCIAL_COOKIES_FILE),
            "platforms": ["tiktok", "facebook", "instagram", "twitter"]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/upload_cookies", methods=["POST"])
def upload_cookies():
    """Upload cookies for Render environment (backward compatibility)"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        file.save(RENDER_COOKIES_FILE)
        
        # Count cookies
        cookie_count = 0
        with open(RENDER_COOKIES_FILE, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    cookie_count += 1
        
        logger.info(f"✅ Uploaded {cookie_count} render cookies")
        
        return jsonify({
            "message": "Cookies uploaded successfully",
            "cookie_count": cookie_count,
            "file_size": os.path.getsize(RENDER_COOKIES_FILE)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/cookies_status")
def cookies_status():
    """Check cookies status for all platforms"""
    try:
        sources = []
        
        # Check Google cookies
        if os.path.exists(GOOGLE_COOKIES_FILE):
            size = os.path.getsize(GOOGLE_COOKIES_FILE)
            count = sum(1 for line in open(GOOGLE_COOKIES_FILE) if line.strip() and not line.startswith('#'))
            sources.append({
                "type": "google",
                "file": GOOGLE_COOKIES_FILE,
                "size": size,
                "count": count,
                "platforms": ["youtube"]
            })
        
        # Check social cookies
        if os.path.exists(SOCIAL_COOKIES_FILE):
            size = os.path.getsize(SOCIAL_COOKIES_FILE)
            count = sum(1 for line in open(SOCIAL_COOKIES_FILE) if line.strip() and not line.startswith('#'))
            sources.append({
                "type": "social",
                "file": SOCIAL_COOKIES_FILE,
                "size": size,
                "count": count,
                "platforms": ["tiktok", "facebook", "instagram", "twitter"]
            })
        
        # Check render cookies
        if os.path.exists(RENDER_COOKIES_FILE):
            size = os.path.getsize(RENDER_COOKIES_FILE)
            count = sum(1 for line in open(RENDER_COOKIES_FILE) if line.strip() and not line.startswith('#'))
            sources.append({
                "type": "render",
                "file": RENDER_COOKIES_FILE,
                "size": size,
                "count": count,
                "platforms": ["all"]
            })
        
        total_cookies = sum(s["count"] for s in sources)
        
        return jsonify({
            "cookies_available": len(sources) > 0,
            "sources": sources,
            "total_cookies": total_cookies,
            "status": "healthy" if total_cookies > 0 else "missing",
            "recommendations": {
                "youtube": "Upload Google cookies for better YouTube access",
                "social": "Upload social media cookies for TikTok, Facebook, Instagram, Twitter"
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/files/<filename>")
def files(filename):
    """Serve downloaded files"""
    try:
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

@app.route("/status")
def system_status():
    """System status and capabilities"""
    try:
        # Check cookie availability
        cookie_sources = []
        if os.path.exists(GOOGLE_COOKIES_FILE):
            cookie_sources.append("google")
        if os.path.exists(SOCIAL_COOKIES_FILE):
            cookie_sources.append("social")
        if os.path.exists(RENDER_COOKIES_FILE):
            cookie_sources.append("render")
        
        # Check Deno availability
        deno_available = os.path.exists(get_deno_path())
        
        status = {
            "status": "online",
            "version": "2.0",
            "environment": "render" if IS_RENDER else "local",
            "server_mode": "OneTap Multi-Platform Video Downloader",
            "supported_platforms": [
                "YouTube", "TikTok", "Facebook", "Instagram", 
                "Twitter/X", "Twitch", "Vimeo", "Dailymotion"
            ],
            "cookies": {
                "available": len(cookie_sources) > 0,
                "sources": cookie_sources
            },
            "deno": {
                "available": deno_available,
                "path": get_deno_path() if deno_available else None
            },
            "downloads_dir": {
                "exists": os.path.exists(DOWNLOAD_DIR),
                "files_count": len(os.listdir(DOWNLOAD_DIR)) if os.path.exists(DOWNLOAD_DIR) else 0
            },
            "capabilities": [
                "Multi-platform video downloading",
                "yt-dlp with platform optimization",
                "Cookie-based authentication",
                "Deno JavaScript engine for YouTube" if deno_available else "Basic YouTube support"
            ],
            "recommendations": []
        }
        
        # Add recommendations
        if not cookie_sources:
            status["recommendations"].append("Upload cookies for better platform access")
        if not deno_available:
            status["recommendations"].append("Deno not found - YouTube downloads may be limited")
        if len(cookie_sources) > 0:
            status["recommendations"].append("Multi-platform support active with authentication")
            
        return jsonify(status)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/platforms")
def supported_platforms():
    """List supported platforms and their requirements"""
    return jsonify({
        "platforms": {
            "youtube": {
                "name": "YouTube",
                "domains": ["youtube.com", "youtu.be"],
                "cookies_file": "google_cookies.txt",
                "requires_deno": True,
                "features": ["High quality", "Age-restricted content", "Private videos"]
            },
            "tiktok": {
                "name": "TikTok",
                "domains": ["tiktok.com"],
                "cookies_file": "social_cookies.txt",
                "requires_deno": False,
                "features": ["HD videos", "Private accounts with cookies"]
            },
            "facebook": {
                "name": "Facebook",
                "domains": ["facebook.com", "fb.watch", "fb.com"],
                "cookies_file": "social_cookies.txt",
                "requires_deno": False,
                "features": ["Public and private videos", "Stories with cookies"]
            },
            "instagram": {
                "name": "Instagram",
                "domains": ["instagram.com"],
                "cookies_file": "social_cookies.txt",
                "requires_deno": False,
                "features": ["Posts", "Stories", "Reels", "IGTV"]
            },
            "twitter": {
                "name": "Twitter/X",
                "domains": ["twitter.com", "x.com"],
                "cookies_file": "social_cookies.txt",
                "requires_deno": False,
                "features": ["Video tweets", "Spaces recordings"]
            },
            "twitch": {
                "name": "Twitch",
                "domains": ["twitch.tv"],
                "cookies_file": "social_cookies.txt",
                "requires_deno": False,
                "features": ["VODs", "Clips", "Highlights"]
            },
            "vimeo": {
                "name": "Vimeo",
                "domains": ["vimeo.com"],
                "cookies_file": None,
                "requires_deno": False,
                "features": ["Public videos", "Password-protected with cookies"]
            },
            "dailymotion": {
                "name": "Dailymotion",
                "domains": ["dailymotion.com"],
                "cookies_file": None,
                "requires_deno": False,
                "features": ["Public videos", "HD quality"]
            }
        },
        "cookie_endpoints": {
            "google_cookies": "/upload_google_cookies",
            "social_cookies": "/upload_social_cookies",
            "render_cookies": "/upload_cookies"
        }
    })

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
    
    logger.info(f"🌐 Environment: {'Render' if IS_RENDER else 'Local Development'}")
    logger.info(f"🎬 Multi-Platform Support: YouTube, TikTok, Facebook, Instagram, Twitter/X")
    
    # Check Deno availability
    deno_path = get_deno_path()
    if os.path.exists(deno_path):
        logger.info(f"🟢 Deno available: {deno_path}")
    else:
        logger.warning("🟡 Deno not found - YouTube downloads may be limited")
    
    # Check cookie availability
    cookie_files = [
        ("Google", GOOGLE_COOKIES_FILE),
        ("Social", SOCIAL_COOKIES_FILE),
        ("Render", RENDER_COOKIES_FILE)
    ]
    
    for name, file_path in cookie_files:
        if os.path.exists(file_path):
            logger.info(f"🍪 {name} cookies: ✅ Available")
        else:
            logger.info(f"🍪 {name} cookies: ❌ Not found")
    
    logger.info(f"🚀 Starting OneTap Multi-Platform Server on port {port}")
    
    # Run the server
    app.run(host="0.0.0.0", port=port, debug=False)