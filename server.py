import os
import uuid
import time
import requests
import yt_dlp
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

# --- Selenium and WebDriver Imports for Cookie Generation ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
# -----------------------------------------------------------

# Load environment variables from .env file FIRST
# This is crucial for fixing the "not set" error
load_dotenv()

app = Flask(__name__)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")

# --- Environment Configuration ---
# Use os.getenv() for safe access. If missing, the app will log a warning.
INSTAGRAM_USERNAME = os.getenv("IG_USERNAME", "placeholder_user")
INSTAGRAM_PASSWORD = os.getenv("IG_PASSWORD", "placeholder_pass")
# ---------------------------------

@app.route("/")
def home():
    """Simple check to see if the server is running."""
    return "OneTap Server is running"

@app.route("/files/<path:filename>")
def serve_file(filename):
    """Serves the downloaded file."""
    return send_from_directory(DOWNLOAD_DIR, filename)

def generate_new_instagram_cookies():
    """
    Automates login using Selenium to generate a fresh cookies.txt file.
    This replaces the external logic and ensures environment variables are checked.
    """
    if INSTAGRAM_USERNAME == "placeholder_user" or INSTAGRAM_PASSWORD == "placeholder_pass":
        print("!!! WARNING: IG_USERNAME or IG_PASSWORD environment variables are NOT set. !!!")
        print("!!! This login attempt will likely fail. Please check your .env file or environment setup. !!!")
    
    print("\n--- Starting automated login to generate fresh cookies (Self-Healing) ---")

    options = Options()
    # Run in headless mode (no visible browser window)
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36")

    # Suppress console log spam from Chrome/GCM (like DEPRECATED_ENDPOINT)
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    try:
        # Use WebDriver Manager to automatically download the correct ChromeDriver
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        
        driver.get("https://www.instagram.com/accounts/login/")
        
        # Wait for the page to load and find the input fields
        time.sleep(5) 

        # Find and enter username
        driver.find_element(By.NAME, "username").send_keys(INSTAGRAM_USERNAME)
        
        # Find and enter password
        driver.find_element(By.NAME, "password").send_keys(INSTAGRAM_PASSWORD)

        # Find and click the login button
        driver.find_element(By.XPATH, "//button[contains(., 'Log in')]").click()

        # Wait for login processing and potential redirects
        time.sleep(10) 

        # Check if login was successful (e.g., if redirected away from login URL)
        if "login" not in driver.current_url:
            print("Login successful. Extracting session cookies...")
            
            # Extract cookies and save them in Netscape format for yt-dlp
            with open(COOKIES_FILE, "w") as f:
                f.write("# Netscape HTTP Cookie File\n# This is a generated file! Do not edit.\n\n")
                for cookie in driver.get_cookies():
                    if cookie.get('domain') and cookie.get('name') and cookie.get('value'):
                        # yt-dlp requires specific fields. We ensure they exist.
                        domain = cookie['domain'].replace('www.', '.')
                        # Netscape format fields:
                        # domain - flag - path - secure - expiration - name - value
                        f.write(
                            f"{domain}\t"
                            f"{'TRUE' if domain.startswith('.') else 'FALSE'}\t"
                            f"{cookie.get('path', '/')}\t"
                            f"{'TRUE' if cookie.get('secure') else 'FALSE'}\t"
                            f"{cookie.get('expiry', '0')}\t"
                            f"{cookie['name']}\t"
                            f"{cookie['value']}\n"
                        )
            print(f"Successfully saved fresh cookies to {COOKIES_FILE}")
        else:
            # If the URL still contains 'login', the login failed
            error_message = f"Login failed. Check credentials for user: {INSTAGRAM_USERNAME}. Current URL: {driver.current_url}"
            print(f"!!! ERROR: {error_message} !!!")
            # Clear the old, broken cookies file if it exists
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
                print(f"Old cookies file removed: {COOKIES_FILE}")
            raise Exception(error_message)

    except Exception as e:
        print(f"An error occurred during cookie generation: {e}")
        # Re-raise the exception to stop the server from starting with bad credentials
        raise
    finally:
        if 'driver' in locals():
            driver.quit()
        print("--- Cookie generation finished ---\n")

