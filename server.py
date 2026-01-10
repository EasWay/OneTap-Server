import os
import uuid
import logging
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('app.log')]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CONFIGURATION ---
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")
GOOGLE_COOKIES_FILE = os.path.join(os.getcwd(), "google_cookies.txt")

# YouTube session extension settings
YOUTUBE_SESSION_INTERVAL_HOURS = 6  # Extend session every 6 hours
last_youtube_extension = None

# --- VERIFY yt-dlp VERSION ---
logger.info(f"🦖 yt-dlp Version: {yt_dlp.version.__version__}")

def youtube_session_scheduler():
    """Background thread that periodically extends YouTube session"""
    global last_youtube_extension
    
    while True:
        try:
            current_time = datetime.now()
            
            # Check if we need to extend the session
            if (last_youtube_extension is None or 
                current_time - last_youtube_extension >= timedelta(hours=YOUTUBE_SESSION_INTERVAL_HOURS)):
                
                # Only try if Google cookies file exists
                if os.path.exists(GOOGLE_COOKIES_FILE):
                    logger.info("🔄 Scheduled YouTube session extension starting...")
                    from cookie_manager import extend_google_youtube_session
                    
                    success = extend_google_youtube_session()
                    if success:
                        last_youtube_extension = current_time
                        logger.info("✅ Scheduled YouTube session extension completed")
                    else:
                        logger.warning("⚠️ Scheduled YouTube session extension failed")
                else:
                    logger.info("📝 No Google cookies found, skipping scheduled extension")
            
            # Sleep for 30 minutes before checking again
            time.sleep(1800)  # 30 minutes
            
        except Exception as e:
            logger.error(f"❌ YouTube session scheduler error: {str(e)}")
            time.sleep(3600)  # Wait 1 hour on error

# Start the background scheduler
scheduler_thread = threading.Thread(target=youtube_session_scheduler, daemon=True)
scheduler_thread.start()
logger.info(f"🕒 YouTube session scheduler started (interval: {YOUTUBE_SESSION_INTERVAL_HOURS}h)")

@app.route("/")
def home():
    return f"OneTap Backend Running 🚀 (yt-dlp v{yt_dlp.version.__version__})"

@app.route("/update_cookies", methods=["POST"])
def update_cookies():
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
    """Upload Google cookies for YouTube session extension"""
    try:
        if 'file' not in request.files: 
            return jsonify({"error": "No file"}), 400
        file = request.files['file']
        google_cookies_file = os.path.join(os.getcwd(), "google_cookies.txt")
        file.save(google_cookies_file)
        return jsonify({"message": "Google cookies updated", "size": os.path.getsize(google_cookies_file)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/extend_youtube_session", methods=["POST"])
def extend_youtube_session():
    """Manually trigger YouTube session extension"""
    try:
        from cookie_manager import extend_google_youtube_session
        success = extend_google_youtube_session()
        if success:
            global last_youtube_extension
            last_youtube_extension = datetime.now()
            return jsonify({"message": "YouTube session extended successfully"})
        else:
            return jsonify({"error": "Failed to extend YouTube session"}), 500
    except Exception as e:
        logger.error(f"YouTube session extension failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/youtube_session_status", methods=["GET"])
def youtube_session_status():
    """Check YouTube session extension status"""
    try:
        google_cookies_exists = os.path.exists(GOOGLE_COOKIES_FILE)
        
        status = {
            "google_cookies_uploaded": google_cookies_exists,
            "last_extension": last_youtube_extension.isoformat() if last_youtube_extension else None,
            "next_scheduled_extension": None,
            "extension_interval_hours": YOUTUBE_SESSION_INTERVAL_HOURS
        }
        
        if last_youtube_extension:
            next_extension = last_youtube_extension + timedelta(hours=YOUTUBE_SESSION_INTERVAL_HOURS)
            status["next_scheduled_extension"] = next_extension.isoformat()
            status["minutes_until_next"] = int((next_extension - datetime.now()).total_seconds() / 60)
        
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download_video():
    logger.info("🚀 Download request received")
    try:
        data = request.get_json()
        url = data.get("url") if data else None
        if not url: 
            return jsonify({"error": "No URL provided"}), 400

        # --- Generate unique filename template ---
        uid = str(uuid.uuid4())
        output_template = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        # --- yt-dlp base options ---
        ydl_opts = {
            "outtmpl": output_template,
            "format": "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
            "noplaylist": True,
            "retries": 5,
            "fragment_retries": 5,
            "quiet": False,
            "noprogress": True,
            "merge_output_format": "mp4",
        }

        # --- Determine platform-specific strategy ---
        if "youtube.com" in url or "youtu.be" in url:
            logger.info("📺 YouTube URL detected")
            
            # Try Google cookies first (for signed-in experience)
            if os.path.exists(GOOGLE_COOKIES_FILE):
                logger.info("🍪 Using Google cookies for YouTube")
                ydl_opts["cookiefile"] = GOOGLE_COOKIES_FILE
                ydl_opts["user_agent"] = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            else:
                logger.info("📱 Using android_tv client for YouTube (no cookies)")
                ydl_opts["extractor_args"] = {"youtube": {"player_client": ["android_tv"]}}
                ydl_opts.pop("cookiefile", None)
        else:
            logger.info("🍪 Social Media: Using Cookies + UA")
            ydl_opts["user_agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            if os.path.exists(COOKIES_FILE):
                ydl_opts["cookiefile"] = COOKIES_FILE

            # --- TikTok / VM links ---
            if "tiktok.com" in url:
                # Skip photo posts
                if "/photo/" in url:
                    return jsonify({"error": "Unsupported TikTok photo URL. Only videos are allowed."}), 400
                logger.info("📱 TikTok/social detected — video-only strategy")

        # --- Start download ---
        logger.info("⬇️ Starting download...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = os.path.basename(ydl.prepare_filename(info))
            logger.info(f"✅ Download complete: {filename}")

        # --- Return secure HTTPS download link ---
        base_url = request.host_url.rstrip("/")
        if base_url.startswith("http://"): 
            base_url = base_url.replace("http://", "https://", 1)

        return jsonify({"download_url": f"{base_url}/files/{filename}"})

    except Exception as e:
        logger.error(f"❌ Download failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/files/<filename>")
def files(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/version", methods=["GET"])
def check_version():
    return jsonify({
        "latest_version": 3, 
        "apk_url": "https://github.com/EasWay/OneTap/releases/download/v1.2/app-release.apk",
        "release_notes": "Critical Fixes"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
