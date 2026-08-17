# Teste rapido do endpoint HTTP para a apresentacao
# Uso: .\scripts\test_http.ps1

$BASE = "http://localhost:8000"

function Invoke-Agent($msg, $label) {
    Write-Host "`n=== $label ===" -ForegroundColor Cyan
    Write-Host "Usuario : $msg" -ForegroundColor Yellow
    $body = @{
        conversation_id = "demo-http-01"
        channel         = "whatsapp"
        message         = $msg
        timestamp       = (Get-Date -Format "o")
    } | ConvertTo-Json
    try {
        $r = Invoke-RestMethod -Uri "$BASE/agent/interact" -Method POST `
             -ContentType "application/json" -Body $body -TimeoutSec 45
        Write-Host "Agente  : $($r.response)" -ForegroundColor Green
    } catch {
        Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Invoke-Agent "Quais franquias de dados o Plano Turbo 40GB inclui?" "[1/3] Catalogo RAG"
Invoke-Agent "Quero cancelar minha linha" "[2/3] Cancelamento (handoff)"
Invoke-Agent "Meu CPF e 123.456.789-00, quero upgrade de plano" "[3/3] PII masking"
