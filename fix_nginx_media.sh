#!/bin/bash
set -e

echo "=== CORRIGINDO NGINX PARA SERVIR /media/ ==="
echo ""

# 1. Backup da config atual
echo "1. Fazendo backup da configuração atual..."
sudo cp /etc/nginx/conf.d/gcm.conf /etc/nginx/conf.d/gcm.conf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "Arquivo gcm.conf não existe ainda"

# 2. Criar configuração correta do Nginx
echo ""
echo "2. Criando configuração correta do Nginx..."
sudo tee /etc/nginx/conf.d/gcm.conf > /dev/null <<'NGINX_CONFIG'
upstream gunicorn_gcm {
    server 127.0.0.1:8001 fail_timeout=0;
}

upstream daphne_gcm {
    server 127.0.0.1:8002 fail_timeout=0;
}

server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 20M;

    # Servir arquivos estáticos
    location /static/ {
        alias /home/ec2-user/gcm_sistema/staticfiles/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Servir arquivos de media (PDFs, imagens, etc)
    location /media/ {
        alias /home/ec2-user/gcm_sistema/media/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public";
    }

    # WebSocket para /ws/
    location /ws/ {
        proxy_pass http://daphne_gcm;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 86400;
    }

    # Aplicação Django (Gunicorn)
    location / {
        proxy_pass http://gunicorn_gcm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 300;
    }
}
NGINX_CONFIG

echo "✓ Configuração criada"

# 3. Garantir permissões de leitura
echo ""
echo "3. Ajustando permissões de leitura para /media/..."
sudo chmod -R o+rX /home/ec2-user/gcm_sistema/media
echo "✓ Permissões ajustadas"

# 4. Testar configuração do Nginx
echo ""
echo "4. Testando configuração do Nginx..."
sudo nginx -t

# 5. Recarregar Nginx
echo ""
echo "5. Recarregando Nginx..."
sudo systemctl reload nginx
echo "✓ Nginx recarregado"

# 6. Verificar status
echo ""
echo "6. Verificando status do Nginx..."
sudo systemctl status nginx --no-pager -l | head -15

# 7. Testar acesso ao media
echo ""
echo "7. Testando acesso a um arquivo de media..."
TEST_FILE=$(find /home/ec2-user/gcm_sistema/media/documentos/origem -name "*.pdf" -type f | head -1)
if [ -n "$TEST_FILE" ]; then
    REL_PATH=${TEST_FILE#/home/ec2-user/gcm_sistema/media/}
    echo "Testando: /media/$REL_PATH"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1/media/$REL_PATH")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✓ Acesso ao media OK (HTTP $HTTP_CODE)"
    else
        echo "✗ Acesso ao media FALHOU (HTTP $HTTP_CODE)"
    fi
else
    echo "⚠ Nenhum PDF encontrado para teste"
fi

echo ""
echo "✅ CONFIGURAÇÃO CONCLUÍDA!"
echo ""
echo "Teste no navegador:"
echo "https://gcmsysint.online/media/documentos/origem/2025/20251207_050257_BOGCMI_6-2025_110_a3b07fcc.pdf"
