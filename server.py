#!/usr/bin/env python3
"""
OneTap Multi-Platform Video Downloader Server
Supports YouTube, TikTok, Facebook, Instagram, Twitter/X with Chrome/Selenium for YouTube authentication
"""

import os
import uuid
import yt_dlp
import logging
import shutil
import socket
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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

# Profile directories for complete Chrome profiles
CHROME_PROFILE_DIR = os.path.join(os.getcwd(), "chrome_profile")
YOUTUBE_PROFILE_DIR = os.path.join(os.getcwd(), "youtube_profile")
AUTHENTICATED_PROFILE_DIR = os.path.join(os.getcwd(), "authenticated_youtube_session")

# Detect environment
IS_RENDER = os.environ.get('RENDER') is not None

# User agent for consistency
EXACT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

class YouTubeAuthenticator:
    """Handle YouTube authentication using Chrome/Selenium with full profile support"""
    
    def __init__(self):
        self.driver = None
        self.cookies_loaded = False
        self.profile_loaded = False
        self.active_profile_dir = None
        
    def find_authenticated_profile(self):
        """Find the best authenticated Chrome profile to use"""
        profile_candidates = [
            AUTHENTICATED_PROFILE_DIR,
            YOUTUBE_PROFILE_DIR,
            CHROME_PROFILE_DIR,
            "authenticated_youtube_session_complete_backup",
            "tldv_profile"
        ]
        
        for profile_dir in profile_candidates:
            if os.path.exists(profile_dir):
                # Check if profile has authentication data
                default_dir = os.path.join(profile_dir, "Default")
                if os.path.exists(default_dir):
                    # Look for key authentication files
                    auth_files = [
                        os.path.join(default_dir, "Login Data"),
                        os.path.join(default_dir, "Preferences"),
                        os.path.join(default_dir, "Network", "Cookies")
                    ]
                    
                    if any(os.path.exists(f) for f in auth_files):
                        logger.info(f"🔍 Found authenticated profile: {profile_dir}")
                        return profile_dir
        
        logger.warning("⚠️ No authenticated Chrome profile found")
        return None
        
    def setup_chrome_driver(self):
        """Setup Chrome driver for YouTube authentication with profile support"""
        try:
            chrome_options = Options()
            
            # Find and use authenticated profile
            self.active_profile_dir = self.find_authenticated_profile()
            
            if self.active_profile_dir:
                # Use the authenticated profile
                chrome_options.add_argument(f"--user-data-dir={self.active_profile_dir}")
                chrome_options.add_argument("--profile-directory=Default")
                logger.info(f"🔐 Using authenticated profile: {self.active_profile_dir}")
                self.profile_loaded = True
            else:
                # Create temporary profile directory
                temp_profile = os.path.join(os.getcwd(), "temp_chrome_profile")
                os.makedirs(temp_profile, exist_ok=True)
                chrome_options.add_argument(f"--user-data-dir={temp_profile}")
                logger.info("🔐 Using temporary profile (no authenticated profile found)")
            
            # Headless mode for server environment with memory optimizations
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-features=TranslateUI")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            chrome_options.add_argument("--memory-pressure-off")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")  # Save memory
            chrome_options.add_argument("--max_old_space_size=512")  # Limit memory
            chrome_options.add_argument("--aggressive-cache-discard")
            
            # Anti-detection options
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(f"--user-agent={EXACT_UA}")
            
            # Preserve session data
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            
            # Try to use the installed Chrome
            chrome_paths = [
                "/usr/bin/google-chrome",
                "/opt/chrome-linux64/chrome"
            ]
            
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    chrome_options.binary_location = chrome_path
                    logger.info(f"🔍 Using Chrome binary: {chrome_path}")
                    break
            
            # Try to use the installed ChromeDriver
            chromedriver_paths = [
                "/usr/bin/chromedriver",
                "/opt/chromedriver-linux64/chromedriver"
            ]
            
            service = None
            for driver_path in chromedriver_paths:
                if os.path.exists(driver_path):
                    service = Service(driver_path)
                    logger.info(f"🔍 Using ChromeDriver: {driver_path}")
                    break
            
            if service:
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            
            # Execute anti-detection scripts
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            
            logger.info("✅ Chrome driver initialized for YouTube authentication")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up Chrome driver: {str(e)}")
            return False
    
    def load_youtube_cookies(self):
        """Load YouTube cookies into Chrome (fallback if profile doesn't have auth)"""
        try:
            # If we're using an authenticated profile, check if it already has auth
            if self.profile_loaded and self.active_profile_dir:
                # Navigate to YouTube to test existing authentication
                self.driver.get("https://www.youtube.com")
                time.sleep(3)
                
                # Quick check for existing authentication
                try:
                    auth_elements = self.driver.find_elements(By.CSS_SELECTOR, "ytd-topbar-menu-button-renderer")
                    if auth_elements:
                        logger.info("✅ Profile already authenticated - using existing session")
                        self.cookies_loaded = True
                        return True
                except:
                    pass
            
            # Fallback to cookie loading if profile auth failed
            cookie_sources = []
            
            if os.path.exists(GOOGLE_COOKIES_FILE):
                cookie_sources.append(GOOGLE_COOKIES_FILE)
            if os.path.exists(RENDER_COOKIES_FILE):
                cookie_sources.append(RENDER_COOKIES_FILE)
            
            if not cookie_sources:
                logger.warning("⚠️ No YouTube cookies found and profile not authenticated")
                return False
            
            # Navigate to YouTube first
            self.driver.get("https://www.youtube.com")
            time.sleep(3)
            
            # Load cookies from the first available source
            cookies_file = cookie_sources[0]
            logger.info(f"🍪 Loading YouTube cookies from: {cookies_file}")
            
            with open(cookies_file, 'r') as f:
                lines = f.readlines()
            
            cookies_loaded = 0
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        parts = line.split('\t')
                        if len(parts) >= 7:
                            domain = parts[0].lstrip('.')
                            name = parts[5]
                            value = parts[6]
                            
                            # Load all Google/YouTube related cookies
                            if any(keyword in domain.lower() for keyword in ['youtube', 'google', 'googlevideo', 'gstatic']):
                                cookie_dict = {
                                    'name': name,
                                    'value': value,
                                    'domain': domain
                                }
                                
                                try:
                                    self.driver.add_cookie(cookie_dict)
                                    cookies_loaded += 1
                                except Exception as cookie_error:
                                    # Some cookies might fail due to domain restrictions, that's okay
                                    pass
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to parse cookie line: {str(e)}")
                        continue
            
            logger.info(f"✅ Loaded {cookies_loaded} YouTube cookies")
            self.cookies_loaded = cookies_loaded > 0
            
            # Refresh page to apply cookies
            if self.cookies_loaded:
                self.driver.refresh()
                time.sleep(5)  # Give more time for page to load with cookies
            
            return self.cookies_loaded
            
        except Exception as e:
            logger.error(f"❌ Error loading YouTube cookies: {str(e)}")
            return False
    
    def verify_youtube_authentication(self):
        """Verify YouTube authentication status with timeout"""
        try:
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            self.driver.get("https://www.youtube.com")
            time.sleep(3)  # Reduced wait time
            
            # Quick check for authentication indicators
            authentication_indicators = [
                (By.ID, "avatar-btn"),
                (By.CSS_SELECTOR, "ytd-topbar-menu-button-renderer"),
                (By.CSS_SELECTOR, "button[aria-label*='Account menu']"),
            ]
            
            for by, selector in authentication_indicators:
                try:
                    elements = self.driver.find_elements(by, selector)
                    if elements:
                        logger.info(f"✅ YouTube: Authentication verified via {selector}")
                        return True
                except:
                    continue
            
            # Quick check for sign-in button
            try:
                sign_in_elements = self.driver.find_elements(By.XPATH, "//a[contains(@aria-label, 'Sign in')]")
                if sign_in_elements and sign_in_elements[0].is_displayed():
                    logger.warning("⚠️ YouTube: Sign-in button found - not authenticated")
                    return False
            except:
                pass
            
            # If no clear indicators, assume authenticated (safer for downloads)
            logger.info("✅ YouTube: No sign-in indicators found - proceeding with authentication")
            return True
            
        except Exception as e:
            logger.error(f"❌ YouTube authentication verification failed: {str(e)}")
            # Return True to allow download attempt even if verification fails
            return True
    
    def extract_youtube_cookies_for_ytdlp(self):
        """Extract cookies from Chrome session for yt-dlp"""
        try:
            if not self.driver:
                return None
                
            cookies = self.driver.get_cookies()
            
            # Convert to Netscape format for yt-dlp
            cookie_lines = ["# Netscape HTTP Cookie File"]
            essential_cookies = 0
            
            for cookie in cookies:
                domain = cookie.get('domain', '')
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                path = cookie.get('path', '/')
                secure = cookie.get('secure', False)
                expires = cookie.get('expiry', 0)
                
                if any(keyword in domain.lower() for keyword in ['youtube', 'google', 'googlevideo']):
                    cookie_line = f"{domain}\tTRUE\t{path}\t{'TRUE' if secure else 'FALSE'}\t{expires}\t{name}\t{value}"
                    cookie_lines.append(cookie_line)
                    
                    # Count essential cookies for authentication
                    if name in ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID', '__Secure-3PAPISID']:
                        essential_cookies += 1
            
            if essential_cookies < 2:
                logger.warning(f"⚠️ Only {essential_cookies} essential cookies found - authentication may be weak")
            else:
                logger.info(f"✅ Found {essential_cookies} essential authentication cookies")
            
            # Save temporary cookies for yt-dlp
            temp_cookies_file = os.path.join(os.getcwd(), "temp_youtube_cookies.txt")
            with open(temp_cookies_file, 'w') as f:
                f.write('\n'.join(cookie_lines))
            
            logger.info(f"✅ Extracted {len(cookie_lines)-1} cookies for yt-dlp")
            return temp_cookies_file
            
        except Exception as e:
            logger.error(f"❌ Error extracting cookies: {str(e)}")
            return None
    
    def cleanup(self):
        """Clean up Chrome driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

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

def get_platform_config(platform, youtube_cookies_file=None, chrome_profile_dir=None):
    """Get platform-specific yt-dlp configuration with Chrome profile support"""
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
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "web", "android"],
                    "skip": ["hls", "dash"],
                    "innertube_host": "www.youtube.com",
                    "innertube_key": None,
                    "comment_sort": "top"
                }
            },
            # Additional anti-bot measures
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "sleep_interval_requests": 1,
            "sleep_interval_subtitles": 1,
            # Retry configuration
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": 3,
            # Network configuration
            "socket_timeout": 30,
            "http_chunk_size": 10485760,
        }
        
        # Add Deno support if available
        if os.path.exists(deno_exe):
            config["extractor_args"]["youtube"]["js_engine"] = "deno"
            config["extractor_args"]["youtube"]["js_runtimes"] = {
                "deno": {"executable": deno_exe}
            }
        
        # Priority order for authentication:
        # 1. Chrome profile directory (full session)
        # 2. Chrome-extracted cookies 
        # 3. File-based cookies
        # 4. No authentication
        
        if chrome_profile_dir and os.path.exists(chrome_profile_dir):
            # Use Chrome profile directory for full session authentication
            logger.info(f"🔐 Using Chrome profile directory: {chrome_profile_dir}")
            # Note: yt-dlp doesn't directly support Chrome profiles, but we extract cookies from them
            
        # Check for extracted cookies from profile
        profile_cookies_file = os.path.join(os.getcwd(), "profile_extracted_cookies.txt")
        if os.path.exists(profile_cookies_file):
            config["cookiefile"] = profile_cookies_file
            logger.info("🍪 Using profile-extracted cookies for YouTube")
        elif youtube_cookies_file and os.path.exists(youtube_cookies_file):
            config["cookiefile"] = youtube_cookies_file
            logger.info("🍪 Using Chrome-extracted cookies for YouTube")
        elif os.path.exists(GOOGLE_COOKIES_FILE):
            config["cookiefile"] = GOOGLE_COOKIES_FILE
            logger.info("🍪 Using Google cookies file for YouTube")
        elif os.path.exists(RENDER_COOKIES_FILE):
            config["cookiefile"] = RENDER_COOKIES_FILE
            logger.info("🍪 Using render cookies for YouTube")
        else:
            # If no cookies, try different strategies
            logger.warning("⚠️ No cookies available for YouTube - using fallback strategies")
            config["extractor_args"]["youtube"]["player_client"] = ["ios", "android", "web"]
            config["extractor_args"]["youtube"]["skip"] = ["hls"]
            
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
    """Download video from supported platforms with Chrome authentication for YouTube"""
    logger.info(f"🚀 Download request received ({'Render' if IS_RENDER else 'Local'} mode)")
    
    youtube_auth = None
    youtube_cookies_file = None
    
    try:
        data = request.get_json()
        url = data.get("url")
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        platform = detect_platform(url)
        logger.info(f"🌍 Detected platform: {platform}")

        # For YouTube, use Chrome authentication with threading timeout
        if platform == "youtube":
            logger.info("🔐 Setting up Chrome authentication for YouTube...")
            youtube_auth = YouTubeAuthenticator()
            
            try:
                # Use threading timeout instead of signal (which doesn't work in Flask threads)
                import threading
                import queue
                
                def chrome_auth_worker(result_queue):
                    try:
                        if youtube_auth.setup_chrome_driver():
                            if youtube_auth.load_youtube_cookies():
                                if youtube_auth.verify_youtube_authentication():
                                    # Extract cookies for yt-dlp
                                    cookies_file = youtube_auth.extract_youtube_cookies_for_ytdlp()
                                    result_queue.put(("success", cookies_file))
                                    return
                        result_queue.put(("failed", None))
                    except Exception as e:
                        result_queue.put(("error", str(e)))
                
                # Run Chrome authentication in a separate thread with timeout
                result_queue = queue.Queue()
                auth_thread = threading.Thread(target=chrome_auth_worker, args=(result_queue,))
                auth_thread.daemon = True
                auth_thread.start()
                auth_thread.join(timeout=45)  # 45 second timeout
                
                if auth_thread.is_alive():
                    logger.warning("⚠️ Chrome authentication timed out - continuing with file cookies")
                else:
                    try:
                        status, result = result_queue.get_nowait()
                        if status == "success" and result:
                            youtube_cookies_file = result
                            logger.info("✅ YouTube authentication successful")
                        else:
                            logger.warning(f"⚠️ Chrome authentication {status} - continuing with file cookies")
                    except queue.Empty:
                        logger.warning("⚠️ Chrome authentication returned no result - continuing with file cookies")
                        
            except Exception as chrome_error:
                logger.warning(f"⚠️ Chrome authentication failed: {str(chrome_error)} - continuing with file cookies")

        # Generate unique filename
        uid = str(uuid.uuid4())[:8]
        
        # Get platform-specific configuration with Chrome profile support
        chrome_profile_dir = None
        if platform == "youtube" and youtube_auth and youtube_auth.active_profile_dir:
            chrome_profile_dir = youtube_auth.active_profile_dir
        
        ydl_opts = get_platform_config(platform, youtube_cookies_file, chrome_profile_dir)
        ydl_opts["outtmpl"] = os.path.join(DOWNLOAD_DIR, f"{uid}_%(title)s.%(ext)s")
        
        # Execute download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if platform == "youtube":
                logger.info(f"Using Deno at: {get_deno_path()}")
                if youtube_cookies_file:
                    logger.info("🍪 Using Chrome-extracted cookies for enhanced YouTube access")
            
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
        
        # Clean up temporary cookies file
        if youtube_cookies_file and os.path.exists(youtube_cookies_file):
            try:
                os.remove(youtube_cookies_file)
            except:
                pass
        
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
            "environment": "render" if IS_RENDER else "local",
            "authentication": {
                "chrome_used": youtube_auth is not None and platform == "youtube",
                "cookies_extracted": youtube_cookies_file is not None,
                "profile_used": youtube_auth is not None and youtube_auth.profile_loaded and platform == "youtube",
                "profile_directory": youtube_auth.active_profile_dir if youtube_auth and youtube_auth.active_profile_dir else None,
                "platform_optimized": True
            }
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
    
    finally:
        # Clean up Chrome driver
        if youtube_auth:
            youtube_auth.cleanup()
        
        # Clean up temporary cookies file
        if youtube_cookies_file and os.path.exists(youtube_cookies_file):
            try:
                os.remove(youtube_cookies_file)
            except:
                pass

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

@app.route("/upload_profile", methods=["POST"])
def upload_profile():
    """Upload complete Chrome profile as ZIP file"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No profile file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not file.filename.lower().endswith('.zip'):
            return jsonify({"error": "Profile must be a ZIP file"}), 400
        
        # Save uploaded ZIP file
        zip_path = os.path.join(os.getcwd(), "uploaded_profile.zip")
        file.save(zip_path)
        
        # Extract profile to authenticated directory
        profile_dir = AUTHENTICATED_PROFILE_DIR
        
        # Remove existing profile if it exists
        if os.path.exists(profile_dir):
            shutil.rmtree(profile_dir)
        
        # Extract ZIP file
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(profile_dir)
        
        # Clean up ZIP file
        os.remove(zip_path)
        
        # Verify profile structure
        default_dir = os.path.join(profile_dir, "Default")
        if not os.path.exists(default_dir):
            # If no Default directory, check if files are in root
            profile_files = os.listdir(profile_dir)
            if any(f in profile_files for f in ["Preferences", "Login Data", "History"]):
                # Create Default directory and move files
                os.makedirs(default_dir, exist_ok=True)
                for item in profile_files:
                    if os.path.isfile(os.path.join(profile_dir, item)):
                        shutil.move(os.path.join(profile_dir, item), os.path.join(default_dir, item))
        
        # Count authentication indicators
        auth_files = []
        if os.path.exists(os.path.join(default_dir, "Login Data")):
            auth_files.append("Login Data")
        if os.path.exists(os.path.join(default_dir, "Preferences")):
            auth_files.append("Preferences")
        if os.path.exists(os.path.join(default_dir, "Network", "Cookies")):
            auth_files.append("Cookies")
        
        # Extract cookies from profile for yt-dlp compatibility
        cookies_extracted = extract_cookies_from_profile(profile_dir)
        
        logger.info(f"✅ Uploaded Chrome profile with {len(auth_files)} authentication files")
        
        return jsonify({
            "message": "Chrome profile uploaded successfully",
            "profile_directory": profile_dir,
            "authentication_files": auth_files,
            "cookies_extracted": cookies_extracted,
            "status": "ready_for_use"
        })
        
    except Exception as e:
        logger.error(f"❌ Profile upload failed: {str(e)}")
        return jsonify({"error": f"Profile upload failed: {str(e)}"}), 500

