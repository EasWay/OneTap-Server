import os
import uuid
import logging
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

# --- VERIFY yt-dlp VERSION ---
logger.info(f"🦖 yt-dlp Version: {yt_dlp.version.__version__}")

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
            logger.info("📺 YouTube URL: Using 'android_tv' client")
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
