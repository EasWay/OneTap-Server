# Use official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RENDER=true

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

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
