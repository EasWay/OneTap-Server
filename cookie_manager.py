#!/usr/bin/env python3
"""
Simple Cookie Manager for OneTap Server
Handles cookie loading and basic validation
"""

import os
import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File paths
COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")
GOOGLE_COOKIES_FILE = os.path.join(os.getcwd(), "google_cookies.txt")

def load_cookies_from_file(driver, cookies_file):
    """
    Load cookies from Netscape format file into Selenium WebDriver
    """
    if not os.path.exists(cookies_file):
        logger.error(f"❌ Cookies file not found: {cookies_file}")
        return False
    
    try:
        # Navigate to a base domain first
        driver.get("https://www.google.com")
        time.sleep(2)
        
        with open(cookies_file, 'r') as f:
            lines = f.readlines()
        
        cookies_loaded = 0
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain = parts[0]
                        name = parts[5]
                        value = parts[6]
                        
                        # Add cookie to driver
                        cookie_dict = {
                            'name': name,
                            'value': value,
                            'domain': domain.lstrip('.'),
                        }
                        
                        driver.add_cookie(cookie_dict)
                        cookies_loaded += 1
                        
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load cookie: {str(e)}")
                    continue
        
        logger.info(f"✅ Loaded {cookies_loaded} cookies from {cookies_file}")
        return cookies_loaded > 0
        
    except Exception as e:
        logger.error(f"❌ Error loading cookies: {str(e)}")
        return False

def save_google_cookies_netscape(selenium_cookies):
    """
    Save Google cookies in Netscape format for yt-dlp compatibility.
    """
    try:
        google_domains = ['google.com', 'youtube.com', 'googlevideo.com', 'gstatic.com']
        important_cookies = ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID', '__Secure-3PAPISID', '__Secure-3PSID']
        
        with open(GOOGLE_COOKIES_FILE, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# Google/YouTube session cookies\n\n")
            
            for cookie in selenium_cookies:
                domain = cookie.get('domain', '')
                name = cookie.get('name', '')
                
                # Filter for Google-related cookies
                if any(gd in domain for gd in google_domains) or name in important_cookies:
                    domain_clean = domain.lstrip('.')
                    secure_flag = 'TRUE' if cookie.get('secure') else 'FALSE'
                    expiry = cookie.get('expiry', 0)
                    
                    line = (
                        f".{domain_clean}\tTRUE\t{cookie.get('path', '/')}\t"
                        f"{secure_flag}\t{expiry}\t"
                        f"{name}\t{cookie['value']}\n"
                    )
                    f.write(line)
        
        logger.info(f"✅ Saved Google cookies to {GOOGLE_COOKIES_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save Google cookies: {str(e)}")
        return False

def validate_cookies_file(cookies_file):
    """
    Validate if a cookies file is in correct Netscape format
    """
    if not os.path.exists(cookies_file):
        return False, "File does not exist"
    
    try:
        with open(cookies_file, 'r') as f:
            lines = f.readlines()
        
        valid_cookies = 0
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split('\t')
                if len(parts) >= 7:
                    valid_cookies += 1
        
        if valid_cookies == 0:
            return False, "No valid cookies found"
        
        return True, f"Found {valid_cookies} valid cookies"
        
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def get_cookies_info():
    """
    Get information about available cookie files
    """
    info = {
        "social_media_cookies": {
            "exists": os.path.exists(COOKIES_FILE),
            "size": os.path.getsize(COOKIES_FILE) if os.path.exists(COOKIES_FILE) else 0,
            "modified": datetime.fromtimestamp(os.path.getmtime(COOKIES_FILE)).isoformat() if os.path.exists(COOKIES_FILE) else None
        },
        "google_cookies": {
            "exists": os.path.exists(GOOGLE_COOKIES_FILE),
            "size": os.path.getsize(GOOGLE_COOKIES_FILE) if os.path.exists(GOOGLE_COOKIES_FILE) else 0,
            "modified": datetime.fromtimestamp(os.path.getmtime(GOOGLE_COOKIES_FILE)).isoformat() if os.path.exists(GOOGLE_COOKIES_FILE) else None
        }
    }
    
    return info

if __name__ == "__main__":
    # Test cookie validation
    info = get_cookies_info()
    print("📊 Cookie Files Info:")
    print(json.dumps(info, indent=2))