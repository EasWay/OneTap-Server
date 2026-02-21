import os
import uuid
import logging
import re
import asyncio
import uvloop
import ipaddress
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

# Security: Allowed domains for SSRF prevention
ALLOWED_DOMAINS = [
    'youtube.com', 'youtu.be', 'm.youtube.com', 'youtube-nocookie.com',
    'tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com', 'douyin.com', 'capcut.com',
    'facebook.com', 'fb.watch', 'fb.com', 'm.facebook.com',
    'instagram.com', 'instagr.am', 'ig.me', 'threads.net',
    'twitter.com', 'x.com', 't.co', 'mobile.twitter.com',
    'vimeo.com', 'dailymotion.com', 'bilibili.com', 'b23.tv',
    'rumble.com', 'streamable.com', 'ted.com', 'sohu.com', 'tv.sohu.com', 'bitchute.com',
    'kuaishou.com', 'kwai.com', 'xiaohongshu.com', 'xhslink.com',
    'ixigua.com', 'weibo.com', 'weibo.cn', 'miaopai.com', 'meipai.com',
    'xiaoying.tv', 'yingke.com', 'sina.com', 'qq.com',
    'reddit.com', 'redd.it', 'snapchat.com', 'pinterest.com', 'pin.it',
    'tumblr.com', 'linkedin.com', 'lnkd.in', 'telegram.org', 't.me',
    'bsky.app', 'bluesky.social', 'sharechat.com', 'likee.video', 'like.video',
    'hipi.co.in', 'imdb.com', 'imgur.com', 'ifunny.co', 'izlesene.com',
    'espn.com', '9gag.com', 'ok.ru', 'oke.ru', 'febspot.com', 'getstickerpack.com',
    'soundcloud.com', 'snd.sc', 'mixcloud.com', 'spotify.com', 'spoti.fi',
    'deezer.com', 'zingmp3.vn', 'bandcamp.com', 'castbox.fm', 'mediafire.com',
    'pornbox.com', 'xvideos.com', 'xnxx.com',
    # J2Download domain
    'j2download.com'
]

# Security: Blocked hosts and ports for SSRF prevention
BLOCKED_HOSTS = [
    'localhost', '127.0.0.1', '0.0.0.0', '::1',
    '169.254.169.254',  # AWS metadata
    '169.254.170.2',    # ECS metadata
    'metadata.google.internal',  # GCP metadata
    '100.100.100.200',  # Alibaba Cloud metadata
]

BLOCKED_PORTS = [22, 23, 25, 3306, 5432, 6379, 27017, 11211, 9200]  # SSH, Telnet, SMTP, MySQL, PostgreSQL, Redis, MongoDB, Memcached, Elasticsearch

def validate_url_security(url: str) -> bool:
    """
    Validate URL to prevent SSRF attacks
    Returns True if URL is safe, False otherwise
    """
    try:
        parsed = urlparse(url)
        
        # Check if scheme is allowed
        if parsed.scheme not in ['http', 'https']:
            logger.warning(f"🚫 Blocked URL with invalid scheme: {parsed.scheme}")
            return False
        
        # Check if domain is in allowed list
        hostname = parsed.hostname
        if not hostname:
            logger.warning(f"🚫 Blocked URL with no hostname")
            return False
        
        # Check against allowed domains
        is_allowed = any(
            hostname == domain or hostname.endswith('.' + domain)
            for domain in ALLOWED_DOMAINS
        )
        
        if not is_allowed:
            logger.warning(f"🚫 Blocked URL with unauthorized domain: {hostname}")
            return False
        
        # Check if hostname resolves to blocked IP
        try:
            # Resolve hostname to IP
            import socket
            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            
            # Block private/internal IPs
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                logger.warning(f"🚫 Blocked URL resolving to private IP: {ip}")
                return False
            
            # Block specific IPs
            if ip in BLOCKED_HOSTS:
                logger.warning(f"🚫 Blocked URL resolving to blocked IP: {ip}")
                return False
                
        except socket.gaierror:
            logger.warning(f"🚫 Could not resolve hostname: {hostname}")
            return False
        
        # Check if port is blocked
        port = parsed.port
        if port and port in BLOCKED_PORTS:
            logger.warning(f"🚫 Blocked URL with forbidden port: {port}")
            return False
        
        logger.info(f"✅ URL passed security validation: {hostname}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error validating URL: {e}")
        return False

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
        
        # Clean URL text if needed (extract URL from text)
        url_match = re.search(r'(https?://[^\s]+)', v)
        if url_match:
            extracted_url = url_match.group(1)
            # Don't be too aggressive with cleaning - preserve the full URL
            return extracted_url
        
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        
        return v.strip()

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
    """Removes tracking parameters but preserves essential YouTube parameters"""
    try:
        if "youtube.com" in url or "youtu.be" in url:
            # For YouTube, preserve essential parameters like 'v', 'list', 't'
            from urllib.parse import urlparse, parse_qs, urlencode
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # Keep essential YouTube parameters
            essential_params = {}
            for key in ['v', 'list', 't', 'feature']:
                if key in query_params:
                    essential_params[key] = query_params[key]
            
            if essential_params:
                new_query = urlencode(essential_params, doseq=True)
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
            else:
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        else:
            # For other platforms, remove query params as before
            if "?" in url: 
                return url.split("?")[0]
            return url
    except: 
        return url

