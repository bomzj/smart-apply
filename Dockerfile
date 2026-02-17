# Use the official Python 3.14.2 slim image
FROM python:3.14.2-slim-noble

# Install system dependencies for Chromium and headless browsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    ffmpeg \
    fonts-liberation \
    libasound2 \
    libnss3 \
    libxss1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV UV_PROJECT_ENVIRONMENT=/usr/local
# Ensure Pydoll can find the system Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_PATH=/usr/lib/chromium/

WORKDIR /workspace

# Copy configuration files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of your application
COPY . .

# Set default command
CMD ["bash"]