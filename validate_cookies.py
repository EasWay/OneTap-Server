#!/usr/bin/env python3
"""
Cookie validation script to check cookie file format and content
"""

import os
import sys

def validate_cookie_file(file_path):
    """Validate a Netscape format cookie file"""
    
    if not os.path.exists(file_path):
        print(f"❌ Cookie file not found: {file_path}")
        return False
    
    file_size = os.path.getsize(file_path)
    print(f"📁 Cookie file: {file_path} ({file_size} bytes)")
    
    if file_size == 0:
        print("❌ Cookie file is empty")
        return False
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        print(f"📄 Total lines: {len(lines)}")
        
        # Count different types of lines
        comment_lines = 0
        empty_lines = 0
        cookie_lines = 0
        invalid_lines = 0
        
        domains = set()
        cookie_names = set()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            if not line:
                empty_lines += 1
                continue
            
            if line.startswith('#'):
                comment_lines += 1
                continue
            
            # Try to parse as cookie
            parts = line.split('\t')
            if len(parts) >= 7:
                cookie_lines += 1
                domain = parts[0].lstrip('.')
                name = parts[5]
                
                domains.add(domain)
                cookie_names.add(name)
                
                # Check for Google/YouTube domains
                google_domains = ['google.com', 'youtube.com', 'googlevideo.com', 'gstatic.com', 'googleapis.com']
                is_google = any(gd in domain for gd in google_domains)
                
                if i <= 10 or is_google:  # Show first 10 lines or Google cookies
                    print(f"   Line {i}: {domain} -> {name}")
            else:
                invalid_lines += 1
                print(f"   ⚠️ Invalid line {i}: {line[:50]}...")
        
        print(f"\n📊 Summary:")
        print(f"   Comment lines: {comment_lines}")
        print(f"   Empty lines: {empty_lines}")
        print(f"   Valid cookies: {cookie_lines}")
        print(f"   Invalid lines: {invalid_lines}")
        
        print(f"\n🌐 Domains found ({len(domains)}):")
        for domain in sorted(domains):
            google_domains = ['google.com', 'youtube.com', 'googlevideo.com', 'gstatic.com', 'googleapis.com']
            is_google = any(gd in domain for gd in google_domains)
            marker = "🎯" if is_google else "  "
            print(f"   {marker} {domain}")
        
        print(f"\n🍪 Important cookie names found:")
        important_cookies = ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID', '__Secure-3PAPISID', '__Secure-3PSID', 'sessionid']
        host_cookies = []
        secure_cookies = []
        
        for cookie_name in cookie_names:
            if cookie_name.startswith('__Host-'):
                host_cookies.append(cookie_name)
            elif cookie_name.startswith('__Secure-'):
                secure_cookies.append(cookie_name)
        
        for cookie_name in important_cookies:
            if cookie_name in cookie_names:
                print(f"   ✅ {cookie_name}")
            else:
                print(f"   ❌ {cookie_name} (missing)")
        
        if host_cookies:
            print(f"\n🔒 __Host- cookies found ({len(host_cookies)}):")
            for cookie in host_cookies[:5]:  # Show first 5
                print(f"   🔐 {cookie}")
            if len(host_cookies) > 5:
                print(f"   ... and {len(host_cookies) - 5} more")
        
        if secure_cookies:
            print(f"\n🛡️ __Secure- cookies found ({len(secure_cookies)}):")
            for cookie in secure_cookies[:5]:  # Show first 5
                print(f"   🔒 {cookie}")
            if len(secure_cookies) > 5:
                print(f"   ... and {len(secure_cookies) - 5} more")
        
        # Check for Google authentication cookies
        google_auth_cookies = ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID']
        google_cookies_found = sum(1 for cookie in google_auth_cookies if cookie in cookie_names)
        
        if google_cookies_found >= 3:
            print(f"\n✅ Good: Found {google_cookies_found}/5 Google auth cookies")
            return True
        else:
            print(f"\n⚠️ Warning: Only found {google_cookies_found}/5 Google auth cookies")
            print("   You may need to re-export cookies while signed into Google/YouTube")
            return False
            
    except Exception as e:
        print(f"❌ Error reading cookie file: {e}")
        return False

def main():
    """Main function"""
    if len(sys.argv) > 1:
        cookie_file = sys.argv[1]
    else:
        # Check common cookie file locations
        possible_files = [
            'google_cookies.txt',
            'cookies.txt',
            'youtube_cookies.txt'
        ]
        
        cookie_file = None
        for file_path in possible_files:
            if os.path.exists(file_path):
                cookie_file = file_path
                break
        
        if not cookie_file:
            print("❌ No cookie file found. Usage:")
            print("   python validate_cookies.py <cookie_file.txt>")
            print("   or place cookies in: google_cookies.txt")
            return
    
    print("🔍 Cookie File Validator")
    print("=" * 50)
    
    is_valid = validate_cookie_file(cookie_file)
    
    print("\n" + "=" * 50)
    if is_valid:
        print("✅ Cookie file appears valid for YouTube session extension")
    else:
        print("⚠️ Cookie file may have issues - check the warnings above")
    
    print("\n💡 Tips:")
    print("1. Export cookies while signed into YouTube")
    print("2. Use Netscape format (tab-separated)")
    print("3. Include Google authentication cookies (SAPISID, HSID, etc.)")
    print("4. Avoid including non-Google cookies to reduce errors")

if __name__ == "__main__":
    main()