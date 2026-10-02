# Crowdsourcing Project Monitor

An asynchronous Python monitor for two Lancers and five CrowdWorks page-one search categories. It stores every observed project in SQLite and sends one Slack notification per genuinely new project. Slack defaults to mock mode, so the application is safe to run before a webhook is supplied.

## Windows / VS Code setup

Install Python 3.12 or newer, open this folder in VS Code, and run the following in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
python main.py
```

The default `.env.example` has `SLACK_ENABLED=false`. In this mode, complete Slack messages are written to the console and `logs/monitor.log`; no network request is made to Slack.

## Behavior

- One Chromium browser and seven independent pages are used.
- Every category revisits its configured page approximately every 30 seconds. Scan duration is deducted from the interval to avoid accumulated drift.
- Only page 1 is visited. The monitor never clicks pagination controls.
- A category's first successful, non-empty parse is its persistent baseline. All visible projects are stored, while only positions 1–3 are queued for notification.
- Later projects are inserted atomically by `(platform, project_id)` and queued only when that insert is new.
- A project seen in two categories on the same platform is stored and notified once.
- Failed or interrupted notifications remain pending and are recovered on the next startup.
- A page failure is logged and retried on its next cycle without stopping other categories.

Runtime data is stored at `data/monitor.db`; logs are written to `logs/monitor.log`. Both are ignored by Git.

## Slack setup

When an incoming webhook is available, edit `.env`:

```dotenv
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

If the URL is absent, the notifier automatically falls back to mock mode. Secrets are never logged and `.env` is ignored by Git.

## Configuration

Available `.env` settings:

```dotenv
SCAN_INTERVAL_SECONDS=30
PAGE_TIMEOUT_MS=30000
HEADLESS=true
DATABASE_PATH=data/monitor.db
LOG_PATH=logs/monitor.log
```

All seven category definitions and URLs are centralized in `config.py`.

## Testing

With the virtual environment active and Chromium installed:

```powershell
pytest
```

The parser tests use local Japanese HTML fixtures and make no request to Lancers or CrowdWorks.

To test first-run behavior again, stop the application and remove only `data/monitor.db` (plus any `monitor.db-wal`/`monitor.db-shm` files if present). This deliberately resets all project history and category initialization state, so the first three projects in every category will be emitted again.

## Shutdown and site changes

Press `Ctrl+C` to cancel all monitor tasks and close Chromium and SQLite cleanly. Generated CrowdWorks CSS suffixes can change; their partial-class selectors are centralized in `scrapers/crowdworks.py`. CAPTCHA or security challenges are logged and retried normally—no bypass behavior is implemented.

