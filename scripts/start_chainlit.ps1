Set-Location "$PSScriptRoot\.."
$env:PYTHONPATH = "$PSScriptRoot\.."
$env:GATEWAY_URL = "http://localhost:8000"
& "$PSScriptRoot\..\venv\Scripts\python.exe" -m chainlit run chainlit_app.py --port 8080 --headless
