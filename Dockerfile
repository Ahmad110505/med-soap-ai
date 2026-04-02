# 1. Use an official, lightweight Python image
FROM python:3.11-slim

# 2. Install system dependencies (CRITICAL: ffmpeg is required by Whisper for audio)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy the requirements file first (This makes future rebuilds 10x faster)
COPY requirements.txt .

# 5. Install the Python packages
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of your application code
COPY . .

# 7. Expose the port your app runs on
EXPOSE 8000

# 8. Command to run the application (Must be 0.0.0.0 to work outside the container!)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 7860"]