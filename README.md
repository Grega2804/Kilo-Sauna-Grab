# Secret Kilo Booking Script (psshht!!)

Automatically books a sauna slot on the [HOAS Tampuuri booking system](https://booking-hoas.tampuuri.fi), reserving the slot 2 weeks in advance.

The script right now is set up to book a spot at 21h.

## How it works

The HOAS booking system opens new slots every day at 21:00 (for the date 14 days ahead(and all time slots at the same time)). This script runs automatically via a cron job at that exact time and grabs the slot before anyone else.

The script:
1. Logs in using saved session cookies (fast, no browser needed)
2. Sends a single GET request to reserve the slot
3. If the session has expired, re-logs in automatically
4. If a CAPTCHA is active (triggered by too many failed attempts), opens a browser for manual login

## Requirements

- Python 3
- Linux, macOS, or Windows

## Setup

### 1. Clone the repo

```bash
git clone git@github.com:Grega2804/Kilo-Sauna-Grab.git
cd hoas-booking
```

### 2. Install dependencies

```bash
pip install requests beautifulsoup4 python-dotenv playwright
playwright install chromium
```

### 3. Create a `.env` file

Create a file named `.env` in the project folder:

```
HOAS_USERNAME=your.email@example.com
HOAS_PASSWORD=YourPassword
```

> Never commit this file. It is listed in `.gitignore`.

### 4. Configure the script

Open `hoas_book.py` and set:

```python
SERVICE_ID = "72"    # ID of the sauna/room — see below how to find it
TIME = "21.00"       # Time slot you want to book
```

**How to find your SERVICE_ID:**
1. Log in to the booking site
2. Navigate to the timetable for your sauna
3. Click on the time slot you want to book
4. Look at the URL — it will be: `/varaus/service/reserve/<SERVICE_ID>/<TIME>/<DATE>`

### 5. First run — save your session

```bash
python3 hoas_book.py
```

On the first run the script will log in and save your session to `session_cookies.json`. If a CAPTCHA appears, a browser window will open for you to log in manually.

### 6. Set up the scheduler

#### Linux / macOS — cron

Run this command to schedule the script every Sunday at 21:00:

```bash
(crontab -l 2>/dev/null; echo '0 21 * * 0 cd "/path/to/hoas-booking" && python3 hoas_book.py >> hoas_book.log 2>&1') | crontab -
```

Replace `/path/to/hoas-booking` with the actual path to the project folder.

Verify it was added:

```bash
crontab -l
```

Check logs after the first automated run:

```bash
cat hoas_book.log
```

#### Windows — Task Scheduler

1. Open **Task Scheduler** (search for it in the Start menu)
2. Click **Create Basic Task**
3. Name it `HOAS Booking`
4. Trigger: **Weekly** → Sunday → set time to **21:00**
5. Action: **Start a program**
   - Program: `python`
   - Arguments: `hoas_book.py`
   - Start in: `C:\path\to\hoas-booking` (your project folder)
6. Finish

To check if it ran, look for `hoas_book.log` in the project folder.

> **Note for Windows:** Make sure Python is added to your PATH during installation (check "Add Python to PATH" in the installer).

## Preventing sleep/suspension

The machine must be **on and not suspended** at 21:00 on the day of booking for the scheduler to fire.

#### Linux (systemd)

Disable suspend and sleep permanently:

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

To re-enable later:

```bash
sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

#### macOS

1. Open **System Settings** → **Battery** (or **Energy Saver** on older macOS)
2. Set **"Turn display off after"** to your preference
3. Enable **"Prevent automatic sleeping when the display is off"** (or "Prevent computer from sleeping automatically")

Or via terminal (permanent):

```bash
sudo pmset -a sleep 0 disksleep 0
```

To revert:

```bash
sudo pmset -a sleep 1 disksleep 10
```

#### Windows

1. Open **Settings** → **System** → **Power & sleep**
2. Set **"When plugged in, PC goes to sleep after"** → **Never**

Or via terminal (permanent):

```powershell
powercfg /change standby-timeout-ac 0
```

To revert:

```powershell
powercfg /change standby-timeout-ac 30
```

## Notes

- `session_cookies.json` is saved locally and reused on every run. If the session expires the script re-logs in automatically.
- The CAPTCHA on the login page is only triggered after multiple failed login attempts. Under normal use it will not appear.

<!-- ## Files

| File | Description |
|------|-------------|
| `hoas_book.py` | Main script |
| `.env` | Credentials (not committed) |
| `session_cookies.json` | Saved session (not committed) |
| `hoas_book.log` | Log output from cron runs | -->

<!-- ## .gitignore

Make sure your `.gitignore` includes:

```
.env
session_cookies.json
hoas_book.log -->
```
