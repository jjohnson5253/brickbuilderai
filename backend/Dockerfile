# Minimal Dockerfile for Railway deployment
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
        unzip \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Download and install LDraw library during build (avoids runtime download issues)
RUN mkdir -p /root/ldraw && \
    curl -A "Mozilla/5.0 (compatible; BrickAI/1.0)" -L \
    "https://library.ldraw.org/library/updates/complete.zip" -o /tmp/ldraw.zip && \
    unzip /tmp/ldraw.zip -d /root/ && \
    rm /tmp/ldraw.zip && \
    echo "✅ LDraw library installed at /root/ldraw"

# Copy project files (README.md is required for package build)
COPY . .

# Install Python dependencies
RUN uv sync --frozen

# Set application environment variables
ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE $PORT

# Make start script executable and use it
RUN chmod +x start.sh
CMD ["./start.sh"]