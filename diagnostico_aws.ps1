#!/usr/bin/env pwsh
# Script de Diagnóstico AWS - Verifica problemas com SSH e EC2
# Uso: .\diagnostico_aws.ps1

$AWS_HOST = "18.229.134.75"
$AWS_USER = "ubuntu"
$AWS_KEY = "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"
$INSTANCE_ID = "i-0977e96dd717517340"

Write-Host "`n=== DIAGNÓSTICO AWS EC2 ===" -ForegroundColor Cyan
Write-Host "Instância: $INSTANCE_ID" -ForegroundColor Yellow
Write-Host "IP: $AWS_HOST" -ForegroundColor Yellow
Write-Host "Chave: $AWS_KEY" -ForegroundColor Yellow
Write-Host ""

# 1. Verificar se a chave existe
Write-Host "[1/6] Verificando arquivo da chave SSH..." -ForegroundColor Green
if (Test-Path $AWS_KEY) {
    $keyInfo = Get-Item $AWS_KEY
    Write-Host "✓ Chave encontrada" -ForegroundColor Green
    Write-Host "  Tamanho: $($keyInfo.Length) bytes" -ForegroundColor Gray
    Write-Host "  Modificado: $($keyInfo.LastWriteTime)" -ForegroundColor Gray
    
    # Verificar permissões
    $acl = Get-Acl $AWS_KEY
    $accessRules = $acl.Access | Where-Object { $_.IdentityReference -like "*$env:USERNAME*" }
    Write-Host "  Permissões: $($accessRules.FileSystemRights)" -ForegroundColor Gray
} else {
    Write-Host "✗ ERRO: Chave não encontrada em $AWS_KEY" -ForegroundColor Red
    Write-Host ""
    Write-Host "Procurando outras chaves .pem..." -ForegroundColor Yellow
    Get-ChildItem "$env:USERPROFILE\Downloads\*.pem" -ErrorAction SilentlyContinue | 
        Select-Object Name, Length, LastWriteTime | 
        Format-Table -AutoSize
    exit 1
}

# 2. Verificar conectividade de rede
Write-Host "`n[2/6] Testando conectividade de rede..." -ForegroundColor Green
$ping = Test-Connection -ComputerName $AWS_HOST -Count 2 -Quiet 2>$null
if ($ping) {
    Write-Host "✓ Servidor responde a ping" -ForegroundColor Green
} else {
    Write-Host "⚠ Servidor não responde a ping (pode ser normal se ICMP estiver bloqueado)" -ForegroundColor Yellow
}

# 3. Testar porta SSH (22)
Write-Host "`n[3/6] Testando porta SSH (22)..." -ForegroundColor Green
$tcpClient = New-Object System.Net.Sockets.TcpClient
try {
    $tcpClient.Connect($AWS_HOST, 22)
    if ($tcpClient.Connected) {
        Write-Host "✓ Porta 22 está aberta e acessível" -ForegroundColor Green
        $tcpClient.Close()
    }
} catch {
    Write-Host "✗ ERRO: Porta 22 não está acessível!" -ForegroundColor Red
    Write-Host "  Possíveis causas:" -ForegroundColor Yellow
    Write-Host "  1. Security Group não permite SSH do seu IP" -ForegroundColor Gray
    Write-Host "  2. Servidor está offline" -ForegroundColor Gray
    Write-Host "  3. Firewall bloqueando a conexão" -ForegroundColor Gray
    exit 1
}

