# 🔐 Secure Multi-Platform Video Downloader

This guide shows you how to deploy your OneTap Multi-Platform Server to Render while keeping your authentication secure.

## 🎬 Supported Platforms

- **YouTube** - High quality, age-restricted content, private videos
- **TikTok** - HD videos, private accounts with cookies
- **Facebook** - Public and private videos, stories
- **Instagram** - Posts, stories, reels, IGTV
- **Twitter/X** - Video tweets, spaces recordings
- **Twitch** - VODs, clips, highlights
- **Vimeo** - Public videos, password-protected content
- **Dailymotion** - Public videos, HD quality

## 🚨 The Problem

Your authenticated profiles contain OAuth tokens that GitHub's security system blocks. We can't commit these files to Git, but we need them on Render for authentication.

## ✅ The Solution

We'll deploy the code to Render first, then securely upload your authentication data separately for each platform.

## 📋 Step-by-Step Deployment

### Step 1: Clean Git Repository

The sensitive files have already been removed from Git tracking and the clean code is ready for deployment.

### Step 2: Deploy to Render

1. **Create Render Service**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Choose the repository with your OneTap Server

2. **Configure Render Settings**:
   ```
   Name: onetap-multi-platform-server
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python server.py
   ```

3. **Add Environment Variables** (Optional):
   ```
   RENDER=true
   ```

4. **Deploy**: Click "Create Web Service"

Wait for the deployment to complete. You'll get a URL like `https://your-app-name.onrender.com`

### Step 3: Upload Platform-Specific Cookies

Now we'll securely upload cookies for different platforms:

#### For YouTube:
```bash
# Upload Google/YouTube cookies
curl -X POST https://your-app-name.onrender.com/upload_google_cookies \
  -F "file=@google_cookies.txt"
```

#### For Social Media (TikTok, Facebook, Instagram, Twitter):
```bash
# Upload social media cookies
curl -X POST https://your-app-name.onrender.com/upload_social_cookies \
  -F "file=@social_cookies.txt"
```

#### Alternative: Use the profile uploader
```bash
# Run the profile uploader (works with any platform)
python profile_uploader.py
```

### Step 4: Test Your Deployment

Test your deployed server with different platforms:

#### YouTube:
```bash
curl -X POST https://your-app-name.onrender.com/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

#### TikTok:
```bash
curl -X POST https://your-app-name.onrender.com/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/VIDEO_ID"}'
```

#### Instagram:
```bash
curl -X POST https://your-app-name.onrender.com/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/p/POST_ID/"}'
```

#### Facebook:
```bash
curl -X POST https://your-app-name.onrender.com/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.facebook.com/watch/?v=VIDEO_ID"}'
```

#### Twitter/X:
```bash
curl -X POST https://your-app-name.onrender.com/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://twitter.com/user/status/TWEET_ID"}'
```

## 🔒 Security Features

### What's Protected:
- ✅ OAuth tokens never stored in Git
- ✅ Platform-specific cookie separation
- ✅ Authentication data encrypted in transit
- ✅ Temporary storage on Render (not persistent)
- ✅ No sensitive data in your repository

### What's Uploaded:
- 🍪 YouTube/Google cookies for YouTube access
- 🍪 Social media cookies for TikTok, Facebook, Instagram, Twitter
- 📊 Session authentication data per platform
- 🔐 Minimal required authentication info

## 🛠️ Troubleshooting

### Platform-Specific Issues

#### YouTube Issues:
1. **Re-upload Google cookies**:
   ```bash
   curl -X POST https://your-app-name.onrender.com/upload_google_cookies \
     -F "file=@google_cookies.txt"
   ```

2. **Check Deno availability**:
   ```bash
   curl https://your-app-name.onrender.com/status
   ```

#### Social Media Issues:
1. **Re-upload social cookies**:
   ```bash
   curl -X POST https://your-app-name.onrender.com/upload_social_cookies \
     -F "file=@social_cookies.txt"
   ```

2. **Check platform support**:
   ```bash
   curl https://your-app-name.onrender.com/platforms
   ```

### General Troubleshooting:

1. **Check overall status**:
   ```bash
   curl https://your-app-name.onrender.com/status
   ```

2. **Check cookie status**:
   ```bash
   curl https://your-app-name.onrender.com/cookies_status
   ```

3. **View supported platforms**:
   ```bash
   curl https://your-app-name.onrender.com/platforms
   ```

### Cookie Expiration

Platform cookies expire periodically. When they do:

1. **Re-authenticate locally** for the specific platform
2. **Export fresh cookies** using your browser's developer tools
3. **Upload new cookies** using the appropriate endpoint

## 🔄 Maintenance

### Regular Updates

1. **Update code**: Push changes to GitHub (Render auto-deploys)
2. **Refresh authentication**: Upload new cookies when needed per platform
3. **Monitor status**: Check `/status` endpoint regularly

### Cookie Refresh Schedule

- **YouTube**: Google cookies typically last 1-2 weeks
- **Social Media**: Platform cookies vary (1-4 weeks typically)
- Set up reminders to refresh authentication
- Monitor your app for authentication failures

## 📱 API Usage

Once deployed, your OneTap Multi-Platform Server will be available at:
```
https://your-app-name.onrender.com
```

### API Endpoints:

#### Core Endpoints:
- `GET /` - Server status and supported platforms
- `GET /status` - Detailed system status
- `GET /platforms` - List all supported platforms
- `POST /download` - Download videos from any supported platform

#### Cookie Management:
- `POST /upload_google_cookies` - Upload YouTube/Google cookies
- `POST /upload_social_cookies` - Upload social media cookies
- `POST /upload_cookies` - Upload general cookies (backward compatibility)
- `GET /cookies_status` - Check authentication status for all platforms

#### File Access:
- `GET /files/<filename>` - Download processed files

### Example Usage:

```javascript
// Download from any supported platform
async function downloadVideo(url) {
  const response = await fetch('https://your-app-name.onrender.com/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: url })
  });
  
  const result = await response.json();
  
  if (result.status === 'success') {
    console.log(`Downloaded: ${result.title}`);
    console.log(`Platform: ${result.platform}`);
    console.log(`Download URL: ${result.download_url}`);
  } else {
    console.error(`Error: ${result.error}`);
  }
}

// Examples for different platforms
downloadVideo('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
downloadVideo('https://www.tiktok.com/@user/video/1234567890');
downloadVideo('https://www.instagram.com/p/ABC123/');
downloadVideo('https://www.facebook.com/watch/?v=1234567890');
downloadVideo('https://twitter.com/user/status/1234567890');
```

## 🎉 Success!

Your OneTap Multi-Platform Server is now securely deployed with:
- ✅ Support for 8+ video platforms
- ✅ Platform-specific optimizations
- ✅ Secure cookie management
- ✅ Maximum bot resistance per platform
- ✅ Production-ready performance

The authentication data stays secure while giving Render everything it needs to work with multiple video platforms.