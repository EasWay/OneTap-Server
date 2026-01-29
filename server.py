#!/usr/bin/env python3
"""
OneTap Social Media Video Downloader Server
Supports TikTok, Facebook, Instagram, and Twitter/X
Optimized for speed, efficiency, and quality
"""

import os
import uuid
import yt_dlp
import logging
import time
import re
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from urllib.parse import urlparse, parse_qs
from tiktok_extractor import TikTokExtractor


class J2Extractor:
    """
    J2Download.com API wrapper for fast video extraction from 100+ sites
    """
    
    def __init__(self):
        self.base_url = "https://j2download.com"
        self.api_url = f"{self.base_url}/api/autolink"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        self.session = None
        
    def _create_session(self):
        """Create a new session with browser-like headers"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.user_agent,
            "Referer": f"{self.base_url}/",
            "Origin": self.base_url,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Dnt": "1"
        })
        return session
    
    def _handshake(self, session):
        """Perform handshake to get CSRF token with robust extraction"""
        try:
            logger.info("🤝 Handshaking with j2download.com...")
            
            # Set navigation headers (simulate typing URL in browser)
            nav_headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Temporarily update headers for navigation
            original_headers = session.headers.copy()
            session.headers.update(nav_headers)
            
            home_response = session.get(self.base_url, timeout=15)
            home_response.raise_for_status()
            
            # Restore original headers
            session.headers = original_headers
            
            # Priority 1: Extract CSRF token from cookies
            csrf_token = session.cookies.get("csrf_token")
            
            # Priority 2: Extract from HTML meta tags
            if not csrf_token:
                logger.info("🔍 Searching HTML for CSRF token...")
                meta_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', home_response.text)
                if meta_match:
                    csrf_token = meta_match.group(1)
                    logger.info("✅ Found CSRF token in Meta Tag")
            
            # Priority 3: Extract from JavaScript variables
            if not csrf_token:
                js_match = re.search(r'csrf_token\s*=\s*["\']([^"\']+)["\']', home_response.text)
                if js_match:
                    csrf_token = js_match.group(1)
                    logger.info("✅ Found CSRF token in JS")
            
            # Priority 4: Look for Laravel token pattern
            if not csrf_token:
                laravel_match = re.search(r'_token["\']?\s*:\s*["\']([^"\']+)["\']', home_response.text)
                if laravel_match:
                    csrf_token = laravel_match.group(1)
                    logger.info("✅ Found Laravel token")
            
            if csrf_token:
                session.headers.update({"x-csrf-token": csrf_token})
                logger.info(f"✅ Acquired CSRF Token: {csrf_token[:10]}...")
                return True
            else:
                logger.warning("⚠️ No CSRF token found - proceeding without token")
                return True  # Continue anyway, some endpoints might work without token
                
        except Exception as e:
            logger.error(f"❌ Handshake failed: {e}")
            return False
    
    def extract_video_info(self, url):
        """
        Extract video information using J2Download API
        Returns: dict with success, video_url, title, etc.
        """
        try:
            # Create fresh session for each request
            session = self._create_session()
            
            # Perform handshake
            if not self._handshake(session):
                return {"success": False, "error": "Handshake failed"}
            
            # Update headers for API call (XHR mode)
            api_headers = {
                "Referer": f"{self.base_url}/",
                "Origin": self.base_url,
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": "XMLHttpRequest"  # Crucial for AJAX endpoints
            }
            session.headers.update(api_headers)
            
            # For J2Download, we need the FULL URL with all parameters intact
            # Don't clean or modify the URL - use it exactly as provided after expansion
            logger.info(f"🚀 Using full URL for J2Download: {url}")
            
            # Make API call
            payload = {"url": url}
            logger.info(f"🚀 Sending payload to {self.api_url}")
            logger.info(f"📤 Payload: {payload}")
            
            response = session.post(self.api_url, json=payload, timeout=30)
            
            logger.info(f"📥 Response status: {response.status_code}")
            logger.info(f"📥 Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"❌ J2Download API Error: {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"❌ Error response: {error_data}")
                except:
                    logger.error(f"❌ Raw error response: {response.text[:500]}")
                return {"success": False, "error": f"API error: {response.status_code}"}
            
            try:
                data = response.json()
                logger.info(f"📥 Full response data: {data}")
            except Exception as e:
                logger.error(f"❌ Failed to parse JSON response: {e}")
                logger.error(f"❌ Raw response: {response.text[:1000]}")
                return {"success": False, "error": "Invalid JSON response"}
            
            # Check for API-level errors first
            if data.get("error") is True:
                error_msg = data.get("message", "Unknown API error")
                logger.warning(f"⚠️ J2Download API returned error: {error_msg}")
                return {"success": False, "error": f"J2 API Error: {error_msg}"}
            
            medias = data.get("medias", [])
            
            # Debugging: Log response if medias is empty
            if not medias:
                logger.warning(f"⚠️ Empty media response from J2Download")
                logger.warning(f"⚠️ Full API response: {data}")
                return {"success": False, "error": "No media found in response"}
            
            logger.info(f"✅ Found {len(medias)} media items from J2Download")
            
            # Find best video format
            best_video = None
            for media in medias:
                # Prioritize video type with audio
                if media.get("type") == "video" and (media.get("is_audio") or media.get("audioQuality")):
                    best_video = media
                    break
            
            # Fallback to first available
            if not best_video:
                best_video = medias[0]
            
            return {
                "success": True,
                "video_url": best_video.get("url"),
                "title": data.get("title", "Video"),
                "extension": best_video.get("extension", "mp4"),
                "thumbnail": data.get("thumbnail"),
                "quality": best_video.get("quality", "unknown"),
                "has_audio": best_video.get("is_audio", True),
                "file_size": best_video.get("size"),
                "extractor": "j2download"
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ J2Download API timeout")
            return {"success": False, "error": "API timeout"}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ J2Download API request failed: {e}")
            return {"success": False, "error": f"Request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"❌ J2Download extraction failed: {e}")
            return {"success": False, "error": str(e)}
    
    def download_video(self, video_url, filepath, headers=None):
        """
        Download video file from direct URL
        """
        try:
            if not headers:
                headers = {
                    "User-Agent": self.user_agent,
                    "Referer": self.base_url,
                    "Accept": "*/*"
                }
            
            logger.info(f"⬇️ Downloading video from J2Download...")
            
            response = requests.get(video_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):  # 64KB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Log progress every 2MB
                        if downloaded_size % (2 * 1024 * 1024) == 0 and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            logger.info(f"📥 Download progress: {progress:.1f}% ({downloaded_size / (1024*1024):.1f}MB)")
            
            # Verify file was downloaded
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                raise Exception("Downloaded file is empty or missing")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ J2Download video download failed: {e}")
            return False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/onetap_server.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Suppress verbose logging from dependencies
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Cookie file for social media platforms
SOCIAL_COOKIES_FILE = os.path.join(os.getcwd(), "social_cookies.txt")

# Detect environment
IS_RENDER = os.environ.get('RENDER') is not None

# Initialize TikTok mobile API extractor (will be created per request for user-specific fingerprinting)
def get_tiktok_extractor(user_ip):
    """Get TikTok extractor with user-specific device fingerprinting"""
    # Use user IP as identifier for consistent device fingerprinting
    return TikTokExtractor(user_identifier=user_ip)

# Platform detection patterns
PLATFORM_PATTERNS = {
    'tiktok': ['tiktok.com', 'vm.tiktok.com'],
    'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
    'instagram': ['instagram.com', 'instagr.am'],
    'twitter': ['twitter.com', 'x.com', 't.co']
}


def expand_short_url(url, max_redirects=5):
    """Expand shortened URLs to their final destination"""
    try:
        logger.info(f"🔗 Expanding short URL: {url}")
        
        # Use HEAD request to follow redirects without downloading content
        response = requests.head(
            url, 
            allow_redirects=True, 
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
            }
        )
        
        final_url = response.url
        if final_url != url:
            logger.info(f"✅ URL expanded: {final_url}")
            return final_url
        else:
            logger.info("ℹ️ URL was not shortened")
            return url
            
    except Exception as e:
        logger.warning(f"⚠️ URL expansion failed: {e}, using original URL")
        return url


def clean_url(url, platform):
    """Clean and normalize URLs for better extraction"""
    try:
        # Remove common tracking parameters
        url = re.sub(r'[?&](utm_[^&]*|fbclid|igshid|igsh|rdid|share_url|_r|_t)[^&]*', '', url)
        
        if platform == "tiktok":
            # Expand TikTok short URLs (vt.tiktok.com, vm.tiktok.com) to full URLs
            if any(domain in url for domain in ['vt.tiktok.com', 'vm.tiktok.com']):
                url = expand_short_url(url)
            
            # Remove query params after expansion
            cleaned = url.split('?')[0]
            logger.info(f"🧹 TikTok URL cleaned: {cleaned}")
            return cleaned
            
        elif platform == "facebook":
            # For Facebook, just remove query params and let yt-dlp handle it
            cleaned = url.split('?')[0]
            logger.info(f"🧹 Facebook URL cleaned: {cleaned}")
            return cleaned
            
        elif platform == "instagram":
            # For Instagram, just remove query params and let yt-dlp handle it
            cleaned = url.split('?')[0]
            logger.info(f"🧹 Instagram URL cleaned: {cleaned}")
            return cleaned
            
        elif platform == "twitter":
            # For Twitter, just remove query params and let yt-dlp handle it
            cleaned = url.split('?')[0]
            logger.info(f"🧹 Twitter URL cleaned: {cleaned}")
            return cleaned
        
        # Fallback: just remove query parameters
        cleaned = url.split('?')[0]
        logger.info(f"🧹 Generic URL cleaned: {cleaned}")
        return cleaned if cleaned else url
        
    except Exception as e:
        logger.warning(f"⚠️ URL cleaning failed: {e}")
        return url


def detect_platform(url):
    """Detect platform from URL with improved accuracy"""
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc
        
        # Remove common prefixes
        for prefix in ['www.', 'm.', 'mobile.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
                break
        
        for platform, patterns in PLATFORM_PATTERNS.items():
            if any(pattern in domain for pattern in patterns):
                logger.info(f"✅ Detected platform: {platform}")
                return platform
        
        logger.warning(f"⚠️ Unknown platform for URL: {url}")
        return "generic"
    except Exception as e:
        logger.error(f"❌ Error detecting platform: {e}")
        return "generic"


def download_tiktok_video(url, uid, start_time):
    """
    Download TikTok video using mobile API emulation with aggressive fallback
    """
    platform = "tiktok"
    try:
        logger.info("🎯 Using TikTok Mobile API Emulation")
        
        # Get user IP for device fingerprinting consistency
        user_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        
        # Create TikTok extractor with user-specific device fingerprinting
        tiktok_extractor = get_tiktok_extractor(user_ip)
        
        # Extract video using mobile API with fallback chain
        extraction_result = tiktok_extractor.extract_video(url)
        
        if not extraction_result["success"]:
            logger.error(f"❌ TikTok extraction failed: {extraction_result['error']}")
            return jsonify({
                "error": "TikTok extraction failed",
                "message": extraction_result["error"],
                "platform": "tiktok"
            }), 400
        
        video_url = extraction_result["video_url"]
        fallback_urls = extraction_result.get("fallback_urls", [])
        all_video_urls = [video_url] + [url for url in fallback_urls if url != video_url]
        
        title = extraction_result.get("title", "TikTok Video")
        author = extraction_result.get("author", "Unknown")
        duration = extraction_result.get("duration", 0)
        view_count = extraction_result.get("view_count", 0)
        like_count = extraction_result.get("like_count", 0)
        extractor_used = extraction_result.get("extractor", "unknown")
        has_watermark = extraction_result.get("has_watermark", True)
        quality = extraction_result.get("quality", "medium")
        
        logger.info(f"✅ TikTok extraction successful via {extractor_used}")
        logger.info(f"�  Video URL: {video_url[:50]}...")
        logger.info(f"� Tuitle: {title}")
        logger.info(f"👤 Author: {author}")
        logger.info(f"💧 Watermark: {'Yes' if has_watermark else 'No'}")
        logger.info(f"🎯 Quality: {quality}")
        if len(all_video_urls) > 1:
            logger.info(f"🔄 {len(all_video_urls)-1} fallback URLs available")
        
        # Download the video file with URL fallback
        logger.info("⬇️ Downloading TikTok video file...")
        
        # Create safe filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_title:
            safe_title = "TikTok Video"
        
        filename = f"{uid}_{safe_title}.mp4"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        
        # Try each URL until one works
        download_successful = False
        last_error = None
        
        for url_index, current_video_url in enumerate(all_video_urls):
            try:
                logger.info(f"🔄 Trying video URL {url_index + 1}/{len(all_video_urls)}")
                
                # Use headers from extraction if available, otherwise use mobile-optimized headers
                extraction_headers = extraction_result.get("http_headers", {})
                if extraction_headers:
                    headers = extraction_headers.copy()
                    logger.info(f"🔧 Using extraction headers: {list(headers.keys())}")
                else:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
                        "Referer": "https://www.tiktok.com/",
                        "Accept": "*/*",
                        "Accept-Encoding": "identity"
                    }
                
                # Download with retry logic and proper error handling
                max_retries = 3
                retry_delay = 1
                
                for attempt in range(max_retries):
                    try:
                        logger.info(f"⬇️ Downloading TikTok video file (URL {url_index + 1}, attempt {attempt + 1}/{max_retries})...")
                        
                        response = requests.get(
                            current_video_url, 
                            headers=headers, 
                            stream=True, 
                            timeout=60,
                            allow_redirects=True
                        )
                        response.raise_for_status()
                        
                        # If we get here, the request was successful
                        break
                        
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code == 403:
                            logger.warning(f"⚠️ 403 Forbidden on attempt {attempt + 1} - trying different headers")
                            
                            # Try with minimal headers on retry
                            if attempt < max_retries - 1:
                                headers = {
                                    "User-Agent": "TikTok 26.2.0 rv:262018 (iPhone; iOS 14.4.2; en_US) Cronet",
                                    "Accept": "*/*"
                                }
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                                continue
                            else:
                                raise Exception(f"Video download failed with 403 Forbidden after {max_retries} attempts")
                                
                        elif e.response.status_code == 404:
                            raise Exception("Video not found (404). The video may have been deleted or the URL is invalid.")
                            
                        else:
                            raise Exception(f"HTTP {e.response.status_code}: {e.response.reason}")
                            
                    except requests.exceptions.Timeout:
                        if attempt < max_retries - 1:
                            logger.warning(f"⚠️ Download timeout on attempt {attempt + 1} - retrying...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            raise Exception("Download timed out after multiple attempts")
                            
                    except requests.exceptions.ConnectionError:
                        if attempt < max_retries - 1:
                            logger.warning(f"⚠️ Connection error on attempt {attempt + 1} - retrying...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            raise Exception("Connection failed after multiple attempts")
                
                # Download the file
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=65536):  # 64KB chunks
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Log progress every 2MB
                            if downloaded_size % (2 * 1024 * 1024) == 0 and total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                logger.info(f"📥 Download progress: {progress:.1f}% ({downloaded_size / (1024*1024):.1f}MB)")
                
                # Verify file was downloaded
                if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                    raise Exception("Downloaded file is empty or missing")
                
                download_successful = True
                logger.info(f"✅ Successfully downloaded using URL {url_index + 1}")
                break
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ URL {url_index + 1} failed: {e}")
                
                # Clean up partial file if it exists
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
                
                # Continue to next URL
                continue
        
        if not download_successful:
            raise Exception(f"All video URLs failed. Last error: {last_error}")
        
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        download_time = time.time() - start_time
        
        # Build response
        base_url = request.host_url.rstrip("/")
        if IS_RENDER:
            base_url = base_url.replace("http://", "https://")
        
        logger.info(f"✅ TikTok download complete: {filename} ({download_time:.2f}s, {file_size_mb:.2f}MB)")
        
        return jsonify({
            "status": "success",
            "message": "TikTok download successful via mobile API",
            "platform": "tiktok",
            "title": title,
            "duration": duration,
            "filename": filename,
            "download_url": f"{base_url}/files/{filename}",
            "uploader": author,
            "view_count": view_count,
            "like_count": like_count,
            "download_time": round(download_time, 2),
            "file_size_mb": round(file_size_mb, 2),
            "extractor": extractor_used,
            "has_watermark": has_watermark,
            "quality": quality,
            "environment": "render" if IS_RENDER else "local",
            # Additional TikTok-specific metadata
            "video_codec": "h264",
            "audio_codec": "aac", 
            "container": "mp4"
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ TikTok video download failed: {e}")
        return jsonify({
            "error": "TikTok download failed",
            "message": f"Network error: {str(e)}",
            "platform": "tiktok"
        }), 500
        
    except Exception as e:
        logger.error(f"❌ TikTok processing failed: {e}")
        return jsonify({
            "error": "TikTok processing failed", 
            "message": str(e),
            "platform": "tiktok"
        }), 500


def get_platform_config(platform):
    """Get optimized platform-specific yt-dlp configuration"""
    
    if platform == "facebook":
        # Ultra-minimal config for Facebook (bypasses all extractors)
        config = {
            "format": "best",
            "quiet": False,
            "no_warnings": False,
            "retries": 3,
            "socket_timeout": 20,
            "extractor_args": {},  # No extractor-specific args
            "force_generic_extractor": True,
            "no_check_certificate": True
        }
    else:
        # Standard minimal config for other platforms
        config = {
            "format": "best",
            "quiet": False,
            "no_warnings": False,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "http_chunk_size": 10485760,  # 10MB chunks
            "concurrent_fragment_downloads": 4  # Parallel downloads for speed
        }
    
    # Add cookies if available
    if os.path.exists(SOCIAL_COOKIES_FILE):
        config["cookiefile"] = SOCIAL_COOKIES_FILE
        logger.info(f"🍪 Using authenticated cookies for {platform}")
    else:
        logger.warning(f"⚠️ No cookies found - some content may be unavailable")
    
    return config


@app.route("/test_j2", methods=["POST"])
def test_j2download():
    """Test J2Download with different URL formats"""
    try:
        data = request.get_json()
        test_url = data.get("url", "https://www.tiktok.com/@mackasy_ai/video/7600355794755849490")
        
        logger.info(f"🧪 Testing J2Download with URL: {test_url}")
        
        j2_extractor = J2Extractor()
        result = j2_extractor.extract_video_info(test_url)
        
        return jsonify({
            "test_url": test_url,
            "result": result,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"❌ J2Download test failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    """Health check and API info"""
    return jsonify({
        "status": "online",
        "service": "OneTap Social Media Video Downloader",
        "version": "2.2.0",
        "supported_platforms": ["tiktok", "facebook", "instagram", "twitter", "youtube", "100+ others"],
        "extraction_methods": {
            "primary": "J2Download API (Fast, 100+ sites)",
            "backup_tiktok": "TikTok Mobile API Emulation",
            "backup_others": "yt-dlp"
        },
        "environment": "render" if IS_RENDER else "local",
        "cookies_loaded": os.path.exists(SOCIAL_COOKIES_FILE),
        "endpoints": {
            "download": "/download (POST)",
            "upload_cookies": "/upload_cookies (POST)",
            "files": "/files/<filename> (GET)",
            "health": "/health (GET)",
            "version": "/version (GET) - App update check"
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Detailed health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "download_dir": os.path.exists(DOWNLOAD_DIR),
        "cookies_available": os.path.exists(SOCIAL_COOKIES_FILE),
        "disk_space_mb": get_disk_space()
    })


@app.route("/version", methods=["GET"])
def version():
    """App update endpoint - returns latest version info"""
    try:
        # Configure your app update information here
        # Update these values when you release a new version
        latest_version_code = 5  # Must match versionCode in app/build.gradle.kts
        apk_download_url = "https://github.com/EasWay/OneTap-Releases/releases/download/v1.4/app-release.apk"
        release_notes = "Bug fixes and performance improvements"
        
        logger.info(f"📱 Version check requested - Latest: v{latest_version_code}")
        
        return jsonify({
            "status": "success",
            "latest_version": latest_version_code,
            "apk_url": apk_download_url,
            "release_notes": release_notes,
            "server_version": "2.1.0",
            "timestamp": time.time()
        })
    except Exception as e:
        logger.error(f"❌ Version check failed: {str(e)}")
        return jsonify({
            "error": f"Version check failed: {str(e)}"
        }), 500


def get_disk_space():
    """Get available disk space in MB"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
        return free // (1024 * 1024)
    except:
        return -1


