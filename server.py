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
    """Resolves short URLs for all supported platforms"""
    try:
        short_domains = [
            # TikTok & Related
            'vt.tiktok.com', 'vm.tiktok.com', 'tiktok.com/t/',
            # General Short URLs
            'bit.ly', 't.co', 'tinyurl.com', 'short.link', 'ow.ly',
            # Platform Specific
            'fb.me', 'fb.watch', 'ig.me', 'pin.it', 'lnkd.in', 'youtu.be',
            't.snapchat.com', 'snd.sc', 'spoti.fi', 'redd.it', 'b23.tv',
            # Chinese Platforms
            'xhslink.com', 'douyin.com/share', 'kuaishou.com/s',
            # Other
            'r.mtdv.me', 'x.com', 'bsky.app', 't.me'
        ]
        
        if any(x in url for x in short_domains):
            logger.info(f"🔗 Expanding short URL: {url}")
            headers = {"User-Agent": J2_UA}
            try:
                resp = requests.head(url, allow_redirects=True, headers=headers, timeout=10)
                if resp.status_code >= 400: raise Exception("Head failed")
            except:
                resp = requests.get(url, allow_redirects=True, headers=headers, stream=True, timeout=10)
                resp.close()
            resolved = resp.url
            if "login" not in resolved and "error" not in resolved:
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
    """Enhanced platform detection for 50+ supported platforms"""
    domain = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    
    # TikTok & Related
    if any(x in domain for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]): return "tiktok"
    if "douyin.com" in domain: return "douyin"
    if "capcut.com" in domain: return "capcut"
    
    # Meta Platforms
    if any(x in domain for x in ["facebook.com", "fb.watch", "fb.com", "m.facebook.com"]): return "facebook"
    if any(x in domain for x in ["instagram.com", "instagr.am", "ig.me"]): return "instagram"
    if "threads.net" in domain: return "threads"
    
    # Twitter/X
    if any(x in domain for x in ["twitter.com", "x.com", "t.co", "mobile.twitter.com"]): return "twitter"
    
    # Video Platforms
    if any(x in domain for x in ["youtube.com", "youtu.be", "m.youtube.com", "youtube-nocookie.com"]): return "youtube"
    if "vimeo.com" in domain: return "vimeo"
    if "dailymotion.com" in domain: return "dailymotion"
    if "bilibili.com" in domain or "b23.tv" in domain: return "bilibili"
    if "rumble.com" in domain: return "rumble"
    if "streamable.com" in domain: return "streamable"
    if "ted.com" in domain: return "ted"
    if "sohu.com" in domain or "tv.sohu.com" in domain: return "sohutv"
    if "bitchute.com" in domain: return "bitchute"
    
    # Chinese Platforms
    if "kuaishou.com" in domain or "kwai.com" in domain: return "kuaishou"
    if "xiaohongshu.com" in domain or "xhslink.com" in domain: return "xiaohongshu"
    if "ixigua.com" in domain: return "ixigua"
    if "weibo.com" in domain or "weibo.cn" in domain: return "weibo"
    if "miaopai.com" in domain: return "miaopai"
    if "meipai.com" in domain: return "meipai"
    if "xiaoying.tv" in domain: return "xiaoying"
    if "yingke.com" in domain: return "yingke"
    if "sina.com" in domain: return "sina"
    
    # Social & Communication
    if "reddit.com" in domain or "redd.it" in domain: return "reddit"
    if "snapchat.com" in domain: return "snapchat"
    if "pinterest.com" in domain or "pin.it" in domain: return "pinterest"
    if "tumblr.com" in domain: return "tumblr"
    if "linkedin.com" in domain or "lnkd.in" in domain: return "linkedin"
    if "telegram.org" in domain or "t.me" in domain: return "telegram"
    if "bsky.app" in domain or "bluesky.social" in domain: return "bluesky"
    
    # Indian Platforms
    if "sharechat.com" in domain: return "sharechat"
    if "likee.video" in domain or "like.video" in domain: return "likee"
    if "hipi.co.in" in domain: return "hipi"
    
    # Entertainment & Media
    if "imdb.com" in domain: return "imdb"
    if "imgur.com" in domain: return "imgur"
    if "ifunny.co" in domain: return "ifunny"
    if "izlesene.com" in domain: return "izlesene"
    if "espn.com" in domain: return "espn"
    if "9gag.com" in domain: return "9gag"
    if "ok.ru" in domain or "oke.ru" in domain: return "oke"
    if "febspot.com" in domain: return "febspot"
    if "getstickerpack.com" in domain: return "getstickerpack"
    
    # Audio Platforms
    if "soundcloud.com" in domain or "snd.sc" in domain: return "soundcloud"
    if "mixcloud.com" in domain: return "mixcloud"
    if "spotify.com" in domain or "spoti.fi" in domain: return "spotify"
    if "deezer.com" in domain: return "deezer"
    if "zingmp3.vn" in domain: return "zingmp3"
    if "bandcamp.com" in domain: return "bandcamp"
    if "castbox.fm" in domain: return "castbox"
    
    # File Sharing
    if "mediafire.com" in domain: return "mediafire"
    
    # Adult Content (if needed)
    if "pornbox.com" in domain: return "pornbox"
    if "xvideos.com" in domain: return "xvideos"
    if "xnxx.com" in domain: return "xnxx"
    
    # QQ Platform
    if "qq.com" in domain: return "qq"
    
    return "generic"

