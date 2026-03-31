import os
import json
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.environ["HOAS_USERNAME"]
PASSWORD = os.environ["HOAS_PASSWORD"]

# --- Config ---
SERVICE_ID = "72"      # sauna/room ID from the URL
TIME = "21.00"         # Sunday sauna turn
DATE = (datetime.date.today() + datetime.timedelta(days=14)).strftime("%Y-%m-%d")
# --------------

BASE = "https://booking-hoas.tampuuri.fi"
COOKIES_FILE = Path(__file__).parent / "session_cookies.json"


def save_session_via_requests():
    """Log in using requests (works when no captcha is active)."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
    })
    r = s.get(f"{BASE}/auth/login")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    csrf = s.cookies.get("csrf_cookie_name")
    captcha_field = soup.find("input", {"name": "captcha"})

    if captcha_field is not None:
        # Captcha is active — fall back to browser
        return None

    r = s.post(f"{BASE}/auth/login", data={
        "csrf_token_name": csrf,
        "login": USERNAME,
        "password": PASSWORD,
        "submit": "Kirjaudu",
    }, headers={
        "Referer": f"{BASE}/auth/login",
        "Origin": BASE,
        "Content-Type": "application/x-www-form-urlencoded",
    })

    if "/auth/login" in r.url:
        return None  # failed, fall back to browser

    # Convert requests cookies to Playwright-compatible format
    cookies = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in s.cookies]
    COOKIES_FILE.write_text(json.dumps(cookies))
    print("Logged in automatically.")
    return s


def save_session_via_browser():
    """Open a real browser, let you log in, then save the session cookies."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(f"{BASE}/auth/login")
        print("Log in manually in the browser window. Waiting...")
        page.wait_for_url(lambda url: "/auth/login" not in url, timeout=120_000)
        print("Logged in! Saving session cookies...")
        cookies = page.context.cookies()
        COOKIES_FILE.write_text(json.dumps(cookies))
        browser.close()
        print(f"Cookies saved to {COOKIES_FILE}")


def book_slot():
    if not COOKIES_FILE.exists():
        print("No saved session. Trying automatic login...")
        if save_session_via_requests() is None:
            print("Captcha detected. Opening browser to log in manually...")
            save_session_via_browser()

    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})

    # Load saved cookies
    cookies = json.loads(COOKIES_FILE.read_text())
    for c in cookies:
        s.cookies.set(c["name"], c["value"], domain=c["domain"])

    # Try booking
    r = s.get(f"{BASE}/varaus/service/reserve/{SERVICE_ID}/{TIME}/{DATE}")
    r.raise_for_status()

    # Check if session expired (redirected to login)
    if "/auth/login" in r.url:
        print("Session expired. Re-logging in...")
        COOKIES_FILE.unlink()
        if save_session_via_requests() is None:
            print("Captcha detected. Opening browser to log in manually...")
            save_session_via_browser()
        return book_slot()

    print(f"Booking request sent: {r.status_code} — {r.url}")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    msg = soup.find(class_="alert") or soup.find(id="confirm-message")
    if msg:
        print(msg.get_text(strip=True))


if __name__ == "__main__":
    book_slot()
