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

# Configure comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/onetap_server.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Set specific log levels for different components
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.INFO)

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
        logger.info("🔍 Searching for authenticated Chrome profiles...")
        
        profile_candidates = [
            AUTHENTICATED_PROFILE_DIR,
            YOUTUBE_PROFILE_DIR,
            CHROME_PROFILE_DIR,
            "authenticated_youtube_session_complete_backup",
            "tldv_profile"
        ]
        
        for profile_dir in profile_candidates:
            logger.debug(f"Checking profile candidate: {profile_dir}")
            
            if os.path.exists(profile_dir):
                logger.info(f"📁 Found profile directory: {profile_dir}")
                
                # Check if profile has authentication data
                default_dir = os.path.join(profile_dir, "Default")
                if os.path.exists(default_dir):
                    logger.debug(f"✅ Default directory exists: {default_dir}")
                    
                    # Look for key authentication files
                    auth_files = [
                        ("Login Data", os.path.join(default_dir, "Login Data")),
                        ("Preferences", os.path.join(default_dir, "Preferences")),
                        ("Network/Cookies", os.path.join(default_dir, "Network", "Cookies")),
                        ("Local Storage", os.path.join(default_dir, "Local Storage")),
                        ("IndexedDB", os.path.join(default_dir, "IndexedDB"))
                    ]
                    
                    found_auth_files = []
                    for name, path in auth_files:
                        if os.path.exists(path):
                            size = "dir" if os.path.isdir(path) else f"{os.path.getsize(path)} bytes"
                            logger.debug(f"  ✅ {name}: {size}")
                            found_auth_files.append(name)
                        else:
                            logger.debug(f"  ❌ {name}: missing")
                    
                    if len(found_auth_files) >= 2:
                        logger.info(f"🔐 Selected authenticated profile: {profile_dir}")
                        logger.info(f"   Authentication files found: {', '.join(found_auth_files)}")
                        return profile_dir
                    else:
                        logger.warning(f"⚠️ Profile {profile_dir} has insufficient auth files: {found_auth_files}")
                else:
                    logger.warning(f"⚠️ Profile {profile_dir} missing Default directory")
            else:
                logger.debug(f"❌ Profile not found: {profile_dir}")
        
        logger.error("❌ No authenticated Chrome profile found")
        return None
        
    def setup_chrome_driver(self):
        """Setup Chrome driver for YouTube authentication with profile support"""
        logger.info("🚀 Initializing Chrome driver for YouTube authentication...")
        
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
                
                # Log profile size and contents
                try:
                    profile_size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(self.active_profile_dir)
                        for filename in filenames
                    )
                    logger.info(f"📊 Profile size: {profile_size / (1024*1024):.1f} MB")
                except Exception as e:
                    logger.warning(f"⚠️ Could not calculate profile size: {e}")
                    
            else:
                # Create temporary profile directory
                temp_profile = os.path.join(os.getcwd(), "temp_chrome_profile")
                os.makedirs(temp_profile, exist_ok=True)
                chrome_options.add_argument(f"--user-data-dir={temp_profile}")
                logger.warning("⚠️ Using temporary profile (no authenticated profile found)")
            
            # Chrome options for server environment
            server_options = [
                "--headless=new",
                "--no-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--memory-pressure-off",
                "--remote-debugging-port=9222",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images",
                "--max_old_space_size=512",
                "--aggressive-cache-discard"
            ]
            
            for option in server_options:
                chrome_options.add_argument(option)
                logger.debug(f"Added Chrome option: {option}")
            
            # Anti-detection options
            anti_detection_options = [
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080",
                f"--user-agent={EXACT_UA}"
            ]
            
            for option in anti_detection_options:
                chrome_options.add_argument(option)
                logger.debug(f"Added anti-detection option: {option}")
            
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Preserve session data
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            
            # Try to use the installed Chrome
            chrome_paths = [
                "/usr/bin/google-chrome",
                "/opt/chrome-linux64/chrome"
            ]
            
            chrome_binary = None
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    chrome_options.binary_location = chrome_path
                    chrome_binary = chrome_path
                    logger.info(f"🔍 Using Chrome binary: {chrome_path}")
                    break
            
            if not chrome_binary:
                logger.warning("⚠️ No Chrome binary found in standard locations")
            
            # Try to use the installed ChromeDriver
            chromedriver_paths = [
                "/usr/bin/chromedriver",
                "/opt/chromedriver-linux64/chromedriver"
            ]
            
            service = None
            chromedriver_binary = None
            for driver_path in chromedriver_paths:
                if os.path.exists(driver_path):
                    service = Service(driver_path)
                    chromedriver_binary = driver_path
                    logger.info(f"🔍 Using ChromeDriver: {driver_path}")
                    break
            
            if not chromedriver_binary:
                logger.warning("⚠️ No ChromeDriver found in standard locations")
            
            # Initialize Chrome driver
            logger.info("🚀 Starting Chrome WebDriver...")
            start_time = time.time()
            
            if service:
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            
            init_time = time.time() - start_time
            logger.info(f"⏱️ Chrome driver initialized in {init_time:.2f} seconds")
            
            # Execute anti-detection scripts
            logger.debug("🛡️ Applying anti-detection measures...")
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            
            # Log browser info
            try:
                user_agent = self.driver.execute_script("return navigator.userAgent;")
                logger.debug(f"🌐 Browser User Agent: {user_agent}")
                
                window_size = self.driver.get_window_size()
                logger.debug(f"📐 Window size: {window_size['width']}x{window_size['height']}")
            except Exception as e:
                logger.warning(f"⚠️ Could not get browser info: {e}")
            
            logger.info("✅ Chrome driver initialized successfully for YouTube authentication")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up Chrome driver: {str(e)}")
            logger.exception("Full Chrome setup error traceback:")
            return False
    
    def load_youtube_cookies(self):
        """Load YouTube cookies into Chrome (fallback if profile doesn't have auth)"""
        logger.info("🍪 Loading YouTube authentication...")
        
        try:
            # If we're using an authenticated profile, check if it already has auth
            if self.profile_loaded and self.active_profile_dir:
                logger.info("🔍 Testing existing profile authentication...")
                
                # Navigate to YouTube to test existing authentication
                start_time = time.time()
                self.driver.get("https://www.youtube.com")
                load_time = time.time() - start_time
                logger.info(f"⏱️ YouTube page loaded in {load_time:.2f} seconds")
                
                time.sleep(3)
                
                # Quick check for existing authentication
                try:
                    auth_elements = self.driver.find_elements(By.CSS_SELECTOR, "ytd-topbar-menu-button-renderer")
                    if auth_elements:
                        logger.info("✅ Profile already authenticated - using existing session")
                        logger.debug(f"Found {len(auth_elements)} authentication elements")
                        self.cookies_loaded = True
                        return True
                    else:
                        logger.info("🔍 No authentication elements found, checking for sign-in button...")
                        
                        sign_in_elements = self.driver.find_elements(By.XPATH, "//a[contains(@aria-label, 'Sign in')]")
                        if sign_in_elements:
                            logger.warning("⚠️ Sign-in button found - profile not authenticated")
                        else:
                            logger.info("✅ No sign-in button found - assuming authenticated")
                            self.cookies_loaded = True
                            return True
                            
                except Exception as e:
                    logger.warning(f"⚠️ Error checking profile authentication: {e}")
            
            # Fallback to cookie loading if profile auth failed
            logger.info("🔄 Falling back to cookie file loading...")
            
            cookie_sources = []
            
            if os.path.exists(GOOGLE_COOKIES_FILE):
                cookie_sources.append(("Google cookies", GOOGLE_COOKIES_FILE))
            if os.path.exists(RENDER_COOKIES_FILE):
                cookie_sources.append(("Render cookies", RENDER_COOKIES_FILE))
            
            if not cookie_sources:
                logger.error("❌ No YouTube cookies found and profile not authenticated")
                return False
            
            # Navigate to YouTube first if not already there
            current_url = self.driver.current_url
            if "youtube.com" not in current_url:
                logger.info("🌐 Navigating to YouTube...")
                self.driver.get("https://www.youtube.com")
                time.sleep(3)
            
            # Load cookies from the first available source
            source_name, cookies_file = cookie_sources[0]
            logger.info(f"🍪 Loading cookies from: {source_name} ({cookies_file})")
            
            # Read and parse cookies file
            with open(cookies_file, 'r') as f:
                lines = f.readlines()
            
            logger.info(f"📄 Cookie file has {len(lines)} lines")
            
            cookies_loaded = 0
            cookies_skipped = 0
            
            for line_num, line in enumerate(lines, 1):
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
                                    logger.debug(f"✅ Added cookie: {name} for {domain}")
                                except Exception as cookie_error:
                                    cookies_skipped += 1
                                    logger.debug(f"⚠️ Skipped cookie {name}: {str(cookie_error)}")
                            else:
                                logger.debug(f"⏭️ Skipped non-YouTube cookie for domain: {domain}")
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to parse cookie line {line_num}: {str(e)}")
                        continue
            
            logger.info(f"✅ Loaded {cookies_loaded} YouTube cookies (skipped {cookies_skipped})")
            self.cookies_loaded = cookies_loaded > 0
            
            # Refresh page to apply cookies
            if self.cookies_loaded:
                logger.info("🔄 Refreshing page to apply cookies...")
                self.driver.refresh()
                time.sleep(5)  # Give more time for page to load with cookies
                logger.info("✅ Page refreshed with new cookies")
            
            return self.cookies_loaded
            
        except Exception as e:
            logger.error(f"❌ Error loading YouTube cookies: {str(e)}")
            logger.exception("Full cookie loading error traceback:")
            return False
    
    def verify_youtube_authentication(self):
        """Verify YouTube authentication status with comprehensive logging"""
        logger.info("🔍 Verifying YouTube authentication status...")
        
        try:
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            current_url = self.driver.current_url
            logger.debug(f"Current URL: {current_url}")
            
            if "youtube.com" not in current_url:
                logger.info("🌐 Navigating to YouTube for authentication check...")
                self.driver.get("https://www.youtube.com")
                time.sleep(3)
            
            # Log page title and basic info
            try:
                page_title = self.driver.title
                logger.debug(f"📄 Page title: {page_title}")
            except Exception as e:
                logger.warning(f"⚠️ Could not get page title: {e}")
            
            # Check for authentication indicators with detailed logging
            authentication_indicators = [
                (By.ID, "avatar-btn", "Avatar button"),
                (By.CSS_SELECTOR, "ytd-topbar-menu-button-renderer", "Topbar menu button"),
                (By.CSS_SELECTOR, "button[aria-label*='Account menu']", "Account menu button"),
                (By.CSS_SELECTOR, "#avatar-btn", "Avatar button (ID)"),
                (By.CSS_SELECTOR, "yt-img-shadow#avatar", "Avatar image")
            ]
            
            found_indicators = []
            
            for by, selector, description in authentication_indicators:
                try:
                    elements = self.driver.find_elements(by, selector)
                    if elements:
                        logger.debug(f"✅ Found {len(elements)} {description} element(s)")
                        found_indicators.append(description)
                        
                        # Log element details
                        for i, element in enumerate(elements[:2]):  # Log first 2 elements
                            try:
                                is_displayed = element.is_displayed()
                                tag_name = element.tag_name
                                logger.debug(f"   Element {i+1}: {tag_name}, displayed: {is_displayed}")
                            except Exception as e:
                                logger.debug(f"   Element {i+1}: Could not get details - {e}")
                    else:
                        logger.debug(f"❌ No {description} found")
                except Exception as e:
                    logger.debug(f"⚠️ Error checking {description}: {e}")
            
            if found_indicators:
                logger.info(f"✅ YouTube authentication verified via: {', '.join(found_indicators)}")
                return True
            
            # Check for sign-in button (indicates not authenticated)
            logger.info("🔍 Checking for sign-in indicators...")
            
            sign_in_selectors = [
                (By.XPATH, "//a[contains(@aria-label, 'Sign in')]", "Sign in link"),
                (By.CSS_SELECTOR, "a[href*='accounts.google.com']", "Google accounts link"),
                (By.XPATH, "//button[contains(text(), 'Sign in')]", "Sign in button"),
                (By.CSS_SELECTOR, "ytd-button-renderer#sign-in-button", "YouTube sign in button")
            ]
            
            sign_in_found = []
            
            for by, selector, description in sign_in_selectors:
                try:
                    elements = self.driver.find_elements(by, selector)
                    if elements:
                        visible_elements = [e for e in elements if e.is_displayed()]
                        if visible_elements:
                            logger.warning(f"⚠️ Found visible {description}: {len(visible_elements)} element(s)")
                            sign_in_found.append(description)
                        else:
                            logger.debug(f"Found hidden {description}: {len(elements)} element(s)")
                except Exception as e:
                    logger.debug(f"Error checking {description}: {e}")
            
            if sign_in_found:
                logger.warning(f"⚠️ YouTube: Sign-in indicators found - {', '.join(sign_in_found)}")
                return False
            
            # Check page source for authentication clues
            try:
                page_source = self.driver.page_source
                auth_keywords = ["LOGGED_IN", "SESSION_INDEX", "VISITOR_DATA"]
                found_keywords = [kw for kw in auth_keywords if kw in page_source]
                
                if found_keywords:
                    logger.info(f"✅ Found authentication keywords in page source: {found_keywords}")
                    return True
                else:
                    logger.debug("No authentication keywords found in page source")
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not check page source: {e}")
            
            # If no clear indicators, check cookies
            try:
                cookies = self.driver.get_cookies()
                auth_cookies = [c for c in cookies if c['name'] in ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID']]
                
                if auth_cookies:
                    logger.info(f"✅ Found {len(auth_cookies)} authentication cookies")
                    for cookie in auth_cookies:
                        logger.debug(f"   Auth cookie: {cookie['name']} for {cookie['domain']}")
                    return True
                else:
                    logger.warning("⚠️ No authentication cookies found")
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not check cookies: {e}")
            
            # Final decision - if no negative indicators, assume authenticated
            logger.info("✅ No definitive authentication status - proceeding optimistically")
            return True
            
        except Exception as e:
            logger.error(f"❌ YouTube authentication verification failed: {str(e)}")
            logger.exception("Full authentication verification error traceback:")
            # Return True to allow download attempt even if verification fails
            return True
    
    def extract_youtube_cookies_for_ytdlp(self):
        """Extract cookies from Chrome session for yt-dlp with timeout handling"""
        logger.info("🍪 Extracting cookies from Chrome session for yt-dlp...")
        
        try:
            if not self.driver:
                logger.error("❌ No Chrome driver available for cookie extraction")
                return None
            
            # Set a shorter timeout for cookie extraction
            logger.debug("⏱️ Setting shorter timeout for cookie extraction...")
            original_timeout = self.driver.implicitly_wait(0)
            
            # Try to get cookies with timeout handling
            logger.info("📊 Attempting to retrieve cookies from Chrome session...")
            
            try:
                # Use a more direct approach with shorter timeout
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Cookie extraction timed out")
                
                # Set alarm for 30 seconds (much shorter than the 6+ minutes we saw)
                if hasattr(signal, 'SIGALRM'):  # Unix systems only
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(30)
                
                cookies = self.driver.get_cookies()
                
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancel alarm
                
                logger.info(f"📊 Retrieved {len(cookies)} total cookies from Chrome session")
                
            except (TimeoutError, Exception) as e:
                logger.warning(f"⚠️ Direct cookie extraction failed: {str(e)}")
                logger.info("🔄 Trying alternative cookie extraction method...")
                
                # Alternative: Extract cookies from profile files directly
                return self.extract_cookies_from_profile_files()
            
            # Convert to Netscape format for yt-dlp
            cookie_lines = ["# Netscape HTTP Cookie File"]
            cookie_lines.append("# Generated by OneTap Chrome session")
            cookie_lines.append(f"# Extracted at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            essential_cookies = 0
            youtube_cookies = 0
            google_cookies = 0
            
            cookie_stats = {
                'youtube.com': 0,
                'google.com': 0,
                'googlevideo.com': 0,
                'gstatic.com': 0,
                'other': 0
            }
            
            for cookie in cookies:
                domain = cookie.get('domain', '')
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                path = cookie.get('path', '/')
                secure = cookie.get('secure', False)
                expires = cookie.get('expiry', 0)
                
                # Skip cookies with empty values
                if not value or not name:
                    logger.debug(f"⏭️ Skipping empty cookie: {name}")
                    continue
                
                # Filter for YouTube/Google related cookies
                if any(keyword in domain.lower() for keyword in ['youtube', 'google', 'googlevideo', 'gstatic']):
                    cookie_line = f"{domain}\tTRUE\t{path}\t{'TRUE' if secure else 'FALSE'}\t{expires}\t{name}\t{value}"
                    cookie_lines.append(cookie_line)
                    
                    # Update statistics
                    if 'youtube' in domain.lower():
                        youtube_cookies += 1
                        cookie_stats['youtube.com'] += 1
                    elif 'google' in domain.lower():
                        google_cookies += 1
                        cookie_stats['google.com'] += 1
                    elif 'googlevideo' in domain.lower():
                        cookie_stats['googlevideo.com'] += 1
                    elif 'gstatic' in domain.lower():
                        cookie_stats['gstatic.com'] += 1
                    
                    # Count essential cookies for authentication
                    if name in ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID', '__Secure-3PAPISID']:
                        essential_cookies += 1
                        logger.debug(f"✅ Found essential auth cookie: {name} for {domain}")
                else:
                    cookie_stats['other'] += 1
                    logger.debug(f"⏭️ Skipped non-Google cookie: {name} for {domain}")
            
            # Log detailed statistics
            logger.info(f"📊 Cookie extraction statistics:")
            logger.info(f"   YouTube cookies: {youtube_cookies}")
            logger.info(f"   Google cookies: {google_cookies}")
            logger.info(f"   Essential auth cookies: {essential_cookies}")
            logger.info(f"   Total extracted: {len(cookie_lines)-3}")
            
            for domain, count in cookie_stats.items():
                if count > 0:
                    logger.debug(f"   {domain}: {count} cookies")
            
            if essential_cookies < 2:
                logger.warning(f"⚠️ Only {essential_cookies} essential cookies found - authentication may be weak")
            else:
                logger.info(f"✅ Found {essential_cookies} essential authentication cookies - strong auth expected")
            
            # Save temporary cookies for yt-dlp
            temp_cookies_file = os.path.join(os.getcwd(), "temp_youtube_cookies.txt")
            with open(temp_cookies_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(cookie_lines))
            
            # Verify the written file
            file_size = os.path.getsize(temp_cookies_file)
            logger.info(f"💾 Saved cookies to: {temp_cookies_file} ({file_size} bytes)")
            
            # Quick validation of the cookie file
            try:
                with open(temp_cookies_file, 'r') as f:
                    validation_lines = f.readlines()
                valid_cookie_lines = [line for line in validation_lines if line.strip() and not line.startswith('#')]
                logger.info(f"✅ Cookie file validation: {len(valid_cookie_lines)} valid cookie lines")
            except Exception as e:
                logger.warning(f"⚠️ Could not validate cookie file: {e}")
            
            logger.info(f"✅ Successfully extracted {len(cookie_lines)-3} cookies for yt-dlp")
            return temp_cookies_file
            
        except Exception as e:
            logger.error(f"❌ Error extracting cookies: {str(e)}")
            logger.exception("Full cookie extraction error traceback:")
            
            # Fallback to profile file extraction
            logger.info("🔄 Attempting fallback cookie extraction from profile files...")
            return self.extract_cookies_from_profile_files()
    
    def extract_cookies_from_profile_files(self):
        """Fallback method: Extract cookies directly from Chrome profile files"""
        logger.info("📁 Extracting cookies directly from profile files...")
        
        try:
            if not self.active_profile_dir:
                logger.error("❌ No active profile directory available")
                return None
            
            cookies_db_path = os.path.join(self.active_profile_dir, "Default", "Network", "Cookies")
            
            if not os.path.exists(cookies_db_path):
                logger.warning(f"⚠️ Cookies database not found: {cookies_db_path}")
                return None
            
            logger.info(f"📂 Reading cookies from: {cookies_db_path}")
            
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
                logger.info(f"📊 Found {len(rows)} cookies in database")
                
                if not rows:
                    logger.warning("⚠️ No YouTube/Google cookies found in database")
                    return None
                
                # Convert to Netscape cookie format
                cookie_lines = ["# Netscape HTTP Cookie File"]
                cookie_lines.append("# Extracted from Chrome profile database")
                cookie_lines.append(f"# Extracted at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                essential_cookies = 0
                valid_cookies = 0
                
                for row in rows:
                    host_key, name, value, path, expires_utc, is_secure, is_httponly = row
                    
                    # Skip cookies with empty values
                    if not value or not name:
                        logger.debug(f"⏭️ Skipping empty cookie: {name}")
                        continue
                    
                    # Convert Chrome timestamp to Unix timestamp
                    if expires_utc:
                        expires = int(expires_utc / 1000000 - 11644473600)
                    else:
                        expires = 0
                    
                    # Format: domain, domain_specified, path, secure, expires, name, value
                    cookie_line = f"{host_key}\tTRUE\t{path}\t{'TRUE' if is_secure else 'FALSE'}\t{expires}\t{name}\t{value}"
                    cookie_lines.append(cookie_line)
                    valid_cookies += 1
                    
                    # Count essential cookies
                    if name in ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID', '__Secure-3PAPISID']:
                        essential_cookies += 1
                        logger.debug(f"✅ Found essential auth cookie: {name} for {host_key}")
                
                conn.close()
                
                # Save extracted cookies
                temp_cookies_file = os.path.join(os.getcwd(), "profile_extracted_cookies.txt")
                with open(temp_cookies_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(cookie_lines))
                
                # Verify the file
                file_size = os.path.getsize(temp_cookies_file)
                logger.info(f"💾 Saved cookies to: {temp_cookies_file} ({file_size} bytes)")
                
                logger.info(f"✅ Extracted {valid_cookies} valid cookies from profile database")
                logger.info(f"✅ Found {essential_cookies} essential authentication cookies")
                
                if essential_cookies >= 2:
                    logger.info("🔐 Strong authentication expected with profile cookies")
                else:
                    logger.warning(f"⚠️ Only {essential_cookies} essential cookies - authentication may be limited")
                
                return temp_cookies_file
                
            finally:
                os.unlink(temp_db_path)
                
        except Exception as e:
            logger.error(f"❌ Profile file cookie extraction failed: {str(e)}")
            logger.exception("Profile cookie extraction error traceback:")
            return None
    
    def cleanup(self):
        """Clean up Chrome driver with force termination if needed"""
        logger.info("🧹 Cleaning up Chrome driver...")
        
        if self.driver:
            try:
                # Try graceful shutdown first
                logger.debug("Attempting graceful Chrome shutdown...")
                self.driver.quit()
                logger.info("✅ Chrome driver closed gracefully")
            except Exception as e:
                logger.warning(f"⚠️ Graceful shutdown failed: {e}")
                
                # Force termination if graceful shutdown fails
                try:
                    logger.info("🔨 Force terminating Chrome process...")
                    import psutil
                    import os
                    
                    # Find and kill Chrome processes
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                                if proc.info['cmdline'] and any('user-data-dir' in arg for arg in proc.info['cmdline']):
                                    logger.debug(f"Terminating Chrome process: {proc.info['pid']}")
                                    proc.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    logger.info("✅ Chrome processes terminated")
                    
                except ImportError:
                    logger.warning("⚠️ psutil not available for force termination")
                except Exception as e:
                    logger.error(f"❌ Force termination failed: {e}")
        
        self.driver = None
        self.cookies_loaded = False
        self.profile_loaded = False

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
            # Validate the extracted cookies file first
            try:
                with open(profile_cookies_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                valid_cookies = 0
                essential_cookies = 0
                
                for line in lines:
                    if line.strip() and not line.startswith('#') and len(line.split('\t')) >= 7:
                        parts = line.split('\t')
                        if len(parts) >= 7 and parts[5] and parts[6]:  # name and value must not be empty
                            valid_cookies += 1
                            # Check for essential auth cookies
                            if parts[5] in ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID', '__Secure-3PAPISID']:
                                essential_cookies += 1
                
                if valid_cookies > 5:  # Need at least some valid cookies
                    config["cookiefile"] = profile_cookies_file
                    logger.info(f"🍪 Using profile-extracted cookies for YouTube ({valid_cookies} valid, {essential_cookies} essential)")
                else:
                    raise ValueError(f"Only {valid_cookies} valid cookies found")
                    
            except Exception as e:
                logger.warning(f"⚠️ Profile cookies invalid: {str(e)} - trying fallback")
                # Remove invalid file and try fallback
                try:
                    os.remove(profile_cookies_file)
                except:
                    pass
                
                # Try fallback cookies
                fallback_cookies = [
                    os.path.join(os.getcwd(), "cookies.txt"),
                    GOOGLE_COOKIES_FILE,
                    RENDER_COOKIES_FILE
                ]
                
                for cookies_file in fallback_cookies:
                    if os.path.exists(cookies_file):
                        config["cookiefile"] = cookies_file
                        logger.info(f"🍪 Using fallback cookies: {os.path.basename(cookies_file)}")
                        break
                        
        elif youtube_cookies_file and os.path.exists(youtube_cookies_file):
            config["cookiefile"] = youtube_cookies_file
            logger.info("🍪 Using Chrome-extracted cookies for YouTube")
        elif os.path.exists(os.path.join(os.getcwd(), "cookies.txt")):
            config["cookiefile"] = os.path.join(os.getcwd(), "cookies.txt")
            logger.info("🍪 Using cookies.txt for YouTube")
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

        # For YouTube, use Chrome authentication
        if platform == "youtube":
            logger.info("🔐 Setting up Chrome authentication for YouTube...")
            youtube_auth = YouTubeAuthenticator()
            
            try:
                if youtube_auth.setup_chrome_driver():
                    # Skip the slow verification steps and go straight to cookie extraction
                    logger.info("⚡ Fast-track: Skipping verification, extracting cookies directly...")
                    
                    # Try direct cookie extraction from profile files first (fastest)
                    youtube_cookies_file = youtube_auth.extract_cookies_from_profile_files()
                    
                    if youtube_cookies_file:
                        logger.info("✅ YouTube authentication successful via profile files")
                    else:
                        logger.warning("⚠️ Profile file extraction failed - using fallback cookies")
                else:
                    logger.warning("⚠️ Chrome setup failed - using fallback cookies")
                        
            except Exception as chrome_error:
                logger.warning(f"⚠️ Chrome authentication failed: {str(chrome_error)} - using fallback cookies")

        # Generate unique filename
        uid = str(uuid.uuid4())[:8]
        
        # Get platform-specific configuration with Chrome profile support
        chrome_profile_dir = None
        if platform == "youtube" and youtube_auth and youtube_auth.active_profile_dir:
            chrome_profile_dir = youtube_auth.active_profile_dir
        
        ydl_opts = get_platform_config(platform, youtube_cookies_file, chrome_profile_dir)
        ydl_opts["outtmpl"] = os.path.join(DOWNLOAD_DIR, f"{uid}_%(title)s.%(ext)s")
        
        # Clean up Chrome immediately after getting cookies to prevent hanging
        if youtube_auth:
            logger.info("🧹 Cleaning up Chrome driver before download...")
            youtube_auth.cleanup()
        
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
        
        # Verify profile structure and ensure essential components
        default_dir = os.path.join(profile_dir, "Default")
        if not os.path.exists(default_dir):
            # If no Default directory, check if files are in root and reorganize
            profile_files = os.listdir(profile_dir)
            if any(f in profile_files for f in ["Preferences", "Login Data", "History"]):
                # Create Default directory and move files
                os.makedirs(default_dir, exist_ok=True)
                for item in profile_files:
                    item_path = os.path.join(profile_dir, item)
                    if os.path.isfile(item_path):
                        shutil.move(item_path, os.path.join(default_dir, item))
                    elif os.path.isdir(item_path) and item in ["Network", "Local Storage", "IndexedDB", "Sessions"]:
                        shutil.move(item_path, os.path.join(default_dir, item))
        
        # Ensure essential directories exist
        essential_dirs = [
            os.path.join(default_dir, "Network"),
            os.path.join(default_dir, "Local Storage"), 
            os.path.join(default_dir, "IndexedDB"),
            os.path.join(default_dir, "Sessions")
        ]
        
        for dir_path in essential_dirs:
            os.makedirs(dir_path, exist_ok=True)
        
        # Count authentication indicators
        auth_files = []
        essential_files = [
            ("Login Data", os.path.join(default_dir, "Login Data")),
            ("Preferences", os.path.join(default_dir, "Preferences")),
            ("Network/Cookies", os.path.join(default_dir, "Network", "Cookies")),
            ("Local Storage", os.path.join(default_dir, "Local Storage")),
            ("IndexedDB", os.path.join(default_dir, "IndexedDB")),
            ("Local State", os.path.join(profile_dir, "Local State"))
        ]
        
        for name, path in essential_files:
            if os.path.exists(path):
                auth_files.append(name)
        
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
                
                # Skip cookies with empty values (causes Netscape format issues)
                if not value or not name:
                    continue
                
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