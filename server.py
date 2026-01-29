import os
import uuid
import yt_dlp
import logging
import shutil
import requests
import time
import re
import json
from flask import Flask, request, jsonify, send_from_directory
from urllib.parse import urlparse, urlunparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CONFIGURATION ---
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Cookie paths
GOOGLE_COOKIES_FILE = os.path.join(os.getcwd(), "google_cookies.txt")
SOCIAL_COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")
EXTRACTED_COOKIES = os.path.join(os.getcwd(), "profile_extracted_cookies.txt")
AUTH_PROFILE_DIR = os.path.join(os.getcwd(), "chrome_profile")

# Exact UA for consistency
EXACT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

# --- J2 WRAPPER CONFIG ---
J2_BASE_URL = "https://j2download.com"
J2_API_URL = f"{J2_BASE_URL}/api/autolink"
J2_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"

def remove_query_params(url):
    """Removes tracking parameters"""
    try:
        if "?" in url: return url.split("?")[0]
        return url
    except: return url

def expand_short_url(url):
    """Resolves short URLs"""
    try:
        short_domains = ['vt.tiktok.com', 'vm.tiktok.com', 'bit.ly', 't.co', 'fb.me', 'pin.it', 't.snapchat.com', 'lnkd.in', 'r.mtdv.me', 'youtu.be', 'x.com']
        if any(x in url for x in short_domains):
            logger.info(f"🔗 Expanding short URL: {url}")
            headers = {"User-Agent": J2_UA}
            try:
                resp = requests.head(url, allow_redirects=True, headers=headers, timeout=5)
                if resp.status_code >= 400: raise Exception("Head failed")
            except:
                resp = requests.get(url, allow_redirects=True, headers=headers, stream=True, timeout=5)
                resp.close()
            resolved = resp.url
            if "login" not in resolved:
                clean = remove_query_params(resolved)
                logger.info(f"✅ Resolved to: {clean}")
                return clean
    except Exception as e:
        logger.warning(f"⚠️ URL Expansion failed: {e}")
    return remove_query_params(url)

def clean_url_text(text):
    match = re.search(r'(https?://[^\s]+)', text)
    if match: return match.group(1)
    return text

def detect_platform(url):
    domain = urlparse(url).netloc.lower()
    if "tiktok" in domain: return "tiktok"
    if "facebook" in domain or "fb.watch" in domain: return "facebook"
    if "instagram" in domain: return "instagram"
    if "twitter" in domain or "x.com" in domain: return "twitter"
    if "youtube" in domain or "youtu.be" in domain: return "youtube"
    return "generic"

# --- SMART PARSER ---
class J2ResponseParser:
    @staticmethod
    def parse(data, platform):
        medias = data.get("medias", [])
        if not medias: return None
        
        logger.info(f"🧠 Parsing {len(medias)} formats for {platform}")
        
        if platform == "tiktok":
            return J2ResponseParser._parse_tiktok(medias)
        elif platform in ["facebook", "instagram"]:
            return J2ResponseParser._parse_meta(medias)
        elif platform == "twitter":
            return J2ResponseParser._parse_twitter(medias)
        elif platform == "youtube":
            return J2ResponseParser._parse_youtube(medias)
        
        # Generic fallback
        # Try to find a video type first
        for m in medias:
            if m.get("type") == "video": return m
        return medias[0]
    
    @staticmethod
    def _parse_tiktok(medias):
        for m in medias:
            if m.get("quality") == "hd_no_watermark": return m
        for m in medias:
            if m.get("quality") == "no_watermark": return m
        return medias[0]
    
    @staticmethod
    def _parse_meta(medias):
        videos = [m for m in medias if m.get("type") == "video"]
        for v in videos:
            q = str(v.get("quality", "")).lower()
            if "hd" in q or "1080" in q or "720" in q:
                return v
        return videos[0] if videos else None
    
    @staticmethod
    def _parse_twitter(medias):
        # Twitter usually returns an m3u8 playlist and mp4s
        # We prefer the highest bitrate mp4
        videos = [m for m in medias if m.get("type") == "video" and m.get("extension") == "mp4"]
        if not videos: return None
        
        # Sometimes formats are nested inside the 'medias' object for Twitter
        # Check if the first media object has a 'formats' list
        if "formats" in medias[0]:
            sub_formats = medias[0].get("formats", [])
            mp4s = [f for f in sub_formats if f.get("container") == "mp4"]
            if mp4s:
                try:
                    # Sort by bitrate descending
                    mp4s.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
                    return {"url": mp4s[0]["url"], "extension": "mp4"}
                except: pass
        
        try:
            videos.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
        except: pass
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_youtube(medias):
        valid_videos = []
        for m in medias:
            if m.get("type") == "video":
                if m.get("is_audio") is True or m.get("audioQuality"):
                    valid_videos.append(m)
        
        if not valid_videos:
            return medias[0]
        
        return valid_videos[0]