async def expand_short_url(url: str) -> str:
    """Resolves short URLs for all supported platforms - ASYNC VERSION with SSRF protection"""
    try:
        # Security: Validate URL before processing
        if not validate_url_security(url):
            logger.warning(f"🚫 URL failed security validation: {url}")
            return url  # Return original if validation fails
        
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
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                try:
                    # Follow redirects manually with validation
                    current_url = url
                    max_redirects = 5
                    redirect_count = 0
                    
                    while redirect_count < max_redirects:
                        resp = await client.head(current_url, headers=headers)
                        
                        if resp.status_code in [301, 302, 303, 307, 308]:
                            redirect_url = resp.headers.get('location')
                            if not redirect_url:
                                break
                            
                            # Security: Validate redirect URL
                            if not validate_url_security(redirect_url):
                                logger.warning(f"🚫 Blocked redirect to unsafe URL: {redirect_url}")
                                return url
                            
                            current_url = redirect_url
                            redirect_count += 1
                        else:
                            break
                    
                    resolved = current_url
                    
                except:
                    # Fallback to GET if HEAD fails
                    resp = await client.get(url, headers=headers, follow_redirects=False)
                    resolved = str(resp.url)
                    
                    # Security: Validate final URL
                    if not validate_url_security(resolved):
                        logger.warning(f"🚫 Resolved URL failed validation: {resolved}")
                        return url
                
                if "login" not in resolved and "error" not in resolved:
                    clean = remove_query_params(resolved)
                    logger.info(f"✅ Resolved to: {clean}")
                    return clean
        else:
            # For non-short URLs, still apply smart query param removal
            clean = remove_query_params(url)
            if clean != url:
                logger.info(f"🧹 Cleaned URL: {url} -> {clean}")
            return clean
    except Exception as e:
        logger.warning(f"⚠️ URL processing failed: {e}")
    
    # Return original URL if processing fails
    return url

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
                            "title": data.get("title") or data.get("author", "") or f"{platform}_post",
                            "medias": medias,  # Include all media items
                            "type": "multi_image"
                        }
                    else:
                        # Single media item - better title fallback
                        title = (
                            data.get("title") or 
                            data.get("author", "") or 
                            f"{platform}_{data.get('id', '')}" or
                            f"{platform}_video"
                        )
                        
                        return {
                            "url": best_media.get("url"),
                            "ext": best_media.get("extension", "mp4"),
                            "title": title
                        }
                else:
                    logger.warning("⚠️ J2Download: No suitable media found in response")
                    return None
                
        except Exception as e:
            logger.error(f"❌ J2 Failed: {e}")
            return None

