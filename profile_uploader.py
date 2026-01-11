#!/usr/bin/env python3
"""
Profile Uploader for Render Deployment
Securely uploads your authenticated Google profile to Render
"""

import os
import json
import zipfile
import base64
import requests
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfileUploader:
    def __init__(self, render_url=None):
        self.render_url = render_url or input("Enter your Render app URL (e.g., https://your-app.onrender.com): ").strip()
        if not self.render_url.startswith('http'):
            self.render_url = f"https://{self.render_url}"
        
    def extract_cookies_from_profile(self, profile_path):
        """Extract cookies from Chrome profile"""
        cookies_data = []
        
        # Look for cookies in the profile
        cookies_file = os.path.join(profile_path, "Default", "Network", "Cookies")
        if not os.path.exists(cookies_file):
            logger.warning(f"Cookies file not found at {cookies_file}")
            return None
            
        try:
            import sqlite3
            
            # Copy cookies file to avoid locking issues
            temp_cookies = "/tmp/temp_cookies.db"
            import shutil
            shutil.copy2(cookies_file, temp_cookies)
            
            conn = sqlite3.connect(temp_cookies)
            cursor = conn.cursor()
            
            # Extract YouTube/Google cookies
            cursor.execute("""
                SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
                FROM cookies 
                WHERE host_key LIKE '%youtube%' OR host_key LIKE '%google%'
                ORDER BY creation_utc DESC
            """)
            
            rows = cursor.fetchall()
            
            # Convert to Netscape cookie format
            cookie_lines = ["# Netscape HTTP Cookie File"]
            for row in rows:
                host_key, name, value, path, expires_utc, is_secure, is_httponly = row
                
                # Convert Chrome timestamp to Unix timestamp
                expires = int(expires_utc / 1000000 - 11644473600) if expires_utc else 0
                
                # Format: domain, domain_specified, path, secure, expires, name, value
                cookie_line = f"{host_key}\tTRUE\t{path}\t{'TRUE' if is_secure else 'FALSE'}\t{expires}\t{name}\t{value}"
                cookie_lines.append(cookie_line)
            
            conn.close()
            os.remove(temp_cookies)
            
            logger.info(f"Extracted {len(cookie_lines)-1} cookies from profile")
            return "\n".join(cookie_lines)
            
        except Exception as e:
            logger.error(f"Failed to extract cookies: {str(e)}")
            return None
    
    def create_profile_package(self):
        """Create a secure package of the authenticated profile"""
        
        # Find authenticated profile
        profile_paths = [
            "authenticated_youtube_session",
            "youtube_profile", 
            "tldv_profile"
        ]
        
        profile_path = None
        for path in profile_paths:
            if os.path.exists(path):
                profile_path = path
                break
                
        if not profile_path:
            logger.error("No authenticated profile found!")
            logger.info("Available profiles should be in: " + ", ".join(profile_paths))
            return None
            
        logger.info(f"Found profile: {profile_path}")
        
        # Extract cookies from profile
        cookies_content = self.extract_cookies_from_profile(profile_path)
        if not cookies_content:
            # Fallback to existing cookies file
            cookies_files = ["google_cookies.txt", "cookies.txt"]
            for cookies_file in cookies_files:
                if os.path.exists(cookies_file):
                    with open(cookies_file, 'r') as f:
                        cookies_content = f.read()
                    logger.info(f"Using existing cookies file: {cookies_file}")
                    break
        
        if not cookies_content:
            logger.error("No cookies found!")
            return None
            
        # Create package info
        package = {
            "cookies": cookies_content,
            "profile_name": profile_path,
            "cookie_count": len([line for line in cookies_content.split('\n') if line.strip() and not line.startswith('#')]),
            "timestamp": int(time.time())
        }
        
        logger.info(f"Created package with {package['cookie_count']} cookies")
        return package
    
    def upload_to_render(self, package):
        """Upload the profile package to Render"""
        try:
            # Create cookies file content
            cookies_content = package["cookies"]
            
            # Upload via the server's upload endpoint
            upload_url = f"{self.render_url}/upload_cookies"
            
            # Create a temporary file-like object
            import io
            cookies_file = io.StringIO(cookies_content)
            
            files = {
                'file': ('google_cookies.txt', cookies_content, 'text/plain')
            }
            
            logger.info(f"Uploading to {upload_url}...")
            response = requests.post(upload_url, files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Upload successful!")
                logger.info(f"   Cookies uploaded: {result.get('cookie_count', 'unknown')}")
                logger.info(f"   File size: {result.get('file_size', 'unknown')} bytes")
                return True
            else:
                logger.error(f"❌ Upload failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Upload error: {str(e)}")
            return False
    
    def verify_upload(self):
        """Verify the upload was successful"""
        try:
            status_url = f"{self.render_url}/cookies_status"
            response = requests.get(status_url, timeout=10)
            
            if response.status_code == 200:
                status = response.json()
                if status.get("cookies_available"):
                    logger.info("✅ Cookies verified on Render!")
                    logger.info(f"   Total cookies: {status.get('total_cookies', 'unknown')}")
                    logger.info(f"   Sources: {', '.join([s['type'] for s in status.get('sources', [])])}")
                    return True
                else:
                    logger.warning("⚠️ Cookies not found on Render")
                    return False
            else:
                logger.error(f"❌ Verification failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Verification error: {str(e)}")
            return False

def main():
    print("🚀 OneTap Profile Uploader")
    print("=" * 50)
    
    uploader = ProfileUploader()
    
    # Create profile package
    print("\n📦 Creating profile package...")
    package = uploader.create_profile_package()
    
    if not package:
        print("❌ Failed to create profile package")
        return
    
    print(f"✅ Package created with {package['cookie_count']} cookies")
    
    # Confirm upload
    confirm = input(f"\n🔐 Upload {package['cookie_count']} cookies to {uploader.render_url}? (y/N): ").strip().lower()
    
    if confirm != 'y':
        print("❌ Upload cancelled")
        return
    
    # Upload to Render
    print("\n⬆️ Uploading to Render...")
    if uploader.upload_to_render(package):
        print("\n🔍 Verifying upload...")
        if uploader.verify_upload():
            print("\n🎉 Success! Your authenticated profile is now available on Render!")
            print(f"   You can now use your Render app: {uploader.render_url}")
        else:
            print("\n⚠️ Upload completed but verification failed")
    else:
        print("\n❌ Upload failed")

if __name__ == "__main__":
    import time
    main()