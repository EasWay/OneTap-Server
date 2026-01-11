#!/usr/bin/env python3
"""
Secure Authentication Manager for Render Deployment
Handles YouTube authentication without storing sensitive data in Git
"""

import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecureAuthManager:
    def __init__(self):
        self.profile_path = "/tmp/chrome_profile"  # Use temp directory on Render
        self.cookies_file = "/tmp/youtube_cookies.json"
        
    def setup_chrome_options(self):
        """Setup Chrome options for Render environment"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--disable-extensions')
        options.add_argument(f'--user-data-dir={self.profile_path}')
        
        # Add mobile user agent to avoid bot detection
        options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15')
        
        return options
    
    def authenticate_with_credentials(self):
        """Authenticate using environment variables"""
        email = os.getenv('YOUTUBE_EMAIL')
        password = os.getenv('YOUTUBE_PASSWORD')
        
        if not email or not password:
            logger.error("YouTube credentials not found in environment variables")
            return False
            
        try:
            options = self.setup_chrome_options()
            driver = webdriver.Chrome(options=options)
            
            # Navigate to YouTube sign-in
            driver.get('https://accounts.google.com/signin')
            time.sleep(3)
            
            # Enter email
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            email_input.send_keys(email)
            
            # Click next
            next_button = driver.find_element(By.ID, "identifierNext")
            next_button.click()
            time.sleep(3)
            
            # Enter password
            password_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.NAME, "password"))
            )
            password_input.send_keys(password)
            
            # Click next
            password_next = driver.find_element(By.ID, "passwordNext")
            password_next.click()
            time.sleep(5)
            
            # Navigate to YouTube to verify authentication
            driver.get('https://www.youtube.com')
            time.sleep(3)
            
            # Save cookies for future use
            self.save_cookies(driver)
            
            driver.quit()
            logger.info("Authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False
    
    def save_cookies(self, driver):
        """Save cookies to file for session persistence"""
        try:
            cookies = driver.get_cookies()
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies, f)
            logger.info("Cookies saved successfully")
        except Exception as e:
            logger.error(f"Failed to save cookies: {str(e)}")
    
    def load_cookies(self, driver):
        """Load saved cookies"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'r') as f:
                    cookies = json.load(f)
                
                driver.get('https://www.youtube.com')
                for cookie in cookies:
                    driver.add_cookie(cookie)
                
                driver.refresh()
                logger.info("Cookies loaded successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to load cookies: {str(e)}")
        return False
    
    def get_authenticated_driver(self):
        """Get an authenticated Chrome driver"""
        options = self.setup_chrome_options()
        driver = webdriver.Chrome(options=options)
        
        # Try to load existing cookies first
        if self.load_cookies(driver):
            return driver
        
        # If cookies don't work, authenticate fresh
        driver.quit()
        if self.authenticate_with_credentials():
            driver = webdriver.Chrome(options=options)
            self.load_cookies(driver)
            return driver
        
        return None
    
    def verify_authentication(self, driver):
        """Verify that the user is authenticated on YouTube"""
        try:
            driver.get('https://www.youtube.com')
            time.sleep(3)
            
            # Check for sign-in button (if present, not authenticated)
            sign_in_elements = driver.find_elements(By.XPATH, "//a[contains(@aria-label, 'Sign in')]")
            
            if sign_in_elements:
                logger.warning("User not authenticated")
                return False
            
            # Check for user avatar or account menu
            avatar_elements = driver.find_elements(By.ID, "avatar-btn")
            if avatar_elements:
                logger.info("User is authenticated")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Authentication verification failed: {str(e)}")
            return False

# Usage example
if __name__ == "__main__":
    auth_manager = SecureAuthManager()
    driver = auth_manager.get_authenticated_driver()
    
    if driver and auth_manager.verify_authentication(driver):
        print("Successfully authenticated!")
        # Use the driver for YouTube operations
        driver.quit()
    else:
        print("Authentication failed!")