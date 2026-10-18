from pathlib import Path
import os

from PyInstaller.utils.hooks import collect_all
import certifi

project_root = Path(SPECPATH)
playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")
browser_root = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
datas = list(playwright_datas)
datas.append((certifi.where(), "certifi"))
headless_revisions = sorted(browser_root.glob("chromium_headless_shell-*"))
if not headless_revisions:
    raise SystemExit("Playwright Chromium is missing. Run: python -m playwright install chromium")
headless_browser = headless_revisions[-1]
datas.append((str(headless_browser), f"ms-playwright/{headless_browser.name}"))
production_env = project_root / ".env"
if not production_env.exists():
    raise SystemExit("Production .env is missing; refusing to build without configuration")
datas.append((str(production_env), "."))

a = Analysis(
    [str(project_root / "gui.py")],
    pathex=[str(project_root)],
    binaries=playwright_binaries,
    datas=datas,
    hiddenimports=playwright_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CrowdsourcingMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
