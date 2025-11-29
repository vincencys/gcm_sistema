#!/usr/bin/env pwsh
# Script de inicialização do servidor GCM com suporte a WebSockets

Write-Host "🚀 Iniciando servidor GCM com WebSockets..." -ForegroundColor Cyan

# Ativar ambiente virtual
Write-Host "📦 Ativando ambiente virtual..." -ForegroundColor Yellow
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

# Verificar se a porta 8000 está livre
$portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "⚠️  Porta 8000 já está em uso. Parando processos..." -ForegroundColor Yellow
    $pids = $portInUse | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Write-Host "   Parou processo PID $pid" -ForegroundColor Gray
    }
    Start-Sleep -Seconds 1
}

# Iniciar Daphne
Write-Host "✅ Iniciando Daphne ASGI Server..." -ForegroundColor Green
Write-Host "   Endereço: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "   Pressione Ctrl+C para parar`n" -ForegroundColor Gray

daphne -b 127.0.0.1 -p 8000 gcm_project.asgi:application
