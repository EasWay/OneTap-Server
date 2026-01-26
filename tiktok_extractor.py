#!/usr/bin/env python3
"""
TikTok Video Extractor with Mobile API Emulation
Implements aggressive fallback chains for maximum success rate
"""

import logging
import time
import requests
from urllib.parse import urlparse
from tiktok_mobile_api import TikTokMobileAPI

logger = logging.getLogger(__name__)

class TikTokExtractor:
    """
    TikTok video extractor with mobile API emulation and fallback chains
    """
    
    def __init__(self, user_identifier=None):
        # Initialize mobile API with user-specific device fingerprint
        self.mobile_api = TikTokMobileAPI(user_identifier)
        self.session = requests.Session()
        
        # Fallback extractors in order of preference
        self.extractors = [
            self._extract_via_mobile_api,
            self._extract_via_web_api,
            self._extract_via_oembed,
            self._extract_via_ytdlp_fallback
        ]
    
    def extract_video(self, url):
        """
        Extract TikTok video with aggressive fallback chain
        Returns direct video URLs with zero HTML parsing
        """
        logger.info(f"🎯 Starting TikTok extraction for: {url}")
        
        # Extract video ID from URL
        video_id = self._extract_video_id(url)
        if not video_id:
            return self._error_response("Could not extract video ID from URL")
        
        logger.info(f"📱 Extracted video ID: {video_id}")
        
        # Try each extractor until one succeeds
        last_error = None
        
        for i, extractor in enumerate(self.extractors):
            try:
                logger.info(f"🔄 Trying extractor {i + 1}/{len(self.extractors)}: {extractor.__name__}")
                
                result = extractor(video_id, url)
                
                if result["success"]:
                    logger.info(f"✅ Extraction successful with {extractor.__name__}")
                    return result
                else:
                    logger.warning(f"⚠️ {extractor.__name__} failed: {result.get('error', 'Unknown error')}")
                    last_error = result.get('error', 'Unknown error')
                    
            except Exception as e:
                logger.error(f"❌ {extractor.__name__} crashed: {e}")
                last_error = str(e)
                continue
        
        # All extractors failed
        logger.error(f"❌ All TikTok extractors failed. Last error: {last_error}")
        return self._error_response(f"All extraction methods failed: {last_error}")
    
    def _extract_video_id(self, url):
        """Extract video ID from various TikTok URL formats"""
        return self.mobile_api.extract_video_id_from_url(url)
    
    def _extract_via_mobile_api(self, video_id, url):
        """
        Primary extractor: Mobile API emulation
        Highest success rate, direct video URLs, no watermark
        """
        try:
            logger.info("🚀 Using TikTok Mobile API emulation")
            
            result = self.mobile_api.get_video_info(video_id)
            
            if not result["success"]:
                return result
            
            video_urls = result["video_urls"]
            metadata = result["metadata"]
            
            # Select best video URL with fallback chain
            video_url = self._select_best_video_url(video_urls)
            
            if not video_url:
                return self._error_response("No valid video URLs found in mobile API response")
            
            return {
                "success": True,
                "video_url": video_url,
                "title": metadata.get("title", "TikTok Video"),
                "author": metadata.get("author", "Unknown"),
                "duration": metadata.get("duration", 0),
                "view_count": metadata.get("view_count", 0),
                "like_count": metadata.get("like_count", 0),
                "extractor": "mobile_api",
                "has_watermark": False,
                "quality": "high"
            }
            
        except Exception as e:
            logger.error(f"❌ Mobile API extraction failed: {e}")
            return self._error_response(f"Mobile API failed: {e}")
    
    def _extract_via_web_api(self, video_id, url):
        """
        Fallback 1: Web API endpoints
        Uses undocumented web endpoints
        """
        try:
            logger.info("🌐 Using TikTok Web API fallback")
            
            # Try different web API endpoints
            web_endpoints = [
                f"https://www.tiktok.com/api/item/detail/?itemId={video_id}",
                f"https://m.tiktok.com/api/item/detail/?itemId={video_id}",
                f"https://www.tiktok.com/node/share/video/{video_id}"
            ]
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.tiktok.com/",
                "Accept": "application/json, text/plain, */*"
            }
            
            for endpoint in web_endpoints:
                try:
                    response = self.session.get(endpoint, headers=headers, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extract video URL from web API response
                        video_url = self._extract_from_web_response(data)
                        
                        if video_url:
                            return {
                                "success": True,
                                "video_url": video_url,
                                "title": "TikTok Video",
                                "extractor": "web_api",
                                "has_watermark": True,
                                "quality": "medium"
                            }
                            
                except Exception as e:
                    logger.warning(f"⚠️ Web API endpoint failed: {e}")
                    continue
            
            return self._error_response("All web API endpoints failed")
            
        except Exception as e:
            logger.error(f"❌ Web API extraction failed: {e}")
            return self._error_response(f"Web API failed: {e}")
    
    def _extract_via_oembed(self, video_id, url):
        """
        Fallback 2: oEmbed API
        Official but limited API
        """
        try:
            logger.info("📺 Using TikTok oEmbed API fallback")
            
            oembed_url = f"https://www.tiktok.com/oembed?url={url}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = self.session.get(oembed_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # oEmbed doesn't provide direct video URLs, but we can extract metadata
                # and try to construct video URLs
                if "html" in data:
                    # Try to extract video URL from embed HTML
                    import re
                    html = data["html"]
                    
                    # Look for video URLs in the embed code
                    video_patterns = [
                        r'"videoUrl":"([^"]+)"',
                        r'"playAddr":"([^"]+)"',
                        r'src="([^"]*\.mp4[^"]*)"'
                    ]
                    
                    for pattern in video_patterns:
                        match = re.search(pattern, html)
                        if match:
                            video_url = match.group(1).replace("\\u002F", "/")
                            
                            return {
                                "success": True,
                                "video_url": video_url,
                                "title": data.get("title", "TikTok Video"),
                                "author": data.get("author_name", "Unknown"),
                                "extractor": "oembed",
                                "has_watermark": True,
                                "quality": "medium"
                            }
            
            return self._error_response("oEmbed API did not return video URL")
            
        except Exception as e:
            logger.error(f"❌ oEmbed extraction failed: {e}")
            return self._error_response(f"oEmbed failed: {e}")
    
    def _extract_via_ytdlp_fallback(self, video_id, url):
        """
        Fallback 3: yt-dlp (last resort)
        Most likely to be blocked but still worth trying
        """
        try:
            logger.info("🔧 Using yt-dlp fallback (last resort)")
            
            import yt_dlp
            
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "format": "best",
                "socket_timeout": 30
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and "url" in info:
                    return {
                        "success": True,
                        "video_url": info["url"],
                        "title": info.get("title", "TikTok Video"),
                        "author": info.get("uploader", "Unknown"),
                        "duration": info.get("duration", 0),
                        "view_count": info.get("view_count", 0),
                        "extractor": "ytdlp",
                        "has_watermark": True,
                        "quality": "medium"
                    }
            
            return self._error_response("yt-dlp could not extract video URL")
            
        except Exception as e:
            logger.error(f"❌ yt-dlp extraction failed: {e}")
            return self._error_response(f"yt-dlp failed: {e}")
    
    def _select_best_video_url(self, video_urls):
        """
        Select best video URL from mobile API response
        Priority: playAddr > downloadAddr > playAddr_h264 > playAddr_bytevc1
        """
        # Use priority order from config
        priority_order = FALLBACK_CONFIG["URL_PRIORITY"]
        
        for url_type in priority_order:
            if url_type in video_urls and video_urls[url_type]:
                urls = video_urls[url_type]
                
                # Try each URL in the list until one works
                for url in urls:
                    if self._test_video_url(url):
                        logger.info(f"✅ Selected {url_type} URL: {url[:50]}...")
                        return url
        
        logger.warning("⚠️ No working video URLs found")
        return None
    
    def _test_video_url(self, url):
        """Test if video URL is accessible"""
        try:
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def _extract_from_web_response(self, data):
        """Extract video URL from web API response"""
        try:
            # Try different possible paths in the response
            paths = [
                ["itemInfo", "itemStruct", "video", "playAddr"],
                ["itemInfo", "itemStruct", "video", "downloadAddr"],
                ["item", "video", "playAddr"],
                ["item", "video", "downloadAddr"]
            ]
            
            for path in paths:
                current = data
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        break
                else:
                    # Successfully navigated the path
                    if isinstance(current, str):
                        return current
                    elif isinstance(current, list) and current:
                        return current[0]
                    elif isinstance(current, dict) and "url_list" in current:
                        url_list = current["url_list"]
                        if url_list:
                            return url_list[0]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to extract from web response: {e}")
            return None
    
    def _error_response(self, message):
        """Create standardized error response"""
        return {
            "success": False,
            "error": message
        }