@app.route("/download", methods=["POST"])
def download_video():
    """Download video from supported social media platforms"""
    logger.info(f"🚀 Download request received ({'Render' if IS_RENDER else 'Local'} mode)")
    
    start_time = time.time()
    
    try:
        # Parse request
        data = request.get_json()
        url = data.get("url")
        
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        # Detect platform
        platform = detect_platform(url)
        
        if platform == "generic":
            return jsonify({
                "error": "Unsupported platform",
                "message": "Only TikTok, Facebook, Instagram, and Twitter are supported"
            }), 400

        # Check for unsupported content types BEFORE cleaning
        if platform == "tiktok" and '/photo/' in url:
            logger.warning("⚠️ TikTok photo post detected - not supported")
            return jsonify({
                "error": "Unsupported content type",
                "message": "TikTok photo posts are not supported. Only video posts can be downloaded.",
                "platform": platform
            }), 400
        
        # Clean URL for better extraction
        cleaned_url = clean_url(url, platform)
        
        # Check if URL cleaning failed
        if cleaned_url is None:
            return jsonify({
                "error": "Unsupported content type",
                "message": "This content type is not supported. Only videos can be downloaded.",
                "platform": platform
            }), 400
        
        logger.info(f"🧹 Cleaned URL: {cleaned_url}")

        # Generate unique filename
        uid = str(uuid.uuid4())[:8]

        # STRATEGY 1: Try J2Extractor first (Primary Method - Fast & Supports 100+ sites)
        logger.info("🎯 Trying J2Extractor (Primary Method)...")
        j2_extractor = J2Extractor()
        
        # For J2Download, only use expanded full URLs - never short URLs
        urls_to_try_j2 = []
        
        # If it's a short URL, expand it first
        if any(domain in url for domain in ['vt.tiktok.com', 'vm.tiktok.com']):
            expanded_url = expand_short_url(url)
            logger.info(f"🔗 Expanded URL: {expanded_url}")
            
            # 1. Expanded URL with parameters
            urls_to_try_j2.append(expanded_url)
            
            # 2. Expanded URL without parameters
            clean_expanded = expanded_url.split('?')[0]
            if clean_expanded != expanded_url:
                urls_to_try_j2.append(clean_expanded)
                logger.info(f"🧹 Clean expanded URL: {clean_expanded}")
        else:
            # If it's already a full URL, use it as-is
            urls_to_try_j2.append(url)
        
        # Try each FULL URL format with J2Download (no short URLs)
        j2_success = False
        for i, test_url in enumerate(urls_to_try_j2):
            logger.info(f"🔄 J2Download attempt {i+1}/{len(urls_to_try_j2)}: {test_url}")
            j2_result = j2_extractor.extract_video_info(test_url)
            if j2_result["success"]:
                j2_success = True
                break
            else:
                logger.warning(f"⚠️ J2Download attempt {i+1} failed: {j2_result.get('error', 'Unknown error')}")
                # If it's the "Invalid link" error, J2Download might not support TikTok right now
                if "Invalid link" in j2_result.get('error', ''):
                    logger.warning("⚠️ J2Download appears to be rejecting TikTok URLs - skipping remaining attempts")
                    break
        
        if j2_success:
            try:
                # Create safe filename
                title = j2_result.get("title", "Video")
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                if not safe_title:
                    safe_title = "Video"
                
                extension = j2_result.get("extension", "mp4")
                filename = f"{uid}_{safe_title}.{extension}"
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                
                # Download video using J2Extractor
                if j2_extractor.download_video(j2_result["video_url"], filepath):
                    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    download_time = time.time() - start_time
                    
                    # Build download URL
                    base_url = request.host_url.rstrip("/")
                    if IS_RENDER:
                        base_url = base_url.replace("http://", "https://")
                    
                    logger.info(f"✅ J2Extractor download complete: {filename} ({download_time:.2f}s, {file_size_mb:.2f}MB)")
                    
                    return jsonify({
                        "status": "success",
                        "message": "Download successful via J2Extractor",
                        "platform": platform,
                        "title": title,
                        "filename": filename,
                        "download_url": f"{base_url}/files/{filename}",
                        "download_time": round(download_time, 2),
                        "file_size_mb": round(file_size_mb, 2),
                        "extractor": "j2download",
                        "quality": j2_result.get("quality", "unknown"),
                        "has_audio": j2_result.get("has_audio", True),
                        "environment": "render" if IS_RENDER else "local",
                        "method": "primary"
                    })
                else:
                    logger.warning("⚠️ J2Extractor download failed, trying backup methods...")
            except Exception as e:
                logger.warning(f"⚠️ J2Extractor processing failed: {e}, trying backup methods...")
        else:
            logger.warning(f"⚠️ J2Extractor failed after trying {len(urls_to_try_j2)} URL formats, trying backup methods...")

        # STRATEGY 2: Special handling for TikTok using mobile API emulation (Backup for TikTok)
        if platform == "tiktok":
            logger.info("🎯 Trying TikTok Mobile API (Backup Method)...")
            return download_tiktok_video(cleaned_url, uid, start_time)
        
        # STRATEGY 3: For other platforms, use yt-dlp as backup
        logger.info(f"🎯 Trying yt-dlp (Backup Method for {platform})...")
        
        # Get platform-specific configuration
        ydl_opts = get_platform_config(platform)
        ydl_opts["outtmpl"] = os.path.join(DOWNLOAD_DIR, f"{uid}_%(title)s.%(ext)s")
        
        # Execute download
        logger.info(f"⬇️ Starting backup download from {platform}...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(cleaned_url, download=True)
            filename = os.path.basename(ydl.prepare_filename(info))
        
        # Clean filename for safety
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        if safe_filename != filename:
            old_path = os.path.join(DOWNLOAD_DIR, filename)
            new_path = os.path.join(DOWNLOAD_DIR, safe_filename)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                filename = safe_filename
        
        # Calculate download time
        download_time = time.time() - start_time
        
        # Build download URL
        base_url = request.host_url.rstrip("/")
        if IS_RENDER:
            base_url = base_url.replace("http://", "https://")
        
        logger.info(f"✅ Backup download complete: {filename} ({download_time:.2f}s)")
        
        return jsonify({
            "status": "success",
            "message": "Download successful via backup method",
            "platform": platform,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "filename": filename,
            "download_url": f"{base_url}/files/{filename}",
            "uploader": info.get("uploader", "Unknown"),
            "view_count": info.get("view_count", 0),
            "download_time": round(download_time, 2),
            "environment": "render" if IS_RENDER else "local",
            "file_size_mb": round(os.path.getsize(os.path.join(DOWNLOAD_DIR, filename)) / (1024 * 1024), 2),
            "extractor": "yt-dlp",
            "method": "backup"
        })

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"❌ Backup download failed: {error_msg}")
        
        # Check if it's a TikTok photo post (detected after redirect)
        if platform == "tiktok" and ("/photo/" in error_msg or "photo" in error_msg.lower()):
            return jsonify({
                "error": "Unsupported content type",
                "message": "TikTok photo posts are not supported. Only video posts can be downloaded.",
                "platform": platform
            }), 400
        
        # Provide helpful error messages
        if "login" in error_msg.lower() or "private" in error_msg.lower():
            return jsonify({
                "error": f"Authentication required for {platform}",
                "message": "Please upload valid cookies using /upload_cookies endpoint",
                "platform": platform
            }), 401
        elif "not available" in error_msg.lower() or "removed" in error_msg.lower():
            return jsonify({
                "error": "Content not available",
                "message": "The video may be private, deleted, or geo-restricted",
                "platform": platform
            }), 404
        elif "unsupported url" in error_msg.lower():
            # Check if the error message contains a photo URL
            if "/photo/" in error_msg:
                return jsonify({
                    "error": "Unsupported content type",
                    "message": "TikTok photo posts are not supported. Only video posts can be downloaded.",
                    "platform": platform
                }), 400
            return jsonify({
                "error": "Unsupported URL format",
                "message": f"This {platform} URL format is not supported",
                "platform": platform
            }), 400
        else:
            return jsonify({
                "error": f"All download methods failed: {error_msg}",
                "platform": platform
            }), 500
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        logger.exception("Full error traceback:")
        platform = locals().get('platform', 'unknown')
        return jsonify({
            "error": f"Server error: {str(e)}",
            "platform": platform
        }), 500


