from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

IS_FROZEN = bool(getattr(sys, "frozen", False))
BASE_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
if IS_FROZEN:
    APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", BASE_DIR)) / "CrowdsourcingMonitor"
    LEGACY_DATABASE_PATH: Path | None = BASE_DIR / "data" / "monitor.db"
else:
    APP_DATA_DIR = BASE_DIR
    LEGACY_DATABASE_PATH = None

if IS_FROZEN:
    # Frozen builds are self-contained: their build-time configuration is
    # bundled into the executable and no adjacent .env file is required.
    load_dotenv(BUNDLE_DIR / ".env")
else:
    load_dotenv(BASE_DIR / ".env", override=True)

if IS_FROZEN:
    bundled_browsers = BUNDLE_DIR / "ms-playwright"
    if bundled_browsers.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled_browsers))


@dataclass(frozen=True, slots=True)
class CategoryConfig:
    platform: str
    key: str
    name: str
    url: str


_LANCERS_QUERY = (
    "type%5B%5D=project&open=1&work_rank%5B%5D=3&work_rank%5B%5D=2&"
    "work_rank%5B%5D=1&work_rank%5B%5D=0&budget_from=&budget_to=&keyword=&not="
)

CATEGORIES = (
    CategoryConfig("lancers", "lancers_system", "System Development", f"https://www.lancers.jp/work/search/system?{_LANCERS_QUERY}"),
    CategoryConfig("lancers", "lancers_web", "Web", f"https://www.lancers.jp/work/search/web?{_LANCERS_QUERY}"),
    CategoryConfig("crowdworks", "crowdworks_226", "226", "https://crowdworks.jp/public/jobs/search?category_id=226&payment_type=hourly%2Cfixed_price"),
    CategoryConfig("crowdworks", "crowdworks_242", "242", "https://crowdworks.jp/public/jobs/search?category_id=242&payment_type=fixed_price%2Chourly"),
    CategoryConfig("crowdworks", "crowdworks_230", "230", "https://crowdworks.jp/public/jobs/search?category_id=230&payment_type=fixed_price%2Chourly"),
    CategoryConfig("crowdworks", "crowdworks_235", "235", "https://crowdworks.jp/public/jobs/search?category_id=235&payment_type=fixed_price%2Chourly"),
    CategoryConfig("crowdworks", "crowdworks_367", "367", "https://crowdworks.jp/public/jobs/search?category_id=367&payment_type=fixed_price%2Chourly"),
)


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


SCAN_INTERVAL_SECONDS = max(1.0, float(os.getenv("SCAN_INTERVAL_SECONDS", "60")))
PAGE_TIMEOUT_MS = max(1_000, int(os.getenv("PAGE_TIMEOUT_MS", "30000")))
HEADLESS = _bool_env("HEADLESS", True)
SLACK_ENABLED = _bool_env("SLACK_ENABLED", True)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(APP_DATA_DIR / "data" / "monitor.db")))
LOG_PATH = Path(os.getenv("LOG_PATH", str(APP_DATA_DIR / "logs" / "monitor.log")))