# --- SMART PARSER ---
class J2ResponseParser:
    @staticmethod
    def parse(data, platform):
        """Enhanced parser for 50+ platforms with smart format selection"""
        medias = data.get("medias", [])
        if not medias: return None
        
        logger.info(f"🧠 Parsing {len(medias)} formats for {platform}")
        
        # Platform-specific parsing
        if platform in ["tiktok", "douyin", "capcut"]:
            return J2ResponseParser._parse_tiktok(medias)
        elif platform in ["facebook", "instagram", "threads"]:
            return J2ResponseParser._parse_meta(medias)
        elif platform in ["twitter", "bluesky"]:
            return J2ResponseParser._parse_twitter(medias)
        elif platform in ["youtube", "vimeo", "dailymotion", "bilibili"]:
            return J2ResponseParser._parse_video_platform(medias)
        elif platform in ["soundcloud", "mixcloud", "spotify", "deezer", "zingmp3", "bandcamp", "castbox"]:
            return J2ResponseParser._parse_audio(medias)
        elif platform in ["pinterest", "imgur", "9gag"]:
            return J2ResponseParser._parse_image_platform(medias)
        elif platform in ["kuaishou", "xiaohongshu", "ixigua", "weibo", "miaopai", "meipai", "xiaoying", "yingke", "sina"]:
            return J2ResponseParser._parse_chinese_platform(medias)
        elif platform in ["sharechat", "likee", "hipi"]:
            return J2ResponseParser._parse_indian_platform(medias)
        elif platform in ["reddit", "tumblr", "linkedin"]:
            return J2ResponseParser._parse_social_platform(medias)
        elif platform in ["snapchat", "telegram"]:
            return J2ResponseParser._parse_messaging_platform(medias)
        elif platform in ["pornbox", "xvideos", "xnxx"]:
            return J2ResponseParser._parse_adult_platform(medias)
        
        # Generic fallback - prioritize video with audio
        return J2ResponseParser._parse_generic(medias)
    
    @staticmethod
    def _parse_tiktok(medias):
        """TikTok/Douyin/Capcut - prioritize no watermark HD"""
        for m in medias:
            if m.get("quality") == "hd_no_watermark": return m
        for m in medias:
            if m.get("quality") == "no_watermark": return m
        for m in medias:
            if "watermark" not in str(m.get("quality", "")).lower(): return m
        return medias[0]
    
    @staticmethod
    def _parse_meta(medias):
        """Facebook/Instagram/Threads - prioritize HD video"""
        videos = [m for m in medias if m.get("type") == "video"]
        for v in videos:
            q = str(v.get("quality", "")).lower()
            if "hd" in q or "1080" in q or "720" in q:
                return v
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_twitter(medias):
        """Twitter/X/Bluesky - prefer highest bitrate MP4"""
        videos = [m for m in medias if m.get("type") == "video" and m.get("extension") == "mp4"]
        if not videos: 
            videos = [m for m in medias if m.get("type") == "video"]
        
        if "formats" in medias[0]:
            sub_formats = medias[0].get("formats", [])
            mp4s = [f for f in sub_formats if f.get("container") == "mp4"]
            if mp4s:
                try:
                    mp4s.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
                    return {"url": mp4s[0]["url"], "extension": "mp4"}
                except: pass
        
        try:
            videos.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
        except: pass
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_video_platform(medias):
        """YouTube/Vimeo/Dailymotion/Bilibili - video with audio"""
        valid_videos = []
        for m in medias:
            if m.get("type") == "video":
                if m.get("is_audio") is True or m.get("audioQuality") or m.get("has_audio"):
                    valid_videos.append(m)
        
        if not valid_videos:
            valid_videos = [m for m in medias if m.get("type") == "video"]
        
        return valid_videos[0] if valid_videos else medias[0]
    
    @staticmethod
    def _parse_audio(medias):
        """Audio platforms - highest quality audio"""
        audio_files = [m for m in medias if m.get("type") == "audio"]
        if audio_files:
            # Sort by bitrate or quality
            try:
                audio_files.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
            except: pass
            return audio_files[0]
        
        # Fallback to any media
        return medias[0]
    
    @staticmethod
    def _parse_image_platform(medias):
        """Pinterest/Imgur/9GAG - prefer images, fallback to video"""
        images = [m for m in medias if m.get("type") == "image"]
        if images: return images[0]
        
        videos = [m for m in medias if m.get("type") == "video"]
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_chinese_platform(medias):
        """Chinese platforms - similar to TikTok logic"""
        for m in medias:
            if "no_watermark" in str(m.get("quality", "")).lower(): return m
        for m in medias:
            if m.get("type") == "video": return m
        return medias[0]
    
    @staticmethod
    def _parse_indian_platform(medias):
        """Indian platforms - prefer video content"""
        videos = [m for m in medias if m.get("type") == "video"]
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_social_platform(medias):
        """Reddit/Tumblr/LinkedIn - flexible content"""
        # Prefer video, then image, then any
        videos = [m for m in medias if m.get("type") == "video"]
        if videos: return videos[0]
        
        images = [m for m in medias if m.get("type") == "image"]
        if images: return images[0]
        
        return medias[0]
    
    @staticmethod
    def _parse_messaging_platform(medias):
        """Snapchat/Telegram - any media type"""
        return medias[0]
    
    @staticmethod
    def _parse_adult_platform(medias):
        """Adult platforms - video priority"""
        videos = [m for m in medias if m.get("type") == "video"]
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_generic(medias):
        """Generic fallback - smart selection"""
        # Priority: video with audio > video > image > audio > any
        videos_with_audio = [m for m in medias if m.get("type") == "video" and (m.get("is_audio") or m.get("has_audio"))]
        if videos_with_audio: return videos_with_audio[0]
        
        videos = [m for m in medias if m.get("type") == "video"]
        if videos: return videos[0]
        
        images = [m for m in medias if m.get("type") == "image"]
        if images: return images[0]
        
        audio = [m for m in medias if m.get("type") == "audio"]
        if audio: return audio[0]
        
        return medias[0]

