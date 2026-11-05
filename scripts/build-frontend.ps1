$ErrorActionPreference = 'Stop'
Push-Location frontend
try { npm run build }
finally { Pop-Location }
