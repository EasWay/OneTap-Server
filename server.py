import os
import tempfile
import uuid
from flask import Flask, request, send_file, jsonify
import yt_dlp
import browser_cookie3

app = Flask(__name__)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_cookies_file():
    try:
        cj = browser_cookie3.load(domain_name="instagram.com")
        if not cj:
            return None
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.close()
        with open(tmp.name, "w", encoding="utf-8") as f:
            for cookie in cj:
                f.write("\t".join([
                    cookie.domain,
                    "TRUE" if cookie.domain_specified else "FALSE",
                    cookie.path,
                    "TRUE" if cookie.secure else "FALSE",
                    str(int(cookie.expires)) if cookie.expires else "0",
                    cookie.name,
                    cookie.value
                ]) + "\n")
        return tmp.name
    except Exception as e:
        print(f"[ERROR] Failed to extract cookies: {e}")
        return None

@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    uid = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

    cookiefile = get_cookies_file()

    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "retries": 3,
        "fragment_retries": 3,
        "quiet": False,
        "noprogress": True,
    }

    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return jsonify({"error": "Download failed"}), 500

            ext = info.get("ext", "mp4")
            file_path = os.path.join(DOWNLOAD_DIR, f"{uid}.{ext}")

        if cookiefile and os.path.exists(cookiefile):
            os.remove(cookiefile)

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found after download"}), 500

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
