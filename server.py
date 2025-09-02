import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp

app = Flask(__name__)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")  # Use your exported cookies.txt

@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    uid = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "retries": 3,
        "fragment_retries": 3,
        "quiet": False,
        "noprogress": True,
    }

    # If cookies.txt exists, always use it
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return jsonify({"error": "Download failed"}), 500

            ext = info.get("ext", "mp4")
            filename = f"{uid}.{ext}"
            file_path = os.path.join(DOWNLOAD_DIR, filename)

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found after download"}), 500

        # Instead of sending the file directly, return a public URL
        base_url = request.host_url.rstrip("/")
        # Ensure the download_url uses https
        download_url = f"{base_url}/files/{filename}"
        if download_url.startswith("http://"):
            download_url = download_url.replace("http://", "https://", 1)
        return jsonify({"download_url": download_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serve the downloaded files
@app.route("/files/<filename>")
def files(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
