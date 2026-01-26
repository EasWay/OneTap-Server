# TikTok Mobile API Deployment Guide

This guide covers deploying the TikTok mobile API emulation system to production.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test the Implementation
```bash
# Test basic functionality
python test_tiktok_api.py

# Test with a real TikTok URL
python test_tiktok_api.py "https://vm.tiktok.com/ZMhQKqLDg/"
```

### 3. Start the Server
```bash
python server.py
```

### 4. Test API Endpoint
```bash
curl -X POST http://localhost:5000/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://vm.tiktok.com/ZMhQKqLDg/"}'
```

## 🌐 Production Deployment

### Render.com Deployment

1. **Update requirements.txt** (already done):
```txt
flask==3.0.0
flask-cors==4.0.0
yt-dlp @ git+https://github.com/yt-dlp/yt-dlp.git@master
requests==2.31.0
```

2. **Environment Variables**:
```bash
RENDER=true
PYTHON_VERSION=3.11
```

3. **Build Command**:
```bash
pip install -r requirements.txt
```

4. **Start Command**:
```bash
python server.py
```

### Heroku Deployment

1. **Create Procfile**:
```
web: python server.py
```

2. **Runtime specification** (runtime.txt):
```
python-3.11
```

3. **Deploy**:
```bash
git add .
git commit -m "Add TikTok mobile API emulation"
git push heroku main
```

### Docker Deployment

1. **Create Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "server.py"]
```

2. **Build and run**:
```bash
docker build -t onetap-server .
docker run -p 5000:5000 onetap-server
```

## ⚙️ Configuration

### Environment Variables

```bash
# Server configuration
PORT=5000
FLASK_ENV=production

# TikTok API settings
TIKTOK_RATE_LIMIT=1.0          # Minimum seconds between requests
TIKTOK_MAX_RETRIES=3           # Maximum retry attempts
TIKTOK_REQUEST_TIMEOUT=30      # Request timeout in seconds

# Logging
LOG_LEVEL=INFO
LOG_API_REQUESTS=true
LOG_DEVICE_FINGERPRINTS=false  # Set to true for debugging
LOG_SIGNATURES=false           # Set to true for debugging (security risk)

# Security
ENABLE_RATE_LIMITING=true
MAX_REQUESTS_PER_MINUTE=60
```

### Configuration Files

**tiktok_config.py** - Update these values regularly:
```python
TIKTOK_CONFIG = {
    "APP_VERSION": "34.1.2",        # Update when TikTok releases new version
    "VERSION_CODE": "2023401020",   # Update accordingly
    "BUILD_NUMBER": "34.1.2",       # Keep in sync with APP_VERSION
}
```

## 🔧 Monitoring and Maintenance

### Health Checks

1. **Basic health endpoint**:
```bash
curl http://your-server.com/health
```

2. **TikTok API test**:
```bash
curl -X POST http://your-server.com/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@test/video/7298573727421123845"}'
```

### Success Rate Monitoring

Add this to your monitoring dashboard:
```python
# Track success rates by extractor
success_rates = {
    "mobile_api": 0.95,
    "web_api": 0.70,
    "oembed": 0.50,
    "ytdlp": 0.30
}

# Alert if mobile API success rate drops below 80%
if success_rates["mobile_api"] < 0.80:
    send_alert("TikTok mobile API success rate low")
```

### Log Analysis

Monitor these patterns in your logs:
```bash
# Success patterns
grep "✅ TikTok extraction successful" server.log

# Failure patterns  
grep "❌ TikTok mobile API failed" server.log

# Rate limiting
grep "⚠️ Rate limited (429)" server.log

# Endpoint rotation
grep "🔄 TikTok API request to" server.log
```

## 🛡️ Security Considerations

### Rate Limiting

Implement application-level rate limiting:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["60 per minute"]
)

@app.route("/download", methods=["POST"])
@limiter.limit("10 per minute")
def download_video():
    # Your existing code
```

### Request Validation

Add input validation:
```python
def validate_tiktok_url(url):
    """Validate TikTok URL format"""
    import re
    patterns = [
        r"tiktok\.com/@[^/]+/video/\d+",
        r"vm\.tiktok\.com/[A-Za-z0-9]+",
        r"vt\.tiktok\.com/[A-Za-z0-9]+",
        r"tiktok\.com/t/[A-Za-z0-9]+"
    ]
    
    return any(re.search(pattern, url) for pattern in patterns)
```

### User Agent Rotation

