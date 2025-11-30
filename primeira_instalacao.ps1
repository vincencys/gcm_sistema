#!/usr/bin/env pwsh
# Primeira instalação do GCM Sistema no AWS

$AWS_HOST = "18.229.134.75"
$AWS_USER = "ec2-user"
$AWS_KEY = "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"

Write-Host "`n=== Primeira Instalação - GCM Sistema AWS ===" -ForegroundColor Cyan
Write-Host "Servidor: $AWS_HOST" -ForegroundColor Yellow
Write-Host ""

# 1. Criar estrutura de pastas no servidor
Write-Host "[1/4] Criando estrutura no servidor..." -ForegroundColor Green
ssh -i $AWS_KEY $AWS_USER@$AWS_HOST @"
mkdir -p ~/GCM_Sistema
mkdir -p ~/backups
echo 'Pastas criadas!'
"@

# 2. Compactar código local
Write-Host "`n[2/4] Compactando código local..." -ForegroundColor Green
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$tarFile = "$env:TEMP\gcm_deploy_$timestamp.tar.gz"

tar -czf $tarFile -C C:\GCM_Sistema `
    --exclude=".git" `
    --exclude=".venv" `
    --exclude="__pycache__" `
    --exclude="*.pyc" `
    --exclude="*.sqlite3" `
    --exclude="db_backup_*.sqlite3" `
    --exclude=".env" `
    --exclude="*.keystore" `
    --exclude="*firebase*.json" `
    --exclude="node_modules" `
    --exclude="media" `
    --exclude="staticfiles" `
    --exclude="dist" `
    --exclude="pdfjs_tmp" `
    --exclude=".tmp.driveupload" `
    .

Write-Host "Arquivo criado: $tarFile" -ForegroundColor Gray
$fileSize = (Get-Item $tarFile).Length / 1MB
Write-Host "Tamanho: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Gray

# 3. Enviar para servidor
Write-Host "`n[3/4] Enviando para servidor..." -ForegroundColor Green
Write-Host "Isso pode levar alguns minutos..." -ForegroundColor Gray
scp -i $AWS_KEY -o StrictHostKeyChecking=no $tarFile "${AWS_USER}@${AWS_HOST}:/tmp/gcm_deploy.tar.gz"

# 4. Extrair no servidor
Write-Host "`n[4/4] Extraindo no servidor..." -ForegroundColor Green
ssh -i $AWS_KEY $AWS_USER@$AWS_HOST @"
cd ~/GCM_Sistema
tar -xzf /tmp/gcm_deploy.tar.gz
rm /tmp/gcm_deploy.tar.gz
ls -lh
echo ''
echo '✓ Código extraído com sucesso!'
"@

# Limpar arquivo local
Remove-Item $tarFile -Force

Write-Host "`n=== Código Instalado com Sucesso! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos passos (execute no Session Manager):" -ForegroundColor Yellow
Write-Host "1. Conecte via Session Manager no console AWS" -ForegroundColor Cyan
Write-Host "2. Execute os comandos de instalação:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   cd ~/GCM_Sistema" -ForegroundColor Gray
Write-Host "   sudo yum install python3 python3-pip git -y" -ForegroundColor Gray
Write-Host "   python3 -m venv venv" -ForegroundColor Gray
Write-Host "   source venv/bin/activate" -ForegroundColor Gray
Write-Host "   pip install -r requirements-prod.txt" -ForegroundColor Gray
Write-Host "   python manage.py migrate" -ForegroundColor Gray
Write-Host "   python manage.py collectstatic --noinput" -ForegroundColor Gray
Write-Host ""
