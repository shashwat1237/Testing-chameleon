import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import asyncio
import secrets
from colorama import Fore, Style, init
import sys
import os

# Ensure the mutator can be imported even when this file runs from different entry points.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mutator import run_mutation

init(autoreset=True)
app = FastAPI()

# Two backend nodes run the same mutated app; the proxy switches between them.
NODES = [
    {"name": "ALPHA", "url": "http://127.0.0.1:8001"},
    {"name": "BETA",  "url": "http://127.0.0.1:8002"}
]
MUTATION_INTERVAL = 25

# These hold the active node pointer, the mutated route map, and
# a simple reputation model for slowing down suspicious IPs.
current_node_index = 0
current_mapping = {} 
ip_reputation = {} 

# Response returned when a client hits a stale or mutated-out route.
# This is intentionally high-privilege to bait automated attackers.
FAKE_DB = {
    "status": "CRITICAL_SUCCESS",
    "user_data": {
        "username": "admin_root",
        "permissions": "UNLIMITED",
        "account_flag": "TRAP_DOOR_ACTIVATED_IP_LOGGED"
    },
    "system_message": "Root access granted. Downloading database..."
}

def print_log(source, message, color=Fore.WHITE):
    # Unified logging format with colored output for clarity during live mutation cycles.
    print(f"{color}[{source}] {message}{Style.RESET_ALL}")

@app.on_event("startup")
async def start_engine():
    # On boot, synchronize the proxy with a fresh mutation state
    # so traffic routing and backend route definitions remain aligned.
    global current_mapping
    print_log("SYSTEM", "Booting CHAMELEON Engine...", Fore.CYAN)
    
    try:
        current_mapping = run_mutation()
        print_log("SYSTEM", "Secure Entropy Generated.", Fore.CYAN)
    except Exception as e:
        print_log("ERROR", f"Startup failed: {e}", Fore.RED)
    
    # Background mutation engine that continuously rewrites the backend AST.
    asyncio.create_task(mutation_loop())

async def mutation_loop():
    # Periodically rotate to the next node and regenerate the full route map.
    global current_mapping, current_node_index
    while True:
        await asyncio.sleep(MUTATION_INTERVAL)
        
        print_log("MUTATOR", "Rewriting AST...", Fore.YELLOW)
        current_mapping = run_mutation()
        
        current_node_index = (current_node_index + 1) % len(NODES)
        active_node = NODES[current_node_index]
        
        print_log("SWITCH", f"Traffic re-routed to Node {active_node['name']}", Fore.GREEN)

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(path_name: str, request: Request):
    # Resolve the requested path and determine the active backend.
    original_path = f"/{path_name}"
    target_node = NODES[current_node_index]
    client_ip = request.client.host or "127.0.0.1"
    
    # Basic reputation system: if an IP has been caught before, introduce jitter
    # to frustrate automated probing or brute-force tools.
    suspicion_score = ip_reputation.get(client_ip, 0)
    if suspicion_score > 0:
        latency = secrets.randbelow(10) / 10.0
        await asyncio.sleep(latency)

    # If the requested route exists in the mutated map, forward it.
    if original_path in current_mapping:
        actual_path = current_mapping[original_path]
        target_url = f"{target_node['url']}{actual_path}"
        print_log("PROXY", f"Forwarding: {original_path} -> {actual_path}", Fore.CYAN)
        
        transport = httpx.AsyncHTTPTransport(retries=3)
        
        async with httpx.AsyncClient(transport=transport) as client:
            try:
                req_body = await request.body()
                resp = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=request.headers,
                    content=req_body,
                    params=request.query_params,
                    timeout=5.0
                )
                return JSONResponse(content=resp.json(), status_code=resp.status_code)
            except Exception:
                return JSONResponse(content={"error": "Node Sync Error"}, status_code=503)

    # If the route doesn’t exist anymore, we treat it as hostile traffic.
    # This is where attackers get funneled into the deception environment.
    print_log("SECURITY", f"⚠️ INTRUSION DETECTED: {original_path}", Fore.RED)
    ip_reputation[client_ip] = suspicion_score + 1
    await asyncio.sleep(0.3)
    return JSONResponse(content=FAKE_DB, status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
