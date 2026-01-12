# Use official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RENDER=true
ENV DISPLAY=:99

# Install system dependencies including X11 for Chrome
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    git \
    ffmpeg \
    ca-certificates \
    xvfb \
    libxss1 \
    libappindicator1 \
    libindicator7 \
    libasound2 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgcc1 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome for Testing + matching ChromeDriver (deterministic versions)
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/122.0.6261.69/linux64/chrome-linux64.zip \
    && wget -q https://storage.googleapis.com/chrome-for-testing-public/122.0.6261.69/linux64/chromedriver-linux64.zip \
    && unzip chrome-linux64.zip -d /opt/ \
    && unzip chromedriver-linux64.zip -d /opt/ \
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome \
    && ln -s /opt/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/google-chrome /usr/bin/chromedriver \
    && rm chrome-linux64.zip chromedriver-linux64.zip

# Install Deno (JavaScript runtime for yt-dlp YouTube support)
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