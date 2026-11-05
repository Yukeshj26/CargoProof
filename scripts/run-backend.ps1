$ErrorActionPreference = 'Stop'
if (!(Test-Path .venv\Scripts\python.exe)) { throw 'Run .\scripts\setup.ps1 first.' }
Push-Location backend
try { & ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 }
finally { Pop-Location }
