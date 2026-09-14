import sys
import os

# 1. Reconfigure stdout and stderr to utf-8 immediately to prevent Windows cp1252 charmap errors
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import time
import threading
import webbrowser
import socket
import uvicorn

# 2. Set current project directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

def is_port_in_use(p):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(('127.0.0.1', p)) == 0
    except Exception:
        return False

def open_browser_delayed(port):
    time.sleep(1.5)
    url = f"http://localhost:{port}"
    print(f"[OK] Dang tu dong mo trinh duyet toi: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[NOTE] Vui long mo trinh duyet thu cong: {url}")

if __name__ == "__main__":
    # Select available port (try 8088 first, then alternatives)
    selected_port = 8088
    if is_port_in_use(selected_port):
        for alt in [8089, 8888, 8050, 8008, 9000]:
            if not is_port_in_use(alt):
                selected_port = alt
                break

    print("=" * 68)
    print("   HE THONG TAO DE THI HOC SINH GIOI MON GDKT&PL (GDPT 2018)")
    print("=" * 68)
    print(f"\n[*] May chu dang khoi chay tai: http://localhost:{selected_port}")
    print("    (Ban co the mo trinh duyet va truy cap dia chi tren)")
    print("[*] Vui long GIU NGUYEN cua so nay trong suot qua trinh lam viec.\n")

    # Start browser opener in background thread
    threading.Thread(target=open_browser_delayed, args=(selected_port,), daemon=True).start()

    # Run FastAPI app with Uvicorn (reload=True so code changes apply immediately)
    uvicorn.run("app.main:app", host="127.0.0.1", port=selected_port, log_level="info", reload=True)
