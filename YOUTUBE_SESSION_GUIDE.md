# YouTube Session Extension Guide

## How It Works

The YouTube session extension system automatically maintains your signed-in Google/YouTube session without needing to log in from scratch on headless servers.

## Setup Process

### 1. Upload Your Google Cookies
First, you need to get your signed-in Google cookies from your browser:

**Method A: Browser Extension**
- Install a cookie export extension (like "Get cookies.txt")
- Visit YouTube while signed in
- Export cookies in Netscape format
- Upload via `/update_google_cookies` endpoint

**Method B: Manual Export**
- Use browser developer tools (F12)
- Go to Application/Storage → Cookies
- Copy relevant Google/YouTube cookies
- Format as Netscape format

### 2. Upload Cookies to Server
```bash
curl -X POST -F "file=@your_google_cookies.txt" https://your-server.com/update_google_cookies
```

## Automation Schedule

### Automatic Extension (Default)
- **Interval**: Every 6 hours
- **Background Process**: Runs automatically when server starts
- **Trigger**: Checks every 30 minutes if extension is needed
- **Logging**: All activities logged with timestamps

### Manual Trigger
```bash
# Trigger immediate session extension
curl -X POST https://your-server.com/extend_youtube_session

# Check session status
curl https://your-server.com/youtube_session_status
```

## API Endpoints

### `/update_google_cookies` (POST)
Upload Google cookies file for YouTube session extension.

### `/extend_youtube_session` (POST)
Manually trigger YouTube session extension.

### `/youtube_session_status` (GET)
Check current session status:
```json
{
  "google_cookies_uploaded": true,
  "last_extension": "2024-01-10T15:30:00",
  "next_scheduled_extension": "2024-01-10T21:30:00",
  "extension_interval_hours": 6,
  "minutes_until_next": 180
}
```

## YouTube Download Behavior

### With Google Cookies (Signed-in)
- Uses your uploaded Google cookies
- Access to higher quality streams
- Can download age-restricted content (if your account allows)
- Bypasses some regional restrictions

### Without Google Cookies (Fallback)
- Uses `android_tv` client method
- Anonymous access only
- Limited to publicly available content

## Configuration

You can modify the extension interval in `server.py`:
```python
YOUTUBE_SESSION_INTERVAL_HOURS = 6  # Change this value
```

## Troubleshooting

### Session Extension Fails
1. Check if `google_cookies.txt` exists and is valid
2. Verify cookies aren't expired
3. Re-export and upload fresh cookies from browser

### No Automatic Extensions
1. Check server logs for scheduler errors
2. Ensure background thread is running
3. Verify file permissions on cookies file

## Security Notes

- Cookies contain sensitive authentication data
- Keep your cookies file secure
- Regularly refresh cookies (every few days)
- Monitor session status via API endpoint