# Use official Python image
FROM python:3.11-slim

# Install Chrome and dependencies for Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

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