def run_download(url, cookies_retry=False):
    """Executes the yt-dlp download with a self-healing cookie check."""
    uid = str(uuid.uuid4())
    # Define a simple template path for the unique file name
    template_name = f"{uid}.%(ext)s"
    output_template = os.path.join(DOWNLOAD_DIR, template_name)

    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "retries": 3,
        "fragment_retries": 3,
        "quiet": True, # Keep quiet when running the server
        "noprogress": True,
        "extractor_args": {"instagram": ["--enable-test-suite"]}, # Use test suite for reliability
    }

    # Always use the cookie file if it exists
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Attempting download for: {url} (Cookie Retry: {cookies_retry})")
            
            # Use 'download=True' to perform the download
            info_dict = ydl.extract_info(url, download=True)
            
            if not info_dict:
                raise Exception("yt-dlp returned no information.")

            # --- FIX: Retrieve the actual file path used by yt-dlp ---
            # yt-dlp stores the final file path(s) in the info dictionary
            # For a single video download, the final file path is often stored 
            # under the '_filename' key for the merged file.
            final_path = info_dict.get('_filename')
            
            if not final_path:
                # Fallback path reconstruction if _filename is missing (e.g., if merge failed)
                ext = info_dict.get("ext", "mp4")
                filename = f"{uid}.{ext}"
                final_path = os.path.join(DOWNLOAD_DIR, filename)

            if not os.path.exists(final_path):
                # We need to look for files that match the UUID in case yt-dlp did not merge
                # This ensures we handle cases where the file extension might differ from 'mp4'
                files_found = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(uid) and os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
                
                if files_found:
                    # Pick the first one found that matches the UUID
                    filename = files_found[0]
                    final_path = os.path.join(DOWNLOAD_DIR, filename)
                else:
                    raise Exception(f"File not found after download (UUID: {uid}).")
            
            # Extract the simple filename from the full path
            filename = os.path.basename(final_path)

            print(f"Download successful. File: {filename}")

            # Return the public URL
            base_url = request.host_url.rstrip("/")
            download_url = f"{base_url}/files/{filename}"
            if download_url.startswith("http://"):
                download_url = download_url.replace("http://", "https://", 1)
            
            return download_url, None # Return download_url and no error

    except yt_dlp.utils.DownloadError as e:
        error_message = str(e)
        # Check for authentication failure indicator
        if "unable to download" in error_message.lower() or "need to log in" in error_message.lower():
            if not cookies_retry:
                print("Download failed due to authentication. Initiating cookie self-healing process...")
                try:
                    # Rerun cookie generation
                    generate_new_instagram_cookies()
                    # Re-attempt download
                    return run_download(url, cookies_retry=True) 
                except Exception as auth_e:
                    # If cookie generation or retry fails, return the original error
                    return None, f"Cookie self-healing failed: {auth_e}. Original error: {error_message}"
            else:
                # If it failed on the second attempt, the credentials are bad
                return None, f"Download failed twice (bad credentials). Error: {error_message}"
        else:
            # Handle non-authentication related download errors
            return None, f"Download Error: {error_message}"
    except Exception as e:
        # Handle general errors
        return None, f"General Error: {str(e)}"

@app.route("/download", methods=["POST"])
def download_video():
    """Endpoint for receiving the video URL and starting the download process."""
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    download_url, error = run_download(url)

    if download_url:
        return jsonify({"download_url": download_url})
    else:
        # If run_download returns None and an error message, use the error
        # The frontend expects a 500 error structure with the message in 'error'
        return jsonify({"error": error}), 500

# --- Server Startup Initialization ---
if __name__ == "__main__":
    # Ensure cookies are fresh or generated before the server starts
    if not os.path.exists(COOKIES_FILE):
        print(f"No cookies file found at {COOKIES_FILE}. Generating fresh cookies...")
        try:
            generate_new_instagram_cookies()
        except:
            print("Cookie generation failed on startup. Server will attempt to run, but downloads requiring Instagram login may fail.")
    else:
        print("Existing cookies.txt found. Server will start and assume cookies are valid.")
        print("They will be regenerated automatically if a download fails due to authentication.")

    # You can remove the 'host' and 'port' arguments if you prefer Flask's default settings.
    # The Debugger PIN is normal for development environments.
    app.run(host='0.0.0.0', port=5000, debug=True)
