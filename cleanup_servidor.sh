#!/bin/bash
# Script para limpar e corrigir estrutura de diretórios

echo "=== LIMPANDO DIRETÓRIOS DUPLICADOS ==="

# 1. Remover link simbólico e diretório GCM_Sistema
echo "1. Removendo GCM_Sistema (maiúsculo)..."
sudo rm -rf /home/ec2-user/GCM_Sistema
sudo rm -f /home/ec2-user/GCM_Sistema
echo "✓ Removido"

# 2. Remover gcm_sistema_new
echo ""
echo "2. Removendo gcm_sistema_new..."
sudo rm -rf /home/ec2-user/gcm_sistema_new
echo "✓ Removido"

# 3. Parar serviços
echo ""
echo "3. Parando serviços..."
sudo systemctl stop gunicorn-gcm daphne-gcm
echo "✓ Serviços parados"

# 4. Atualizar serviços systemd para usar caminho correto
echo ""
echo "4. Corrigindo serviços systemd..."

# Corrigir Gunicorn
sudo tee /etc/systemd/system/gunicorn-gcm.service > /dev/null <<'SERVICE'
[Unit]
Description=Gunicorn daemon for GCM Sistema
After=network.target

[Service]
Type=notify
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/gcm_sistema
Environment="PATH=/home/ec2-user/gcm_sistema/.venv/bin"
ExecStart=/home/ec2-user/gcm_sistema/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8001 --timeout 120 gcm_project.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

# Corrigir Daphne
sudo tee /etc/systemd/system/daphne-gcm.service > /dev/null <<'SERVICE'
[Unit]
Description=Daphne ASGI daemon for GCM Sistema
After=network.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/gcm_sistema
Environment="PATH=/home/ec2-user/gcm_sistema/.venv/bin"
ExecStart=/home/ec2-user/gcm_sistema/.venv/bin/daphne -b 127.0.0.1 -p 8002 gcm_project.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

echo "✓ Serviços corrigidos"

# 5. Recarregar systemd
echo ""
echo "5. Recarregando systemd..."
sudo systemctl daemon-reload
echo "✓ Daemon recarregado"

# 6. Iniciar serviços
echo ""
echo "6. Iniciando serviços..."
sudo systemctl start gunicorn-gcm
sleep 2
sudo systemctl start daphne-gcm
sleep 2
echo "✓ Serviços iniciados"

# 7. Verificar status
echo ""
echo "7. Status dos serviços:"
sudo systemctl status gunicorn-gcm --no-pager -l | head -10
echo ""
sudo systemctl status daphne-gcm --no-pager -l | head -10

# 8. Testar media
echo ""
echo "8. Testando acesso ao media..."
PDF=$(find /home/ec2-user/gcm_sistema/media -name "*.pdf" -type f | head -1)
if [ -n "$PDF" ]; then
    REL=${PDF#/home/ec2-user/gcm_sistema/media/}
    echo "Testando: /media/$REL"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1/media/$REL")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ MEDIA FUNCIONANDO! (HTTP $HTTP_CODE)"
    else
        echo "❌ Media com problema (HTTP $HTTP_CODE)"
        curl -I "http://127.0.0.1/media/$REL" | head -5
    fi
fi

echo ""
echo "=== LIMPEZA CONCLUÍDA ==="
echo ""
echo "Diretórios restantes:"
ls -la /home/ec2-user/ | grep gcm
