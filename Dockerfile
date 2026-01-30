FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV UV_PROJECT_ENVIRONMENT=/usr/local

WORKDIR /workspace

# Copy configuration files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-install-project --no-dev

# Install Playwright chromium browser
RUN playwright install chromium --with-deps

# Set default command
CMD ["bash"]