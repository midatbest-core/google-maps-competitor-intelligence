"""
Quick Smoke Test: Verifies server startup, browser launch, and login page rendering.
"""
import os
import sys
import time
import socket
import subprocess
import requests

os.environ['APP_ENV'] = 'development'
sys.path.insert(0, os.path.abspath('backend'))

from playwright.sync_api import sync_playwright

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def ensure_servers():
    procs = []
    # 1. Backend on 8000
    if not is_port_open(8000):
        print("Starting backend uvicorn on port 8000...", flush=True)
        backend_proc = subprocess.Popen(
            [os.path.abspath("venv/Scripts/python.exe"), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--app-dir", "backend"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        procs.append(backend_proc)

    # 2. Frontend on 5173
    if not is_port_open(5173):
        print("Starting frontend vite on port 5173...", flush=True)
        frontend_proc = subprocess.Popen(
            ["npx.cmd", "vite", "--host", "127.0.0.1", "--port", "5173"],
            cwd=os.path.abspath("frontend"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        procs.append(frontend_proc)

    # Wait for readiness
    for _ in range(30):
        b_ok = False
        f_ok = False
        try:
            r = requests.get("http://127.0.0.1:8000/health", timeout=1)
            b_ok = r.status_code == 200
        except:
            pass
        try:
            r = requests.get("http://127.0.0.1:5173/", timeout=1)
            f_ok = r.status_code == 200
        except:
            pass

        if b_ok and f_ok:
            print("Both Backend (:8000) and Frontend (:5173) are ready!", flush=True)
            break
        time.sleep(0.5)
    else:
        print("WARNING: Timed out waiting for servers to become ready.", flush=True)

    return procs

def run_smoke():
    os.makedirs("qa_audit/screenshots", exist_ok=True)
    servers = ensure_servers()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(10000)

            print("Navigating to http://127.0.0.1:5173/login...", flush=True)
            page.goto("http://127.0.0.1:5173/login", wait_until="domcontentloaded")
            time.sleep(1)

            # Check form
            email_visible = page.locator('input[type="email"]').is_visible()
            pw_visible = page.locator('input[type="password"]').is_visible()
            btn_visible = page.locator('button[type="submit"]').is_visible()

            print(f"Login elements visible: email={email_visible}, password={pw_visible}, submit={btn_visible}", flush=True)
            assert email_visible and pw_visible and btn_visible, "Login form inputs not visible"

            screenshot_path = "qa_audit/screenshots/smoke_login.png"
            page.screenshot(path=screenshot_path)
            print(f"Smoke screenshot saved to {screenshot_path}", flush=True)

            browser.close()
            print("SMOKE TEST PASSED SUCCESSFULLY!", flush=True)
    finally:
        pass

if __name__ == "__main__":
    run_smoke()
