FROM python:3.11-slim

WORKDIR /app

# Install system deps for some Python packages (may need adjusting for heavy ML libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy repository
COPY . /app

# Install Python dependencies: include AI requirements and backend extras
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r ai/requirements.txt -r backend/requirements.txt

ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "backend.server:app"]