# 4. Tentar conexão SSH
Write-Host "`n[4/6] Tentando conexão SSH..." -ForegroundColor Green
Write-Host "Executando: ssh -i `"$AWS_KEY`" -v $AWS_USER@$AWS_HOST" -ForegroundColor Gray

$sshOutput = ssh -i $AWS_KEY -v -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$AWS_USER@$AWS_HOST" "echo 'Conexao OK'" 2>&1

if ($sshOutput -match "Conexao OK") {
    Write-Host "✓ SSH: Conexão bem-sucedida!" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== Tudo OK! Você pode executar .\deploy_aws_direto.ps1 ===" -ForegroundColor Green
} else {
    Write-Host "✗ SSH: Falha na autenticação" -ForegroundColor Red
    Write-Host ""
    Write-Host "Saída do SSH (últimas 10 linhas):" -ForegroundColor Yellow
    $sshOutput | Select-Object -Last 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    
    # Analisar erro
    if ($sshOutput -match "Permission denied") {
        Write-Host "`nDIAGNÓSTICO: Problema de autenticação" -ForegroundColor Red
        Write-Host "Causas possíveis:" -ForegroundColor Yellow
        Write-Host "  1. A chave .pem não corresponde à chave configurada na instância EC2" -ForegroundColor Gray
        Write-Host "  2. A chave pública não está em ~/.ssh/authorized_keys do servidor" -ForegroundColor Gray
        Write-Host "  3. Permissões incorretas no servidor (authorized_keys deve ser 600)" -ForegroundColor Gray
    }
    
    if ($sshOutput -match "bad permissions") {
        Write-Host "`nDIAGNÓSTICO: Permissões da chave muito abertas" -ForegroundColor Red
        Write-Host "Executando correção..." -ForegroundColor Yellow
        icacls $AWS_KEY /inheritance:r | Out-Null
        icacls $AWS_KEY /grant:r "$($env:USERNAME):(R)" | Out-Null
        Write-Host "✓ Permissões corrigidas. Tente novamente." -ForegroundColor Green
    }
}

# 5. Informações sobre como acessar via console AWS
Write-Host "`n[5/6] Alternativa: Session Manager (sem SSH)" -ForegroundColor Green
Write-Host "Se o SSH não funcionar, use o Session Manager:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Acesse: https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#Instances:" -ForegroundColor Cyan
Write-Host "2. Selecione a instância: GCM-Sistema ($INSTANCE_ID)" -ForegroundColor Cyan
Write-Host "3. Clique no botão 'Conectar' (canto superior direito)" -ForegroundColor Cyan
Write-Host "4. Selecione a aba 'Session Manager'" -ForegroundColor Cyan
Write-Host "5. Clique em 'Conectar' (abre terminal no navegador)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Dentro do Session Manager, você pode:" -ForegroundColor Gray
Write-Host "  • Verificar chaves SSH: cat ~/.ssh/authorized_keys" -ForegroundColor Gray
Write-Host "  • Ver logs: sudo journalctl -u gunicorn -n 50" -ForegroundColor Gray
Write-Host "  • Reiniciar serviços: sudo systemctl restart gunicorn" -ForegroundColor Gray

# 6. Verificar fingerprint da chave
Write-Host "`n[6/6] Gerando fingerprint da chave..." -ForegroundColor Green
try {
    $fingerprint = ssh-keygen -l -f $AWS_KEY 2>&1
    if ($fingerprint) {
        Write-Host "Fingerprint da chave local:" -ForegroundColor Yellow
        Write-Host "  $fingerprint" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Compare com o fingerprint no console AWS:" -ForegroundColor Yellow
        Write-Host "  EC2 > Pares de chaves > Procure pela chave da instância" -ForegroundColor Gray
    }
} catch {
    Write-Host "⚠ Não foi possível gerar fingerprint (ssh-keygen não disponível)" -ForegroundColor Yellow
}

Write-Host "`n=== Fim do Diagnóstico ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "PRÓXIMOS PASSOS:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Se SSH funcionar:" -ForegroundColor Green
Write-Host "  .\deploy_aws_direto.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "Se SSH NÃO funcionar:" -ForegroundColor Red
Write-Host "  1. Use Session Manager (instruções acima)" -ForegroundColor Cyan
Write-Host "  2. Baixe a chave correta do AWS Console" -ForegroundColor Cyan
Write-Host "  3. Ou recrie a instância com uma nova chave" -ForegroundColor Cyan
Write-Host ""
