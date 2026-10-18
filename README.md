# Crowdsourcing Project Monitor

An asynchronous Python monitor for two Lancers and five CrowdWorks page-one search categories. It stores every observed project in SQLite and sends one Slack notification per genuinely new project. Slack is enabled by default and uses mock mode only until a webhook is configured.

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

`SLACK_ENABLED=true` is the default. If the webhook is empty, complete Slack messages are written to the console and `logs/monitor.log`; no request is made to Slack.

## Behavior

- One Chromium browser and seven independent pages are used.
- Every category independently revisits its configured page every 60 seconds by default. Scan duration is deducted from the interval to avoid accumulated drift.
- Only page 1 is visited. The monitor never clicks pagination controls.
- A category's first successful, non-empty parse is a silent persistent baseline. Existing listings are stored but never notified; only project IDs first observed on later scans are queued.
- CrowdWorks pages are explicitly reloaded before every scan after the initial load.
- Later projects are inserted atomically by `(platform, project_id)` and queued only when that insert is new.
- A project seen in two categories on the same platform is stored and notified once.
- Failed or interrupted notifications remain pending and are recovered on the next startup.
- A page failure is logged and retried on its next cycle without stopping other categories.

Source-mode runtime data is stored under the project directory. The EXE stores its database and logs under `%LOCALAPPDATA%\CrowdsourcingMonitor`, which remains writable even when the EXE is launched from a protected directory such as `Program Files`.

## Slack setup

When running from source, an incoming webhook can be supplied in `.env`:

```dotenv
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

If the URL is absent, the notifier automatically falls back to mock mode. Secrets are never logged and `.env` is ignored by Git.

## Configuration

Available `.env` settings:

```dotenv
SCAN_INTERVAL_SECONDS=60
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

To reset source-mode history, stop the application and remove only `data/monitor.db` (plus any `monitor.db-wal`/`monitor.db-shm` files if present). For the EXE, the equivalent files are under `%LOCALAPPDATA%\CrowdsourcingMonitor\data`. Resetting creates a fresh silent baseline; existing page items are not notified.

## Shutdown and site changes

Press `Ctrl+C` to cancel all monitor tasks and close Chromium and SQLite cleanly. Generated CrowdWorks CSS suffixes can change; their partial-class selectors are centralized in `scrapers/crowdworks.py`. CAPTCHA or security challenges are logged and retried normally—no bypass behavior is implemented.

## Windows GUI and executable

Run the desktop interface directly with:

```powershell
python gui.py
```

Enter the Slack webhook and scan interval in the settings row and select **Save settings**. These settings persist in the current Windows user profile and are applied immediately, including while monitors are running. The large Start and Stop buttons control the complete service. Each category row also has its own Stop button; stopping one category leaves the other monitors and Slack worker running. Logs appear in the window and continue to be written to `logs/monitor.log`.

Build the distributable Windows application with:

```powershell
.\build_exe.ps1
```

The portable executable is created at `dist\CrowdsourcingMonitor.exe`. Python, Qt, Playwright, and headless Chromium are embedded in this single file, so the target Windows PC does not need Python or any modules installed. On first launch, startup can take several seconds while the bundled runtime is extracted to a temporary directory.

The production build embeds the local `.env`, Mozilla CA certificates, Python, Qt, Playwright, and Chromium. HTTPS also trusts certificates installed in the target PC's Windows certificate stores. It does not require or read an adjacent `.env`. Later in-app changes are kept by Windows `QSettings`, because a running executable cannot safely rewrite itself. No Python, browser, module, environment-variable, or sidecar configuration setup is required on the target PC. Treat the executable and the Windows account as secret-bearing when a webhook is stored.