@app.route("/upload_cookies", methods=["POST"])
def upload_cookies():
    """Upload social media cookies in Netscape format"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Save cookies file
        file.save(SOCIAL_COOKIES_FILE)
        
        # Validate and count cookies
        cookie_stats = validate_cookies(SOCIAL_COOKIES_FILE)
        
        if cookie_stats['total'] == 0:
            return jsonify({"error": "No valid cookies found in file"}), 400
        
        logger.info(f"✅ Uploaded {cookie_stats['total']} cookies")
        
        return jsonify({
            "message": "Cookies uploaded successfully",
            "statistics": cookie_stats,
            "platforms": ["tiktok", "facebook", "instagram", "twitter"]
        })
        
    except Exception as e:
        logger.error(f"❌ Cookie upload failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


def validate_cookies(cookie_file):
    """Validate and analyze cookies file"""
    stats = {
        'total': 0,
        'tiktok': 0,
        'facebook': 0,
        'instagram': 0,
        'twitter': 0,
        'other': 0
    }
    
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain = parts[0].lower()
                        stats['total'] += 1
                        
                        if 'tiktok' in domain:
                            stats['tiktok'] += 1
                        elif 'facebook' in domain or 'fb' in domain:
                            stats['facebook'] += 1
                        elif 'instagram' in domain:
                            stats['instagram'] += 1
                        elif 'twitter' in domain or 'x.com' in domain:
                            stats['twitter'] += 1
                        else:
                            stats['other'] += 1
    except Exception as e:
        logger.error(f"❌ Error validating cookies: {e}")
    
    return stats


@app.route("/files/<filename>", methods=["GET"])
def serve_file(filename):
    """Serve downloaded files"""
    try:
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404


@app.route("/cleanup", methods=["POST"])
def cleanup_downloads():
    """Clean up old downloaded files"""
    try:
        import shutil
        
        if os.path.exists(DOWNLOAD_DIR):
            file_count = len([f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))])
            shutil.rmtree(DOWNLOAD_DIR)
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            
            logger.info(f"🧹 Cleaned up {file_count} files")
            
            return jsonify({
                "message": "Cleanup successful",
                "files_removed": file_count
            })
        else:
            return jsonify({"message": "Nothing to clean up"})
            
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


def get_port():
    """Get port from environment or find an available one"""
    # Prefer RENDER's PORT environment variable
    if os.environ.get("PORT"):
        return int(os.environ.get("PORT"))
    
    # In local/Replit development, default to 5000 if not specified
    # However, user requested to find an available port for Render
    # Flask app.run(port=0) or not specifying port usually lets OS decide,
    # but we need to know it for the logs.
    return int(os.environ.get("PORT", 0))


if __name__ == "__main__":
    port = get_port()
    logger.info(f"🚀 Starting OneTap Social Media Downloader v2.2.0")
    logger.info(f"📁 Download directory: {DOWNLOAD_DIR}")
    logger.info(f"🍪 Cookies file: {SOCIAL_COOKIES_FILE}")
    logger.info(f"🌍 Environment: {'Render' if IS_RENDER else 'Local'}")
    logger.info(f"⚡ Primary Method: J2Download API (100+ sites)")
    logger.info(f"🔄 Backup Methods: TikTok Mobile API + yt-dlp")
    logger.info(f"✅ Supported platforms: TikTok, Facebook, Instagram, Twitter, YouTube + 100+ others")
    
    # If port is 0, Flask will pick an available port
    app.run(host="0.0.0.0", port=port if port != 0 else None, debug=False)
