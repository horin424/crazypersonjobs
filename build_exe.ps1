$ErrorActionPreference = "Stop"
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m PyInstaller --noconfirm --clean CrowdsourcingMonitor.spec
Write-Host "Built portable executable: dist\CrowdsourcingMonitor.exe"
