#!/usr/bin/env python3
"""
Profile Uploader for Render Deployment
Securely uploads your complete authenticated Chrome profile to Render
"""

import os
import json
import zipfile
import base64
import requests
import logging
import shutil
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfileUploader:
    def __init__(self, render_url=None):
        self.render_url = render_url or input("Enter your Render app URL (e.g., https://your-app.onrender.com): ").strip()
        if not self.render_url.startswith('http'):
            self.render_url = f"https://{self.render_url}"
        
    def find_chrome_profiles(self):
        """Find available Chrome profiles on the system"""
        profiles = []
        
        # Local profile directories to check
        local_profiles = [
            "authenticated_youtube_session",
            "authenticated_youtube_session_complete_backup", 
            "youtube_profile",
            "tldv_profile",
            "chrome_profile"
        ]
        
        for profile_dir in local_profiles:
            if os.path.exists(profile_dir):
                profiles.append({
                    "name": profile_dir,
                    "path": profile_dir,
                    "type": "local_authenticated"
                })
        
        # System Chrome profiles (optional)
        system_chrome_paths = [
            os.path.expanduser("~/AppData/Local/Google/Chrome/User Data"),  # Windows
            os.path.expanduser("~/Library/Application Support/Google/Chrome"),  # macOS
            os.path.expanduser("~/.config/google-chrome"),  # Linux
        ]
        
        for chrome_path in system_chrome_paths:
            if os.path.exists(chrome_path):
                default_profile = os.path.join(chrome_path, "Default")
                if os.path.exists(default_profile):
                    profiles.append({
                        "name": f"System Chrome ({os.path.basename(chrome_path)})",
                        "path": chrome_path,
                        "type": "system_chrome"
                    })
        
        return profiles
    
    def validate_profile(self, profile_path):
        """Validate that the profile contains authentication data"""
        default_dir = os.path.join(profile_path, "Default")
        
        if not os.path.exists(default_dir):
            return False, "No Default profile directory found"
        
        # Check for essential authentication files
        required_files = [
            "Preferences",
            "Login Data"
        ]
        
        optional_files = [
            os.path.join("Network", "Cookies"),
            "History",
            "Web Data"
        ]
        
        missing_required = []
        for file_path in required_files:
            full_path = os.path.join(default_dir, file_path)
            if not os.path.exists(full_path):
                missing_required.append(file_path)
        
        if missing_required:
            return False, f"Missing required files: {', '.join(missing_required)}"
        
        # Count optional files
        found_optional = []
        for file_path in optional_files:
            full_path = os.path.join(default_dir, file_path)
            if os.path.exists(full_path):
                found_optional.append(file_path)
        
        return True, f"Valid profile with {len(found_optional)} optional auth files"
    
    def create_profile_zip(self, profile_path):
        """Create a ZIP file of the Chrome profile"""
        try:
            # Create temporary ZIP file
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_zip.close()
            
            logger.info(f"Creating profile ZIP from: {profile_path}")
            
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Walk through profile directory
                for root, dirs, files in os.walk(profile_path):
                    # Skip some unnecessary directories to reduce size
                    dirs[:] = [d for d in dirs if d not in [
                        'Crashpad', 'ShaderCache', 'GPUCache', 'Code Cache',
                        'Service Worker', 'DawnCache', 'optimization_guide_model_store'
                    ]]
                    
                    for file in files:
                        # Skip large unnecessary files
                        if file.endswith(('.log', '.tmp', '.lock', '.old')):
                            continue
                        if file.startswith('LOG'):
                            continue
                            
                        file_path = os.path.join(root, file)
                        
                        # Skip very large files (>50MB)
                        try:
                            if os.path.getsize(file_path) > 50 * 1024 * 1024:
                                logger.info(f"Skipping large file: {file}")
                                continue
                        except:
                            continue
                        
                        # Add to ZIP with relative path
                        arcname = os.path.relpath(file_path, profile_path)
                        try:
                            zipf.write(file_path, arcname)
                        except Exception as e:
                            logger.warning(f"Could not add {file}: {str(e)}")
                            continue
            
            # Check ZIP size
            zip_size = os.path.getsize(temp_zip.name)
            zip_size_mb = zip_size / (1024 * 1024)
            
            logger.info(f"Profile ZIP created: {zip_size_mb:.1f} MB")
            
            if zip_size_mb > 100:
                logger.warning(f"ZIP file is large ({zip_size_mb:.1f} MB) - upload may take time")
            
            return temp_zip.name, zip_size_mb
            
        except Exception as e:
            logger.error(f"Failed to create profile ZIP: {str(e)}")
            return None, 0
    
    def extract_cookies_from_profile(self, profile_path):
        """Extract cookies from Chrome profile"""
        try:
            cookies_db_path = os.path.join(profile_path, "Default", "Network", "Cookies")
            
            if not os.path.exists(cookies_db_path):
                logger.warning("No cookies database found in profile")
                return None
                
            import sqlite3
            
            # Copy cookies file to avoid locking issues
            with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_db:
                shutil.copy2(cookies_db_path, temp_db.name)
                temp_db_path = temp_db.name
            
            try:
                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()
                
                # Extract YouTube/Google cookies
                cursor.execute("""
                    SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
                    FROM cookies 
                    WHERE host_key LIKE '%youtube%' OR host_key LIKE '%google%' OR host_key LIKE '%googlevideo%'
                    ORDER BY creation_utc DESC
                """)
                
                rows = cursor.fetchall()
                
                # Convert to Netscape cookie format
                cookie_lines = ["# Netscape HTTP Cookie File"]
                cookie_lines.append("# Extracted from Chrome profile")
                
                for row in rows:
                    host_key, name, value, path, expires_utc, is_secure, is_httponly = row
                    
                    # Convert Chrome timestamp to Unix timestamp
                    if expires_utc:
                        expires = int(expires_utc / 1000000 - 11644473600)
                    else:
                        expires = 0
                    
                    # Format: domain, domain_specified, path, secure, expires, name, value
                    cookie_line = f"{host_key}\tTRUE\t{path}\t{'TRUE' if is_secure else 'FALSE'}\t{expires}\t{name}\t{value}"
                    cookie_lines.append(cookie_line)
                
                conn.close()
                
                logger.info(f"Extracted {len(cookie_lines)-2} cookies from profile")
                return "\n".join(cookie_lines)
                
            finally:
                os.unlink(temp_db_path)
                
        except Exception as e:
            logger.error(f"Failed to extract cookies: {str(e)}")
            return None
    
    def upload_profile_to_render(self, zip_path):
        """Upload the profile ZIP to Render"""
        try:
            upload_url = f"{self.render_url}/upload_profile"
            
            logger.info(f"Uploading profile to {upload_url}...")
            
            with open(zip_path, 'rb') as f:
                files = {
                    'file': ('chrome_profile.zip', f, 'application/zip')
                }
                
                # Upload with timeout for large files
                response = requests.post(upload_url, files=files, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Profile upload successful!")
                logger.info(f"   Profile directory: {result.get('profile_directory', 'unknown')}")
                logger.info(f"   Authentication files: {result.get('authentication_files', [])}")
                logger.info(f"   Cookies extracted: {result.get('cookies_extracted', 'unknown')}")
                return True
            else:
                logger.error(f"❌ Upload failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Upload error: {str(e)}")
            return False
    
    def upload_cookies_fallback(self, cookies_content):
        """Fallback: upload just cookies if profile upload fails"""
        try:
            upload_url = f"{self.render_url}/upload_cookies"
            
            files = {
                'file': ('google_cookies.txt', cookies_content, 'text/plain')
            }
            
            logger.info(f"Uploading cookies to {upload_url}...")
            response = requests.post(upload_url, files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Cookies upload successful!")
                logger.info(f"   Cookies uploaded: {result.get('cookie_count', 'unknown')}")
                return True
            else:
                logger.error(f"❌ Cookies upload failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Cookies upload error: {str(e)}")
            return False
    
    def verify_upload(self):
        """Verify the upload was successful"""
        try:
            # Check profile status
            profile_status_url = f"{self.render_url}/profile_status"
            response = requests.get(profile_status_url, timeout=10)
            
            if response.status_code == 200:
                status = response.json()
                if status.get("profiles_found", 0) > 0:
                    logger.info("✅ Profile verified on Render!")
                    profiles = status.get("profiles", [])
                    for profile in profiles:
                        logger.info(f"   Profile: {profile['name']} ({profile['status']})")
                    
                    extracted = status.get("extracted_cookies", {})
                    if extracted.get("available"):
                        logger.info(f"   Extracted cookies: {extracted.get('count', 0)}")
                    
                    return True
                else:
                    logger.warning("⚠️ No profiles found on Render")
                    return False
            else:
                logger.error(f"❌ Profile verification failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Verification error: {str(e)}")
            return False

def main():
    print("🚀 OneTap Complete Profile Uploader")
    print("=" * 50)
    
    uploader = ProfileUploader()
    
    # Find available profiles
    print("\n🔍 Searching for Chrome profiles...")
    profiles = uploader.find_chrome_profiles()
    
    if not profiles:
        print("❌ No Chrome profiles found!")
        print("   Make sure you have an authenticated Chrome profile in one of these directories:")
        print("   - authenticated_youtube_session")
        print("   - youtube_profile") 
        print("   - tldv_profile")
        return
    
    # Display available profiles
    print(f"\n📁 Found {len(profiles)} profile(s):")
    for i, profile in enumerate(profiles):
        valid, msg = uploader.validate_profile(profile["path"])
        status = "✅ Valid" if valid else "❌ Invalid"
        print(f"   {i+1}. {profile['name']} - {status}")
        print(f"      Path: {profile['path']}")
        print(f"      Info: {msg}")
    
    # Select profile
    if len(profiles) == 1:
        selected_profile = profiles[0]
        print(f"\n🎯 Using profile: {selected_profile['name']}")
    else:
        while True:
            try:
                choice = int(input(f"\nSelect profile (1-{len(profiles)}): ")) - 1
                if 0 <= choice < len(profiles):
                    selected_profile = profiles[choice]
                    break
                else:
                    print("Invalid choice!")
            except ValueError:
                print("Please enter a number!")
    
    # Validate selected profile
    valid, msg = uploader.validate_profile(selected_profile["path"])
    if not valid:
        print(f"❌ Selected profile is invalid: {msg}")
        return
    
    print(f"✅ Selected profile is valid: {msg}")
    
    # Create profile package
    print(f"\n📦 Creating profile ZIP...")
    zip_path, zip_size_mb = uploader.create_profile_zip(selected_profile["path"])
    
    if not zip_path:
        print("❌ Failed to create profile ZIP")
        return
    
    print(f"✅ Profile ZIP created: {zip_size_mb:.1f} MB")
    
    # Extract cookies as fallback
    print("\n🍪 Extracting cookies as fallback...")
    cookies_content = uploader.extract_cookies_from_profile(selected_profile["path"])
    
    if cookies_content:
        cookie_count = len([line for line in cookies_content.split('\n') if line.strip() and not line.startswith('#')])
        print(f"✅ Extracted {cookie_count} cookies")
    else:
        print("⚠️ Could not extract cookies")
    
    # Confirm upload
    print(f"\n🔐 Ready to upload:")
    print(f"   Profile: {selected_profile['name']}")
    print(f"   Size: {zip_size_mb:.1f} MB")
    print(f"   Destination: {uploader.render_url}")
    
    confirm = input(f"\nProceed with upload? (y/N): ").strip().lower()
    
    if confirm != 'y':
        print("❌ Upload cancelled")
        os.unlink(zip_path)
        return
    
    # Upload profile
    print("\n⬆️ Uploading complete profile...")
    profile_success = uploader.upload_profile_to_render(zip_path)
    
    # Clean up ZIP file
    os.unlink(zip_path)
    
    if profile_success:
        print("\n🔍 Verifying upload...")
        if uploader.verify_upload():
            print("\n🎉 Success! Your complete authenticated profile is now available on Render!")
            print(f"   Your Render app: {uploader.render_url}")
            print("   yt-dlp will now use your full Chrome session for YouTube downloads")
        else:
            print("\n⚠️ Upload completed but verification failed")
    else:
        # Fallback to cookies only
        if cookies_content:
            print("\n⚠️ Profile upload failed, trying cookies fallback...")
            if uploader.upload_cookies_fallback(cookies_content):
                print("✅ Cookies uploaded as fallback")
            else:
                print("❌ Both profile and cookies upload failed")
        else:
            print("❌ Profile upload failed and no cookies available")

if __name__ == "__main__":
    import time
    main()