# Use official Python image
FROM python:3.11-slim


# Set working directory
WORKDIR /app


# Copy files
COPY requirements.txt ./
COPY server.py ./


# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Create downloads folder
RUN mkdir downloads


# Expose port
EXPOSE 5000


# Run the server
CMD ["python", "server.py"]