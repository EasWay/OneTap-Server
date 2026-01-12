# Use official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RENDER=true
ENV CHROME_BIN=/usr/bin/google-chrome
ENV DISPLAY=:99

# Install Chrome and dependencies for Selenium
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    xvfb \
    git \
    ffmpeg \
    gnupg \
    ca-certificates \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver using the new Chrome for Testing API
RUN CHROME_VERSION=$(google-chrome --version | cut -d " " -f3) \
    && echo "Chrome version: $CHROME_VERSION" \
    && CHROMEDRIVER_URL="https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json" \
    && CHROMEDRIVER_VERSION=$(curl -s "$CHROMEDRIVER_URL" | grep -o '"version":"[^"]*' | head -1 | cut -d'"' -f4) \
    && echo "ChromeDriver version: $CHROMEDRIVER_VERSION" \
    && wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64

# Install Deno (JavaScript runtime for yt-dlp)
RUN curl -fsSL https://deno.land/x/install/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . ./

# Create downloads folder
RUN mkdir -p downloads

# Expose port (Render uses PORT environment variable)
EXPOSE 10000

# Run the server
CMD ["python", "server.py"]