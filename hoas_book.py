import os
import json
import time
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.environ["HOAS_USERNAME"]
PASSWORD = os.environ["HOAS_PASSWORD"]

# # --- Config ---
# SERVICE_ID = "72"      # sauna/room ID from the URL
# TIME = "21.00"         # Sunday sauna turn
# DATE = (datetime.date.today() + datetime.timedelta(days=14)).strftime("%Y-%m-%d")
# # --------------

# --- Config ---
SERVICE_ID = "73"      # sauna/room ID from the URL
TIME = "21.00"         # Sunday sauna turn
# Booking opens Saturday 21:00 for the Sunday 15 days out (not 14).
DATE = (datetime.date.today() + datetime.timedelta(days=15)).strftime("%Y-%m-%d")
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


def build_session():
    """Create an authenticated session, reusing saved cookies."""
    if not COOKIES_FILE.exists():
        print("No saved session. Trying automatic login...")
        if save_session_via_requests() is None:
            print("Captcha detected. Opening browser to log in manually...")
            save_session_via_browser()

    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    cookies = json.loads(COOKIES_FILE.read_text())
    for c in cookies:
        s.cookies.set(c["name"], c["value"], domain=c["domain"])
    return s


def try_book(s):
    """Make a single booking attempt with an existing session. Returns 'success', 'taken', or 'not_open'."""
    r = s.get(f"{BASE}/varaus/service/reserve/{SERVICE_ID}/{TIME}/{DATE}")
    r.raise_for_status()

    if "/auth/login" in r.url:
        return "session_expired"

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    msg = soup.find(class_="alert") or soup.find(id="confirm-message")
    if msg:
        text = msg.get_text(strip=True)
        print(text)
        text_lower = text.lower()
        if any(w in text_lower for w in ("varaus tehty", "booked", "confirmed", "vahvistet")):
            return "success"
        if any(w in text_lower for w in ("ei ole", "not available", "unavailable", "varattu", "taken", "full")):
            return "taken"
        if any(w in text_lower for w in ("ei voi", "not yet", "liian", "too early")):
            return "not_open"

    return "not_open"


if __name__ == "__main__":
    BOOK_HOUR = 21
    BOOK_MINUTE = 0
    START_SECONDS_EARLY = 5    # start hammering this many seconds before opening
    RETRY_INTERVAL = 0.1       # seconds between attempts

    # Build session once — reused across all attempts
    s = build_session()

    now = datetime.datetime.now()
    target = now.replace(hour=BOOK_HOUR, minute=BOOK_MINUTE, second=0, microsecond=0)
    start = target - datetime.timedelta(seconds=START_SECONDS_EARLY)

    # Pre-warm the connection so the first real attempt skips TCP+TLS setup
    warmup_at = start - datetime.timedelta(seconds=2)
    wait = (warmup_at - datetime.datetime.now()).total_seconds()
    if wait > 0:
        print(f"Waiting until {warmup_at.strftime('%H:%M:%S')} to pre-warm connection...")
        time.sleep(wait)
    try:
        s.get(f"{BASE}/", timeout=3)
        print("Connection pre-warmed.")
    except Exception:
        pass

    wait = (start - datetime.datetime.now()).total_seconds()
    if wait > 0:
        print(f"Waiting until {start.strftime('%H:%M:%S')} to start retrying...")
        time.sleep(wait)

    print("Starting booking attempts...")
    attempt = 0
    while True:
        attempt += 1
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{ts}] Attempt {attempt}")
        result = try_book(s)
        if result == "success":
            print("Booking confirmed!")
            break
        if result == "taken":
            print("Slot already taken. Stopping.")
            break
        if result == "session_expired":
            print("Session expired mid-run. Re-logging in...")
            COOKIES_FILE.unlink()
            if save_session_via_requests() is None:
                save_session_via_browser()
            s = build_session()
        time.sleep(RETRY_INTERVAL)
