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
    csrf_token: Optional[str] = None
    cookie_string: Optional[str] = None
    user_agent: Optional[str] = None
    
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
    size: Optional[int] = None

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
    if "sohu.com" in domain or "tv.sohu.com" in domain: return "sobutv"
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
        """TikTok/Douyin/Capcut - prioritize no watermark HD; prefer tiktokcdn.com over api.tiktokv.com.

        api.tiktokv.com URLs require a session-bound tt_chain_token cookie which is unavailable
        on the proxy server. tiktokcdn.com URLs work without that cookie."""
        video_medias = [m for m in medias if m.get("type") == "video"]
        if not video_medias:
            return medias[0]

        quality_rank = {"hd_no_watermark": 0, "no_watermark": 1}

        def sort_key(m):
            url = m.get("url", "")
            # Prefer CDN URLs that don't require the tt_chain_token cookie
            is_api = 1 if "api.tiktokv.com" in url else 0
            quality = quality_rank.get(m.get("quality", ""), 2)
            return (is_api, quality)

        video_medias.sort(key=sort_key)
        return video_medias[0]

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
    async def extract_download_url(
        self, 
        video_url: str, 
        provided_token: Optional[str] = None,
        provided_cookies: Optional[str] = None,
        provided_ua: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
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
                
                # Handshake logic (only if token not provided)
                csrf_token = provided_token
                cookies_to_use = {}
                
                if provided_cookies:
                    # Parse simplified cookie string: "name1=value1; name2=value2"
                    for cookie in provided_cookies.split(';'):
                        if '=' in cookie:
                            name, value = cookie.strip().split('=', 1)
                            cookies_to_use[name] = value
                    logger.info("✅ Using client-provided session cookies")

                if not csrf_token:
                    logger.info("🤝 Performing J2Download handshake...")
                    home_resp = await client.get(J2_BASE_URL, headers=nav_headers)
                    
                    if home_resp.status_code != 200:
                        logger.warning(f"⚠️ Handshake returned status {home_resp.status_code}")
                        return None
                    
                    cookies_to_use = home_resp.cookies
                    
                    # Deep Token Extraction - Priority 1: Cookies
                    csrf_token = home_resp.cookies.get("csrf_token")
                    if csrf_token:
                        logger.info("✅ Found CSRF token in Cookies")
                else:
                    logger.info("✅ Using client-provided CSRF token")
                
                # Priority 2: HTML Meta Tags (only if handshake was performed)
                if not csrf_token and 'home_resp' in locals():
                    logger.info("🔍 Searching HTML for CSRF token...")
                    meta_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', home_resp.text)
                    if meta_match:
                        csrf_token = meta_match.group(1)
                        logger.info("✅ Found CSRF token in Meta Tag")
                
                # Priority 3: JavaScript variables (only if handshake was performed)
                if not csrf_token and 'home_resp' in locals():
                    js_match = re.search(r'csrf[_-]token["\s]*[:=]["\s]*([a-zA-Z0-9_\-]+)', home_resp.text)
                    if js_match:
                        csrf_token = js_match.group(1)
                        logger.info("✅ Found CSRF token in JS")
                
                if not csrf_token:
                    logger.warning("⚠️ No CSRF token found!")
                    return None
                
                # Step 2: Build API request headers (simulate XHR from j2download.com)
                api_headers = {
                    "User-Agent": provided_ua or J2_UA,
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": J2_BASE_URL,
                    "Referer": J2_BASE_URL + "/",
                    "Sec-Ch-Ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                    "X-Csrf-Token": csrf_token,
                    "X-Requested-With": "XMLHttpRequest"
                }
                
                # Step 3: POST to J2Download API
                form_data = {"url": video_url, "lang": "en"}
                logger.info(f"📡 Posting to J2 API for: {video_url}")
                
                api_resp = await client.post(
                    J2_API_URL,
                    headers=api_headers,
                    cookies=cookies_to_use,
                    data=form_data
                )
                
                logger.info(f"📨 J2 API Response status: {api_resp.status_code}")
                
                if api_resp.status_code != 200:
                    logger.warning(f"⚠️ J2 API failed with status {api_resp.status_code}")
                    return None
                
                data = api_resp.json()
                
                if data.get("status") != "success":
                    logger.warning(f"⚠️ J2 extraction failed: {data.get('mess', 'Unknown error')}")
                    return None
                
                # Parse response based on platform
                selected = J2ResponseParser.parse(data, platform)
                
                if selected:
                    logger.info(f"✅ Selected format: {selected.get('quality', 'N/A')} - {selected.get('extension', 'N/A')}")
                
                return selected
                
        except Exception as e:
            logger.error(f"❌ J2 extraction error: {e}")
            return None


# --- INSTAGRAM MULTI-IMAGE HANDLER ---
async def handle_instagram_carousel(video_url: str, extractor: AsyncJ2Extractor) -> Optional[Dict]:
    """Handle Instagram carousel posts with multiple images"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            nav_headers = {"User-Agent": J2_UA}
            home_resp = await client.get(J2_BASE_URL, headers=nav_headers)
            
            if home_resp.status_code != 200:
                return None
            
            cookies_to_use = home_resp.cookies
            csrf_token = home_resp.cookies.get("csrf_token")
            
            if not csrf_token:
                meta_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', home_resp.text)
                if meta_match:
                    csrf_token = meta_match.group(1)
            
            if not csrf_token:
                return None
            
            api_headers = {
                "User-Agent": J2_UA,
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": J2_BASE_URL,
                "Referer": J2_BASE_URL + "/",
                "X-Csrf-Token": csrf_token,
                "X-Requested-With": "XMLHttpRequest"
            }
            
            form_data = {"url": video_url, "lang": "en"}
            api_resp = await client.post(J2_API_URL, headers=api_headers, cookies=cookies_to_use, data=form_data)
            
            if api_resp.status_code != 200:
                return None
            
            data = api_resp.json()
            
            if data.get("status") != "success":
                return None
            
            medias = data.get("medias", [])
            
            # Check if carousel (multiple items with type image/video)
            images = [m for m in medias if m.get("type") == "image"]
            videos = [m for m in medias if m.get("type") == "video"]
            
            if len(images) > 1:
                return {
                    "type": "carousel",
                    "images": images,
                    "videos": videos,
                    "title": data.get("title", "Instagram Carousel")
                }
            
            return None
    except Exception as e:
        logger.error(f"❌ Instagram carousel error: {e}")
        return None


# --- GLOBAL EXTRACTOR ---
extractor = AsyncJ2Extractor()

# --- API ENDPOINTS ---

@post("/api/extract")
async def extract_url(data: DownloadRequest) -> DownloadResponse:
    """Main extraction endpoint - supports 50+ platforms"""
    try:
        url = await expand_short_url(data.url)
        platform = detect_platform(url)
        
        logger.info(f"🎬 Extract request for {platform}: {url}")
        
        # Instagram carousel check
        if platform == "instagram":
            carousel_data = await handle_instagram_carousel(url, extractor)
            if carousel_data and carousel_data.get("type") == "carousel":
                images = carousel_data.get("images", [])
                videos = carousel_data.get("videos", [])
                all_files = []
                
                for i, img in enumerate(images):
                    all_files.append({
                        "type": "image",
                        "url": img.get("url"),
                        "filename": f"image_{i+1}.jpg",
                        "quality": img.get("quality", "original")
                    })
                
                for i, vid in enumerate(videos):
                    all_files.append({
                        "type": "video",
                        "url": vid.get("url"),
                        "filename": f"video_{i+1}.mp4",
                        "quality": vid.get("quality", "hd")
                    })
                
                return DownloadResponse(
                    status="success",
                    type="carousel",
                    total_images=len(images),
                    files=all_files,
                    title=carousel_data.get("title"),
                    platform=platform,
                    message=f"Found {len(images)} images and {len(videos)} videos"
                )
        
        # Standard extraction
        result = await extractor.extract_download_url(
            url,
            provided_token=data.csrf_token,
            provided_cookies=data.cookie_string,
            provided_ua=data.user_agent
        )
        
        if not result:
            raise HTTPException(status_code=422, detail="Could not extract download URL")
        
        download_url = result.get("url")
        if not download_url:
            raise HTTPException(status_code=422, detail="No download URL in response")
        
        extension = result.get("extension", "mp4")
        filename = f"{uuid.uuid4()}.{extension}"
        
        return DownloadResponse(
            status="success",
            download_url=download_url,
            filename=filename,
            type=result.get("type", "video"),
            platform=platform,
            size=result.get("size")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Extract error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@get("/api/stream")
async def stream_video(url: str, referer: Optional[str] = None) -> Stream:
    """Stream/proxy a video URL with proper headers.
    
    For TikTok URLs (tiktokcdn.com / api.tiktokv.com), a Referer of
    https://www.tiktok.com/ is injected automatically so the CDN accepts
    the request without a session cookie.
    """
    try:
        if not url or not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid URL")
        
        # Build headers for proxied request
        proxy_headers = {
            "User-Agent": EXACT_UA,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }

        # Inject Referer for TikTok CDN URLs
        if "tiktokcdn.com" in url or "tiktokv.com" in url:
            proxy_headers["Referer"] = "https://www.tiktok.com/"
        elif referer:
            proxy_headers["Referer"] = referer

        client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        
        req = client.build_request("GET", url, headers=proxy_headers)
        response = await client.send(req, stream=True)
        
        if response.status_code == 403 and "tiktokv.com" in url:
            # Fallback: swap api.tiktokv.com for tiktokcdn.com CDN domain
            fallback_url = url.replace("api.tiktokv.com", "v19-webapp.tiktok.com")
            logger.info(f"🔄 TikTok 403 – retrying with fallback URL: {fallback_url}")
            await response.aclose()
            req2 = client.build_request("GET", fallback_url, headers=proxy_headers)
            response = await client.send(req2, stream=True)

        if response.status_code not in (200, 206):
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch video")
        
        content_type = response.headers.get("content-type", "video/mp4")
        content_length = response.headers.get("content-length")
        
        headers = {"Content-Type": content_type}
        if content_length:
            headers["Content-Length"] = content_length
        
        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()
        
        return Stream(
            content=stream_generator(),
            media_type=content_type,
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "onetap-server", "version": "2.0.0"}


# --- APP ---
app = Litestar(
    route_handlers=[extract_url, stream_video, health_check],
    debug=False
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "server:app",
        host="0.0.0.0", 
        port=port,
        loop="uvloop"
    )
