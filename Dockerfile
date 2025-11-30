# Dockerfile - Corrected for Render.com
FROM python:3.11-slim

# Install tini (signal handling), graphviz (dashboard), and procps (for pkill in start.sh)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    graphviz \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN useradd --create-home appuser
WORKDIR /app

# Copy files
COPY . /app

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Ensure start script is executable
RUN chmod +x /app/start.sh

# Use Tini as the entrypoint
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
