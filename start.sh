#!/usr/bin/env bash
# start.sh — orchestrates the full defense environment: mutation engine,
# dual backend nodes, proxy layer, attacker simulator, and the dashboard.
set -euo pipefail

echo "🚀 Booting Chameleon Defense System..."

cleanup() {
    # Ensure every component shuts down cleanly, avoiding orphaned processes.
    echo "🛑 Shutting down Chameleon Defense System..."
    pkill -f "uvicorn dynamic_server:app" || true
    pkill -f "python -m core.proxy" || true
    pkill -f "python -m demo_scripts.hacker_bot" || true
    pkill -P $$ || true
    sleep 0.3
}
trap cleanup SIGINT SIGTERM

export PYTHONUNBUFFERED=1

# Initialize minimal Streamlit configuration so the dashboard can launch cleanly.
mkdir -p .streamlit
cat <<EOF > .streamlit/credentials.toml
[general]
email = ""
EOF

echo "🛠️ Generating initial mutation state..."
python -m core.mutator || true

# The mutator generates a runtime server module inside the project directory.
RUNTIME_MUTATED="target_app/active_server.py"

WAIT_SECONDS=0
MAX_WAIT=10
echo "[startup] Waiting for runtime mutated server at ${RUNTIME_MUTATED}..."

# Give the system a small buffer to allow the mutator to finish generating the file.
while [ ! -f "$RUNTIME_MUTATED" ] && [ $WAIT_SECONDS -lt $MAX_WAIT ]; do
    sleep 0.5
    WAIT_SECONDS=$((WAIT_SECONDS+1))
done

if [ -f "$RUNTIME_MUTATED" ]; then
    echo "[startup] Found mutated runtime server after ${WAIT_SECONDS} checks."
else
    echo "[startup][warning] Mutated runtime server not found at ${RUNTIME_MUTATED}. Proceeding..."
fi

echo "⚙️ Starting Server Node A..."
python -m uvicorn dynamic_server:app --port 8001 --host 0.0.0.0 &

echo "⚙️ Starting Server Node B..."
python -m uvicorn dynamic_server:app --port 8002 --host 0.0.0.0 &

echo "⚙️ Starting Proxy..."
python -m core.proxy &

echo "⏳ Waiting for subsystems to initialize..."
sleep 2

echo "🤖 Launching Hacker Bot..."
python -m demo_scripts.hacker_bot &
sleep 0.5

# All services log directly to Render stdout for real-time visibility.
echo "📡 Logs streaming directly to Render..."

PORT=${PORT:-10000}
echo "✅ Starting Dashboard on Port $PORT"

# Streamlit remains in the foreground as the primary visible service.
python -m streamlit run dashboard.py \
  --server.port $PORT \
  --server.enableCORS false \
  --server.address 0.0.0.0 \
  --server.headless true \
  --theme.base "dark"

# If Streamlit exits, the trap will capture the signal and perform cleanup.