class J2Extractor:
    def extract_download_url(self, video_url):
        try:
            platform = detect_platform(video_url)
            logger.info(f"🎯 J2 Extraction for {platform}: {video_url}")
            
            session = requests.Session()
            session.headers.update({
                "User-Agent": J2_UA,
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Mode": "cors",
                "Origin": J2_BASE_URL,
                "Referer": f"{J2_BASE_URL}/"
            })
            
            # Handshake
            home_resp = session.get(J2_BASE_URL, timeout=10)
            csrf_token = session.cookies.get("csrf_token")
            
            if not csrf_token:
                meta = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', home_resp.text)
                if meta: csrf_token = meta.group(1)
            
            if not csrf_token:
                js_match = re.search(r'csrf_token\s*=\s*["\']([^"\']+)["\']', home_resp.text)
                if js_match: csrf_token = js_match.group(1)
            
            if not csrf_token: return None
            
            # API Call
            session.headers.update({
                "Content-Type": "application/json",
                "x-csrf-token": csrf_token,
                "X-Requested-With": "XMLHttpRequest"
            })
            
            payload = {
                "data": {
                    "url": video_url,
                    "unlock": True
                }
            }
            
            response = session.post(J2_API_URL, json=payload, timeout=25)
            data = response.json()
            
            if "error" in data and data["error"]: return None
            
            # Use Smart Parser
            best_media = J2ResponseParser.parse(data, platform)
            if best_media:
                return {
                    "url": best_media.get("url"),
                    "ext": best_media.get("extension", "mp4"),
                    "title": data.get("title", "video")
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ J2 Failed: {e}")
            return None

class OneTapDownloader:
    """Selenium / yt-dlp Logic (Backup Strategy)"""
    
    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={EXACT_UA}")
        chrome_options.add_argument("--disable-gpu")
        
        if os.path.exists(AUTH_PROFILE_DIR):
            chrome_options.add_argument(f"--user-data-dir={AUTH_PROFILE_DIR}")
        
        try:
            if os.path.exists("/usr/bin/google-chrome"):
                chrome_options.binary_location = "/usr/bin/google-chrome"
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            return driver
        except Exception as e:
            logger.error(f"❌ Failed to start Chrome: {e}")
            return None
    
    def get_direct_video_url(self, target_url):
        driver = self.setup_driver()
        if not driver: return None
        
        try:
            logger.info(f"🌐 Selenium Scraper: Digging for video in {target_url}")
            driver.get(target_url)
            time.sleep(5)
            
            # Expanded selectors for all platforms
            selectors = [
                "video", "video source", 
                "div[data-sigil='inlineVideo'] video", 
                "video.xh-highlight",
                "div[data-testid='video-player'] video"
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        src = el.get_attribute("src")
                        if src and src.startswith("http") and "blob:" not in src:
                            return src
                except: continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Scraper Error: {e}")
            return None
        finally:
            driver.quit()

def download_to_server(url, filename):
    """Downloads file from URL to server.
    FIX: Removed generic headers to prevent 403 Forbidden on CDNs (like Twitter/X)
    """
    try:
        # Some CDNs reject requests with Referer set or specific UAs
        # We start with a clean session and minimal headers
        session = requests.Session()
        headers = {
            "User-Agent": EXACT_UA,
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
        
        with session.get(url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"❌ File Save Failed: {e}")
        return False

@app.route("/download", methods=["POST"])
def download_video():
    logger.info("🚀 Download request received")
    
    try:
        data = request.get_json()
        raw_url = data.get("url")
        if not raw_url: return jsonify({"error": "No URL"}), 400
        
        uid = str(uuid.uuid4())
        final_filename = None
        
        # 1. Clean & Expand URL
        clean_text = clean_url_text(raw_url)
        url = expand_short_url(clean_text)
        domain = urlparse(url).netloc.lower()
        platform = detect_platform(url)
        
        logger.info(f"✅ Processing [{platform}]: {url}")
        
        # --- STRATEGY 1: J2 API ---
        j2 = J2Extractor()
        j2_result = j2.extract_download_url(url)
        
        if j2_result:
            logger.info("✅ J2 Success. Downloading...")
            ext = j2_result.get("ext", "mp4")
            filename = f"{uid}.{ext}"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            
            if download_to_server(j2_result["url"], filepath):
                final_filename = filename
            else:
                logger.warning("⚠️ J2 link valid, but download failed. Falling back...")
        
        # --- STRATEGY 2: LOCAL BACKUP ---
        if not final_filename:
            logger.info("🔄 Triggering Local Backup...")
            
            ydl_opts = {
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s"),
                "user_agent": EXACT_UA,
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "quiet": False
            }
            
            if platform == "youtube":
                deno_path = shutil.which("deno") or "/opt/render/.deno/bin/deno"
                if not os.path.exists(deno_path): deno_path = "/root/.deno/bin/deno"
                
                ydl_opts.update({
                    "format": "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[ext=m4a]/best",
                    "js_engine": "deno",
                    "js_runtimes": [deno_path],
                    "extractor_args": {
                        "youtube": {
                            "player_client": ["ios", "web"]
                        }
                    }
                })
                
                if os.path.exists(GOOGLE_COOKIES_FILE):
                    ydl_opts["cookiefile"] = GOOGLE_COOKIES_FILE
            elif os.path.exists(SOCIAL_COOKIES_FILE):
                ydl_opts["cookiefile"] = SOCIAL_COOKIES_FILE
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    final_filename = os.path.basename(ydl.prepare_filename(info))
            except Exception as e:
                # --- STRATEGY 3: SELENIUM ---
                if platform in ["facebook", "instagram", "tiktok", "snapchat", "pinterest", "twitter"]:
                    logger.warning("⚠️ yt-dlp failed. Activating Selenium Scraper...")
                    
                    downloader = OneTapDownloader()
                    direct_url = downloader.get_direct_video_url(url)
                    
                    if direct_url:
                        filename = f"{uid}.mp4"
                        filepath = os.path.join(DOWNLOAD_DIR, filename)
                        
                        if download_to_server(direct_url, filepath):
                            final_filename = filename
        
        if not final_filename:
            return jsonify({"error": "All extraction methods failed"}), 500
        
        base_url = request.host_url.rstrip("/").replace("http://", "https://")
        
        return jsonify({
            "status": "success",
            "download_url": f"{base_url}/files/{final_filename}",
            "filename": final_filename
        })
        
    except Exception as e:
        logger.error(f"❌ Final Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/files/<filename>")
def files(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/update_cookies", methods=["POST"])
def update_social_cookies():
    try:
        file = request.files['file']
        file.save(SOCIAL_COOKIES_FILE)
        return jsonify({"status": "success"})
    except: return jsonify({"error": "Failed"}), 500

@app.route("/update_google_cookies", methods=["POST"])
def update_google_cookies():
    try:
        file = request.files['file']
        file.save(GOOGLE_COOKIES_FILE)
        return jsonify({"status": "success"})
    except: return jsonify({"error": "Failed"}), 500

@app.route("/upload_profile", methods=["POST"])
def upload_profile():
    try:
        file = request.files['file']
        if os.path.exists(AUTH_PROFILE_DIR): shutil.rmtree(AUTH_PROFILE_DIR)
        os.makedirs(AUTH_PROFILE_DIR)
        
        zip_path = os.path.join(AUTH_PROFILE_DIR, "profile.zip")
        file.save(zip_path)
        
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(AUTH_PROFILE_DIR)
        
        return jsonify({"status": "success"})
    except: return jsonify({"error": "Failed"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)