import pytest
import time
import subprocess
import os
import signal
from playwright.sync_api import sync_playwright


def test_playwright_e2e_browser_workflow():
    """End-to-End Browser verification of React Frontend and FastAPI Backend via Playwright."""
    port = 8011
    env = os.environ.copy()
    env["PYTHONPATH"] = ".:backend"

    # 1. Start live uvicorn server on port 8011
    server_proc = subprocess.Popen(
        [
            ".venv/bin/python", "-m", "uvicorn",
            "backend.src.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning"
        ],
        cwd="/Users/tejashr/Downloads/enterprise-agentic-ops-workspace",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Give server time to bind and initialize
        time.sleep(2.0)

        # 2. Launch headless Chromium
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 3. Load root page
            page.goto(f"http://127.0.0.1:{port}/", timeout=15000)

            # 4. Verify title and DOM elements
            assert "Enterprise Agentic Ops Workspace" in page.title()

            # Verify Header rendered
            page.wait_for_selector("text=Enterprise Agentic Ops Workspace", timeout=5000)
            page.wait_for_selector("text=ENV: LOCAL_DETERMINISTIC_ENGINE", timeout=5000)

            # Verify Sidebar rendered
            page.wait_for_selector("text=New Procurement Chat", timeout=5000)
            page.wait_for_selector("text=SAP S/4HANA OData", timeout=5000)
            page.wait_for_selector("text=Tejas H R (BE ISE 2026)", timeout=5000)

            # 5. Open Enterprise Inspector Drawer
            inspector_btn = page.locator("button:has-text('Enterprise Inspector')")
            inspector_btn.click()
            page.wait_for_selector("text=SAP Catalog", timeout=5000)
            page.wait_for_selector("text=Audit Trail", timeout=5000)

            # 6. Click SAP Catalog tab
            sap_tab = page.locator("button:has-text('SAP Catalog')")
            sap_tab.click()
            page.wait_for_selector("text=WS-ERGO-01", timeout=5000)
            page.wait_for_selector("text=Dell Technologies India Ltd", timeout=5000)

            browser.close()
            print("Playwright E2E browser verification completed successfully!")

    finally:
        # Cleanly terminate uvicorn
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()