def extract_cookies_from_profile(profile_path):
    """Extract cookies from Chrome profile and save as text file"""
    try:
        cookies_db_path = os.path.join(profile_path, "Default", "Network", "Cookies")
        
        if not os.path.exists(cookies_db_path):
            logger.warning("No cookies database found in profile")
            return False
        
        import sqlite3
        import tempfile
        
        # Copy cookies database to avoid locking issues
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_db:
            shutil.copy2(cookies_db_path, temp_db.name)
            temp_db_path = temp_db.name
        
        try:
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            
            # Extract YouTube/Google cookies
            cursor.execute("""
                SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
                FROM cookies 
                WHERE host_key LIKE '%youtube%' OR host_key LIKE '%google%' OR host_key LIKE '%googlevideo%'
                ORDER BY creation_utc DESC
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning("No YouTube/Google cookies found in profile")
                return False
            
            # Convert to Netscape cookie format
            cookie_lines = ["# Netscape HTTP Cookie File"]
            cookie_lines.append("# Extracted from Chrome profile")
            
            for row in rows:
                host_key, name, value, path, expires_utc, is_secure, is_httponly = row
                
                # Convert Chrome timestamp to Unix timestamp
                if expires_utc:
                    expires = int(expires_utc / 1000000 - 11644473600)
                else:
                    expires = 0
                
                # Format: domain, domain_specified, path, secure, expires, name, value
                cookie_line = f"{host_key}\tTRUE\t{path}\t{'TRUE' if is_secure else 'FALSE'}\t{expires}\t{name}\t{value}"
                cookie_lines.append(cookie_line)
            
            conn.close()
            
            # Save extracted cookies
            extracted_cookies_file = os.path.join(os.getcwd(), "profile_extracted_cookies.txt")
            with open(extracted_cookies_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(cookie_lines))
            
            logger.info(f"✅ Extracted {len(cookie_lines)-2} cookies from profile")
            return len(cookie_lines) - 2
            
        finally:
            os.unlink(temp_db_path)
            
    except Exception as e:
        logger.error(f"❌ Cookie extraction failed: {str(e)}")
        return False

@app.route("/profile_status")
def profile_status():
    """Check status of uploaded Chrome profiles"""
    try:
        profiles = []
        
        # Check for different profile directories
        profile_candidates = [
            ("authenticated_session", AUTHENTICATED_PROFILE_DIR),
            ("youtube_profile", YOUTUBE_PROFILE_DIR),
            ("chrome_profile", CHROME_PROFILE_DIR),
            ("tldv_profile", "tldv_profile"),
            ("backup_session", "authenticated_youtube_session_complete_backup")
        ]
        
        for name, path in profile_candidates:
            if os.path.exists(path):
                default_dir = os.path.join(path, "Default")
                
                # Check authentication files
                auth_files = []
                if os.path.exists(os.path.join(default_dir, "Login Data")):
                    auth_files.append("Login Data")
                if os.path.exists(os.path.join(default_dir, "Preferences")):
                    auth_files.append("Preferences")
                if os.path.exists(os.path.join(default_dir, "Network", "Cookies")):
                    auth_files.append("Cookies Database")
                if os.path.exists(os.path.join(default_dir, "History")):
                    auth_files.append("History")
                
                # Get profile size
                profile_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(path)
                    for filename in filenames
                )
                
                profiles.append({
                    "name": name,
                    "path": path,
                    "size_mb": round(profile_size / (1024 * 1024), 2),
                    "authentication_files": auth_files,
                    "has_default_profile": os.path.exists(default_dir),
                    "status": "authenticated" if len(auth_files) >= 2 else "incomplete"
                })
        
        # Check extracted cookies
        extracted_cookies_file = os.path.join(os.getcwd(), "profile_extracted_cookies.txt")
        cookies_available = os.path.exists(extracted_cookies_file)
        cookie_count = 0
        
        if cookies_available:
            with open(extracted_cookies_file, 'r') as f:
                cookie_count = sum(1 for line in f if line.strip() and not line.startswith('#'))
        
        return jsonify({
            "profiles_found": len(profiles),
            "profiles": profiles,
            "extracted_cookies": {
                "available": cookies_available,
                "count": cookie_count,
                "file": "profile_extracted_cookies.txt" if cookies_available else None
            },
            "recommended_profile": profiles[0]["name"] if profiles else None,
            "status": "ready" if profiles else "no_profiles"
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
        # Check Chrome availability
        chrome_available = False
        chrome_status = "not_available"
        
        chrome_paths = ["/usr/bin/google-chrome", "/opt/chrome-linux64/chrome"]
        chromedriver_paths = ["/usr/bin/chromedriver", "/opt/chromedriver-linux64/chromedriver"]
        
        chrome_binary = None
        chromedriver_binary = None
        
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_binary = path
                break
                
        for path in chromedriver_paths:
            if os.path.exists(path):
                chromedriver_binary = path
                break
        
        if chrome_binary and chromedriver_binary:
            chrome_available = True
            chrome_status = "available"
        elif chrome_binary:
            chrome_status = "chrome_only"
        elif chromedriver_binary:
            chrome_status = "chromedriver_only"
        
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
            "server_mode": "OneTap Multi-Platform Video Downloader with Chrome Authentication",
            "supported_platforms": [
                "YouTube (with Chrome authentication)", "TikTok", "Facebook", "Instagram", 
                "Twitter/X", "Twitch", "Vimeo", "Dailymotion"
            ],
            "chrome": {
                "available": chrome_available,
                "status": chrome_status,
                "binary": chrome_binary,
                "driver": chromedriver_binary
            },
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
                "Multi-platform video downloading (YouTube, TikTok, Facebook, Instagram, Twitter/X, Twitch, Vimeo, Dailymotion)",
                "yt-dlp with platform-specific optimizations",
                "Cookie-based authentication for private content",
                "Chrome/Selenium authentication for YouTube" if chrome_available else "Basic YouTube support",
                "Deno JavaScript engine for enhanced YouTube support" if deno_available else "Basic YouTube support"
            ],
            "recommendations": []
        }
        
        # Add recommendations
        if not chrome_available:
            if not chrome_binary:
                status["recommendations"].append("Chrome not found - YouTube authentication limited")
            if not chromedriver_binary:
                status["recommendations"].append("ChromeDriver not found - YouTube authentication limited")
        
        if not cookie_sources:
            status["recommendations"].append("Upload cookies for better platform access")
        
        if not deno_available:
            status["recommendations"].append("Deno not found - YouTube downloads may be limited")
        
        if chrome_available and len(cookie_sources) > 0:
            status["recommendations"].append("Full multi-platform support active with Chrome authentication")
            
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