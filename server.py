import os
import uuid
import yt_dlp
import logging
import shutil
from flask import Flask, request, jsonify, send_from_directory
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CONFIGURATION ---
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Separate cookie files
GOOGLE_COOKIES_FILE = os.path.join(os.getcwd(), "google_cookies.txt")
SOCIAL_COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")

# Exact UA for session consistency
EXACT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.7499.192 Safari/537.36"

def get_deno_path():
    """Aggressively locate Deno for YouTube challenges"""
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
    domain = urlparse(url).netloc.lower()
    if "youtube" in domain or "youtu.be" in domain:
        return "youtube"
    elif "tiktok" in domain:
        return "tiktok"
    elif "facebook" in domain or "fb.watch" in domain:
        return "facebook"
    elif "instagram" in domain:
        return "instagram"
    elif "twitter" in domain or "x.com" in domain:
        return "twitter"
    return "generic"

@app.route("/update_cookies", methods=["POST"])
def update_social_cookies():
    try:
        if 'file' not in request.files: return jsonify({"error": "No file"}), 400
        file = request.files['file']
        file.save(SOCIAL_COOKIES_FILE)
        logger.info(f"🍪 Social cookies updated ({os.path.getsize(SOCIAL_COOKIES_FILE)} bytes)")
        return jsonify({"status": "success", "message": "Social cookies updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_google_cookies", methods=["POST"])
def update_google_cookies():
    try:
        if 'file' not in request.files: return jsonify({"error": "No file"}), 400
        file = request.files['file']
        file.save(GOOGLE_COOKIES_FILE)
        logger.info(f"🍪 Google cookies updated ({os.path.getsize(GOOGLE_COOKIES_FILE)} bytes)")
        return jsonify({"status": "success", "message": "Google cookies updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download_video():
    logger.info("🚀 Download request received")
    try:
        data = request.get_json()
        url = data.get("url")
        if not url: return jsonify({"error": "No URL"}), 400

        platform = detect_platform(url)
        logger.info(f"🌍 Detected platform: {platform}")

        uid = str(uuid.uuid4())
        # Base Options
        ydl_opts = {
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s"),
            "user_agent": EXACT_UA,
            "quiet": False,
            "no_warnings": False,
            "format": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "http_headers": {
                "User-Agent": EXACT_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
            }
        }

        # --- PLATFORM SPECIFIC STRATEGIES ---
        if platform == "youtube":
            deno_exe = get_deno_path()
            ydl_opts["js_engine"] = "deno"
            ydl_opts["js_runtimes"] = [deno_exe]
            ydl_opts["remote_components"] = "ejs:github"
            
            if os.path.exists(GOOGLE_COOKIES_FILE):
                logger.info("🍪 Using Google cookies")
                ydl_opts["cookiefile"] = GOOGLE_COOKIES_FILE
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": ["ios", "web"], 
                        "remote_components": ["ejs:github"]
                    }
                }
            else:
                ydl_opts["extractor_args"] = {"youtube": {"player_client": ["ios", "web"]}}

        elif platform in ["facebook", "instagram"]:
            if os.path.exists(SOCIAL_COOKIES_FILE):
                logger.info(f"🍪 Using Social cookies for {platform}")
                ydl_opts["cookiefile"] = SOCIAL_COOKIES_FILE
            
            if platform == "instagram":
                ydl_opts["format"] = "best" 

        elif platform == "tiktok":
            ydl_opts["format"] = "best[ext=mp4]/best"

        # --- EXECUTION ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if platform == "youtube":
                logger.info(f"Using Deno at: {get_deno_path()}")
            
            info = ydl.extract_info(url, download=True)
            filename = os.path.basename(ydl.prepare_filename(info))
            
        base_url = request.host_url.rstrip("/").replace("http://", "https://")
        
        return jsonify({
            "status": "success",
            "download_url": f"{base_url}/files/{filename}",
            "filename": filename,
            "platform": platform,
            "title": info.get("title", "Unknown")
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Download failed: {error_msg}")
        
        if "confirm you're not a bot" in error_msg.lower():
            return jsonify({"error": "Bot check triggered. Refresh cookies."}), 403
        if "login" in error_msg.lower():
            return jsonify({"error": f"Login required for {platform}. Upload cookies."}), 401
            
        return jsonify({"error": error_msg}), 500

@app.route("/files/<filename>")
def files(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/version", methods=["GET"])
def check_version():
    return jsonify({
        "latest_version": 4, 
        "status": "active", 
        "features": ["youtube", "tiktok", "facebook", "instagram", "twitter"]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🛠️ OneTap Multi-Platform Server starting on port {port}")
    # Fixed the syntax error here:
    app.run(host="0.0.0.0", port=port, threaded=True)
            "meta[property='og:title']"
            ]
            
            for selector in title_selectors:
                try:
                    if selector.startswith("meta"):
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        title = element.get_attribute("content")
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        title = element.text.strip()
                    
                    if title and title != "Unknown":
                        logger.info(f"📺 Video title: {title}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extract video duration from page source or meta tags
            duration = 0
            try:
                # Try to get duration from meta tag
                duration_element = self.driver.find_element(By.CSS_SELECTOR, "meta[itemprop='duration']")
                duration_content = duration_element.get_attribute("content")
                if duration_content:
                    # Parse ISO 8601 duration (PT1M30S -> 90 seconds)
                    duration = self.parse_duration(duration_content)
                    logger.info(f"⏱️ Video duration: {duration}s")
            except NoSuchElementException:
                logger.warning("⚠️ Could not extract video duration")
            
            # Get video ID from URL
            video_id = self.extract_video_id(url)
            
            return {
                "title": title,
                "duration": duration,
                "video_id": video_id,
                "original_url": url,
                "cookies_used": self.cookies_loaded,
                "method": "selenium"
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting video info: {str(e)}")
            return None
        """Extract video information using Selenium"""
        try:
            logger.info(f"🔍 Extracting video info from: {url}")
            
            # Load cookies if not already loaded
            if not self.cookies_loaded:
                self.load_authenticated_cookies()
            
            # Navigate to the video
            self.driver.get(url)
            time.sleep(5)
            
            # Wait for page to load
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                logger.warning("⚠️ Page load timeout, continuing...")
            
            # Extract video title
            title = "Unknown"
            title_selectors = [
                "h1.ytd-video-primary-info-renderer",
                "h1 yt-formatted-string",
                "h1.style-scope.ytd-video-primary-info-renderer",
                "meta[property='og:title']"
            ]
            
            for selector in title_selectors:
                try:
                    if selector.startswith("meta"):
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        title = element.get_attribute("content")
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        title = element.text.strip()
                    
                    if title and title != "Unknown":
                        logger.info(f"📺 Video title: {title}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extract video duration from page source or meta tags
            duration = 0
            try:
                # Try to get duration from meta tag
                duration_element = self.driver.find_element(By.CSS_SELECTOR, "meta[itemprop='duration']")
                duration_content = duration_element.get_attribute("content")
                if duration_content:
                    # Parse ISO 8601 duration (PT1M30S -> 90 seconds)
                    duration = self.parse_duration(duration_content)
                    logger.info(f"⏱️ Video duration: {duration}s")
            except NoSuchElementException:
                logger.warning("⚠️ Could not extract video duration")
            
            # Get video ID from URL
            video_id = self.extract_video_id(url)
            
            return {
                "title": title,
                "duration": duration,
                "video_id": video_id,
                "original_url": url,
                "cookies_used": self.cookies_loaded
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting video info: {str(e)}")
            return None
    
    def extract_video_id(self, url):
        """Extract video ID from YouTube URL"""
        try:
            if "watch?v=" in url:
                return url.split("watch?v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                return url.split("youtu.be/")[1].split("?")[0]
            return None
        except:
            return None
    
    def parse_duration(self, duration_str):
        """Parse ISO 8601 duration to seconds"""
        try:
            # Remove PT prefix
            duration_str = duration_str.replace("PT", "")
            
            total_seconds = 0
            
            # Parse hours
            if "H" in duration_str:
                hours = int(duration_str.split("H")[0])
                total_seconds += hours * 3600
                duration_str = duration_str.split("H")[1]
            
            # Parse minutes
            if "M" in duration_str:
                minutes = int(duration_str.split("M")[0])
                total_seconds += minutes * 60
                duration_str = duration_str.split("M")[1]
            
            # Parse seconds
            if "S" in duration_str:
                seconds = int(duration_str.split("S")[0])
                total_seconds += seconds
            
            return total_seconds
        except:
            return 0
    
    def download_video_fallback(self, video_info):
        """Fallback download method using yt-dlp with extracted cookies"""
        try:
            import yt_dlp
            
            video_id = video_info.get("video_id")
            if not video_id:
                return None
            
            # Generate filename
            title = video_info.get("title", "video")
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not safe_title:
                safe_title = "video"
            
            filename = f"{safe_title}_{video_id}.%(ext)s"
            output_path = os.path.join(DOWNLOAD_DIR, filename)
            
            # yt-dlp options with cookies
            ydl_opts = {
                "outtmpl": output_path,
                "format": "best[ext=mp4]/best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True
            }
            
            # Add cookies if available
            cookies_sources = []
            if IS_RENDER and os.path.exists(COOKIES_FILE):
                cookies_sources.append(COOKIES_FILE)
            
            local_cookies = os.path.join(os.getcwd(), "google_cookies.txt")
            if os.path.exists(local_cookies):
                cookies_sources.append(local_cookies)
            
            if cookies_sources:
                ydl_opts["cookiefile"] = cookies_sources[0]
            
            # Enhanced options for different environments
            if IS_RENDER:
                ydl_opts.update({
                    "extractor_args": {
                        "youtube": {
                            "player_client": ["web", "ios"],
                            "skip": ["hls"]
                        }
                    }
                })
            else:
                ydl_opts.update({
                    "extractor_args": {
                        "youtube": {
                            "player_client": ["ios", "web", "android_tv"]
                        }
                    }
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_info["original_url"], download=True)
                actual_filename = os.path.basename(ydl.prepare_filename(info))
                
                logger.info(f"✅ Download successful: {actual_filename}")
                return actual_filename
                
        except Exception as e:
            logger.error(f"❌ Download failed: {str(e)}")
            return None
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

@app.route("/")
def home():
    env_info = "Render" if IS_RENDER else "Local"
    return f"OneTap Server 🚀 ({env_info} Environment)"

@app.route("/download", methods=["POST"])
def download_video():
    """Download video using authenticated Chrome profile or fallback methods"""
    logger.info(f"🚀 Download request received ({'Render' if IS_RENDER else 'Local'} mode)")
    
    downloader = None
    try:
        data = request.get_json()
        url = data.get("url") if data else None
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        # Initialize downloader
        downloader = OneTapDownloader()
        
        # Try to setup Chrome driver, but continue without it if it fails
        chrome_available = downloader.setup_driver()
        
        if chrome_available:
            # Extract video information using Selenium
            logger.info("🔍 Extracting video information with Chrome...")
            video_info = downloader.extract_video_info(url)
        else:
            # Fallback to yt-dlp only extraction
            logger.info("🔍 Extracting video information with yt-dlp fallback...")
            video_info = downloader.extract_video_info_fallback(url)
        
        if not video_info:
            return jsonify({"error": "Failed to extract video information"}), 400

        # Download the video
        logger.info("⬇️ Starting video download...")
        filename = downloader.download_video_fallback(video_info)
        
        if not filename:
            return jsonify({"error": "Failed to download video"}), 400

        logger.info(f"✅ Download complete: {filename}")

        return jsonify({
            "message": "Download successful",
            "filename": filename,
            "title": video_info["title"],
            "duration": video_info["duration"],
            "method": f"{'chrome_' if chrome_available else 'yt-dlp_'}{'render' if IS_RENDER else 'local'}",
            "environment": "render" if IS_RENDER else "local",
            "chrome_available": chrome_available,
            "extraction_method": video_info.get("method", "unknown")
        })

    except Exception as e:
        logger.error(f"❌ Download error: {str(e)}")
        return jsonify({"error": f"Download failed: {str(e)}"}), 500
        
    finally:
        if downloader:
            downloader.cleanup()

@app.route("/upload_cookies", methods=["POST"])
def upload_cookies():
    """Upload cookies for Render environment"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Save cookies file
        file.save(COOKIES_FILE)
        
        # Validate cookies
        cookie_count = 0
        with open(COOKIES_FILE, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    cookie_count += 1
        
        logger.info(f"✅ Uploaded {cookie_count} cookies")
        
        return jsonify({
            "message": "Cookies uploaded successfully",
            "cookie_count": cookie_count,
            "file_size": os.path.getsize(COOKIES_FILE)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/cookies_status")
def cookies_status():
    """Check cookies status"""
    try:
        # Check multiple cookie sources
        sources = []
        
        # Render cookies
        if os.path.exists(COOKIES_FILE):
            size = os.path.getsize(COOKIES_FILE)
            count = 0
            with open(COOKIES_FILE, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        count += 1
            sources.append({"type": "render", "file": COOKIES_FILE, "size": size, "count": count})
        
        # Local cookies
        local_cookies = os.path.join(os.getcwd(), "google_cookies.txt")
        if os.path.exists(local_cookies):
            size = os.path.getsize(local_cookies)
            count = 0
            with open(local_cookies, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        count += 1
            sources.append({"type": "local", "file": local_cookies, "size": size, "count": count})
        
        total_cookies = sum(s["count"] for s in sources)
        
        return jsonify({
            "cookies_available": len(sources) > 0,
            "sources": sources,
            "total_cookies": total_cookies,
            "status": "healthy" if total_cookies > 0 else "missing"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/files/<filename>")
def files(filename):
    """Serve downloaded files"""
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/status")
def system_status():
    """System status"""
    try:
        # Check Chrome availability
        chrome_available = False
        chrome_status = "not_available"
        
        try:
            test_downloader = OneTapDownloader()
            chrome_available = test_downloader.setup_driver()
            if chrome_available:
                chrome_status = "available"
                test_downloader.cleanup()
            else:
                chrome_status = "setup_failed"
        except Exception as e:
            chrome_status = f"error: {str(e)}"
        
        # Check cookie availability
        cookies_available = False
        cookie_sources = []
        
        if IS_RENDER and os.path.exists(COOKIES_FILE):
            cookies_available = True
            cookie_sources.append("render_uploaded")
        
        local_cookies = os.path.join(os.getcwd(), "google_cookies.txt")
        if os.path.exists(local_cookies):
            cookies_available = True
            cookie_sources.append("local_profile")
        
        # Determine bot resistance level
        if chrome_available and cookies_available:
            bot_resistance = "Maximum (Chrome + Authenticated Cookies)"
        elif chrome_available:
            bot_resistance = "High (Chrome Only)"
        elif cookies_available:
            bot_resistance = "Medium (yt-dlp + Cookies)"
        else:
            bot_resistance = "Basic (yt-dlp Only)"
        
        status = {
            "status": "online",
            "environment": "render" if IS_RENDER else "local",
            "server_mode": "OneTap Server with Adaptive Bot Resistance",
            "chrome": {
                "available": chrome_available,
                "status": chrome_status
            },
            "cookies": {
                "available": cookies_available,
                "sources": cookie_sources
            },
            "downloads_dir": {
                "exists": os.path.exists(DOWNLOAD_DIR),
                "files_count": len(os.listdir(DOWNLOAD_DIR)) if os.path.exists(DOWNLOAD_DIR) else 0
            },
            "bot_resistance": bot_resistance,
            "capabilities": [],
            "recommendations": []
        }
        
        # Add capabilities
        if chrome_available:
            status["capabilities"].append("Chrome browser automation")
        status["capabilities"].append("yt-dlp video extraction")
        if cookies_available:
            status["capabilities"].append("Authenticated downloads")
        
        # Add recommendations
        if not chrome_available and IS_RENDER:
            status["recommendations"].append("Chrome not available on Render - using yt-dlp fallback")
        elif not chrome_available:
            status["recommendations"].append("Install Chrome/Chromedriver for better bot resistance")
            
        if not cookies_available:
            if IS_RENDER:
                status["recommendations"].append("Upload cookies using /upload_cookies endpoint")
            else:
                status["recommendations"].append("Create authenticated profile for better success rate")
        else:
            status["recommendations"].append(f"{bot_resistance} active")
            
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
    
    logger.info(f"🌐 Environment: {'Render' if IS_RENDER else 'Local Development'}")
    
    # Check cookie availability
    cookies_available = False
    if IS_RENDER and os.path.exists(COOKIES_FILE):
        cookies_available = True
        logger.info("🍪 Render cookies: ✅ Available")
    
    local_cookies = os.path.join(os.getcwd(), "google_cookies.txt")
    if os.path.exists(local_cookies):
        cookies_available = True
        logger.info("🍪 Local cookies: ✅ Available")
    
    if not cookies_available:
        logger.warning("⚠️ No cookies found - reduced bot resistance")
    
    logger.info(f"🛡️ Bot Resistance: {'Maximum' if cookies_available else 'High'}")
    logger.info(f"🚀 Starting OneTap Server on port {port}")
    
    # Run the server
    app.run(host="0.0.0.0", port=port, debug=False)
