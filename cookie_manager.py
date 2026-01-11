import os
import time
import pickle
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Define the path where the cookies will be saved (must match server.py)
COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")
GOOGLE_COOKIES_FILE = os.path.join(os.getcwd(), "google_cookies.txt")

def extend_google_youtube_session():
    """
    Extends an existing Google/YouTube session by loading uploaded cookies,
    refreshing the session, and saving updated tokens. This approach avoids
    the need to log in from scratch on headless servers.
    
    Returns:
        bool: True if session was successfully extended, False otherwise.
    """
    print("--- 🚀 Starting YouTube session extension ---")
    
    # Check if existing Google cookies file exists
    if not os.path.exists(GOOGLE_COOKIES_FILE):
        print(f"❌ No Google cookies found at {GOOGLE_COOKIES_FILE}")
        print("Please upload your Google cookies file first.")
        return False
    
    # Check if file is not empty
    try:
        file_size = os.path.getsize(GOOGLE_COOKIES_FILE)
        if file_size == 0:
            print(f"❌ Google cookies file is empty: {GOOGLE_COOKIES_FILE}")
            return False
        print(f"✅ Found Google cookies file ({file_size} bytes)")
    except Exception as e:
        print(f"❌ Error checking cookies file: {e}")
        return False
    
    # Setup Chrome options for ultra-minimal memory usage
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")  # Use new efficient headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")  # Don't load images to save memory
    chrome_options.add_argument("--disable-javascript")  # Disable JS initially
    chrome_options.add_argument("--memory-pressure-off")
    chrome_options.add_argument("--max_old_space_size=1024")  # Very conservative memory limit
    chrome_options.add_argument("--aggressive-cache-discard")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Disable stylesheets to save even more memory
    prefs = {
        "profile.managed_default_content_settings.stylesheets": 2
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Minimal user agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
    
    driver = None
    try:
        print("🔧 Initializing minimal Chrome WebDriver...")
        
        # Use webdriver-manager for automatic ChromeDriver management
        service = Service(ChromeDriverManager().install())
        
        # Create driver with minimal configuration
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ Chrome WebDriver created successfully")
        
        # Set aggressive timeouts
        driver.set_page_load_timeout(15)  # Very short timeout
        driver.implicitly_wait(3)  # Very short wait
        
        print("✅ Chrome WebDriver configured with timeouts")
        
    except Exception as e:
        print(f"❌ Error initializing WebDriver: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return False

    try:
        # Load existing cookies from file (this will handle navigation)
        print("🍪 Loading existing Google cookies...")
        cookies_loaded = load_cookies_from_file(driver, GOOGLE_COOKIES_FILE)
        
        if not cookies_loaded:
            print("❌ Failed to load existing cookies")
            return False
        
        print("✅ Cookies loaded successfully")
        
        # Lightweight verification - check if important cookies are present
        print("🔍 Verifying session cookies...")
        current_cookies = driver.get_cookies()
        
        # Look for key Google authentication cookies
        auth_cookies = ['SID', 'HSID', 'SSID', 'APISID', 'SAPISID']
        found_auth_cookies = [cookie['name'] for cookie in current_cookies if cookie['name'] in auth_cookies]
        
        print(f"🔑 Found {len(found_auth_cookies)} auth cookies: {found_auth_cookies}")
        
        if len(found_auth_cookies) >= 2:
            print("✅ Session verification successful")
        else:
            print("⚠️ Limited auth cookies found, but proceeding...")
        
        # Extract updated cookies directly (no additional navigation needed)
        print("📦 Extracting session cookies...")
        selenium_cookies = driver.get_cookies()
        print(f"📊 Found {len(selenium_cookies)} cookies")
        
        # Save updated cookies in Netscape format
        save_google_cookies_netscape(selenium_cookies)
        
        print(f"✅ Session extended and saved to {GOOGLE_COOKIES_FILE}")
        return True

    except Exception as e:
        print(f"❌ An error occurred during session extension: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False
    
    finally:
        if driver:
            try:
                print("🧹 Cleaning up Chrome WebDriver...")
                driver.quit()
            except Exception as quit_error:
                print(f"⚠️ Warning: Error closing driver: {quit_error}")
        print("--- 🏁 Session extension finished ---")

def load_cookies_from_file(driver, cookies_file):
    """
    Load cookies from Netscape format file into the browser.
    Uses domain-specific navigation and batched injection to avoid timeouts.
    
    Args:
        driver: Selenium WebDriver instance
        cookies_file (str): Path to cookies file
    
    Returns:
        bool: True if cookies were loaded successfully
    """
    print(f"📂 Reading cookies from {cookies_file}")
    try:
        with open(cookies_file, 'r') as f:
            lines = f.readlines()
        
        # Group cookies by specific domains for targeted injection
        domain_buckets = {
            'accounts.google.com': [],
            'google.com': [],
            'youtube.com': [],
            'googlevideo.com': [],
            'other_google': []
        }
        
        for line in lines:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 7:
                domain = parts[0].lstrip('.')
                path = parts[2]
                secure = parts[3] == 'TRUE'
                expiry = int(parts[4]) if parts[4] != '0' and parts[4].isdigit() else None
                name = parts[5]
                value = parts[6]
                
                # Only process Google/YouTube related domains
                google_domains = ['google.com', 'youtube.com', 'googlevideo.com', 'gstatic.com', 'googleapis.com']
                if any(gd in domain for gd in google_domains):
                    print(f"✅ Processing Google cookie: {domain} -> {name}")
                    
                    cookie_dict = {
                        'name': name,
                        'value': str(value),  # Ensure string type
                        'path': path,
                        'secure': secure
                    }
                    
                    # Handle domain normalization and __Host- prefix rules
                    if name.startswith('__Host-'):
                        # __Host- cookies must NOT have domain attribute
                        pass  # Don't set domain for __Host- cookies
                    else:
                        # Regular cookies get normalized domain
                        normalized_domain = domain if domain.startswith('.') else f'.{domain}'
                        cookie_dict['domain'] = normalized_domain
                    
                    if expiry and expiry > 0:
                        cookie_dict['expiry'] = expiry
                    
                    # Sort into appropriate bucket
                    if 'accounts.google' in domain:
                        domain_buckets['accounts.google.com'].append(cookie_dict)
                    elif 'youtube' in domain:
                        domain_buckets['youtube.com'].append(cookie_dict)
                    elif 'googlevideo' in domain:
                        domain_buckets['googlevideo.com'].append(cookie_dict)
                    elif 'google' in domain:
                        domain_buckets['google.com'].append(cookie_dict)
                    else:
                        domain_buckets['other_google'].append(cookie_dict)
        
        total_cookies_loaded = 0
        
        # Process each domain bucket with lightweight robots.txt navigation
        domain_urls = {
            'accounts.google.com': 'https://accounts.google.com/robots.txt',
            'google.com': 'https://google.com/robots.txt',
            'youtube.com': 'https://youtube.com/robots.txt',
            'googlevideo.com': 'https://youtube.com/robots.txt',  # Use YouTube robots.txt for googlevideo cookies
            'other_google': 'https://google.com/robots.txt'
        }
        
        for bucket_name, cookies in domain_buckets.items():
            if not cookies:
                continue
                
            try:
                target_url = domain_urls[bucket_name]
                print(f"🤖 Loading lightweight context: {target_url}")
                driver.get(target_url)
                time.sleep(0.5)  # Very minimal wait for text file
                
                # Inject cookies in very small batches to avoid timeouts
                batch_size = 5  # Reduced from 10
                cookies_injected = 0
                
                for i in range(0, len(cookies), batch_size):
                    batch = cookies[i:i + batch_size]
                    
                    for cookie in batch:
                        try:
                            driver.add_cookie(cookie)
                            cookies_injected += 1
                        except Exception:
                            # Silently skip failed cookies to avoid log flooding
                            pass
                    
                    # Small delay between batches
                    if i + batch_size < len(cookies):
                        time.sleep(0.5)
                
                print(f"✅ Injected {cookies_injected}/{len(cookies)} cookies for {bucket_name}")
                total_cookies_loaded += cookies_injected
                
            except Exception as domain_error:
                print(f"⚠️ Could not process {bucket_name}: {domain_error}")
                continue
        
        print(f"🎯 Total cookies successfully loaded: {total_cookies_loaded}")
        return total_cookies_loaded > 0
        
    except Exception as e:
        print(f"Error loading cookies from file: {e}")
        return False

def save_google_cookies_netscape(selenium_cookies):
    """
    Save Google cookies in Netscape format for yt-dlp compatibility.
    
    Args:
        selenium_cookies: List of cookies from Selenium
    """
    google_domains = ['google.com', 'youtube.com', 'googlevideo.com', 'gstatic.com']
    important_cookies = ['SAPISID', 'HSID', 'SSID', 'APISID', 'SID', '__Secure-3PAPISID', '__Secure-3PSID']
    
    with open(GOOGLE_COOKIES_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# Extended Google/YouTube session cookies\n\n")
        
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

def generate_new_instagram_cookies(username, password):
    """
    Automates login to Instagram using Selenium, extracts cookies, 
    and saves them in the Netscape format expected by yt-dlp.
    
    Args:
        username (str): Instagram username.
        password (str): Instagram password.
    
    Returns:
        bool: True if cookies were successfully saved, False otherwise.
    """
    print("--- Attempting automated login to generate fresh cookies ---")
    
    # 1. Setup Chrome options for headless execution
    # Headless is generally better for server environments
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--memory-pressure-off")
    chrome_options.add_argument("--max_old_space_size=4096")
    
    # Initialize the WebDriver using webdriver-manager
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        print("Please ensure Chrome is installed and accessible.")
        if driver:
            driver.quit()
        return False

    try:
        # 2. Navigate to the Instagram login page
        driver.get("https://www.instagram.com/accounts/login/")
        
        # Wait until the page loads and the username field is visible (max 20 seconds)
        wait = WebDriverWait(driver, 20)
        
        # Find the login form elements (names are stable)
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_field = driver.find_element(By.NAME, "password")
        
        # Fill credentials
        username_field.send_keys(username)
        password_field.send_keys(password)
        
        # Find and click the login button
        # The button often has a specific text or type='submit'
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        # 3. Wait for post-login page (e.g., the home feed or a profile page)
        # We wait until the URL changes from 'login' or a key element appears.
        # Instagram often shows a "Save Login Info?" prompt, we wait for that to pass.
        time.sleep(5) 
        
        # Check for successful login by verifying the URL
        if "login" in driver.current_url.lower():
            print("Login failed: URL did not change from login page.")
            return False
        
        print("Login successful. Extracting session cookies...")

        # 4. Extract all cookies
        selenium_cookies = driver.get_cookies()
        
        # 5. Convert Selenium cookies to Netscape format and save to cookies.txt
        # yt-dlp needs the Netscape format, which is manually crafted here.
        with open(COOKIES_FILE, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file was automatically generated by cookie_manager.py\n\n")
            
            for cookie in selenium_cookies:
                # We only care about Instagram cookies that are useful for authentication
                if "instagram.com" in cookie.get('domain', '') and 'sessionid' in cookie.get('name', '').lower():
                    # Format: domain, flag, path, secure, expiration, name, value
                    domain = cookie.get('domain').lstrip('.')
                    secure_flag = 'TRUE' if cookie.get('secure') else 'FALSE'
                    expiry = cookie.get('expiry', 0) # Use 0 if no expiry is set
                    
                    line = (
                        f".{domain}\tTRUE\t{cookie.get('path', '/')}\t"
                        f"{secure_flag}\t{expiry}\t"
                        f"{cookie['name']}\t{cookie['value']}\n"
                    )
                    f.write(line)

        print(f"Successfully saved fresh cookies to {COOKIES_FILE}")
        return True

    except Exception as e:
        print(f"An error occurred during cookie generation: {e}")
        return False
    
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as quit_error:
                print(f"Warning: Error closing driver: {quit_error}")
        print("--- Cookie generation finished ---")

if __name__ == "__main__":
    # Example usage when running standalone
    IG_USERNAME = os.environ.get("IG_USERNAME", "placeholder_user")
    IG_PASSWORD = os.environ.get("IG_PASSWORD", "placeholder_password")
    
    # Check if we should extend Google session or generate Instagram cookies
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "google":
        print("Running Google/YouTube session extension...")
        extend_google_youtube_session()
    else:
        print("Running Instagram cookie generation...")
        if IG_USERNAME == "placeholder_user":
            print("WARNING: IG_USERNAME environment variable not set. Using placeholder credentials.")
            print("Please set IG_USERNAME and IG_PASSWORD before deploying.")
        
        generate_new_instagram_cookies(IG_USERNAME, IG_PASSWORD)