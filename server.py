import os
import uuid
import logging
import re
import asyncio
import uvloop
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

# Modern Async Stack
from litestar import Litestar, get, post
from litestar.response import File, Stream
from litestar.exceptions import HTTPException
from pydantic import BaseModel, field_validator
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set uvloop as the event loop policy for maximum performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# --- CONFIGURATION ---
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Exact UA for consistency
EXACT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

# --- J2 WRAPPER CONFIG ---
J2_BASE_URL = "https://j2download.com"
J2_API_URL = f"{J2_BASE_URL}/api/autolink"
J2_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"

# --- PYDANTIC MODELS ---
class DownloadRequest(BaseModel):
    url: str
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v or not v.strip():
            raise ValueError('URL cannot be empty')
        # Clean URL text if needed
        match = re.search(r'(https?://[^\s]+)', v)
        if match:
            return match.group(1)
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class DownloadResponse(BaseModel):
    status: str
    download_url: Optional[str] = None
    filename: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    total_images: Optional[int] = None
    files: Optional[List[Dict[str, Any]]] = None
    title: Optional[str] = None
    platform: Optional[str] = None

def remove_query_params(url: str) -> str:
    """Removes tracking parameters"""
    try:
        if "?" in url: 
            return url.split("?")[0]
        return url
    except: 
        return url

async def expand_short_url(url: str) -> str:
    """Resolves short URLs for all supported platforms - ASYNC VERSION"""
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
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    resp = await client.head(url, headers=headers, follow_redirects=True)
                    if resp.status_code >= 400:
                        raise Exception("Head failed")
                except:
                    resp = await client.get(url, headers=headers, follow_redirects=True)
                
                resolved = str(resp.url)
                if "login" not in resolved and "error" not in resolved:
                    clean = remove_query_params(resolved)
                    logger.info(f"✅ Resolved to: {clean}")
                    return clean
    except Exception as e:
        logger.warning(f"⚠️ URL Expansion failed: {e}")
    return remove_query_params(url)

def clean_url_text(text: str) -> str:
    match = re.search(r'(https?://[^\s]+)', text)
    if match: 
        return match.group(1)
    return text

def detect_platform(url: str) -> str:
    """Enhanced platform detection for 50+ supported platforms"""
    domain = urlparse(url).netloc.lower()
    
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
    
    # Adult Content
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

class AsyncJ2Extractor:
    async def extract_download_url(self, video_url: str) -> Optional[Dict[str, Any]]:
        try:
            platform = detect_platform(video_url)
            logger.info(f"🎯 J2 Extraction for {platform}: {video_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                
                # Handshake with navigation headers
                logger.info("🤝 Performing J2Download handshake...")
                home_resp = await client.get(J2_BASE_URL, headers=nav_headers)
                
                if home_resp.status_code != 200:
                    logger.warning(f"⚠️ Handshake returned status {home_resp.status_code}")
                    return None
                
                # Deep Token Extraction - Priority 1: Cookies
                csrf_token = home_resp.cookies.get("csrf_token")
                
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
                    "User-Agent": J2_UA,
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
                
                payload = {
                    "data": {
                        "url": video_url,
                        "unlock": True
                    }
                }
                
                logger.info(f"🚀 Sending J2Download API request...")
                logger.info(f"📤 Payload: {payload}")
                
                response = await client.post(J2_API_URL, json=payload, headers=xhr_headers, cookies=home_resp.cookies)
                
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

async def download_to_server_with_retry(url: str, filename: str, max_retries: int = 3) -> bool:
    """Single attempt download - googlevideo URLs are single-use, retries poison the URL"""
    return await download_to_server(url, filename)

async def download_to_server(url: str, filename: str) -> bool:
    """Downloads file from URL - YouTube single-node strategy to avoid multi-redirect 403"""
    try:
        # Exact YouTube Android app headers - full client emulation
        headers = {
            "User-Agent": "com.google.android.youtube/19.02.39 (Linux; U; Android 13; SM-G998B) gzip",
            "Accept": "*/*",
            "Referer": "https://www.youtube.com/",
            "Origin": "https://www.youtube.com",
            "Range": "bytes=0-",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "video",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site"
        }
        
        # Disable automatic redirects - handle manually to avoid multi-node 403
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=15.0),
            follow_redirects=False,  # KEY CHANGE: Manual redirect handling
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            
            logger.info(f"🚀 YouTube single-node download (no auto-redirects)")
            
            # First request - check for redirects
            response = await client.get(url, headers=headers)
            
            # Handle redirects manually - max 3 hops to avoid poisoning
            redirect_count = 0
            max_redirects = 3
            
            while response.status_code in [301, 302, 303, 307, 308] and redirect_count < max_redirects:
                redirect_url = response.headers.get('location')
                if not redirect_url:
                    logger.error("❌ Redirect without Location header")
                    return False
                
                redirect_count += 1
                logger.info(f"🔄 Manual redirect {redirect_count}/{max_redirects}: {redirect_url[:50]}...")
                
                # Fresh client for each redirect to avoid fingerprint tracking
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(120.0, connect=15.0),
                    follow_redirects=False,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
                ) as redirect_client:
                    response = await redirect_client.get(redirect_url, headers=headers)
            
            # Check final response
            if response.status_code not in [200, 206]:
                logger.error(f"❌ HTTP {response.status_code}: {response.reason_phrase}")
                return False
            
            # Stream download from final URL
            logger.info(f"📦 Starting stream download")
            
            downloaded = 0
            with open(filename, 'wb') as f:
                async for chunk in response.aiter_bytes(chunk_size=16384):
                    f.write(chunk)
                    downloaded += len(chunk)
            
            logger.info(f"✅ Downloaded: {downloaded:,} bytes")
            return True
                
    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        return False

