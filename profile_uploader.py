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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

class ProfileUploader:
    def __init__(self, render_url=None):
        self.render_url = render_url or input("Enter your Render app URL (e.g., https://your-app.onrender.com): ").strip()
        if not self.render_url.startswith('http'):
            self.render_url = f"https://{self.render_url}"
        
    def find_chrome_profiles(self):
        """Find available Chrome profiles on the system"""
        logger.info("🔍 Searching for Chrome profiles...")
        profiles = []
        
        # Local profile directories to check
        local_profiles = [
            "authenticated_youtube_session",
            "authenticated_youtube_session_complete_backup", 
            "youtube_profile",
            "tldv_profile",
            "chrome_profile"
        ]
        
        logger.debug(f"Checking {len(local_profiles)} local profile directories...")
        
        for profile_dir in local_profiles:
            logger.debug(f"Checking: {profile_dir}")
            
            if os.path.exists(profile_dir):
                try:
                    # Get profile size
                    profile_size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(profile_dir)
                        for filename in filenames
                    )
                    size_mb = profile_size / (1024 * 1024)
                    
                    logger.info(f"✅ Found local profile: {profile_dir} ({size_mb:.1f} MB)")
                    
                    profiles.append({
                        "name": profile_dir,
                        "path": profile_dir,
                        "type": "local_authenticated",
                        "size_mb": size_mb
                    })
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error analyzing profile {profile_dir}: {e}")
            else:
                logger.debug(f"❌ Not found: {profile_dir}")
        
        # System Chrome profiles (optional)
        logger.debug("Checking system Chrome profiles...")
        
        system_chrome_paths = [
            os.path.expanduser("~/AppData/Local/Google/Chrome/User Data"),  # Windows
            os.path.expanduser("~/Library/Application Support/Google/Chrome"),  # macOS
            os.path.expanduser("~/.config/google-chrome"),  # Linux
        ]
        
        for chrome_path in system_chrome_paths:
            logger.debug(f"Checking system path: {chrome_path}")
            
            if os.path.exists(chrome_path):
                default_profile = os.path.join(chrome_path, "Default")
                if os.path.exists(default_profile):
                    try:
                        profile_size = sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, dirnames, filenames in os.walk(chrome_path)
                            for filename in filenames
                        )
                        size_mb = profile_size / (1024 * 1024)
                        
                        logger.info(f"✅ Found system Chrome: {chrome_path} ({size_mb:.1f} MB)")
                        
                        profiles.append({
                            "name": f"System Chrome ({os.path.basename(chrome_path)})",
                            "path": chrome_path,
                            "type": "system_chrome",
                            "size_mb": size_mb
                        })
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Error analyzing system profile {chrome_path}: {e}")
                else:
                    logger.debug(f"❌ No Default profile in: {chrome_path}")
            else:
                logger.debug(f"❌ System path not found: {chrome_path}")
        
        logger.info(f"📊 Profile search complete: found {len(profiles)} profiles")
        return profiles
    
    def validate_profile(self, profile_path):
        """Validate that the profile contains authentication data"""
        default_dir = os.path.join(profile_path, "Default")
        
        if not os.path.exists(default_dir):
            return False, "No Default profile directory found"
        
        # Check for essential authentication files and directories
        essential_items = [
            ("Preferences", "file"),
            ("Login Data", "file"),
            ("Network/Cookies", "file"),
            ("Local Storage", "dir"),
            ("IndexedDB", "dir")
        ]
        
        missing_required = []
        found_items = []
        
        for item_name, item_type in essential_items:
            full_path = os.path.join(default_dir, item_name)
            
            if item_type == "file" and os.path.isfile(full_path):
                found_items.append(item_name)
            elif item_type == "dir" and os.path.isdir(full_path):
                found_items.append(item_name)
            else:
                missing_required.append(item_name)
        
        # Check for Local State at profile root
        local_state_path = os.path.join(profile_path, "Local State")
        if os.path.exists(local_state_path):
            found_items.append("Local State")
        else:
            missing_required.append("Local State")
        
        # Need at least Login Data and Network/Cookies for authentication
        critical_items = ["Login Data", "Network/Cookies"]
        missing_critical = [item for item in critical_items if item in missing_required]
        
        if missing_critical:
            return False, f"Missing critical auth files: {', '.join(missing_critical)}"
        
        return True, f"Valid profile with {len(found_items)} auth components: {', '.join(found_items)}"
    
    def create_profile_zip(self, profile_path):
        """Create a ZIP file of the Chrome profile with all essential components"""
        try:
            # Create temporary ZIP file
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_zip.close()
            
            logger.info(f"Creating profile ZIP from: {profile_path}")
            
            # Essential directories and files that MUST be included
            essential_items = [
                "Default/Cookies",
                "Default/Network/Cookies", 
                "Default/Local Storage",
                "Default/IndexedDB",
                "Default/Login Data",
                "Default/Preferences",
                "Default/Secure Preferences",
                "Default/Web Data",
                "Default/History",
                "Default/Sessions",
                "Local State"
            ]
            
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # First, ensure all essential items are included
                essential_added = []
                for essential_item in essential_items:
                    essential_path = os.path.join(profile_path, essential_item)
                    if os.path.exists(essential_path):
                        if os.path.isfile(essential_path):
                            zipf.write(essential_path, essential_item)
                            essential_added.append(essential_item)
                        elif os.path.isdir(essential_path):
                            # Add directory contents
                            for root, dirs, files in os.walk(essential_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, profile_path)
                                    try:
                                        zipf.write(file_path, arcname)
                                    except Exception as e:
                                        logger.warning(f"Could not add {file}: {e}")
                            essential_added.append(essential_item)
                
                logger.info(f"✅ Added {len(essential_added)} essential components")
                
                # Then add other profile files, excluding unnecessary ones
                for root, dirs, files in os.walk(profile_path):
                    # Skip some unnecessary directories to reduce size
                    dirs[:] = [d for d in dirs if d not in [
                        'Crashpad', 'ShaderCache', 'GPUCache', 'Code Cache',
                        'Service Worker', 'DawnCache', 'DawnWebGPUCache', 'optimization_guide_model_store',
                        'AutofillStrikeDatabase', 'BudgetDatabase', 'commerce_subscription_db'
                    ]]
                    
                    for file in files:
                        # Skip large unnecessary files
                        if file.endswith(('.log', '.tmp', '.lock', '.old', '-journal')):
                            continue
                        if file.startswith(('LOG', 'LOCK')):
                            continue
                            
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, profile_path)
                        
                        # Skip if already added as essential item
                        if any(arcname.startswith(essential) for essential in essential_items):
                            continue
                        
                        # Skip very large files (>50MB)
                        try:
                            if os.path.getsize(file_path) > 50 * 1024 * 1024:
                                logger.info(f"Skipping large file: {file}")
                                continue
                        except:
                            continue
                        
                        # Add to ZIP with relative path
                        try:
                            zipf.write(file_path, arcname)
                        except Exception as e:
                            logger.warning(f"Could not add {file}: {str(e)}")
                            continue
            
            # Check ZIP size
            zip_size = os.path.getsize(temp_zip.name)
            zip_size_mb = zip_size / (1024 * 1024)
            
            # Verify essential components are in the ZIP
            with zipfile.ZipFile(temp_zip.name, 'r') as zipf:
                zip_contents = zipf.namelist()
                missing_essential = []
                for item in essential_items:
                    if not any(path.startswith(item) for path in zip_contents):
                        missing_essential.append(item)
                
                if missing_essential:
                    logger.warning(f"⚠️ ZIP missing essential items: {missing_essential}")
                else:
                    logger.info("✅ All essential profile components included")
            
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
                    
                    # Skip cookies with empty values (causes Netscape format issues)
                    if not value or not name:
                        continue
                    
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