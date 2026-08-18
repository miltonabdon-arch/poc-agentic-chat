$env:PYTHONPATH = "$PSScriptRoot\.."
Set-Location "$PSScriptRoot\..\mock_services"
& "$PSScriptRoot\..\venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8001
