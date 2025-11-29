#!/usr/bin/env pwsh
# Deploy Direto AWS (sem Git remoto, usando SCP)
# Uso: .\deploy_aws_direto.ps1

param(
    [string]$Message = "Deploy direto via SCP",
    [switch]$SkipTests = $false
)

$ErrorActionPreference = "Stop"

# ===== CONFIGURAÇÕES =====
$AWS_HOST = "18.229.134.75"
$AWS_USER = "ec2-user"
$AWS_KEY = "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"
$REMOTE_PATH = "/home/ec2-user/GCM_Sistema"
$LOCAL_PATH = "C:\GCM_Sistema"

# Arquivos/pastas a EXCLUIR do deploy
$EXCLUDE = @(
    ".git",
    ".venv",
    "__pycache__",
    "*.pyc",
    "*.sqlite3",
    "db_backup_*.sqlite3",
    ".env",
    "*.keystore",
    "gcm-sistema-firebase-adminsdk-*.json",
    "node_modules",
    "media",
    "staticfiles",
    "pdfjs_tmp",
    "dist",
    ".vscode",
    ".tmp.driveupload"
)

Write-Host "`n=== Deploy Direto AWS (via SCP) ===" -ForegroundColor Cyan
Write-Host "Servidor: $AWS_HOST" -ForegroundColor Yellow
Write-Host "Origem: $LOCAL_PATH" -ForegroundColor Yellow
Write-Host "Destino: $REMOTE_PATH" -ForegroundColor Yellow
Write-Host ""

# 1. Testar conexão SSH
Write-Host "[1/5] Testando conexão SSH..." -ForegroundColor Green
$sshTest = ssh -i $AWS_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$AWS_USER@$AWS_HOST" "echo 'OK'" 2>&1

if ($sshTest -match "OK") {
    Write-Host "✓ Conexão SSH: OK" -ForegroundColor Green
} else {
    Write-Host "✗ ERRO: Falha na conexão SSH!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Diagnóstico:" -ForegroundColor Yellow
    Write-Host "1. Verifique se a chave '$AWS_KEY' está correta" -ForegroundColor Gray
    Write-Host "2. No console AWS, vá em EC2 > Instâncias > GCM-Sistema" -ForegroundColor Gray
    Write-Host "3. Clique em 'Conectar' > 'Session Manager' (não precisa de chave SSH)" -ForegroundColor Gray
    Write-Host "4. Dentro do servidor, execute: cat ~/.ssh/authorized_keys" -ForegroundColor Gray
    Write-Host "5. Verifique se a chave pública corresponde à sua chave privada .pem" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Alternativamente, use o botão 'Conectar' no console AWS." -ForegroundColor Yellow
    exit 1
}

# 2. Backup remoto
Write-Host "`n[2/5] Criando backup no servidor..." -ForegroundColor Green
$backupCmd = @"
cd /home/ubuntu &&
if [ -d GCM_Sistema ]; then
    timestamp=\$(date +%Y%m%d_%H%M%S)
    cp -r GCM_Sistema GCM_Sistema_backup_\$timestamp
    echo "Backup criado: GCM_Sistema_backup_\$timestamp"
else
    echo "Primeira instalação - sem backup"
fi
"@

ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $backupCmd

# 3. Criar arquivo temporário com lista de exclusões
Write-Host "`n[3/5] Preparando arquivos para upload..." -ForegroundColor Green
$excludeFile = [System.IO.Path]::GetTempFileName()
$EXCLUDE | ForEach-Object { $_ } | Out-File -FilePath $excludeFile -Encoding ASCII

# 4. Copiar arquivos via SCP/RSYNC
Write-Host "`n[4/5] Enviando arquivos para o servidor..." -ForegroundColor Green
Write-Host "Isso pode levar alguns minutos..." -ForegroundColor Gray

# Verificar se rsync está disponível
$rsyncAvailable = Get-Command rsync -ErrorAction SilentlyContinue