Rotate User-Agents to avoid detection:
```python
def get_random_user_agent():
    """Get random mobile User-Agent"""
    user_agents = [
        "com.zhiliaoapp.musically/34.1.2 (Linux; U; Android 13; SM-G998B)",
        "com.zhiliaoapp.musically/34.1.2 (Linux; U; Android 14; Pixel 7 Pro)",
        "com.zhiliaoapp.musically/34.1.2 (Linux; U; Android 13; OnePlus 11)"
    ]
    return random.choice(user_agents)
```

## 📊 Performance Optimization

### Caching

Implement Redis caching for repeated requests:
```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_video_info(video_id, info, ttl=3600):
    """Cache video info for 1 hour"""
    redis_client.setex(f"tiktok:{video_id}", ttl, json.dumps(info))

def get_cached_video_info(video_id):
    """Get cached video info"""
    cached = redis_client.get(f"tiktok:{video_id}")
    return json.loads(cached) if cached else None
```

### Connection Pooling

Use connection pooling for better performance:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=retry_strategy
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session
```

### Async Processing

For high-volume deployments, consider async processing:
```python
import asyncio
import aiohttp

async def download_video_async(url):
    """Async video download"""
    async with aiohttp.ClientSession() as session:
        # Your async implementation
        pass
```

## 🔄 Update Procedures

### Regular Updates (Weekly)

1. **Check TikTok app version**:
```bash
# Check Google Play Store for latest version
# Update APP_VERSION in tiktok_config.py
```

2. **Test API endpoints**:
```bash
python test_tiktok_api.py
```

3. **Monitor success rates**:
```bash
# Check logs for declining success rates
grep "success_rate" server.log | tail -100
```

### Emergency Updates (When Blocked)

1. **Update API endpoints**:
```python
# Add new endpoints to tiktok_config.py
"BASE_URLS": [
    "https://api16-normal-c-useast1a.tiktokv.com",
    "https://api25-normal-c-useast1a.tiktokv.com",  # New endpoint
    # ... existing endpoints
]
```

2. **Update device fingerprints**:
```python
# Add new device models to tiktok_config.py
{
    "model": "Pixel 8 Pro",
    "brand": "google",
    "android_version": "14",
    # ... other properties
}
```

3. **Update signature algorithms**:
```python
# May require reverse engineering new TikTok app
def _generate_x_ss_stub(self, params_str):
    # Updated signature generation
    pass
```

## 🚨 Troubleshooting

### Common Issues

**High 403 Error Rate**
```bash
# Solution: Update device fingerprints and rotate endpoints
# Check logs for patterns:
grep "403" server.log | head -20
```

**Rate Limiting (429 Errors)**
```bash
# Solution: Increase delays between requests
# Update TIKTOK_RATE_LIMIT in config
```

**Invalid JSON Responses**
```bash
# Solution: API endpoint may have changed
# Test endpoints manually:
curl -H "User-Agent: ..." https://api16-normal-c-useast1a.tiktokv.com/aweme/v1/feed/
```

**Device Detection**
```bash
# Solution: Update device fingerprints
# Add more realistic device models and signatures
```

### Debug Mode

Enable debug logging for troubleshooting:
```python
# In tiktok_config.py
LOGGING_CONFIG = {
    "LOG_LEVEL": "DEBUG",
    "LOG_API_REQUESTS": True,
    "LOG_DEVICE_FINGERPRINTS": True,
    "LOG_SIGNATURES": True  # Only for debugging - security risk
}
```

### Performance Issues

**Slow Response Times**
```bash
# Check network latency to TikTok APIs
ping api16-normal-c-useast1a.tiktokv.com

# Monitor request times in logs
grep "response_time" server.log
```

**Memory Usage**
```bash
# Monitor memory usage
ps aux | grep python

# Check for memory leaks in device fingerprinting
```

## 📈 Scaling

### Horizontal Scaling

Deploy multiple instances behind a load balancer:
```yaml
# docker-compose.yml
version: '3.8'
services:
  onetap-server-1:
    build: .
    ports:
      - "5001:5000"
  
  onetap-server-2:
    build: .
    ports:
      - "5002:5000"
  
  nginx:
    image: nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### Database Integration

For user tracking and analytics:
```python
# Add database models
class TikTokRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    user_ip = db.Column(db.String(45), nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    extractor_used = db.Column(db.String(50))
    response_time = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

This deployment guide ensures your TikTok mobile API emulation runs reliably in production while maintaining high success rates and avoiding detection.