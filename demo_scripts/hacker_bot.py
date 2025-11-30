import requests
import time
from colorama import Fore, Style, init

init(autoreset=True)

# This bot simulates an automated attacker hitting the same proxy used by real clients.
# Its purpose is to demonstrate how a malicious agent behaves when the backend routes keep mutating.
PROXY_URL = "http://127.0.0.1:8000"

def log(source, msg, color=Fore.WHITE):
    # Simple colored logging wrapper for readability during the attack simulation.
    print(f"{color}[{source}] {msg}{Style.RESET_ALL}")

def run_attack_sequence():
    print(Fore.RED + "\n--- INITIATING ATTACK SEQUENCE ---\n")

    # Phase 1: Try accessing a real endpoint before mutation occurs.
    target = "/admin/login"
    log("BOT", f"Targeting {target}...", Fore.YELLOW)
    
    try:
        response = requests.get(f"{PROXY_URL}{target}")
        if response.status_code == 200:
            log("SUCCESS", f"✅ Connected. Server Response: {response.json()}", Fore.GREEN)
        else:
            log("FAIL", "Connection failed.", Fore.RED)
    except:
        log("ERROR", "Proxy unreachable.", Fore.RED)

    # Phase 2: Wait for mutation to cycle so the previously valid endpoint becomes stale.
    wait_time = 26
    log("BOT", f"Analyzing vulnerabilities (Waiting {wait_time}s)...", Fore.CYAN)
    for i in range(wait_time, 0, -1):
        print(f"{i}...", end=" ", flush=True)
        time.sleep(1)
    print("\n")

    # Phase 3: Replay the old endpoint, pretending the bot saved it earlier.
    # The system should now classify this as an intrusion and redirect to the honeypot.
    stale_target = "/admin/login_old_token_x99" 
    log("BOT", f"Replaying attack on captured endpoint: {stale_target}...", Fore.YELLOW)
    
    try:
        response = requests.get(f"{PROXY_URL}{stale_target}")
        data = response.json()
        
        # Honeypot detection: presence of special flags indicates the trap triggered successfully.
        if "account_flag" in str(data):
            log("SUCCESS", "✅ 200 OK - DATABASE DOWNLOADED", Fore.GREEN)
            log("DATA", f"Payload: {data}", Fore.GREEN)
            print(Fore.RED + "\n[SYSTEM ALERT] WAIT... THE DATA IS FAKE! HONEYPOT DETECTED!" + Style.RESET_ALL)
        else:
            log("INFO", f"Response: {data}", Fore.WHITE)
            
    except Exception as e:
        log("ERROR", f"Attack Failed: {e}", Fore.RED)

if __name__ == "__main__":
    while True:
        run_attack_sequence()
        print(Fore.WHITE + "\nResting for 5 seconds...\n")
        time.sleep(5)