@get("/version")
async def get_version() -> Dict[str, Any]:
    """Version endpoint for system updates"""
    return {
        "version": "4.0.0",
        "latest_version": 400,  # Version code for comparison
        "apk_url": "https://github.com/YourUsername/OneTap/releases/download/v4.0.0/OneTap_v4.0.0.apk",
        "release_notes": "🚀 Major Update v4.0.0\n\n✨ New Features:\n• Lightning-fast async processing\n• Support for 50+ platforms\n• Enhanced TikTok photo slideshow downloads\n• Improved error handling and retry logic\n\n🔧 Improvements:\n• Better network stability\n• Faster download speeds\n• Reduced memory usage\n• Enhanced UI responsiveness\n\n🐛 Bug Fixes:\n• Fixed duplicate detection issues\n• Resolved timeout problems on slow networks\n• Fixed crashes on certain device configurations",
        "status": "online",
        "service": "Universal Media Downloader - ASYNC EDITION",
        "framework": "Litestar (ASGI)",
        "performance": "High-Concurrency Async",
        "total_platforms": 50,
        "features": [
            "Lightning-fast async processing",
            "Handle thousands of concurrent downloads",
            "Download videos without watermarks (TikTok, etc.)",
            "Support for images, videos, and audio",
            "Multiple format support (.mp4, .mp3, .jpg, .png)",
            "Works on all devices (PC, Mac, Android, iOS)",
            "Photo slideshow downloads in MP4 format",
            "Free service with no registration required"
        ],
        "supported_platforms": {
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
    }

@get("/")
async def index() -> Dict[str, Any]:
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
    
    return {
        "status": "online",
        "service": "Universal Media Downloader - ASYNC EDITION",
        "version": "4.0.0",
        "latest_version": 400,  # Version code for comparison
        "apk_url": "https://github.com/YourUsername/OneTap/releases/download/v4.0.0/OneTap_v4.0.0.apk",
        "release_notes": "🚀 Major Update v4.0.0\n\n✨ New Features:\n• Lightning-fast async processing\n• Support for 50+ platforms\n• Enhanced TikTok photo slideshow downloads\n• Improved error handling and retry logic\n\n🔧 Improvements:\n• Better network stability\n• Faster download speeds\n• Reduced memory usage\n• Enhanced UI responsiveness\n\n🐛 Bug Fixes:\n• Fixed duplicate detection issues\n• Resolved timeout problems on slow networks\n• Fixed crashes on certain device configurations",
        "framework": "Litestar (ASGI)",
        "performance": "High-Concurrency Async",
        "supported_platforms": supported_platforms,
        "total_platforms": sum(len(platforms) for platforms in supported_platforms.values()),
        "features": [
            "Lightning-fast async processing",
            "Handle thousands of concurrent downloads",
            "Download videos without watermarks (TikTok, etc.)",
            "Support for images, videos, and audio",
            "Multiple format support (.mp4, .mp3, .jpg, .png)",
            "Works on all devices (PC, Mac, Android, iOS)",
            "Photo slideshow downloads in MP4 format",
            "Free service with no registration required"
        ],
        "extraction_methods": {
            "primary": "J2Download API (Fast, 50+ sites) - ASYNC",
            "architecture": "Modern async stack with uvloop"
        },
        "endpoints": {
            "download": "/download (POST)",
            "files": "/files/<filename> (GET)",
            "version": "/version (GET)"
        }
    }

@post("/download")
async def download_video(data: DownloadRequest) -> DownloadResponse:
    """
    ASYNC High-Performance Download Endpoint with Stream Proxy
    - Uses Pydantic for automatic validation
    - HTTPX for non-blocking HTTP requests
    - Implements stream proxy to avoid 403 errors
    """
    logger.info("🚀 Async download request received")
    
    try:
        uid = str(uuid.uuid4())
        
        # 1. Clean & Expand URL (ASYNC)
        url = await expand_short_url(data.url)
        domain = urlparse(url).netloc.lower()
        platform = detect_platform(url)
        
        logger.info(f"✅ Processing [{platform}]: {url}")
        
        # --- J2 API EXTRACTION (ASYNC) ---
        j2 = AsyncJ2Extractor()
        j2_result = await j2.extract_download_url(url)
        
        if not j2_result:
            raise HTTPException(status_code=400, detail="J2Download extraction failed")
        
        logger.info("✅ J2 Success. Setting up stream proxy...")
        
        # Check if it's a multi-image post (like TikTok photo slideshow)
        if isinstance(j2_result, dict) and "medias" in j2_result:
            medias = j2_result["medias"]
            images = [m for m in medias if m.get("type") == "image"]
            
            if len(images) > 1:
                logger.info(f"📸 Multi-image post detected: {len(images)} images")
                
                # For multi-image, we still download to server since they're usually small
                download_tasks = []
                filenames = []
                
                for i, image in enumerate(images):
                    ext = image.get("extension", "jpg")
                    filename = f"{uid}_image_{i+1}.{ext}"
                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    filenames.append(filename)
                    
                    # Create async download task with retry
                    download_tasks.append(download_to_server_with_retry(image["url"], filepath))
                
                # Execute all downloads concurrently
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
                
                # Check results
                downloaded_files = []
                for i, (result, filename) in enumerate(zip(results, filenames)):
                    if result is True:
                        downloaded_files.append(filename)
                        logger.info(f"✅ Downloaded image {i+1}/{len(images)}: {filename}")
                    else:
                        logger.warning(f"⚠️ Failed to download image {i+1}: {result}")
                
                if downloaded_files:
                    return DownloadResponse(
                        status="success",
                        message=f"Downloaded {len(downloaded_files)} images from photo slideshow",
                        type="multi_image",
                        total_images=len(downloaded_files),
                        files=[
                            {
                                "filename": filename,
                                "download_url": f"/files/{filename}",
                                "type": "image"
                            } for filename in downloaded_files
                        ],
                        title=j2_result.get("title", "TikTok Photo Post"),
                        platform=platform
                    )
                else:
                    raise HTTPException(status_code=500, detail="All image downloads failed")
        
        # For single video/audio files, use stream proxy approach
        ext = j2_result.get("ext", "mp4")
        
        # Store the direct URL and metadata for streaming
        stream_id = uid
        stream_data = {
            "url": j2_result["url"],
            "ext": ext,
            "title": j2_result.get("title", "video"),
            "platform": platform
        }
        
        # Store stream data in memory (in production, use Redis or database)
        if not hasattr(app.state, 'streams'):
            app.state.streams = {}
        app.state.streams[stream_id] = stream_data
        
        logger.info(f"✅ Stream proxy ready for {stream_id}")
        logger.info(f"🔗 Stream URL will be: /stream/{stream_id}")
        
        return DownloadResponse(
            status="success",
            download_url=f"/stream/{stream_id}",
            filename=f"{j2_result.get('title', 'video')}.{ext}",
            message="Stream proxy ready"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Final Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@get("/files/{filename:str}")
async def serve_file(filename: str) -> File:
    """Serve downloaded files"""
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return File(file_path, filename=filename)

@get("/stream/{stream_id:str}")
async def stream_proxy(stream_id: str) -> Stream:
    """
    Stream Proxy Endpoint - The Cobalt Way
    
    This endpoint acts as a tunnel between the client and the video source.
    The client never talks directly to YouTube/TikTok - only to this server.
    This prevents 403 errors caused by signature validation failures.
    """
    from litestar.types import Receive, Scope, Send
    
    try:
        # Get stream data
        if not hasattr(app.state, 'streams'):
            logger.error(f"❌ App state has no streams attribute")
            raise HTTPException(status_code=500, detail="Server state not initialized")
            
        if stream_id not in app.state.streams:
            logger.error(f"❌ Stream {stream_id} not found in {list(app.state.streams.keys())}")
            raise HTTPException(status_code=404, detail="Stream not found")
        
        stream_data = app.state.streams[stream_id]
        video_url = stream_data["url"]
        ext = stream_data["ext"]
        title = stream_data["title"]
        platform = stream_data["platform"]
        
        logger.info(f"🌊 Starting stream proxy for {platform}: {stream_id}")
        logger.info(f"📺 Video URL: {video_url[:100]}...")
        
        async def stream_generator():
            """Generator that streams video data chunk by chunk"""
            try:
                # Use appropriate headers based on platform
                if platform == "youtube":
                    headers = {
                        "User-Agent": "com.google.android.youtube/19.02.39 (Linux; U; Android 13; SM-G998B) gzip",
                        "Accept": "*/*",
                        "Referer": "https://www.youtube.com/",
                        "Origin": "https://www.youtube.com",
                        "Range": "bytes=0-",
                        "Connection": "keep-alive",
                        "Sec-Fetch-Dest": "video",
                        "Sec-Fetch-Mode": "no-cors",
                        "Sec-Fetch-Site": "cross-site"
                    }
                else:
                    # Generic headers for other platforms
                    headers = {
                        "User-Agent": EXACT_UA,
                        "Accept": "*/*",
                        "Referer": video_url.split('/')[0] + '//' + video_url.split('/')[2] + '/',
                        "Connection": "keep-alive"
                    }
                
                # Create HTTP client with no redirects (handle manually for YouTube)
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(120.0, connect=15.0),
                    follow_redirects=False if platform == "youtube" else True,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
                ) as client:
                    
                    logger.info(f"🚀 Connecting to {platform} source...")
                    
                    # Handle YouTube redirects manually
                    if platform == "youtube":
                        response = await client.get(video_url, headers=headers)
                        
                        # Handle redirects manually for YouTube
                        redirect_count = 0
                        max_redirects = 3
                        
                        while response.status_code in [301, 302, 303, 307, 308] and redirect_count < max_redirects:
                            redirect_url = response.headers.get('location')
                            if not redirect_url:
                                logger.error("❌ Redirect without Location header")
                                return
                            
                            redirect_count += 1
                            logger.info(f"🔄 Manual redirect {redirect_count}/{max_redirects}")
                            
                            # Fresh request for redirect
                            response = await client.get(redirect_url, headers=headers)
                        
                        if response.status_code not in [200, 206]:
                            logger.error(f"❌ HTTP {response.status_code}: {response.reason_phrase}")
                            return
                    else:
                        # Direct request for other platforms
                        response = await client.get(video_url, headers=headers)
                        
                        if response.status_code not in [200, 206]:
                            logger.error(f"❌ HTTP {response.status_code}: {response.reason_phrase}")
                            return
                    
                    logger.info(f"✅ Connected! Streaming {platform} content...")
                    
                    # Stream the content chunk by chunk
                    total_bytes = 0
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        if chunk:
                            total_bytes += len(chunk)
                            yield chunk
                    
                    logger.info(f"✅ Stream complete: {total_bytes:,} bytes streamed")
                    
                    # Clean up stream data after successful completion
                    if hasattr(app.state, 'streams') and stream_id in app.state.streams:
                        del app.state.streams[stream_id]
                        
            except Exception as e:
                logger.error(f"❌ Stream generator error: {e}")
                logger.error(f"❌ Error type: {type(e).__name__}")
                import traceback
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                # Clean up on error
                if hasattr(app.state, 'streams') and stream_id in app.state.streams:
                    del app.state.streams[stream_id]
                return
        
        # Determine content type based on extension
        content_type_map = {
            "mp4": "video/mp4",
            "mp3": "audio/mpeg",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webm": "video/webm",
            "m4a": "audio/mp4"
        }
        content_type = content_type_map.get(ext.lower(), "application/octet-stream")
        
        # Create safe filename
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()[:50]
        filename = f"{safe_title}.{ext}" if safe_title else f"video.{ext}"
        
        logger.info(f"🎬 Returning stream response: {filename} ({content_type})")
        
        return Stream(
            iterator=stream_generator(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Stream proxy error: {e}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Stream proxy error: {str(e)}")

# Create Litestar app
app = Litestar(
    route_handlers=[index, get_version, download_video, serve_file, stream_proxy]
)

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting ASYNC Universal Media Downloader on port {port}")
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0", 
        port=port,
        loop="uvloop"
    )