if ($rsyncAvailable) {
    Write-Host "Usando rsync (mais rápido)..." -ForegroundColor Gray
    
    # Construir argumentos de exclusão
    $excludeArgs = $EXCLUDE | ForEach-Object { "--exclude=$_" }
    
    $rsyncCmd = @(
        "-avz",
        "--delete"
        "-e", "ssh -i `"$AWS_KEY`" -o StrictHostKeyChecking=no"
    ) + $excludeArgs + @(
        "$LOCAL_PATH/",
        "${AWS_USER}@${AWS_HOST}:${REMOTE_PATH}/"
    )
    
    & rsync @rsyncCmd
    
} else {
    Write-Host "rsync não encontrado, usando SCP..." -ForegroundColor Yellow
    Write-Host "Para deploys mais rápidos, instale rsync via WSL ou Git Bash" -ForegroundColor Gray
    
    # Criar tarball temporário (excluindo arquivos grandes)
    $tempTar = "$env:TEMP\gcm_deploy_$(Get-Date -Format 'yyyyMMdd_HHmmss').tar"
    
    Write-Host "Compactando arquivos..." -ForegroundColor Gray
    tar -czf $tempTar -C $LOCAL_PATH `
        --exclude='.git' `
        --exclude='.venv' `
        --exclude='__pycache__' `
        --exclude='*.pyc' `
        --exclude='*.sqlite3' `
        --exclude='db_backup_*.sqlite3' `
        --exclude='.env' `
        --exclude='*.keystore' `
        --exclude='*firebase*.json' `
        --exclude='node_modules' `
        --exclude='media' `
        --exclude='staticfiles' `
        --exclude='dist' `
        --exclude='pdfjs_tmp' `
        .
    
    Write-Host "Enviando arquivo compactado..." -ForegroundColor Gray
    scp -i $AWS_KEY -o StrictHostKeyChecking=no $tempTar "${AWS_USER}@${AWS_HOST}:/tmp/gcm_deploy.tar"
    
    Write-Host "Extraindo no servidor..." -ForegroundColor Gray
    $extractCmd = @"
mkdir -p $REMOTE_PATH &&
tar -xzf /tmp/gcm_deploy.tar -C $REMOTE_PATH &&
rm /tmp/gcm_deploy.tar &&
echo 'Arquivos extraídos com sucesso!'
"@
    ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $extractCmd
    
    Remove-Item $tempTar -Force
}

Remove-Item $excludeFile -Force

# 5. Executar comandos de deploy no servidor
Write-Host "`n[5/5] Configurando aplicação no servidor..." -ForegroundColor Green

$deployCmd = @"
cd $REMOTE_PATH &&
echo '--- Ativando ambiente virtual ---' &&
source venv/bin/activate &&
echo '--- Instalando dependências ---' &&
pip install -r requirements-prod.txt --quiet &&
echo '--- Executando migrations ---' &&
python manage.py migrate --noinput &&
echo '--- Coletando arquivos estáticos ---' &&
python manage.py collectstatic --noinput --clear &&
echo '--- Verificando configuração ---' &&
python manage.py check --deploy &&
echo '--- Reiniciando serviços ---' &&
sudo systemctl restart gunicorn &&
sudo systemctl restart daphne &&
sudo systemctl restart celery 2>/dev/null || true &&
sudo systemctl restart nginx 2>/dev/null || true &&
echo '' &&
echo '=== STATUS DOS SERVIÇOS ===' &&
echo 'Gunicorn:' && sudo systemctl is-active gunicorn &&
echo 'Daphne:' && sudo systemctl is-active daphne &&
echo 'Nginx:' && sudo systemctl is-active nginx &&
echo '' &&
echo '✓ Deploy concluído com sucesso!'
"@

ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $deployCmd

Write-Host "`n=== Deploy Concluído! ===" -ForegroundColor Green
Write-Host "URL: http://$AWS_HOST" -ForegroundColor Cyan
Write-Host ""

# Mostrar logs recentes (opcional)
$showLogs = Read-Host "Deseja ver os últimos logs do Gunicorn? (s/n)"
if ($showLogs -eq 's') {
    Write-Host "`nÚltimas 20 linhas do log:" -ForegroundColor Yellow
    ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" "sudo journalctl -u gunicorn -n 20 --no-pager"
}

# Abrir navegador
$openBrowser = Read-Host "`nDeseja abrir o sistema no navegador? (s/n)"
if ($openBrowser -eq 's') {
    Start-Process "http://$AWS_HOST"
}
