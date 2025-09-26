import os
import uuid
import time
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import sys

# Import the new cookie management module
# NOTE: This assumes cookie_manager.py is in the same directory
from cookie_manager import generate_new_instagram_cookies

app = Flask(__name__)

# --- Configuration ---
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")

# Load credentials from environment variables
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")

if not IG_USERNAME or not IG_PASSWORD:
    print("WARNING: IG_USERNAME or IG_PASSWORD environment variables are not set.")
    print("Video downloads from private sites will likely fail.")
    # Exit here to prevent unexpected runtime errors if you need the creds to start
    # sys.exit(1) # Consider exiting in a real server environment

# --- Helper Functions ---

def attempt_download(url, output_template):
    """
    Attempts to download a video using yt-dlp with the current cookies.
    Returns (filename, error_message)
    """
    
    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "retries": 3,
        "fragment_retries": 3,
        "quiet": True,  # Suppress excessive output for cleaner logs
        "noprogress": True,
    }

    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, "Download failed (yt-dlp returned no info)."

            # Get the actual filename after potential merging and file extension resolution
            # The 'requested_downloads' attribute is a good indicator of the final path
            final_path = ydl.in_template_path(output_template)
            
            # Since yt-dlp might rename/merge, we need to find the actual file.
            # A common reliable way is to check the post-processing status
            if 'filepath' in info:
                file_path = info['filepath']
            elif 'requested_downloads' in info and info['requested_downloads']:
                # Get the path of the first successful download/merge
                file_path = info['requested_downloads'][0].get('filepath', '')
            else:
                # Fallback on old method if the above doesn't work, though less reliable
                ext = info.get("ext", "mp4")
                file_path = f"{output_template.split('%')[0].strip('.')}.{ext}"
            
            # Extract just the filename for the return value
            filename = os.path.basename(file_path)

        if not os.path.exists(os.path.join(DOWNLOAD_DIR, filename)):
            return None, f"File not found after download: {filename}. Possible authentication failure."

        return filename, None

    except Exception as e:
        error_msg = str(e)
        # Check if the error suggests a login/auth issue
        # yt-dlp often reports 'HTTP Error 404' or '403 Forbidden' for auth issues
        if "403 Forbidden" in error_msg or "404 Not Found" in error_msg or "No such file or directory" in error_msg:
             return None, f"Auth or Download Failure: {error_msg}"
        return None, error_msg

# --- Flask Routes ---

@app.route("/")
def home():
    return "OneTap Server is running"

@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    uid = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")
    
    # 1. First download attempt
    filename, error_msg = attempt_download(url, output_template)

    # 2. Check for authentication/cookie failure
    if error_msg and ("Auth" in error_msg or "Forbidden" in error_msg):
        print(f"Download failed with potential auth error: {error_msg}")
        
        if IG_USERNAME and IG_PASSWORD:
            # Attempt to refresh cookies
            if generate_new_instagram_cookies(IG_USERNAME, IG_PASSWORD):
                # Retry download after successful cookie refresh
                print("Cookie refresh successful. Retrying download...")
                filename, error_msg = attempt_download(url, output_template)
            else:
                print("Cookie refresh failed. Aborting retry.")
        else:
            print("Cannot refresh cookies: IG_USERNAME or IG_PASSWORD not configured.")

    # 3. Final error check
    if error_msg:
        # Check if the generated cookie file is now empty, indicating a failed login
        if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) < 100:
             return jsonify({"error": f"Download failed, and automated login also failed. Please check credentials or network: {error_msg}"}), 500
        return jsonify({"error": f"Download failed after all attempts: {error_msg}"}), 500

    # 4. Success response
    base_url = request.host_url.rstrip("/")
    download_url = f"{base_url}/files/{filename}"
    if download_url.startswith("http://"):
        download_url = download_url.replace("http://", "https://", 1)
        
    return jsonify({"download_url": download_url})

# Serve the downloaded files
@app.route("/files/<filename>")
def files(filename):
    # Security note: send_from_directory handles path traversal security
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Generate cookies on startup to ensure initial session is valid
    if IG_USERNAME and IG_PASSWORD:
        generate_new_instagram_cookies(IG_USERNAME, IG_PASSWORD)
    
    app.run(host="0.0.0.0", port=port, debug=True)
