#!/usr/bin/env python3
"""
Chrome Profile ZIP Creator
Creates a ZIP file of your Chrome profile for upload to Render
"""

import os
import zipfile
import tempfile
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_chrome_profiles():
    """Find available Chrome profiles"""
    profiles = []
    
    # Local authenticated profiles
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
                "type": "local"
            })
    
    return profiles

def validate_profile(profile_path):
    """Check if profile has authentication data"""
    default_dir = os.path.join(profile_path, "Default")
    
    if not os.path.exists(default_dir):
        return False, "No Default directory found"
    
    # Check for key files
    key_files = ["Preferences", "Login Data"]
    missing = []
    
    for file_name in key_files:
        if not os.path.exists(os.path.join(default_dir, file_name)):
            missing.append(file_name)
    
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    
    return True, "Profile looks good"

def create_profile_zip(profile_path, output_path):
    """Create ZIP file of Chrome profile with all essential components"""
    try:
        logger.info(f"Creating ZIP: {output_path}")
        
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
            "Default/Local State",
            "Local State"
        ]
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # First, ensure all essential items are included
            for essential_item in essential_items:
                essential_path = os.path.join(profile_path, essential_item)
                if os.path.exists(essential_path):
                    if os.path.isfile(essential_path):
                        zipf.write(essential_path, essential_item)
                        logger.info(f"✅ Added essential file: {essential_item}")
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
                        logger.info(f"✅ Added essential directory: {essential_item}")
                else:
                    logger.warning(f"⚠️ Missing essential item: {essential_item}")
            
            # Then add other profile files, excluding unnecessary ones
            for root, dirs, files in os.walk(profile_path):
                # Skip unnecessary directories but keep essential ones
                dirs[:] = [d for d in dirs if d not in [
                    'Crashpad', 'ShaderCache', 'GPUCache', 'Code Cache',
                    'Service Worker', 'DawnCache', 'DawnWebGPUCache',
                    'optimization_guide_model_store', 'AutofillStrikeDatabase'
                ]]
                
                for file in files:
                    # Skip unnecessary files
                    if file.endswith(('.log', '.tmp', '.lock', '.old', '-journal')):
                        continue
                    if file.startswith(('LOG', 'LOCK')):
                        continue
                    
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, profile_path)
                    
                    # Skip if already added as essential item
                    if arcname in essential_items:
                        continue
                    
                    # Skip very large files
                    try:
                        if os.path.getsize(file_path) > 50 * 1024 * 1024:  # 50MB
                            logger.info(f"Skipping large file: {file}")
                            continue
                    except:
                        continue
                    
                    # Add to ZIP
                    try:
                        zipf.write(file_path, arcname)
                    except Exception as e:
                        logger.warning(f"Could not add {file}: {e}")
        
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"ZIP created: {size_mb:.1f} MB")
        
        # Verify essential components are in the ZIP
        with zipfile.ZipFile(output_path, 'r') as zipf:
            zip_contents = zipf.namelist()
            missing_essential = []
            for item in essential_items:
                if not any(path.startswith(item) for path in zip_contents):
                    missing_essential.append(item)
            
            if missing_essential:
                logger.warning(f"⚠️ ZIP missing essential items: {missing_essential}")
            else:
                logger.info("✅ All essential profile components included")
        
        return True, size_mb
        
    except Exception as e:
        logger.error(f"Failed to create ZIP: {e}")
        return False, 0

def main():
    print("🚀 Chrome Profile ZIP Creator")
    print("=" * 40)
    
    # Find profiles
    profiles = find_chrome_profiles()
    
    if not profiles:
        print("❌ No Chrome profiles found!")
        print("Make sure you have a profile in one of these directories:")
        print("- authenticated_youtube_session")
        print("- youtube_profile")
        print("- tldv_profile")
        return
    
    # Show available profiles
    print(f"\n📁 Found {len(profiles)} profile(s):")
    for i, profile in enumerate(profiles):
        valid, msg = validate_profile(profile["path"])
        status = "✅" if valid else "❌"
        print(f"  {i+1}. {profile['name']} {status} - {msg}")
    
    # Select profile
    if len(profiles) == 1:
        selected = profiles[0]
    else:
        while True:
            try:
                choice = int(input(f"\nSelect profile (1-{len(profiles)}): ")) - 1
                if 0 <= choice < len(profiles):
                    selected = profiles[choice]
                    break
                else:
                    print("Invalid choice!")
            except ValueError:
                print("Please enter a number!")
    
    # Validate selection
    valid, msg = validate_profile(selected["path"])
    if not valid:
        print(f"❌ Profile invalid: {msg}")
        return
    
    print(f"✅ Selected: {selected['name']}")
    
    # Create ZIP
    output_file = f"{selected['name']}_profile.zip"
    print(f"\n📦 Creating ZIP file: {output_file}")
    
    success, size_mb = create_profile_zip(selected["path"], output_file)
    
    if success:
        print(f"✅ ZIP created successfully!")
        print(f"   File: {output_file}")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"\n📤 Upload this file using:")
        print(f"   python profile_uploader.py")
        print(f"   Or upload directly to /upload_profile endpoint")
    else:
        print("❌ Failed to create ZIP file")

if __name__ == "__main__":
    main()