FROM python:3.9-slim

WORKDIR /app

# Install required system-level packages used by the app (tini for init handling, graphviz for visual generation, procps for process tools, sed for text ops)
RUN apt-get update && apt-get install -y \
    curl \
    tini \
    graphviz \
    procps \
    sed \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install all Python dependencies from the project's pinned requirements list
RUN pip install --no-cache-dir -r requirements.txt

# Create a dedicated non-root user/group with /app as home to avoid Streamlit write-permission issues
RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --gid 1000 --home /app appuser

COPY . .

# Configure Streamlit’s environment so it doesn't attempt to write telemetry or machine_id files in restricted directories
ENV HOME=/app
ENV STREAMLIT_GATHER_USAGE_STATS=false
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_ENABLE_GATHER_USAGE_STATS=false

# Normalize Windows-style CRLF endings if present to prevent shell execution errors
RUN sed -i 's/\r$//' /app/start.sh

# Ensure start script is executable and owned by the non-root runtime user
RUN chmod +x /app/start.sh && \
    chown -R appuser:appgroup /app

# Switch execution to the non-root user for security best practices
USER appuser

ENV PORT=8501

# Launch the container through the app's startup script
CMD ["/bin/sh", "-c", "/app/start.sh"]
