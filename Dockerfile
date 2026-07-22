# Use official Python image
FROM python:3.11-slim

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Prevent Python buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Flask port
EXPOSE 5050

# Run Flask app
CMD ["python", "run.py"]