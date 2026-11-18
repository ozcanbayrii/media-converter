FROM python:3.11-slim

# Install system dependencies: ffmpeg (for audio/video conversion) and nodejs (for yt-dlp JS challenges)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create downloads folder
RUN mkdir -p downloads

EXPOSE 5000

ENV PORT=5000

CMD ["python", "server.py"]