@get("/version")
async def get_version() -> Dict[str, Any]:
    """Version endpoint for system updates"""
    return {
        "version": "1.6",
        "latest_version": 6,  # Version code for comparison
        "apk_url": "https://github.com/EasWay/OneTap-Releases/releases/download/v1.6/app-release.apk",
        "release_notes": "🚀 OneTap v1.6 - Simplified & Optimized\n\n✨ New Features:\n• Unified J2Download extraction for all platforms\n• Fixed YouTube URL truncation issues\n• Improved URL processing and validation\n• Enhanced stream proxy for all platforms\n\n🔧 Performance Improvements:\n• Simplified extraction strategy (removed complexity)\n• Better YouTube parameter preservation\n• Smarter URL cleaning that preserves essential data\n• Optimized for reliability over speed\n\n🐛 Bug Fixes:\n• Fixed YouTube regular video URLs being truncated\n• Improved URL expansion and cleaning logic\n• Better error handling for malformed URLs\n• Enhanced compatibility with all YouTube URL formats",
        "status": "online",
        "service": "Universal Media Downloader - ASYNC EDITION",
        "framework": "Litestar (ASGI)",
        "performance": "High-Concurrency Async",
        "total_platforms": 50,
        "features": [
            "Lightning-fast async processing with uvloop",
            "Unified J2Download extraction for all platforms",
            "Smart URL processing that preserves essential parameters",
            "Stream proxy for reliable downloads",
            "Handle thousands of concurrent downloads",
            "Download videos without watermarks (TikTok, etc.)",
            "Support for images, videos, and audio",
            "Multiple format support (.mp4, .mp3, .jpg, .png)",
            "Works on all devices (PC, Mac, Android, iOS)",
            "Photo slideshow downloads via stream proxy",
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
        "version": "1.5",
        "latest_version": 5,  # Version code for comparison
        "apk_url": "https://github.com/EasWay/OneTap-Releases/releases/download/v1.5/app-release.apk",
        "release_notes": "🚀 OneTap v1.5 Update\n\n✨ New Features:\n• Enhanced video download stability\n• Support for 50+ social media platforms",
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
            "youtube": "RapidAPI Direct (Ultra-Fast)",
            "social_media": "J2Download API (50+ sites)",
            "fallback": "Cross-platform compatibility",
            "architecture": "Optimized async stack with uvloop"
        },
        "endpoints": {
            "download": "/download (POST)",
            "files": "/files/<filename> (GET)",
            "version": "/version (GET)"
        }
    }

from litestar.datastructures import State
from threading import Lock

# Security: Thread-safe global streams storage with lock
streams_storage: Dict[str, Dict[str, Any]] = {}
storage_lock = Lock()

