FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY ai/requirements.txt ./ai/requirements.txt
RUN pip install --no-cache-dir -r ai/requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn pydantic python-dotenv structlog tenacity circuitbreaker flask-cors

# Copy only necessary folders
COPY ai/ ./ai/
COPY backend/ ./backend/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "backend/main.py"]
