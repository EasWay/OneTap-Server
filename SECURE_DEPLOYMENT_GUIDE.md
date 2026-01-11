# 🔐 Secure Deployment Guide for OneTap Server

This guide shows you how to deploy your OneTap Server to Render while keeping your Google authentication secure.

## 🚨 The Problem

Your authenticated Google profile contains OAuth tokens that GitHub's security system blocks. We can't commit these files to Git, but we need them on Render for authentication.

## ✅ The Solution

We'll deploy the code to Render first, then securely upload your authentication data separately.

## 📋 Step-by-Step Deployment

### Step 1: Clean Git Repository

First, let's remove the sensitive files from Git and push the clean code:

```bash
# Remove sensitive files from Git tracking
git rm -r --cached authenticated_youtube_session/ || true
git rm -r --cached authenticated_youtube_session_complete_backup/ || true
git rm -r --cached youtube_profile/ || true
git rm -r --cached youtube_profile_backup/ || true
git rm -r --cached tldv_profile/ || true
git rm --cached google_cookies.txt || true
git rm --cached cookies.txt || true
git rm --cached *.db || true

# Commit the cleanup
git add .gitignore
git commit -m "Secure deployment: Remove sensitive authentication data from Git"

# Push to GitHub
git push origin main
```

### Step 2: Deploy to Render

1. **Create Render Service**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Choose the repository with your OneTap Server

2. **Configure Render Settings**:
   ```
   Name: onetap-server (or your preferred name)
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

### Step 3: Upload Your Authentication

Now we'll securely upload your Google authentication to Render:

```bash
# Run the profile uploader
python profile_uploader.py
```

The uploader will:
1. 🔍 Find your authenticated profile
2. 📦 Extract the necessary cookies
3. ⬆️ Upload them securely to your Render app
4. ✅ Verify the upload was successful

### Step 4: Test Your Deployment

Test your deployed server:

```bash
# Check server status
curl https://your-app-name.onrender.com/status

# Check authentication status
curl https://your-app-name.onrender.com/cookies_status

# Test a download
curl -X POST https://your-app-name.onrender.com/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

## 🔒 Security Features

### What's Protected:
- ✅ OAuth tokens never stored in Git
- ✅ Authentication data encrypted in transit
- ✅ Temporary storage on Render (not persistent)
- ✅ No sensitive data in your repository

### What's Uploaded:
- 🍪 YouTube/Google cookies only
- 📊 Session authentication data
- 🔐 Minimal required authentication info

## 🛠️ Troubleshooting

### Authentication Issues

If authentication fails on Render:

1. **Re-upload cookies**:
   ```bash
   python profile_uploader.py
   ```

2. **Check cookie status**:
   ```bash
   curl https://your-app-name.onrender.com/cookies_status
   ```

3. **Refresh your local authentication**:
   - Run your local profile manager
   - Re-authenticate with Google
   - Upload the new profile

### Render Deployment Issues

1. **Check logs** in Render Dashboard
2. **Verify environment variables**
3. **Check build/start commands**

### Cookie Expiration

Google cookies expire periodically. When they do:

1. **Re-authenticate locally**:
   ```bash
   # Use your local profile manager to refresh authentication
   python robust_profile_manager.py
   ```

2. **Upload fresh cookies**:
   ```bash
   python profile_uploader.py
   ```

## 🔄 Maintenance

### Regular Updates

1. **Update code**: Push changes to GitHub (Render auto-deploys)
2. **Refresh authentication**: Upload new cookies when needed
3. **Monitor status**: Check `/status` endpoint regularly

### Cookie Refresh Schedule

- Google cookies typically last 1-2 weeks
- Set up a reminder to refresh authentication
- Monitor your app for authentication failures

## 📱 Usage

Once deployed, your OneTap Server will be available at:
```
https://your-app-name.onrender.com
```

### API Endpoints:

- `GET /` - Server status
- `GET /status` - Detailed system status
- `GET /cookies_status` - Authentication status
- `POST /download` - Download videos
- `POST /upload_cookies` - Upload new cookies
- `GET /files/<filename>` - Download files

### Example Usage:

```javascript
// Download a video
fetch('https://your-app-name.onrender.com/download', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'https://www.youtube.com/watch?v=VIDEO_ID' })
})
.then(response => response.json())
.then(data => console.log(data));
```

## 🎉 Success!

Your OneTap Server is now securely deployed with:
- ✅ Maximum bot resistance
- ✅ Google authentication
- ✅ Secure token handling
- ✅ Production-ready performance

The authentication data stays secure while giving Render everything it needs to work with your Google account.