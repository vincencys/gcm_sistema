#!/bin/bash
set -e

echo "=== DEPLOY GCM SISTEMA VIA SESSION MANAGER ==="
echo "Data: $(date)"
echo ""

# 1. Navegar para projeto
cd /home/ec2-user/gcm_sistema
echo "✓ Diretório: $(pwd)"

# 2. Ativar ambiente virtual
echo ""
echo "==> Ativando ambiente virtual..."
source .venv/bin/activate
echo "✓ Ambiente virtual ativado"

# 3. Atualizar código do GitHub
echo ""
echo "==> Atualizando código do GitHub..."
git fetch origin
git reset --hard origin/main
echo "✓ Código atualizado"
git log --oneline -1

# 4. Verificar e instalar dependências (se necessário)
echo ""
echo "==> Verificando dependências Python..."
pip install -q --upgrade pip
if [ -f requirements-prod.txt ]; then
    pip install -q -r requirements-prod.txt
    echo "✓ Dependências instaladas (requirements-prod.txt)"
elif [ -f requirements.txt ]; then
    pip install -q -r requirements.txt
    echo "✓ Dependências instaladas (requirements.txt)"
fi

# 5. Aplicar migrações do banco de dados
echo ""
echo "==> Aplicando migrações do banco de dados..."
python manage.py migrate --noinput
echo "✓ Migrações aplicadas"

# 6. Coletar arquivos estáticos
echo ""
echo "==> Coletando arquivos estáticos..."
python manage.py collectstatic --noinput --clear
echo "✓ Arquivos estáticos coletados"

# 7. Executar verificação do Django
echo ""
echo "==> Executando verificação do Django..."
python manage.py check
echo "✓ Verificação OK"

# 8. Reiniciar serviços
echo ""
echo "==> Reiniciando serviços..."
sudo systemctl restart gunicorn-gcm
sleep 2
sudo systemctl restart daphne-gcm
sleep 2
echo "✓ Serviços reiniciados"

# 9. Verificar status dos serviços
echo ""
echo "==> Status dos serviços:"
echo ""
echo "--- GUNICORN ---"
sudo systemctl status gunicorn-gcm --no-pager -l | head -10

echo ""
echo "--- DAPHNE ---"
sudo systemctl status daphne-gcm --no-pager -l | head -10

echo ""
echo "--- NGINX ---"
sudo systemctl status nginx --no-pager -l | head -5

# 10. Teste rápido
echo ""
echo "==> Testando conectividade local..."
echo ""
echo "Gunicorn (8001):"
curl -s -I http://127.0.0.1:8001/ | head -3

echo ""
echo "✅ DEPLOY CONCLUÍDO COM SUCESSO!"
echo "Data: $(date)"
echo ""
echo "Acesse: https://gcmsysint.online ou https://gcmsystem.online"
