#!/usr/bin/env python3
"""
Chrome Profile Manager for YouTube Session Extension
Utilizes existing Chrome profile (like tldv_profile) for YouTube authentication
"""

import os
import shutil
import sqlite3
import json
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChromeProfileManager:
    def __init__(self, profile_path="tldv_profile", backup_profile_path="youtube_profile"):
        self.profile_path = os.path.abspath(profile_path)
        self.backup_profile_path = os.path.abspath(backup_profile_path)
        self.cookies_file = os.path.join(self.profile_path, "Default", "Network", "Cookies")
        self.google_cookies_output = "google_cookies.txt"
        
    def backup_profile(self):
        """Create a backup of the current profile for YouTube use"""
        try:
            if os.path.exists(self.backup_profile_path):
                shutil.rmtree(self.backup_profile_path)
            
            shutil.copytree(self.profile_path, self.backup_profile_path)
            logger.info(f"✅ Profile backed up to {self.backup_profile_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to backup profile: {str(e)}")
            return False
    
    def extract_cookies_from_profile(self):
        """Extract cookies from Chrome profile database"""
        try:
            if not os.path.exists(self.cookies_file):
                logger.error(f"❌ Cookies file not found: {self.cookies_file}")
                return []
            
            # Copy cookies file to avoid locking issues
            temp_cookies = "temp_cookies.db"
            shutil.copy2(self.cookies_file, temp_cookies)
            
            conn = sqlite3.connect(temp_cookies)
            cursor = conn.cursor()
            
            # Query for Google/YouTube related cookies
            query = """
            SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly
            FROM cookies 
            WHERE host_key LIKE '%google%' 
               OR host_key LIKE '%youtube%' 
               OR host_key LIKE '%googlevideo%'
               OR host_key LIKE '%gstatic%'
            ORDER BY host_key, name
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            cookies = []
            for row in rows:
                name, value, host_key, path, expires_utc, is_secure, is_httponly = row
                
                # Convert Chrome timestamp to Unix timestamp
                if expires_utc:
                    # Chrome uses microseconds since Jan 1, 1601
                    # Unix uses seconds since Jan 1, 1970
                    expires_unix = (expires_utc - 11644473600000000) // 1000000
                else:
                    expires_unix = 0
                
                cookie = {
                    'name': name,
                    'value': value,
                    'domain': host_key,
                    'path': path,
                    'expires': expires_unix,
                    'secure': bool(is_secure),
                    'httponly': bool(is_httponly)
                }
                cookies.append(cookie)
            
            conn.close()
            os.remove(temp_cookies)
            
            logger.info(f"✅ Extracted {len(cookies)} Google/YouTube cookies from profile")
            return cookies
            
        except Exception as e:
            logger.error(f"❌ Failed to extract cookies: {str(e)}")
            return []
    
    def save_cookies_netscape_format(self, cookies):
        """Save cookies in Netscape format for yt-dlp"""
        try:
            with open(self.google_cookies_output, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Generated from Chrome profile\n")
                f.write("# This file contains cookies for Google/YouTube domains\n\n")
                
                for cookie in cookies:
                    domain = cookie['domain']
                    if domain.startswith('.'):
                        domain_flag = 'TRUE'
                        domain_clean = domain
                    else:
                        domain_flag = 'FALSE'
                        domain_clean = cookie['domain']
                    
                    secure_flag = 'TRUE' if cookie['secure'] else 'FALSE'
                    expires = cookie['expires'] if cookie['expires'] > 0 else 2147483647  # Max 32-bit int
                    
                    line = f"{domain_clean}\t{domain_flag}\t{cookie['path']}\t{secure_flag}\t{expires}\t{cookie['name']}\t{cookie['value']}\n"
                    f.write(line)
            
            logger.info(f"✅ Saved {len(cookies)} cookies to {self.google_cookies_output}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save cookies: {str(e)}")
            return False
    
    def launch_youtube_session(self):
        """Launch Chrome with the profile and navigate to YouTube to refresh session"""
        try:
            # Use backup profile for YouTube session
            if not os.path.exists(self.backup_profile_path):
                if not self.backup_profile():
                    return False
            
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.backup_profile_path}")
            chrome_options.add_argument("--profile-directory=Default")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")  # We just need to load the page
            
            # For headless operation (optional)
            # chrome_options.add_argument("--headless")
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            try:
                logger.info("🔄 Launching YouTube session...")
                
                # Navigate to YouTube to refresh session
                driver.get("https://www.youtube.com")
                time.sleep(5)  # Wait for page load
                
                # Check if we're logged in
                try:
                    # Look for user avatar or sign-in button
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "[aria-label*='Account menu']") or 
                                 d.find_element(By.CSS_SELECTOR, "[aria-label*='Sign in']")
                    )
                    logger.info("✅ YouTube page loaded successfully")
                except:
                    logger.warning("⚠️ Could not determine login status")
                
                # Navigate to a few more Google services to refresh tokens
                services = [
                    "https://accounts.google.com",
                    "https://myaccount.google.com"
                ]
                
                for service_url in services:
                    try:
                        driver.get(service_url)
                        time.sleep(3)
                        logger.info(f"✅ Refreshed session for {service_url}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not refresh {service_url}: {str(e)}")
                
                return True
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"❌ Failed to launch YouTube session: {str(e)}")
            return False
    
    def extend_youtube_session(self):
        """Main method to extend YouTube session using Chrome profile"""
        try:
            logger.info("🔄 Starting YouTube session extension using Chrome profile...")
            
            # Step 1: Launch YouTube session to refresh cookies
            if not self.launch_youtube_session():
                logger.error("❌ Failed to launch YouTube session")
                return False
            
            # Step 2: Extract fresh cookies from profile
            cookies = self.extract_cookies_from_profile()
            if not cookies:
                logger.error("❌ No cookies extracted from profile")
                return False
            
            # Step 3: Save cookies in Netscape format
            if not self.save_cookies_netscape_format(cookies):
                logger.error("❌ Failed to save cookies")
                return False
            
            logger.info("✅ YouTube session extension completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ YouTube session extension failed: {str(e)}")
            return False
    
    def get_session_info(self):
        """Get information about the current session"""
        try:
            cookies = self.extract_cookies_from_profile()
            
            # Look for important session cookies
            session_cookies = ['SID', 'HSID', 'SSID', 'APISID', 'SAPISID']
            found_cookies = []
            
            for cookie in cookies:
                if cookie['name'] in session_cookies:
                    found_cookies.append({
                        'name': cookie['name'],
                        'domain': cookie['domain'],
                        'expires': datetime.fromtimestamp(cookie['expires']).isoformat() if cookie['expires'] > 0 else 'Session'
                    })
            
            return {
                'total_cookies': len(cookies),
                'session_cookies': found_cookies,
                'profile_path': self.profile_path,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get session info: {str(e)}")
            return None


def main():
    """Test the Chrome profile manager"""
    manager = ChromeProfileManager()
    
    # Get current session info
    info = manager.get_session_info()
    if info:
        print("📊 Current Session Info:")
        print(json.dumps(info, indent=2))
    
    # Extend YouTube session
    success = manager.extend_youtube_session()
    if success:
        print("✅ YouTube session extended successfully!")
    else:
        print("❌ Failed to extend YouTube session")


if __name__ == "__main__":
    main()