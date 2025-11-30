#!/usr/bin/env bash
# Upgraded Render-safe start script (replaces the original start.sh)
# Preserves original messages and flow while making runtime files /tmp-based
set -euo pipefail

echo "🚀 Booting Chameleon Defense System..."

# Handles graceful shutdowns so the platform (Render/Docker/etc.) doesn’t leave orphan processes behind.
cleanup() {
    echo "🛑 Shutting down Chameleon Defense System..."
    pkill -P $$ || true
}
trap cleanup SIGINT SIGTERM

# Ensure Python outputs are unbuffered so logs stream immediately
export PYTHONUNBUFFERED=1

# Streamlit needs a credentials file even in headless mode.
# We create the directory manually to avoid permission issues inside containers.
mkdir -p .streamlit
cat <<EOF > .streamlit/credentials.toml
[general]
email = ""
EOF

# Before launching anything, generate the first mutation cycle so both nodes
# start with a consistent route map. Without this, the system would boot
# with stale or mismatched endpoints.
echo "🛠️ Generating initial mutation state..."
# Use python -m to be robust across environments
python -m core.mutator || true

# Wait for the runtime mutated server to exist in /tmp (mutator writes /tmp/active_server.py)
RUNTIME_MUTATED="/tmp/active_server.py"
MUTATION_STATE="/tmp/mutation_state.json"
WAIT_SECONDS=0
MAX_WAIT=10

echo "[startup] Waiting for runtime mutated server at ${RUNTIME_MUTATED} ..."
while [ ! -f "$RUNTIME_MUTATED" ] && [ $WAIT_SECONDS -lt $MAX_WAIT ]; do
    sleep 0.5
    WAIT_SECONDS=$((WAIT_SECONDS+1))
done

if [ -f "$RUNTIME_MUTATED" ]; then
    echo "[startup] Found mutated runtime server after ${WAIT_SECONDS} checks."
else
    echo "[startup][warning] Mutated runtime server not found at ${RUNTIME_MUTATED}. Proceeding anyway (will retry on node startup)."
fi

# Start the two backend nodes. These run the same app but are intentionally
# started on different ports so the proxy can switch between them as the
# MTD cycle progresses.
echo "⚙️ Starting Server Node A..."
# Use python -m uvicorn and dynamic_server:app which loads /tmp/active_server.py
python -m uvicorn dynamic_server:app --port 8001 --host 0.0.0.0 > /tmp/nodeA.log 2>&1 &

echo "⚙️ Starting Server Node B..."
python -m uvicorn dynamic_server:app --port 8002 --host 0.0.0.0 > /tmp/nodeB.log 2>&1 &

# Launch the proxy that routes traffic to the correct node based on
# the mutation window. This is effectively the brains of the active switching logic.
echo "⚙️ Starting Proxy..."
python -m core.proxy > /tmp/proxy.log 2>&1 &

# Give all subsystems a moment to warm up—Uvicorn, the proxy, and mutation state.
echo "⏳ Waiting for subsystems to initialize..."
sleep 3

# Launch the simulated attacker to continuously probe the system.
# It drives the telemetry panel and shows how attackers interact with mutated routes.
echo "🤖 Launching Hacker Bot..."
python -m demo_scripts.hacker_bot > /tmp/bot.log 2>&1 &

# Start the Streamlit dashboard in the foreground so logs remain attached
# and the container behaves correctly on most hosting providers.
# If Render provides $PORT, use it; otherwise default to 10000 for local testing.
PORT=${PORT:-10000}
echo "✅ Starting Dashboard on Port $PORT"

# Exec replaces shell so the container's main process is Streamlit (good for Render)
exec python -m streamlit run dashboard.py \
    --server.port $PORT \
    --server.enableCORS false \
    --server.address 0.0.0.0 \
    --server.headless true \
    --theme.base "dark"
