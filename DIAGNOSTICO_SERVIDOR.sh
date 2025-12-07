#!/bin/bash

# SCRIPT DE DIAGNÓSTICO COMPLETO
# Cole isso no Session Manager para ver exatamente o que está errado

echo "=== DIAGNÓSTICO COMPLETO GCM_SISTEMA ==="
echo ""

echo "1. VERIFICAR DIRETÓRIOS:"
ls -la /home/ec2-user/ | grep -i gcm

echo ""
echo "2. ONDE ESTÁ O PROJETO?"
find /home/ec2-user -type d -name "*gcm*" -o -name "*GCM*" 2>/dev/null | head -10

echo ""
echo "3. VERIFICAR .venv:"
find /home/ec2-user -type d -name ".venv" 2>/dev/null

echo ""
echo "4. VERIFICAR manage.py:"
find /home/ec2-user -name "manage.py" 2>/dev/null

echo ""
echo "5. VERIFICAR SERVIÇOS:"
sudo systemctl list-units --type=service | grep -i gcm

echo ""
echo "6. VERIFICAR GUNICORN:"
sudo systemctl status gunicorn-gcm 2>&1 || echo "Serviço gunicorn-gcm não encontrado"

echo ""
echo "7. VERIFICAR DAPHNE:"
sudo systemctl status daphne-gcm 2>&1 || echo "Serviço daphne-gcm não encontrado"

echo ""
echo "8. VERIFICAR ARQUIVOS DE SERVIÇO:"
ls -la /etc/systemd/system/*gcm* 2>/dev/null || echo "Nenhum arquivo de serviço encontrado"

echo ""
echo "9. VERIFICAR NGINX:"
sudo systemctl status nginx --no-pager
sudo nginx -T 2>&1 | head -20

echo ""
echo "10. PORTAS ABERTAS:"
sudo ss -tlnp | grep -E ':(80|443|8000|8001|8002)'

echo ""
echo "11. VERIFICAR LOGS NGINX:"
sudo tail -20 /var/log/nginx/error.log

echo ""
echo "=== FIM DO DIAGNÓSTICO ==="
