#!/usr/bin/env pwsh
# Script de Deploy Automático para AWS EC2
# Uso: .\deploy_aws.ps1

param(
    [string]$Message = "Deploy automático via script",
    [switch]$SkipTests = $false
)

$ErrorActionPreference = "Stop"

# ===== CONFIGURAÇÕES (EDITE AQUI) =====
$AWS_HOST = "18.229.134.75"  # IP do servidor AWS
$AWS_USER = "ec2-user"  # Usuário do servidor (Amazon Linux)
$AWS_KEY = "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"  # Caminho para chave SSH
$REMOTE_PATH = "/home/ec2-user/GCM_Sistema"  # Caminho do projeto no servidor
$GIT_BRANCH = "main"
# ======================================

Write-Host "`n=== Deploy Automático AWS ===" -ForegroundColor Cyan
Write-Host "Servidor: $AWS_HOST" -ForegroundColor Yellow
Write-Host "Branch: $GIT_BRANCH" -ForegroundColor Yellow
Write-Host ""

# 1. Verificar se há mudanças não commitadas
Write-Host "[1/7] Verificando mudanças locais..." -ForegroundColor Green
$status = git status --porcelain
if ($status) {
    Write-Host "Mudanças detectadas. Commitando..." -ForegroundColor Yellow
    git add .
    git commit -m $Message
    Write-Host "Commit realizado!" -ForegroundColor Green
} else {
    Write-Host "Nenhuma mudança local detectada." -ForegroundColor Gray
}

# 2. Push para repositório (se houver remote configurado)
Write-Host "`n[2/7] Enviando para repositório Git..." -ForegroundColor Green
try {
    git push origin $GIT_BRANCH
    Write-Host "Push concluído!" -ForegroundColor Green
} catch {
    Write-Host "Aviso: Push falhou ou não há remote configurado. Continuando..." -ForegroundColor Yellow
}

# 3. Verificar conectividade SSH
Write-Host "`n[3/7] Testando conexão SSH..." -ForegroundColor Green
$sshTest = ssh -i $AWS_KEY -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$AWS_USER@$AWS_HOST" "echo 'OK'" 2>&1
if ($sshTest -match "OK") {
    Write-Host "Conexão SSH: OK" -ForegroundColor Green
} else {
    Write-Host "ERRO: Não foi possível conectar ao servidor AWS!" -ForegroundColor Red
    Write-Host "Verifique: IP, usuário, chave SSH e security group" -ForegroundColor Red
    exit 1
}

# 4. Atualizar código no servidor
Write-Host "`n[4/7] Atualizando código no servidor..." -ForegroundColor Green
$updateCmd = @"
cd $REMOTE_PATH || mkdir -p $REMOTE_PATH && cd $REMOTE_PATH && 
if [ ! -d .git ]; then echo 'Clonando repositório...'; git clone https://github.com/vincencys/gcm_sistema.git .; fi && 
 git fetch origin main && git checkout main && git pull origin main && 
echo 'Código atualizado/clonado com sucesso!'
"@

ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $updateCmd

# 5. Instalar dependências e migrar banco
Write-Host "`n[5/7] Instalando dependências e migrando banco..." -ForegroundColor Green
$setupCmd = @"
cd $REMOTE_PATH && 
command -v python3 >/dev/null 2>&1 || sudo yum install -y python3 && 
if [ ! -d venv ]; then python3 -m venv venv; fi && 
source venv/bin/activate && 
pip install --upgrade pip setuptools wheel >/dev/null 2>&1 && 
pip install -r requirements-prod.txt --quiet || pip install -r requirements.txt --quiet && 
python manage.py migrate --noinput && 
python manage.py collectstatic --noinput --clear && 
echo 'Setup concluído!'
"@

ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $setupCmd

# 6. Testes (opcional)
if (-not $SkipTests) {
    Write-Host "`n[6/7] Executando testes..." -ForegroundColor Green
    $testCmd = @"
cd $REMOTE_PATH && source venv/bin/activate && python manage.py check --deploy && echo 'Testes OK!'
"@
    try {
        ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $testCmd
        Write-Host "Testes passaram!" -ForegroundColor Green
    } catch {
        Write-Host "Aviso: Testes falharam, mas continuando deploy..." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[6/7] Testes: PULADOS (--SkipTests)" -ForegroundColor Gray
}

# 7. Reiniciar serviços (somente se existirem)
Write-Host "`n[7/7] Reiniciando serviços Django..." -ForegroundColor Green
$restartCmd = @"
for svc in gunicorn daphne celery nginx; do 
  if systemctl list-units --type=service | grep -q "${svc}.service"; then 
    sudo systemctl restart $svc && echo "Reiniciado: $svc"; 
  else 
    echo "Serviço ausente (skip): $svc"; 
  fi; 
done; 
echo 'Reinício concluído.'
"@
ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $restartCmd

# Verificar status dos serviços
Write-Host "`n=== Verificando status dos serviços ===" -ForegroundColor Cyan
$statusCmd = @"
for svc in gunicorn daphne nginx; do 
  echo "${svc}:"; systemctl is-active $svc || echo 'inactive'; 
 done
"@
ssh -i $AWS_KEY "$AWS_USER@$AWS_HOST" $statusCmd

Write-Host "`n=== Deploy Finalizado (com verificações) ===" -ForegroundColor Green
Write-Host "Acesse: http://$AWS_HOST" -ForegroundColor Cyan
Write-Host ""

