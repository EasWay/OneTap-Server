# OneTap Multi-Platform Video Downloader

A high-performance, streamlined video downloader for YouTube, TikTok, Facebook, Instagram, and Twitter/X. Built with Flask and yt-dlp, optimized for speed, efficiency, and quality.

## 🚀 Features

- **Multi-Platform Support**: YouTube, TikTok, Facebook, Instagram, Twitter/X
- **Authenticated Downloads**: Cookie-based authentication for private content
- **High Quality**: Best available quality with MP4 format
- **Fast Downloads**: Concurrent fragment downloads for speed
- **Production Ready**: Optimized for Render deployment
- **RESTful API**: Clean, simple API endpoints
- **Error Handling**: Comprehensive error messages and logging

## 📋 Supported Platforms

| Platform | Public Content | Private Content | Stories | Reels |
|----------|---------------|-----------------|---------|-------|
| YouTube | ✅ | ✅ (with cookies) | N/A | N/A |
| TikTok | ✅ | ✅ (with cookies) | ✅ | ✅ |
| Facebook | ✅ | ✅ (with cookies) | ✅ | ✅ |
| Instagram | ✅ | ✅ (with cookies) | ✅ | ✅ |
| Twitter/X | ✅ | ✅ (with cookies) | N/A | N/A |

## 🛠️ Quick Start

### Deploy to Render (Recommended)

1. Fork this repository
2. Create a Web Service on [Render](https://render.com)
3. Connect your GitHub repository
4. Deploy automatically with Docker
5. Upload cookies via API

### Local Development

```bash
# Clone and setup
git clone <your-repo>
cd OneTap-Server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run server
python server.py
```

## 🔑 Authentication Setup

Export cookies from your browser for each platform:

### Using Browser Extension (Recommended)
1. Install "Get cookies.txt LOCALLY" extension
2. Visit each platform while logged in:
   - youtube.com
   - tiktok.com
   - facebook.com
   - instagram.com
   - twitter.com
3. Export cookies as `social_cookies.txt`
4. Upload via API

### Upload Cookies
```bash
# Using the upload script
python upload_cookies.py https://your-app.onrender.com

# Or via curl
curl -X POST https://your-app.onrender.com/upload_cookies \
  -F "file=@social_cookies.txt"
```

## 📡 API Usage

### Download Video
```bash
curl -X POST https://your-app.onrender.com/download \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

**Response:**
```json
{
  "status": "success",
  "platform": "youtube",
  "title": "Video Title",
  "filename": "abc123_Video_Title.mp4",
  "download_url": "https://your-app.onrender.com/files/abc123_Video_Title.mp4",
  "duration": 212,
  "uploader": "Channel Name",
  "view_count": 1000000,
  "download_time": 8.45,
  "file_size_mb": 25.3
}
```

### Health Check
```bash
curl https://your-app.onrender.com/health
```

### Example URLs
```bash
# YouTube
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4w9WgXcQ

# TikTok
https://www.tiktok.com/@user/video/123456789
https://vm.tiktok.com/ZMhvw9wgX/

# Facebook
https://www.facebook.com/watch/?v=123456789
https://www.facebook.com/reel/123456789

# Instagram
https://www.instagram.com/reel/ABC123/
https://www.instagram.com/p/ABC123/

# Twitter
https://twitter.com/user/status/123456789
https://x.com/user/status/123456789
```

## 🔧 Configuration

### Environment Variables
- `PORT`: Server port (default: 10000)
- `RENDER`: Auto-detected for Render deployment

### Performance Settings
- **Concurrent Downloads**: 4 parallel fragments
- **Chunk Size**: 10MB for optimal streaming
- **Retries**: 5 attempts with exponential backoff
- **Timeout**: 30 seconds per request

## 🐛 Troubleshooting

### Common Issues

**"No cookies found"**
- Upload cookies using `/upload_cookies` endpoint
- Ensure cookies file is in Netscape format

**"Authentication required"**
- Cookies expired - export fresh cookies
- Make sure you're logged into the platform

**"Cannot parse data" (Facebook)**
- Handled automatically with fallback methods
- Try different URL format if persists

**"Connection timeout"**
- Free tier may spin down (wait 30s)
- Check Render service status

### Error Codes
- **401**: Authentication required (upload cookies)
- **404**: Content not available (private/deleted/geo-restricted)
- **400**: Unsupported URL format
- **500**: Server error (check logs)

## 📊 Performance

### Render Free Tier
- ✅ 750 hours/month free
- ✅ Automatic SSL & deployment
- ⚠️ Spins down after 15min inactivity
- ⚠️ 512MB RAM limit

### Optimization Features
- URL cleaning and normalization
- Platform-specific configurations
- Minimal resource usage
- Efficient error handling

## 🔒 Security

- Cookies stored securely on server
- No sensitive data in logs
- HTTPS-only communication
- Input validation on all endpoints

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Submit pull request

## 📄 License

MIT License - Free for personal and commercial use

---

**Built with ❤️ for seamless video downloading**