@post("/download")
async def download_video(data: DownloadRequest, state: State) -> DownloadResponse:
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
        
        # --- SIMPLIFIED EXTRACTION STRATEGY ---
        # All platforms: J2Download (works for all social media + YouTube)
        
        extraction_result = None
        
        logger.info(f"🎯 {platform} detected - using J2Download")
        j2 = AsyncJ2Extractor()
        extraction_result = await j2.extract_download_url(url)
        
        if not extraction_result:
            raise HTTPException(status_code=400, detail="All extraction methods failed")
        
        logger.info("✅ Extraction successful. Setting up stream proxy...")
        
        # Check if it's a multi-image post (like TikTok photo slideshow)
        if isinstance(extraction_result, dict) and "medias" in extraction_result:
            medias = extraction_result["medias"]
            images = [m for m in medias if m.get("type") == "image"]
            
            if len(images) > 1:
                logger.info(f"📸 Multi-image post detected: {len(images)} images")
                
                # For multi-image, create stream URLs for each image
                files = []
                for i, image in enumerate(images):
                    ext = image.get("extension", "jpg")
                    image_stream_id = f"{uid}_image_{i+1}"
                    
                    # Store each image stream in global storage
                    streams_storage[image_stream_id] = {
                        "url": image["url"],
                        "ext": ext,
                        "title": f"image_{i+1}",
                        "platform": platform,
                        "source": extraction_result.get("source", "j2")
                    }
                    
                    files.append({
                        "filename": f"image_{i+1}.{ext}",
                        "download_url": f"/stream/{image_stream_id}",
                        "type": "image"
                    })
                
                return DownloadResponse(
                    status="success",
                    message=f"Ready to download {len(files)} images from photo slideshow",
                    type="multi_image",
                    total_images=len(files),
                    files=files,
                    title=extraction_result.get("title", "Photo Post"),
                    platform=platform
                )
        
        # For single video/audio files
        ext = extraction_result.get("ext", "mp4")
        source = extraction_result.get("source", "j2")
        title = extraction_result.get("title", "video")
        
        # All platforms: Use stream proxy approach (including YouTube)
        # This prevents 403 errors by proxying the request through the server
        
        # Store the direct URL and metadata for streaming
        stream_id = uid
        stream_data = {
            "url": extraction_result["url"],
            "ext": ext,
            "title": title,
            "platform": platform,
            "source": source
        }
        
        # Security: Thread-safe storage access
        with storage_lock:
            streams_storage[stream_id] = stream_data
        
        logger.info(f"✅ {platform}: Stream proxy ready for {stream_id} (via {source})")
        
        return DownloadResponse(
            status="success",
            download_url=f"/stream/{stream_id}",
            filename=f"{title}.{ext}",
            message="Stream proxy ready",
            title=title,
            platform=platform
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Final Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@get("/files/{filename:str}")
async def serve_file(filename: str) -> File:
    """Serve downloaded files with path traversal protection"""
    from pathlib import Path
    
    # Security: Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name  # Removes any path components
    
    # Remove any remaining dangerous characters
    safe_filename = re.sub(r'[^\w\s\-_.]', '', safe_filename)
    
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join(DOWNLOAD_DIR, safe_filename)
    
    # Security: Verify the resolved path is within DOWNLOAD_DIR
    abs_file_path = os.path.abspath(file_path)
    abs_download_dir = os.path.abspath(DOWNLOAD_DIR)
    
    if not abs_file_path.startswith(abs_download_dir):
        logger.warning(f"🚫 Path traversal attempt blocked: {filename}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return File(file_path, filename=safe_filename)

@get("/stream/{stream_id:str}")
async def stream_proxy(stream_id: str, state: State) -> Stream:
    """
    Stream Proxy Endpoint - The Cobalt Way
    
    This endpoint acts as a tunnel between the client and the video source.
    The client never talks directly to YouTube/TikTok - only to this server.
    This prevents 403 errors caused by signature validation failures.
    """
    from litestar.types import Receive, Scope, Send
    from litestar.response import Response
    
    try:
        # Get stream data from global storage
        if stream_id not in streams_storage:
            logger.error(f"❌ Stream {stream_id} not found in {list(streams_storage.keys())}")
            raise HTTPException(status_code=404, detail="Stream not found")
        
        stream_data = streams_storage[stream_id]
        video_url = stream_data["url"]
        ext = stream_data["ext"]
        title = stream_data["title"]
        platform = stream_data["platform"]
        source = stream_data.get("source", "j2")
        
        logger.info(f"🌊 Starting stream proxy for {platform}: {stream_id} (via {source})")
        logger.info(f"📺 Video URL: {video_url[:100]}...")
        
        # Determine headers based on source
        if source == "rapidapi":
            request_headers = {
                "User-Agent": "OneTap-Server/4.0.0",
                "Accept": "*/*",
                "Connection": "keep-alive"
            }
        elif platform == "youtube":
            request_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Referer": "https://www.youtube.com/",
                "Connection": "keep-alive"
            }
        else:
            request_headers = {
                "User-Agent": EXACT_UA,
                "Accept": "*/*",
                "Connection": "keep-alive"
            }
        
        # Create HTTP client
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=15.0),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
        
        # Start the GET request to get headers including Content-Length
        logger.info(f"🚀 Initiating stream from {source}...")
        response = await client.get(video_url, headers=request_headers)
        
        logger.info(f"� Response status: {response.status_code}")
        
        if response.status_code not in [200, 206]:
            await client.aclose()
            error_msg = f"HTTP {response.status_code}: {response.reason_phrase}"
            logger.error(f"❌ {error_msg}")
            raise HTTPException(status_code=response.status_code, detail=error_msg)
        
        # Extract Content-Length from response
        content_length = response.headers.get("content-length")
        if content_length:
            logger.info(f"📏 Content-Length: {content_length} bytes ({int(content_length)/1024/1024:.2f} MB)")
        else:
            logger.warning(f"⚠️ No Content-Length header from source")
        
        async def stream_generator():
            """Generator that streams video data chunk by chunk"""
            try:
                logger.info(f"✅ Streaming content...")
                
                # Stream the response we already started
                total_bytes = 0
                async for chunk in response.aiter_bytes(chunk_size=65536):  # 64KB chunks
                    if chunk:
                        total_bytes += len(chunk)
                        yield chunk
                
                logger.info(f"✅ Stream complete: {total_bytes:,} bytes")
                
            except Exception as e:
                logger.error(f"❌ Stream generator error: {e}")
                raise
            finally:
                # Clean up
                await client.aclose()
                if stream_id in streams_storage:
                    del streams_storage[stream_id]
        
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
        
        # Create safe filename - handle Unicode and special characters properly
        safe_title = re.sub(r'\s+', ' ', title)
        safe_title = safe_title.encode('ascii', 'ignore').decode('ascii')
        safe_title = re.sub(r'[^\w\s-]', '', safe_title).strip()[:50]
        if not safe_title:
            safe_title = f"media_{stream_id[:8]}"
        
        filename = f"{safe_title}.{ext}"
        
        # URL encode the filename
        from urllib.parse import quote
        encoded_filename = quote(filename)
        
        logger.info(f"🎬 Returning stream response: {filename} ({content_type})")
        
        # Build response headers
        response_headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "no-cache"
        }
        
        # Add Content-Length if available
        if content_length:
            response_headers["Content-Length"] = content_length
            logger.info(f"✅ Including Content-Length: {content_length} bytes")
        
        return Stream(
            stream_generator(),
            media_type=content_type,
            headers=response_headers
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