class J2Extractor:
    def extract_download_url(self, video_url):
        try:
            platform = detect_platform(video_url)
            logger.info(f"🎯 J2 Extraction for {platform}: {video_url}")
            
            session = requests.Session()
            
            # Step 1: Navigation headers (simulate typing URL in browser)
            nav_headers = {
                "User-Agent": J2_UA,
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
            
            session.headers.update(nav_headers)
            
            # Handshake with navigation headers
            logger.info("🤝 Performing J2Download handshake...")
            home_resp = session.get(J2_BASE_URL, timeout=15)
            
            if home_resp.status_code != 200:
                logger.warning(f"⚠️ Handshake returned status {home_resp.status_code}")
                return None
            
            # Deep Token Extraction - Priority 1: Cookies
            csrf_token = session.cookies.get("csrf_token")
            
            # Priority 2: HTML Meta Tags
            if not csrf_token:
                logger.info("🔍 Searching HTML for CSRF token...")
                meta_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', home_resp.text)
                if meta_match:
                    csrf_token = meta_match.group(1)
                    logger.info("✅ Found CSRF token in Meta Tag")
            
            # Priority 3: JavaScript Variables
            if not csrf_token:
                js_match = re.search(r'csrf_token\s*=\s*["\']([^"\']+)["\']', home_resp.text)
                if js_match:
                    csrf_token = js_match.group(1)
                    logger.info("✅ Found CSRF token in JS")
            
            # Priority 4: Laravel Token Pattern
            if not csrf_token:
                laravel_match = re.search(r'_token["\']?\s*:\s*["\']([^"\']+)["\']', home_resp.text)
                if laravel_match:
                    csrf_token = laravel_match.group(1)
                    logger.info("✅ Found Laravel token")
            
            # Priority 5: XSRF Token (alternative name)
            if not csrf_token:
                xsrf_match = re.search(r'xsrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)["\']', home_resp.text, re.IGNORECASE)
                if xsrf_match:
                    csrf_token = xsrf_match.group(1)
                    logger.info("✅ Found XSRF token")
            
            if not csrf_token: 
                logger.warning("⚠️ No CSRF token found after deep search")
                return None
            
            logger.info(f"✅ CSRF token acquired: {csrf_token[:10]}...")
            
            # Step 2: Switch to XHR headers for API call
            xhr_headers = {
                "Referer": f"{J2_BASE_URL}/",
                "Origin": J2_BASE_URL,
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "x-csrf-token": csrf_token,
                "X-Requested-With": "XMLHttpRequest"
            }
            
            # Update session with XHR headers
            session.headers.update(xhr_headers)
            
            payload = {
                "data": {
                    "url": video_url,
                    "unlock": True
                }
            }
            
            logger.info(f"🚀 Sending J2Download API request...")
            logger.info(f"📤 Payload: {payload}")
            
            response = session.post(J2_API_URL, json=payload, timeout=30)
            
            logger.info(f"📥 Response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"❌ J2Download API HTTP error: {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"❌ Error response: {error_data}")
                except:
                    logger.error(f"❌ Raw error response: {response.text[:500]}")
                return None
            
            try:
                data = response.json()
                logger.info(f"📥 J2Download response: {data}")
            except Exception as e:
                logger.error(f"❌ Failed to parse JSON: {e}")
                logger.error(f"❌ Raw response: {response.text[:1000]}")
                return None
            
            if "error" in data and data["error"]: 
                logger.warning(f"⚠️ J2Download API error: {data.get('message', 'Unknown error')}")
                return None
            
            # Use Smart Parser
            best_media = J2ResponseParser.parse(data, platform)
            if best_media:
                logger.info(f"✅ J2Download extraction successful!")
                
                # Check if it's a multi-media response (like TikTok photo slideshow)
                medias = data.get("medias", [])
                images = [m for m in medias if m.get("type") == "image"]
                
                if len(images) > 1:
                    # Return full data for multi-image posts
                    return {
                        "url": best_media.get("url"),
                        "ext": best_media.get("extension", "jpg"),
                        "title": data.get("title", "video"),
                        "medias": medias,  # Include all media items
                        "type": "multi_image"
                    }
                else:
                    # Single media item
                    return {
                        "url": best_media.get("url"),
                        "ext": best_media.get("extension", "mp4"),
                        "title": data.get("title", "video")
                    }
            else:
                logger.warning("⚠️ J2Download: No suitable media found in response")
                return None
            
        except Exception as e:
            logger.error(f"❌ J2 Failed: {e}")
            return None

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

@app.route("/", methods=["GET"])
def index():
    """API information and supported platforms"""
    supported_platforms = {
        "video_platforms": [
            "TikTok", "Douyin", "Capcut", "YouTube", "Vimeo", "Dailymotion", 
            "Bilibili", "Rumble", "Streamable", "Ted", "SohuTv", "Bitchute"
        ],
        "social_media": [
            "Instagram", "Facebook", "Threads", "Twitter/X", "Snapchat", 
            "Pinterest", "Reddit", "Tumblr", "LinkedIn", "Bluesky", "Telegram"
        ],
        "chinese_platforms": [
            "Kuaishou", "Xiaohongshu", "Ixigua", "Weibo", "Miaopai", 
            "Meipai", "Xiaoying", "Yingke", "Sina", "QQ"
        ],
        "indian_platforms": [
            "Sharechat", "Likee", "Hipi"
        ],
        "audio_platforms": [
            "Soundcloud", "Mixcloud", "Spotify", "Deezer", "Zingmp3", 
            "Bandcamp", "Castbox"
        ],
        "entertainment": [
            "ESPN", "IMDB", "Imgur", "iFunny", "Izlesene", "9GAG", 
            "oke.ru", "Febspot", "Getstickerpack"
        ],
        "file_sharing": [
            "Mediafire"
        ],
        "adult_content": [
            "Pornbox", "Xvideos", "Xnxx"
        ]
    }
    
    return jsonify({
        "status": "online",
        "service": "Universal Media Downloader",
        "version": "3.0.0",
        "supported_platforms": supported_platforms,
        "total_platforms": sum(len(platforms) for platforms in supported_platforms.values()),
        "features": [
            "Download videos without watermarks (TikTok, etc.)",
            "Support for images, videos, and audio",
            "Multiple format support (.mp4, .mp3, .jpg, .png)",
            "Works on all devices (PC, Mac, Android, iOS)",
            "Photo slideshow downloads in MP4 format",
            "Free service with no registration required"
        ],
        "extraction_methods": {
            "primary": "J2Download API (Fast, 50+ sites)",
            "secondary": "yt-dlp with platform optimization"
        },
        "endpoints": {
            "download": "/download (POST)",
            "files": "/files/<filename> (GET)",
            "cookies": "/update_cookies (POST)",
            "google_cookies": "/update_google_cookies (POST)",
            "profile": "/upload_profile (POST)"
        }
    })

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
            
            # Check if it's a multi-image post (like TikTok photo slideshow)
            if isinstance(j2_result, dict) and "medias" in j2_result:
                medias = j2_result["medias"]
                images = [m for m in medias if m.get("type") == "image"]
                
                if len(images) > 1:
                    logger.info(f"📸 Multi-image post detected: {len(images)} images")
                    
                    # Download all images
                    downloaded_files = []
                    for i, image in enumerate(images):
                        ext = image.get("extension", "jpg")
                        filename = f"{uid}_image_{i+1}.{ext}"
                        filepath = os.path.join(DOWNLOAD_DIR, filename)
                        
                        if download_to_server(image["url"], filepath):
                            downloaded_files.append(filename)
                            logger.info(f"✅ Downloaded image {i+1}/{len(images)}: {filename}")
                        else:
                            logger.warning(f"⚠️ Failed to download image {i+1}")
                    
                    if downloaded_files:
                        # Return info about all downloaded files
                        base_url = request.host_url.rstrip("/").replace("http://", "https://")
                        
                        return jsonify({
                            "status": "success",
                            "message": f"Downloaded {len(downloaded_files)} images from photo slideshow",
                            "type": "multi_image",
                            "total_images": len(downloaded_files),
                            "files": [
                                {
                                    "filename": filename,
                                    "download_url": f"{base_url}/files/{filename}",
                                    "type": "image"
                                } for filename in downloaded_files
                            ],
                            "title": j2_result.get("title", "TikTok Photo Post"),
                            "platform": platform
                        })
                    else:
                        logger.warning("⚠️ J2 extraction successful but all image downloads failed. Falling back...")
                else:
                    # Single image - use original logic
                    ext = j2_result.get("ext", "jpg")
                    filename = f"{uid}.{ext}"
                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    
                    if download_to_server(j2_result["url"], filepath):
                        final_filename = filename
                    else:
                        logger.warning("⚠️ J2 link valid, but download failed. Falling back...")
            else:
                # Single media item - use original logic
                ext = j2_result.get("ext", "mp4")
                filename = f"{uid}.{ext}"
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                
                if download_to_server(j2_result["url"], filepath):
                    final_filename = filename
                else:
                    logger.warning("⚠️ J2 link valid, but download failed. Falling back...")
        else:
            logger.warning("⚠️ J2Extractor failed, trying backup methods...")
        
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
            
            # Platform-specific optimizations
            elif platform in ["tiktok", "douyin"]:
                ydl_opts.update({
                    "format": "best[ext=mp4]/best",
                    "extractor_args": {
                        "tiktok": {
                            "api_hostname": "api16-normal-c-useast1a.tiktokv.com"
                        }
                    }
                })
            
            elif platform in ["facebook", "instagram", "threads"]:
                ydl_opts.update({
                    "format": "best[height<=1080]/best"
                })
            
            elif platform in ["twitter", "bluesky"]:
                ydl_opts.update({
                    "format": "best[ext=mp4]/best"
                })
            
            elif platform in ["bilibili", "kuaishou", "weibo"]:
                ydl_opts.update({
                    "format": "best[ext=mp4]/best",
                    "geo_bypass": True
                })
            
            elif platform in ["soundcloud", "mixcloud", "spotify", "deezer"]:
                ydl_opts.update({
                    "format": "bestaudio/best",
                    "extract_flat": False
                })
            
            # Apply cookies based on platform
            if platform in ["youtube", "google"] and os.path.exists(GOOGLE_COOKIES_FILE):
                ydl_opts["cookiefile"] = GOOGLE_COOKIES_FILE
            elif os.path.exists(SOCIAL_COOKIES_FILE):
                ydl_opts["cookiefile"] = SOCIAL_COOKIES_FILE
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    final_filename = os.path.basename(ydl.prepare_filename(info))
            except Exception as e:
                logger.error(f"❌ yt-dlp failed: {e}")
                # No more fallback strategies available
        
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

def find_available_port(start_port=5000, max_port=65535):
    """Find an available port starting from start_port"""
    import socket
    
    for port in range(start_port, max_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                logger.info(f"✅ Found available port: {port}")
                return port
        except OSError:
            continue
    
    logger.error("❌ No available ports found")
    return None

if __name__ == "__main__":
    # Check for environment port first (for deployment platforms like Render, Heroku)
    env_port = os.environ.get("PORT")
    
    if env_port:
        port = int(env_port)
        logger.info(f"🌍 Using environment port: {port}")
    else:
        # Find available port dynamically
        port = find_available_port(5000, 10000)
        if not port:
            logger.error("❌ Could not find available port, using default 5000")
            port = 5000
    
    logger.info(f"🚀 Starting Universal Media Downloader on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)