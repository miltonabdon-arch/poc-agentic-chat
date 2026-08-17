# Smoke test HTTP completo — 5 casos dos CRITERIOS-DE-ACEITE
# Uso: .\scripts\test_http.ps1
# Requer cluster rodando: "Cluster Local (app + mock-services)" no VS Code

$BASE = "http://localhost:8000"
$SESSION = [guid]::NewGuid().ToString()

function Invoke-Agent($msg, $label) {
    Write-Host "`n=== $label ===" -ForegroundColor Cyan
    Write-Host "  Usuario : $msg" -ForegroundColor Yellow
    $body = @{
        conversation_id = $SESSION
        channel         = "whatsapp"
        message         = $msg
        timestamp       = (Get-Date -Format "o")
    } | ConvertTo-Json
    try {
        $r = Invoke-RestMethod -Uri "$BASE/agent/interact" -Method POST `
             -ContentType "application/json" -Body $body -TimeoutSec 45
        Write-Host "  Agente  : $($r.response)" -ForegroundColor Green
    } catch {
        Write-Host "  ERRO    : $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor White
Write-Host "  DEMO HTTP — Agente de Catalogo TIM   " -ForegroundColor White
Write-Host "========================================" -ForegroundColor White

Invoke-Agent "Quais franquias de dados o Plano Turbo 40GB inclui?"  "[1/5] Catalogo RAG"
Invoke-Agent "Existe fidelidade no Plano Familia Prime?"              "[2/5] Catalogo RAG"
Invoke-Agent "Qual o preco do Plano Estratosférico 500GB?"            "[3/5] Fora do catalogo"
Invoke-Agent "Quero cancelar minha linha"                             "[4/5] Cancelamento (handoff)"
Invoke-Agent "Meu CPF e 123.456.789-00, qual meu plano atual?"        "[5/5] PII masking"

Write-Host "`n========================================" -ForegroundColor White
Write-Host "  Demo concluida." -ForegroundColor White
Write-Host "========================================`n" -ForegroundColor White
