Set-Location "$PSScriptRoot\.."
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^([^#=\s][^=]*)=(.*)$') {
        Set-Item -Path "Env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}
$env:PYTHONPATH = "$PSScriptRoot\.."
$env:MOCK_SERVICES_URL = "http://localhost:8001"
$env:CHAINLIT_URL = "http://localhost:8080"
& "$PSScriptRoot\..\venv\Scripts\python.exe" -m uvicorn gateway.app:app --host 0.0.0.0 --port 8000 --log-level info
