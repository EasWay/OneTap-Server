# Use official Python image
FROM python:3.11-slim

# Install Chrome and dependencies for Selenium
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    xvfb \
    git \
    ffmpeg \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (JavaScript runtime for yt-dlp)
RUN curl -fsSL https://deno.land/x/install/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy files
COPY requirements.txt ./
COPY server.py ./
COPY cookie_manager.py ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create downloads folder
RUN mkdir downloads

# Set Chrome options for headless operation
ENV CHROME_BIN=/usr/bin/google-chrome
ENV DISPLAY=:99

# Expose port
EXPOSE 5000

# Run the server
CMD ["python", "server.py"]