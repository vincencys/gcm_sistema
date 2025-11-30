#!/usr/bin/env bash
# Script de deploy automatizado para EC2
# Sincroniza código do Git, instala dependências, aplica migrações e reinicia serviços

set -Eeuo pipefail

APP_DIR="/home/ec2-user/gcm_sistema"
VENV="$APP_DIR/.venv"
BRANCH="main"  # branch de deploy
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "==> Iniciando deploy em $(date)"

cd "$APP_DIR"

# 1. Sincronizar código do repositório
echo "==> Sincronizando código do Git..."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git fetch --all --prune
  git reset --hard "origin/$BRANCH"
  echo "Código atualizado para: $(git rev-parse --short HEAD)"
else
  echo "ERRO: Diretório não é um repositório Git."
  echo "Execute primeiro: cd $APP_DIR && git init && git remote add origin <URL>"
  exit 1
fi

# 2. Atualizar ambiente virtual e dependências
echo "==> Instalando/atualizando dependências..."
[ -x "$PY" ] || python3.11 -m venv "$VENV"
"$PIP" install --upgrade pip wheel setuptools

if [ -f requirements-prod.txt ]; then
  "$PIP" install -r requirements-prod.txt
elif [ -f requirements.txt ]; then
  "$PIP" install -r requirements.txt
else
  echo "AVISO: Nenhum arquivo requirements encontrado"
fi

# 3. Aplicar migrações do banco de dados
echo "==> Aplicando migrações..."
"$PY" manage.py migrate --noinput

# 4. Coletar arquivos estáticos
echo "==> Coletando arquivos estáticos..."
"$PY" manage.py collectstatic --noinput --clear || echo "Collectstatic falhou (pode ser normal se não configurado)"

# 5. Validar projeto Django
echo "==> Validando configuração do Django..."
"$PY" manage.py check

# 6. Reiniciar serviços
echo "==> Reiniciando serviços..."
sudo systemctl restart gunicorn-gcm
sudo systemctl restart daphne-gcm

# Aguardar 2 segundos para serviços iniciarem
sleep 2

# 7. Verificar saúde dos serviços
echo "==> Verificando status dos serviços..."
sudo systemctl is-active --quiet gunicorn-gcm && echo "✓ gunicorn-gcm: RUNNING" || echo "✗ gunicorn-gcm: FAILED"
sudo systemctl is-active --quiet daphne-gcm && echo "✓ daphne-gcm: RUNNING" || echo "✗ daphne-gcm: FAILED"

# 8. Testar endpoint HTTP
echo "==> Testando endpoint HTTP..."
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -H "Host: gcmsysint.online" http://127.0.0.1:8001/ || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
  echo "✓ Aplicação respondendo: HTTP $HTTP_CODE"
else
  echo "✗ ATENÇÃO: Aplicação retornou HTTP $HTTP_CODE"
  echo "Execute: sudo journalctl -u gunicorn-gcm -n 50"
fi

echo "==> Deploy finalizado em $(date)"
