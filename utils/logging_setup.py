import logging
import sys
from pathlib import Path


def configure_logging(log_path: Path) -> None:
    # Windows may inherit a legacy code page even in VS Code. Japanese project
    # text and the Slack preview must remain printable without crashing.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")
    handlers: list[logging.Handler] = [logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")]
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
