#!/usr/bin/env pwsh
# Verifica se há instâncias EC2 em todas as regiões
# Uso: .\encontrar_instancia.ps1

Write-Host "`n=== Procurando instâncias EC2 ===" -ForegroundColor Cyan
Write-Host ""

# Tentar ping no IP que temos
$AWS_HOST = "18.229.134.75"
Write-Host "Testando conectividade com $AWS_HOST..." -ForegroundColor Yellow

$tcpClient = New-Object System.Net.Sockets.TcpClient
try {
    $tcpClient.Connect($AWS_HOST, 22)
    if ($tcpClient.Connected) {
        Write-Host "✓ IP $AWS_HOST está ONLINE (porta 22 aberta)" -ForegroundColor Green
        $tcpClient.Close()
        
        Write-Host "`nO servidor EXISTE, mas a instância não aparece no console!" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Possíveis causas:" -ForegroundColor Yellow
        Write-Host "1. Você está logado na CONTA AWS ERRADA" -ForegroundColor Red
        Write-Host "2. Você está na REGIÃO ERRADA (verifique se está em São Paulo - sa-east-1)" -ForegroundColor Red
        Write-Host "3. A instância foi criada por OUTRO USUÁRIO e você não tem permissão" -ForegroundColor Red
        Write-Host ""
        Write-Host "SOLUÇÃO:" -ForegroundColor Green
        Write-Host "1. No canto superior direito do console AWS, clique no seletor de REGIÃO" -ForegroundColor Cyan
        Write-Host "2. Selecione 'América do Sul (São Paulo) sa-east-1'" -ForegroundColor Cyan
        Write-Host "3. Ou tente outras regiões: us-east-1, us-west-2, etc" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "4. Verifique se você está logado na conta correta (canto superior direito)" -ForegroundColor Cyan
        Write-Host ""
    }
} catch {
    Write-Host "✗ IP $AWS_HOST está OFFLINE ou inacessível" -ForegroundColor Red
    Write-Host ""
    Write-Host "O servidor pode ter sido:" -ForegroundColor Yellow
    Write-Host "1. Desligado (stopped)" -ForegroundColor Gray
    Write-Host "2. Terminado (deleted)" -ForegroundColor Gray
    Write-Host "3. O IP mudou" -ForegroundColor Gray
}

Write-Host "`n=== COMO ENCONTRAR SUA INSTÂNCIA ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "OPÇÃO 1 - Verificar todas as regiões manualmente:" -ForegroundColor Green
Write-Host "1. Vá em EC2 > Instâncias" -ForegroundColor Cyan
Write-Host "2. No filtro de busca, digite: GCM" -ForegroundColor Cyan
Write-Host "3. Se não encontrar, mude a REGIÃO (canto superior direito)" -ForegroundColor Cyan
Write-Host "4. Teste cada região: sa-east-1, us-east-1, us-west-2, eu-west-1" -ForegroundColor Cyan
Write-Host ""

Write-Host "OPÇÃO 2 - Criar nova instância:" -ForegroundColor Green
Write-Host "Se a instância foi deletada, você precisará:" -ForegroundColor Yellow
Write-Host "1. Criar nova instância EC2" -ForegroundColor Cyan
Write-Host "2. Gerar nova chave SSH (.pem)" -ForegroundColor Cyan
Write-Host "3. Configurar security group (permitir SSH)" -ForegroundColor Cyan
Write-Host "4. Instalar o sistema do zero" -ForegroundColor Cyan
Write-Host ""

Write-Host "OPÇÃO 3 - Usar IP Elástico existente:" -ForegroundColor Green
Write-Host "Vá em EC2 > IPs Elásticos" -ForegroundColor Cyan
Write-Host "Procure por: $AWS_HOST" -ForegroundColor Cyan
Write-Host "Veja a qual instância ele está associado" -ForegroundColor Cyan
Write-Host ""

# Tentar descobrir informações via whois
Write-Host "Verificando informações do IP..." -ForegroundColor Yellow
try {
    $whois = Resolve-DnsName -Name $AWS_HOST -ErrorAction Stop
    Write-Host "Informações DNS:" -ForegroundColor Gray
    $whois | Format-Table -AutoSize
} catch {
    Write-Host "Não foi possível resolver DNS reverso" -ForegroundColor Gray
}

Write-Host "`n=== AÇÃO RECOMENDADA ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Verifique a REGIÃO no console AWS (canto superior direito)" -ForegroundColor Yellow
Write-Host "2. Vá em: EC2 > Instâncias" -ForegroundColor Yellow
Write-Host "3. Procure por 'GCM-Sistema' ou filtre por todos os estados" -ForegroundColor Yellow
Write-Host "4. Se não encontrar, vá em 'IPs Elásticos' e procure $AWS_HOST" -ForegroundColor Yellow
Write-Host ""
Write-Host "Me avise o que você encontrou!" -ForegroundColor Green
Write-Host ""
