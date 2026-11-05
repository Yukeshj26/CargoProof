$ErrorActionPreference = 'Stop'
Push-Location backend
try { & ..\.venv\Scripts\python.exe -m pytest -q }
finally { Pop-Location }
