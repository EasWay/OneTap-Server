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
from tiktok_config import FALLBACK_CONFIG

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
            self._extract_via_web_scraping,  # New web scraping method
            self._extract_via_direct_construction,  # Try to construct URLs directly
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
            logger.warning(f"⚠️ Could not extract video ID from URL: {url}")
            # Try fallback extractors that don't require video ID
            return self._try_fallback_extractors_without_id(url)
        
        logger.info(f"📱 Extracted video ID: {video_id}")
        
        # Validate video ID is numeric
        if not video_id.isdigit():
            logger.warning(f"⚠️ Video ID is not numeric: {video_id}")
            return self._try_fallback_extractors_without_id(url)
        
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
    
    def _try_fallback_extractors_without_id(self, url):
        """Try extractors that don't require video ID"""
        logger.info("🔄 Trying fallback extractors without video ID requirement")
        
        fallback_extractors = [
            self._extract_via_web_scraping,
            self._extract_via_ytdlp_fallback,
            self._extract_via_oembed
        ]
        
        for extractor in fallback_extractors:
            try:
                logger.info(f"🔄 Trying {extractor.__name__} without video ID")
                result = extractor(None, url)  # Pass None as video_id
                
                if result["success"]:
                    logger.info(f"✅ Fallback extraction successful with {extractor.__name__}")
                    return result
                    
            except Exception as e:
                logger.error(f"❌ {extractor.__name__} failed: {e}")
                continue
        
        return self._error_response("Could not extract video ID and all fallback methods failed")
    
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
            
            # Store all available URLs for fallback during download
            all_urls = []
            for url_type, urls in video_urls.items():
                all_urls.extend(urls)
            
            return {
                "success": True,
                "video_url": video_url,
                "fallback_urls": all_urls[:5],  # Limit to 5 fallback URLs
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
    
    def _extract_via_web_scraping(self, video_id, url):
        """
        Fallback 1.5: Web scraping approach
        Scrapes the TikTok web page directly to extract video URLs
        """
        try:
            logger.info("🕷️ Using TikTok web scraping fallback")
            
            # Construct the full TikTok URL if we have video_id
            if video_id and video_id.isdigit():
                # Try to construct a proper TikTok URL
                scrape_url = url
            else:
                scrape_url = url
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0"
            }
            
            # First, resolve the URL if it's a short URL
            if 'vt.tiktok.com' in scrape_url or 'vm.tiktok.com' in scrape_url:
                logger.info(f"🔗 Resolving short URL: {scrape_url}")
                response = self.session.head(scrape_url, headers=headers, allow_redirects=True, timeout=15)
                scrape_url = response.url
                logger.info(f"🔗 Resolved to: {scrape_url}")
            
            # Now scrape the actual TikTok page
            response = self.session.get(scrape_url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                return self._error_response(f"Failed to load TikTok page: HTTP {response.status_code}")
            
            html_content = response.text
            
            # Extract video URLs using regex patterns
            import re
            
            # Look for various video URL patterns in the HTML
            video_patterns = [
                # Direct video URLs
                r'"playAddr":"([^"]+)"',
                r'"downloadAddr":"([^"]+)"',
                r'"url":"(https://[^"]*\.mp4[^"]*)"',
                r'"videoUrl":"([^"]+)"',
                # Encoded URLs
                r'playAddr%22%3A%22([^%]+)%22',
                r'downloadAddr%22%3A%22([^%]+)%22',
                # JSON-LD structured data
                r'"contentUrl":"([^"]+\.mp4[^"]*)"',
                r'"embedUrl":"([^"]+)"',
                # Other patterns
                r'src="([^"]*v\d+[^"]*\.mp4[^"]*)"',
                r'data-video-url="([^"]+)"'
            ]
            
            found_urls = []
            
            for pattern in video_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    # Decode URL if it's encoded
                    import urllib.parse
                    decoded_url = urllib.parse.unquote(match)
                    
                    # Clean up the URL
                    if decoded_url.startswith('http') and '.mp4' in decoded_url:
                        found_urls.append(decoded_url)
            
            # Remove duplicates while preserving order
            unique_urls = []
            for url in found_urls:
                if url not in unique_urls:
                    unique_urls.append(url)
            
            if not unique_urls:
                # Try to extract from SIGI_STATE or __NEXT_DATA__
                sigi_patterns = [
                    r'window\.__SIGI_STATE__\s*=\s*({.+?});',
                    r'window\.__NEXT_DATA__\s*=\s*({.+?});'
                ]
                
                for sigi_pattern in sigi_patterns:
                    match = re.search(sigi_pattern, html_content)
                    if match:
                        try:
                            import json
                            data = json.loads(match.group(1))
                            
                            # Navigate through the data structure to find video URLs
                            video_urls = self._extract_urls_from_sigi_data(data)
                            if video_urls:
                                unique_urls.extend(video_urls)
                                break
                        except:
                            continue
            
            if unique_urls:
                logger.info(f"🕷️ Found {len(unique_urls)} video URLs via web scraping")
                
                # Try to extract title and author from HTML
                title_match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
                title = title_match.group(1) if title_match else "TikTok Video"
                
                # Clean up title
                title = title.replace(' | TikTok', '').strip()
                
                author_patterns = [
                    r'"author":"([^"]+)"',
                    r'"uniqueId":"([^"]+)"',
                    r'@([a-zA-Z0-9_.]+)',
                ]
                
                author = "Unknown"
                for pattern in author_patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        author = match.group(1)
                        break
                
                return {
                    "success": True,
                    "video_url": unique_urls[0],  # Use the first URL as primary
                    "fallback_urls": unique_urls[1:5],  # Store others as fallbacks
                    "title": title,
                    "author": author,
                    "extractor": "web_scraping",
                    "has_watermark": True,
                    "quality": "medium"
                }
            
            return self._error_response("No video URLs found in web page")
            
        except Exception as e:
            logger.error(f"❌ Web scraping extraction failed: {e}")
            return self._error_response(f"Web scraping failed: {e}")
    
    def _extract_urls_from_sigi_data(self, data):
        """Extract video URLs from SIGI_STATE or __NEXT_DATA__ structure"""
        urls = []
        
        def recursive_search(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ['playAddr', 'downloadAddr', 'url_list', 'videoUrl'] and isinstance(value, (str, list)):
                        if isinstance(value, str) and value.startswith('http') and '.mp4' in value:
                            urls.append(value)
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, str) and item.startswith('http') and '.mp4' in item:
                                    urls.append(item)
                    else:
                        recursive_search(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    recursive_search(item, f"{path}[{i}]")
        
        recursive_search(data)
        return urls
    
    def _extract_via_direct_construction(self, video_id, url):
        """
        Fallback 2: Direct URL construction
        Try to construct video URLs using known TikTok CDN patterns
        """
        try:
            logger.info("🔧 Using direct URL construction fallback")
            
            if not video_id or not video_id.isdigit():
                return self._error_response("Video ID required for direct construction")
            
            # Common TikTok CDN patterns
            cdn_patterns = [
                "https://v16-webapp-prime.tiktok.com/video/tos/maliva/tos-maliva-ve-0068c799-us/",
                "https://v19-webapp-prime.tiktok.com/video/tos/maliva/tos-maliva-ve-0068c799-us/",
                "https://v77-webapp-prime.tiktok.com/video/tos/maliva/tos-maliva-ve-0068c799-us/",
                "https://v16-web.tiktok.com/video/tos/maliva/tos-maliva-ve-0068c799-us/",
                "https://v19-web.tiktok.com/video/tos/maliva/tos-maliva-ve-0068c799-us/"
            ]
            
            # Try to construct URLs with different patterns
            constructed_urls = []
            
            for cdn_base in cdn_patterns:
                # Generate some common URL patterns
                patterns = [
                    f"{cdn_base}{video_id}/?a=1988&ch=0&cr=3&dr=0&lr=all&cd=0%7C0%7C0%7C&cv=1&br=2732&bt=1366&cs=2&ds=4",
                    f"{cdn_base}o{video_id}/?a=1988&ch=0&cr=3&dr=0&lr=all",
                    f"{cdn_base}{video_id}.mp4"
                ]
                constructed_urls.extend(patterns)
            
            # Test each constructed URL
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15",
                "Referer": "https://www.tiktok.com/",
                "Accept": "*/*"
            }
            
            for test_url in constructed_urls:
                try:
                    # Quick HEAD request to test if URL is valid
                    response = requests.head(test_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'video' in content_type or 'mp4' in content_type:
                            logger.info(f"✅ Found working constructed URL")
                            
                            return {
                                "success": True,
                                "video_url": test_url,
                                "title": "TikTok Video",
                                "author": "Unknown",
                                "extractor": "direct_construction",
                                "has_watermark": True,
                                "quality": "medium"
                            }
                except:
                    continue
            
            return self._error_response("No working URLs could be constructed")
            
        except Exception as e:
            logger.error(f"❌ Direct construction failed: {e}")
            return self._error_response(f"Direct construction failed: {e}")
    
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
            
            # Use headers that work better with TikTok
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.tiktok.com/',
                'Origin': 'https://www.tiktok.com',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site'
            }
            
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "format": "best",
                "socket_timeout": 30,
                "http_headers": headers,
                # Add additional options for better success rate
                "retries": 3,
                "fragment_retries": 3,
                "extractor_retries": 2,
                "file_access_retries": 3,
                # Disable some features that might cause issues
                "no_check_certificate": True,
                "prefer_insecure": False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and "url" in info:
                    video_url = info["url"]
                    formats = info.get('formats', [])
                    if formats:
                        # Find the best format with a direct URL
                        best_format = None
                        for fmt in reversed(formats):  # Start from highest quality
                            if fmt.get('url') and not fmt.get('fragments'):  # Prefer non-fragmented
                                best_format = fmt
                                break
                        
                        if best_format:
                            video_url = best_format.get('url', video_url)
                            # Get format-specific headers if available
                            format_headers = best_format.get('http_headers', {})
                            if format_headers:
                                headers.update(format_headers)

                    return {
                        "success": True,
                        "video_url": video_url,
                        "title": info.get("title", "TikTok Video"),
                        "author": info.get("uploader", "Unknown"),
                        "duration": info.get("duration", 0),
                        "view_count": info.get("view_count", 0),
                        "extractor": "ytdlp",
                        "has_watermark": True,
                        "quality": "medium",
                        "http_headers": headers  # Pass headers for download
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
        
        logger.info(f"📹 Available video URL types: {list(video_urls.keys())}")
        
        for url_type in priority_order:
            if url_type in video_urls and video_urls[url_type]:
                urls = video_urls[url_type]
                logger.info(f"🔍 Checking {url_type}: {len(urls)} URLs available")
                
                # Return the first URL from this type (they're usually all valid)
                if urls:
                    selected_url = urls[0]
                    logger.info(f"✅ Selected {url_type} URL: {selected_url[:50]}...")
                    return selected_url
        
        # If no URLs found in priority order, try any available URLs
        for url_type, urls in video_urls.items():
            if urls:
                selected_url = urls[0]
                logger.info(f"✅ Fallback selected {url_type} URL: {selected_url[:50]}...")
                return selected_url
        
        logger.warning("⚠️ No video URLs found in response")
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