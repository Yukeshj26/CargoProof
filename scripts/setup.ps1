$ErrorActionPreference = 'Stop'
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if (!(Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
if (!(Test-Path frontend\.env)) { Copy-Item frontend\.env.example frontend\.env }
Push-Location frontend
npm install
Pop-Location
Write-Host 'Setup complete. Configure backend/.env and frontend/.env.' -ForegroundColor Green
