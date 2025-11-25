FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /workspace

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# install Playwright browsers
#RUN playwright install

# Install Camoufox stealth browser
RUN camoufox fetch

# Set default command
CMD ["bash"]